from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse

import oss2
import requests


CONTENT_TYPE_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


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
        timeout: int = 20,
    ) -> None:
        self.force_enabled = enabled
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.bucket_name = bucket_name
        self.endpoint = endpoint
        self.view_domain = view_domain.rstrip("/") + "/" if view_domain else ""
        self.prefix = prefix.strip("/") + "/" if prefix else ""
        self.timeout = timeout
        self.session = requests.Session()
        self.upload_cache: dict[str, str] = {}
        self.enabled = self.force_enabled and all(
            [self.access_key_id, self.access_key_secret, self.bucket_name, self.endpoint, self.view_domain]
        )
        self.bucket = None
        if self.enabled:
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)

    def upload_url(self, url: str) -> str:
        url = (url or "").strip()
        if not url:
            return ""
        if not self.enabled:
            return url
        if url.startswith(self.view_domain):
            return url
        if url in self.upload_cache:
            return self.upload_cache[url]

        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        content = response.content
        if not content:
            raise ValueError("empty_image_content")

        oss_key = self._url_to_oss_key(url)
        content_type = self._guess_content_type(oss_key)
        assert self.bucket is not None
        self.bucket.put_object(oss_key, content, headers={"Content-Type": content_type})
        new_url = f"{self.view_domain}{oss_key}"
        self.upload_cache[url] = new_url
        return new_url

    def upload_urls(self, urls: list[str]) -> list[str]:
        uploaded: list[str] = []
        for url in urls:
            if not url:
                continue
            uploaded.append(self.upload_url(url))
        return uploaded

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
