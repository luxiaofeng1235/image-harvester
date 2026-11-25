from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import tempfile
import threading
from urllib.parse import urlparse

import httpx
import oss2

from ai_goods_pipeline.utils.image_url import (
    is_standard_storable_image_url,
    normalize_storable_image_url,
)
from ai_goods_pipeline.utils.image_decode import probe_image_content


CONTENT_TYPE_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)

OBJECT_ACL_MAP = {
    "": None,
    "inherit": None,
    "bucket": None,
    "default": None,
    "private": oss2.OBJECT_ACL_PRIVATE,
    "public-read": oss2.OBJECT_ACL_PUBLIC_READ,
    "public_read": oss2.OBJECT_ACL_PUBLIC_READ,
    "public-read-write": oss2.OBJECT_ACL_PUBLIC_READ_WRITE,
    "public_read_write": oss2.OBJECT_ACL_PUBLIC_READ_WRITE,
}


def normalize_object_acl(value: str | None) -> str:
    return str(value or "").strip().lower().replace("_", "-")


def resolve_object_acl(value: str | None):
    normalized = normalize_object_acl(value)
    if normalized not in OBJECT_ACL_MAP:
        raise ValueError(f"unsupported_oss_object_acl:{value}")
    return OBJECT_ACL_MAP[normalized]


class OSSImageUploader:
    def __init__(
        self,
        *,
        enabled: bool,
        access_key_id: str,
        access_key_secret: str,
        bucket_name: str,
        endpoint: str,
        view_domain: str,
        prefix: str,
        object_acl: str = "",
        timeout: int = 20,
        max_concurrency: int = 4,
    ) -> None:
        self.force_enabled = enabled
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.bucket_name = bucket_name
        self.endpoint = endpoint
        self.view_domain = view_domain.rstrip("/") + "/" if view_domain else ""
        self.prefix = prefix.strip("/") + "/" if prefix else ""
        self.object_acl = normalize_object_acl(object_acl)
        self.object_acl_permission = resolve_object_acl(self.object_acl)
        self.timeout = timeout
        self.max_concurrency = max(1, max_concurrency)
        self.upload_cache: dict[str, str] = {}
        self._cache_lock = threading.Lock()
        self.enabled = self.force_enabled and all(
            [self.access_key_id, self.access_key_secret, self.bucket_name, self.endpoint, self.view_domain]
        )
        self.bucket = None
        if self.enabled:
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)

    async def close(self) -> None:
        pass

    async def upload_url(self, url: str, *, force_upload: bool = False) -> str:
        """Download a remote image to a temporary file and upload it to OSS."""
        url = normalize_storable_image_url(url)
        if not url:
            return ""
        if not force_upload and is_standard_storable_image_url(url):
            return url
        if not self.enabled:
            return url
        if url.startswith(self.view_domain):
            return url
        cache_key = f"{int(force_upload)}:{url}"
        with self._cache_lock:
            cached = self.upload_cache.get(cache_key)
        if cached:
            return cached

        # 流式下载到临时文件（与 fastapi-server 一致）
        with tempfile.TemporaryDirectory(prefix="oss-upload-") as directory:
            path = Path(directory) / "resource"
            try:
                async with httpx.AsyncClient(timeout=self.timeout, trust_env=False, follow_redirects=True) as client:
                    headers = {}
                    referer = self._guess_referer(url)
                    if referer:
                        headers["Referer"] = referer
                    async with client.stream("GET", url, headers=headers) as response:
                        if response.status_code in (403, 404, 410):
                            raise ValueError(f"image_unavailable:{response.status_code}")
                        response.raise_for_status()
                        content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0] or ""
                        if not content_type.startswith("image/"):
                            raise ValueError("non_image_content_type")
                        size = 0
                        with path.open("wb") as output:
                            async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                                size += len(chunk)
                                await asyncio.to_thread(output.write, chunk)
            except httpx.HTTPError:
                raise ValueError("remote_download_failed") from None

            # 验证图片内容
            content = path.read_bytes()
            if not content:
                raise ValueError("empty_image_content")
            if probe_image_content(content) is None:
                raise ValueError("invalid_image_content")

            # 上传到 OSS
            oss_key = self._url_to_oss_key(url)
            content_type = self._guess_content_type(oss_key)
            assert self.bucket is not None
            await asyncio.to_thread(self.bucket.put_object, oss_key, content, headers={"Content-Type": content_type})
            if self.object_acl_permission is not None:
                await asyncio.to_thread(self.bucket.put_object_acl, oss_key, self.object_acl_permission)

        new_url = f"{self.view_domain}{oss_key}"
        with self._cache_lock:
            self.upload_cache[cache_key] = new_url
        return new_url

    async def upload_urls(self, urls: list[str], *, force_upload: bool = False) -> list[str]:
        valid_urls = [str(url or "").strip() for url in urls if str(url or "").strip()]
        if not valid_urls:
            return []
        if len(valid_urls) == 1:
            return [await self.upload_url(valid_urls[0], force_upload=force_upload)]
        # 并发上传
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _limited_upload(url: str) -> str:
            async with semaphore:
                return await self.upload_url(url, force_upload=force_upload)

        return await asyncio.gather(*[_limited_upload(url) for url in valid_urls])

    def _url_to_oss_key(self, url: str) -> str:
        md5 = hashlib.md5(url.encode("utf-8")).hexdigest()
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1].lower().split("?")[0]
        if ext not in CONTENT_TYPE_MAP:
            ext = ".jpg"
        return f"{self.prefix}{md5}{ext}"

    def _guess_content_type(self, oss_key: str) -> str:
        ext = Path(oss_key).suffix.lower()
        return CONTENT_TYPE_MAP.get(ext, "image/jpeg")

    @staticmethod
    def _guess_referer(url: str) -> str:
        host = (urlparse(url).netloc or "").lower()
        if "baidu" in host or "bdstatic" in host or "bcebos" in host or "bdimg" in host:
            return "https://image.baidu.com/"
        if "bing" in host or "bing.net" in host:
            return "https://cn.bing.com/"
        return ""
