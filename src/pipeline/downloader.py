import hashlib
import logging
import mimetypes
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

from PIL import Image, ImageFile

from .dedupe import DedupeIndex
from .filters import match_size, size_bucket
from ..utils.http import get, head, is_blocked

ImageFile.LOAD_TRUNCATED_IMAGES = True


@dataclass
class DownloadResult:
    status: str
    url: str
    reason: Optional[str] = None
    path: Optional[Path] = None
    width: Optional[int] = None
    height: Optional[int] = None
    content_hash: Optional[str] = None


def _safe_keyword(keyword: str) -> str:
    keep = []
    for ch in keyword.strip():
        if ch.isalnum() or ch in ("-", "_"):
            keep.append(ch)
        elif ch.isspace():
            keep.append("_")
    return "".join(keep) or "keyword"


def _guess_extension(content_type: Optional[str], pil_format: Optional[str], url: str) -> str:
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ext.lstrip(".")
    if pil_format:
        return pil_format.lower()
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext.lstrip(".") or "jpg"


def download_and_filter(
    url: str,
    out_root: Path,
    keyword: str,
    rules: list,
    settings: Dict,
    dedupe: DedupeIndex,
) -> DownloadResult:
    logger = logging.getLogger("image-harvester")
    timeout = float(settings.get("timeout", 10))
    probe_bytes = int(settings.get("probe_bytes", 262144))
    blocked_domains = settings.get("blocked_domains", [])

    if is_blocked(url, blocked_domains):
        return DownloadResult(status="blocked", url=url, reason="blocked_domain")

    if settings.get("dedupe", {}).get("url", True) and dedupe.check_url(url):
        return DownloadResult(status="duplicate", url=url, reason="url_duplicate")
    dedupe.add_url(url)

    try:
        try:
            resp_head = head(url, timeout=timeout)
            content_type = resp_head.headers.get("Content-Type")
        except Exception:
            content_type = None

        path: Optional[Path] = None
        keep_reading = True
        width = height = None
        pil_format = None

        with get(url, timeout=timeout, stream=True) as resp:
            resp.raise_for_status()

            parser = ImageFile.Parser()
            temp_dir = Path(settings.get("temp_dir") or tempfile.gettempdir())
            temp_dir.mkdir(parents=True, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix="img_", dir=str(temp_dir))
            os.close(fd)
            path = Path(temp_path)

            total = 0
            hasher = hashlib.new(settings.get("hash_algo", "sha1"))

            try:
                with path.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        total += len(chunk)
                        f.write(chunk)
                        hasher.update(chunk)
                        try:
                            parser.feed(chunk)
                        except Exception:
                            pass

                        if width is None and parser.image:
                            width, height = parser.image.size
                            if not match_size(width, height, rules):
                                keep_reading = False
                                break
                        if width is None and total >= probe_bytes:
                            # Give up on early size detection, continue to full download
                            pass

                if not keep_reading:
                    return DownloadResult(
                        status="filtered",
                        url=url,
                        reason="size_mismatch",
                        width=width,
                        height=height,
                    )

                with Image.open(path) as img:
                    if width is None or height is None:
                        width, height = img.size
                    pil_format = img.format

            finally:
                if path and path.exists() and not keep_reading:
                    path.unlink(missing_ok=True)

            content_hash = hasher.hexdigest()

        if settings.get("dedupe", {}).get("content_hash", True) and dedupe.check_hash(content_hash):
            logger.debug("download_duplicate hash url=%s", url)
            if path:
                path.unlink(missing_ok=True)
            return DownloadResult(status="duplicate", url=url, reason="hash_duplicate")

        dedupe.add_hash(content_hash)

        if not match_size(width, height, rules):
            logger.debug("download_filtered size_mismatch url=%s size=%sx%s", url, width, height)
            if path:
                path.unlink(missing_ok=True)
            return DownloadResult(status="filtered", url=url, reason="size_mismatch", width=width, height=height)

        bucket = size_bucket(width, height)
        safe_keyword = _safe_keyword(keyword)
        date_str = settings.get("date_str")
        dest_dir = out_root / date_str / bucket
        dest_dir.mkdir(parents=True, exist_ok=True)

        ext = _guess_extension(content_type, pil_format, url)
        filename = f"{safe_keyword}_{width}x{height}_{content_hash}.{ext}"
        final_path = dest_dir / filename

        if final_path.exists():
            if path:
                path.unlink(missing_ok=True)
            return DownloadResult(status="duplicate", url=url, reason="file_exists")

        if path is None:
            return DownloadResult(status="error", url=url, reason="download_failed")

        shutil.move(str(path), str(final_path))
        logger.debug(
            "download_saved url=%s size=%sx%s path=%s",
            url,
            width,
            height,
            final_path,
        )

        return DownloadResult(
            status="saved",
            url=url,
            path=final_path,
            width=width,
            height=height,
            content_hash=content_hash,
        )

    except Exception as e:
        return DownloadResult(status="error", url=url, reason=str(e))
