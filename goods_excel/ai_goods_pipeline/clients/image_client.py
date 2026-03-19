from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from ai_goods_pipeline.clients.bing_image_client import BingImageClient
from ai_goods_pipeline.constants import (
    IMAGE_BING_FETCH_LIMIT,
    IMAGE_CANDIDATE_POOL_TARGET,
    IMAGE_DETAIL_COUNT,
    IMAGE_FALLBACK_QUERY_MAX_LEN,
    IMAGE_QUERY_LIMIT,
    IMAGE_REQUIRED_TOTAL,
    IMAGE_TITLE_QUERY_MAX_LEN,
    IMAGE_URL_HOST_BLOCKLIST,
    IMAGE_URL_PATH_BLOCKLIST,
)
from ai_goods_pipeline.utils.retry import retry_call
from ai_goods_pipeline.utils.text import normalize_title, similarity_ratio


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
        api_url: str,
        timeout: int,
        retries: int,
        min_bytes: int,
        allow_gif_as_main: bool,
        preset_file: Path,
    ) -> None:
        self.api_url = api_url
        self.timeout = timeout
        self.retries = retries
        self.min_bytes = min_bytes
        self.allow_gif_as_main = allow_gif_as_main
        self.preset_file = preset_file
        self.session = requests.Session()
        self.bing_image_client = BingImageClient(timeout=timeout)
        self.validation_cache: dict[str, ImageProbe | None] = {}
        self.ai_tech_presets = self._load_ai_tech_presets()

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
            bing_urls = self.fetch_bing_images(query)
            if bing_urls:
                source_queries.append(f"bing_images:{query}")
                for url in bing_urls:
                    if url not in candidate_urls:
                        candidate_urls.append(url)
            api_urls = self.fetch_images(query)
            if api_urls:
                source_queries.append(f"api:{query}")
                for url in api_urls:
                    if url not in candidate_urls:
                        candidate_urls.append(url)
            if len(candidate_urls) >= IMAGE_CANDIDATE_POOL_TARGET:
                break

        valid_images = self._validate_urls(candidate_urls)
        static_images = [img.url for img in valid_images if not img.is_gif]
        gif_images = [img.url for img in valid_images if img.is_gif]

        # AI 科技类允许使用预置素材兜底，但默认仍应优先走图片接口。
        if category_id == 128 and not static_images and not (self.allow_gif_as_main and gif_images):
            preset_urls = self._match_ai_tech_preset_images(title, image_keywords, keywords)
            if preset_urls:
                for url in preset_urls:
                    if url not in candidate_urls:
                        candidate_urls.append(url)
                source_queries.append("preset_fallback")
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

    def fetch_images(self, query: str) -> list[str]:
        query = query.strip()
        if not query:
            return []

        def _request() -> dict:
            response = self.session.get(
                self.api_url,
                params={"key": query},
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

        try:
            payload = retry_call(_request, retries=self.retries)
        except Exception:
            return []

        if payload.get("code") != 1:
            return []

        urls = payload.get("data") or []
        return [str(url).strip() for url in urls if str(url).strip()]

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
            url = str(item.get("image_url") or "").strip()
            if url and url not in urls:
                urls.append(url)
        return urls

    def _build_queries(
        self,
        title: str,
        image_keywords: list[str],
        keywords: list[str],
    ) -> list[str]:
        queries: list[str] = []
        ordered_terms = [title] + image_keywords + keywords
        for index, item in enumerate(ordered_terms):
            value = str(item).strip()
            if not value or value in queries:
                continue
            max_len = IMAGE_TITLE_QUERY_MAX_LEN if index == 0 else IMAGE_FALLBACK_QUERY_MAX_LEN
            queries.append(value[:max_len])
        return queries[:IMAGE_QUERY_LIMIT]

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

    def _load_ai_tech_presets(self) -> list[dict[str, str]]:
        if not self.preset_file.exists():
            return []
        entries: list[dict[str, str]] = []
        pattern = re.compile(r"^(?P<title>.+?)\s{2,}(?P<price>\d+(?:\.\d+)?)\s+(?P<url>https?://\S+)$")
        for line in self.preset_file.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            match = pattern.match(raw.replace("\t", "  "))
            if not match:
                continue
            entries.append(
                {
                    "title": match.group("title").strip(),
                    "price": match.group("price").strip(),
                    "url": match.group("url").strip(),
                }
            )
        return entries

    def _match_ai_tech_preset_images(
        self,
        title: str,
        image_keywords: list[str],
        keywords: list[str],
    ) -> list[str]:
        if not self.ai_tech_presets:
            return []
        reference_terms = [term for term in [title] + image_keywords + keywords if str(term).strip()]
        if not reference_terms:
            return []
        scored: list[tuple[float, str]] = []
        for item in self.ai_tech_presets:
            preset_title = item["title"]
            score = max(
                similarity_ratio(normalize_title(term), normalize_title(preset_title))
                for term in reference_terms
            )
            if score >= 0.25:
                scored.append((score, item["url"]))
        scored.sort(key=lambda row: row[0], reverse=True)
        urls: list[str] = []
        for _, url in scored[:2]:
            if url not in urls:
                urls.append(url)
        return urls
