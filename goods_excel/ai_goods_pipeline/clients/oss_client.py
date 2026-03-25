from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import threading
from urllib.parse import urlparse

import oss2
import requests

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
        self.session = requests.Session()
        self.upload_cache: dict[str, str] = {}
        self._cache_lock = threading.Lock()
        self.enabled = self.force_enabled and all(
            [self.access_key_id, self.access_key_secret, self.bucket_name, self.endpoint, self.view_domain]
        )
        self.bucket = None
        if self.enabled:
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def upload_url(self, url: str, *, force_upload: bool = False) -> str:
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

        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        content_type = (response.headers.get("Content-Type") or "").lower()
        if not content_type.startswith("image/"):
            raise ValueError("non_image_content_type")
        content = response.content
        if not content:
            raise ValueError("empty_image_content")
        if probe_image_content(content) is None:
            raise ValueError("invalid_image_content")

        oss_key = self._url_to_oss_key(url)
        content_type = self._guess_content_type(oss_key)
        assert self.bucket is not None
        self.bucket.put_object(oss_key, content, headers={"Content-Type": content_type})
        if self.object_acl_permission is not None:
            self.bucket.put_object_acl(oss_key, self.object_acl_permission)
        new_url = f"{self.view_domain}{oss_key}"
        with self._cache_lock:
            self.upload_cache[cache_key] = new_url
        return new_url

    def upload_urls(self, urls: list[str], *, force_upload: bool = False) -> list[str]:
        valid_urls = [str(url or "").strip() for url in urls if str(url or "").strip()]
        if not valid_urls:
            return []
        if len(valid_urls) == 1:
            return [self.upload_url(valid_urls[0], force_upload=force_upload)]
        with ThreadPoolExecutor(max_workers=min(self.max_concurrency, len(valid_urls))) as executor:
            futures = [
                executor.submit(self.upload_url, url, force_upload=force_upload)
                for url in valid_urls
            ]
            return [future.result() for future in futures]

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
