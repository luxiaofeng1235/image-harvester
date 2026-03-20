from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from ai_goods_pipeline.clients.baidu_image_client import BaiduImageClient
from ai_goods_pipeline.clients.bing_image_client import BingImageClient
from ai_goods_pipeline.constants import (
    IMAGE_BAIDU_FETCH_LIMIT,
    IMAGE_BING_META_BLOCKLIST,
    IMAGE_BING_FETCH_LIMIT,
    IMAGE_CANDIDATE_POOL_TARGET,
    IMAGE_DETAIL_COUNT,
    IMAGE_REQUIRED_TOTAL,
    IMAGE_TITLE_QUERY_MAX_LEN,
    IMAGE_URL_HOST_BLOCKLIST,
    IMAGE_URL_PATH_BLOCKLIST,
)
from ai_goods_pipeline.utils.retry import retry_call


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


@dataclass(slots=True)
class ImageProbe:
    url: str
    content_type: str
    size: int
    is_gif: bool


@dataclass(slots=True)
class ImageResolutionResult:
    main_image: str
    detail_images: list[str]
    source_queries: list[str]
    all_valid_urls: list[str]


class ImageClient:
    def __init__(
        self,
        *,
        timeout: int,
        retries: int,
        min_bytes: int,
        allow_gif_as_main: bool,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.min_bytes = min_bytes
        self.allow_gif_as_main = allow_gif_as_main
        self.session = requests.Session()
        self.baidu_image_client = BaiduImageClient(timeout=timeout)
        self.bing_image_client = BingImageClient(timeout=timeout)
        self.validation_cache: dict[str, ImageProbe | None] = {}

    def resolve_images(
        self,
        *,
        title: str,
        image_keywords: list[str],
        category_id: int,
        keywords: list[str],
    ) -> ImageResolutionResult:
        candidate_urls: list[str] = []
        source_queries: list[str] = []

        search_queries = self._build_queries(title, image_keywords, keywords)
        for query in search_queries:
            baidu_urls = self.fetch_baidu_images(query)
            if baidu_urls:
                source_queries.append(f"baidu_images:{query}")
                for url in baidu_urls:
                    if url not in candidate_urls:
                        candidate_urls.append(url)
            if len(candidate_urls) >= IMAGE_CANDIDATE_POOL_TARGET:
                break

            bing_urls = self.fetch_bing_images(query)
            if bing_urls:
                source_queries.append(f"bing_images:{query}")
                for url in bing_urls:
                    if url not in candidate_urls:
                        candidate_urls.append(url)
            if len(candidate_urls) >= IMAGE_CANDIDATE_POOL_TARGET:
                break

        valid_images = self._validate_urls(candidate_urls)
        static_images = [img.url for img in valid_images if not img.is_gif]
        gif_images = [img.url for img in valid_images if img.is_gif]

        main_image = static_images[0] if static_images else ""
        if not main_image and self.allow_gif_as_main and gif_images:
            main_image = gif_images[0]

        details_pool = [url for url in static_images if url != main_image]
        if len(details_pool) < IMAGE_DETAIL_COUNT:
            for url in gif_images:
                if url == main_image or url in details_pool:
                    continue
                details_pool.append(url)
                if len(details_pool) >= IMAGE_DETAIL_COUNT:
                    break
        detail_images = details_pool[:IMAGE_DETAIL_COUNT]
        return ImageResolutionResult(
            main_image=main_image,
            detail_images=detail_images,
            source_queries=source_queries,
            all_valid_urls=[img.url for img in valid_images],
        )

    def fetch_bing_images(self, query: str) -> list[str]:
        query = query.strip()
        if not query:
            return []
        try:
            items = self.bing_image_client.fetch_images(query, limit=IMAGE_BING_FETCH_LIMIT)
        except Exception:
            return []
        urls: list[str] = []
        for item in items:
            if self._is_blocked_search_result(item):
                continue
            url = str(item.get("image_url") or "").strip()
            if self._is_blocked_image_url(url):
                continue
            if url and url not in urls:
                urls.append(url)
        return urls

    def fetch_baidu_images(self, query: str) -> list[str]:
        query = query.strip()
        if not query:
            return []
        try:
            items = self.baidu_image_client.fetch_images(query, limit=IMAGE_BAIDU_FETCH_LIMIT)
        except Exception:
            return []
        urls: list[str] = []
        for item in items:
            if self._is_blocked_search_result(item):
                continue
            url = str(item.get("image_url") or "").strip()
            if self._is_blocked_image_url(url):
                continue
            if url and url not in urls:
                urls.append(url)
        return urls

    def _build_queries(
        self,
        title: str,
        image_keywords: list[str],
        keywords: list[str],
    ) -> list[str]:
        del image_keywords, keywords
        value = str(title).strip()
        if not value:
            return []
        return [value[:IMAGE_TITLE_QUERY_MAX_LEN]]

    def _is_blocked_search_result(self, item: dict[str, str]) -> bool:
        meta_text = " ".join(
            str(item.get(field) or "").strip().lower()
            for field in ("title", "desc", "source_page")
        )
        if not meta_text:
            return False
        return any(token in meta_text for token in IMAGE_BING_META_BLOCKLIST)

    def _validate_urls(self, urls: list[str]) -> list[ImageProbe]:
        valid_images: list[ImageProbe] = []
        for url in urls:
            probe = self._probe_url(url)
            if probe is not None:
                valid_images.append(probe)
        return valid_images

    def _probe_url(self, url: str) -> ImageProbe | None:
        if url in self.validation_cache:
            return self.validation_cache[url]

        def _request() -> ImageProbe | None:
            response = self.session.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            content_type = (response.headers.get("Content-Type") or "").lower()
            if not content_type.startswith("image/"):
                response.close()
                return None
            if self._is_blocked_image_url(url):
                response.close()
                return None
            content_length = int(response.headers.get("Content-Length") or 0)
            size = 0
            for chunk in response.iter_content(chunk_size=2048):
                if not chunk:
                    continue
                size += len(chunk)
                if size >= self.min_bytes:
                    break
            response.close()
            if max(content_length, size) < self.min_bytes:
                return None
            is_gif = "gif" in content_type or url.lower().endswith(".gif")
            return ImageProbe(
                url=url,
                content_type=content_type,
                size=max(content_length, size),
                is_gif=is_gif,
            )

        try:
            probe = retry_call(_request, retries=self.retries)
        except Exception:
            probe = None

        self.validation_cache[url] = probe
        return probe

    def _is_blocked_image_url(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        if any(token in host for token in IMAGE_URL_HOST_BLOCKLIST):
            return True
        if any(token in path for token in IMAGE_URL_PATH_BLOCKLIST):
            return True
        return False
