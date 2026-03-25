from __future__ import annotations

import asyncio

from ai_goods_pipeline.clients.oss_client import OSSImageUploader


class AsyncOSSImageUploader:
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
        self.uploader = OSSImageUploader(
            enabled=enabled,
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            bucket_name=bucket_name,
            endpoint=endpoint,
            view_domain=view_domain,
            prefix=prefix,
            object_acl=object_acl,
            timeout=timeout,
        )
        self.semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._lock = asyncio.Lock()
        self._inflight: dict[str, asyncio.Task[str]] = {}

    async def close(self) -> None:
        await asyncio.to_thread(self.uploader.close)

    async def upload_url(self, url: str) -> str:
        return await self.upload_url_with_options(url)

    async def upload_url_with_options(self, url: str, *, force_upload: bool = False) -> str:
        key = str(url or "").strip()
        if not key:
            return ""
        inflight_key = f"{int(force_upload)}:{key}"

        async with self._lock:
            task = self._inflight.get(inflight_key)
            if task is None:
                task = asyncio.create_task(self._upload_one(key, force_upload=force_upload))
                self._inflight[inflight_key] = task
        try:
            return await task
        finally:
            async with self._lock:
                if self._inflight.get(inflight_key) is task:
                    self._inflight.pop(inflight_key, None)

    async def upload_urls(self, urls: list[str], *, force_upload: bool = False) -> list[str]:
        tasks = [
            self.upload_url_with_options(url, force_upload=force_upload)
            for url in urls
            if str(url or "").strip()
        ]
        if not tasks:
            return []
        return list(await asyncio.gather(*tasks))

    async def _upload_one(self, url: str, *, force_upload: bool = False) -> str:
        async with self.semaphore:
            return await asyncio.to_thread(
                self.uploader.upload_url,
                url,
                force_upload=force_upload,
            )
