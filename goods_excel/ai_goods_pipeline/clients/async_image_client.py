from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
from urllib.parse import urlparse

import httpx

from ai_goods_pipeline.clients.async_baidu_image_client import AsyncBaiduImageClient
from ai_goods_pipeline.clients.clip_image_reranker import ClipImageReranker
from ai_goods_pipeline.constants import (
    CITY_POOL,
    CRAFT_KEYWORDS,
    FOOD_KEYWORDS,
    FOOTBALL_KEYWORDS,
    IMAGE_BAIDU_FETCH_LIMIT,
    IMAGE_BING_META_BLOCKLIST,
    IMAGE_CANDIDATE_POOL_TARGET,
    IMAGE_DETAIL_COUNT,
    IMAGE_QUERY_LIMIT,
    IMAGE_TITLE_QUERY_MAX_LEN,
    IMAGE_URL_HOST_BLOCKLIST,
    IMAGE_URL_PATH_BLOCKLIST,
    JIANGSU_HINTS,
    SUZHOU_HINTS,
)
from ai_goods_pipeline.enums.image_semantics import (
    IMAGE_CARRIER_KEYWORDS,
    IMAGE_FINISHED_DISPLAY_CARRIERS,
    IMAGE_FLAT_DISPLAY_CARRIERS,
    IMAGE_MATERIAL_HINTS,
    IMAGE_QUERY_TERM_BLOCKLIST,
)
from ai_goods_pipeline.utils.image_url import normalize_storable_image_url
from ai_goods_pipeline.utils.async_retry import async_retry_call


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


@dataclass(slots=True)
class AsyncImageProbe:
    url: str
    content_type: str
    size: int
    is_gif: bool


@dataclass(slots=True)
class AsyncImageResolutionResult:
    main_image: str
    detail_images: list[str]
    main_image_source: str
    detail_image_sources: list[str]
    source_queries: list[str]
    all_valid_urls: list[str]


@dataclass(slots=True)
class SearchRelevanceContext:
    category_id: int
    query_terms: tuple[str, ...]
    expected_cities: tuple[str, ...]


class AsyncImageClient:
    def __init__(
        self,
        *,
        timeout: int,
        retries: int,
        min_bytes: int,
        allow_gif_as_main: bool,
        enable_clip_rerank: bool,
        clip_model_name: str,
        clip_min_score: float,
        clip_max_candidates: int,
        clip_category_ids: tuple[int, ...],
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.min_bytes = min_bytes
        self.allow_gif_as_main = allow_gif_as_main
        self.http_client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self.baidu_image_client = AsyncBaiduImageClient(timeout=timeout)
        self.clip_reranker = ClipImageReranker(
            enabled=enable_clip_rerank,
            model_name=clip_model_name,
            min_score=clip_min_score,
            max_candidates=clip_max_candidates,
            category_ids=clip_category_ids,
            timeout=timeout,
            user_agent=USER_AGENT,
        )
        self.validation_cache: dict[str, AsyncImageProbe | None] = {}

    async def close(self) -> None:
        await self.http_client.aclose()
        await self.baidu_image_client.close()

    async def resolve_images(
        self,
        *,
        title: str,
        image_keywords: list[str],
        category_id: int,
        keywords: list[str],
    ) -> AsyncImageResolutionResult:
        candidate_urls: list[str] = []
        candidate_preview_urls: dict[str, str] = {}
        candidate_sources: dict[str, str] = {}
        source_queries: list[str] = []
        search_context = self._build_search_context(
            title=title,
            image_keywords=image_keywords,
            category_id=category_id,
            keywords=keywords,
        )

        for query in self._build_queries(title, image_keywords, keywords, category_id):
            baidu_items = await self.fetch_baidu_candidates(query, context=search_context)
            if baidu_items:
                source_queries.append(f"baidu_images:{query}")
                for item in baidu_items:
                    url = normalize_storable_image_url(str(item.get("image_url") or "").strip())
                    preview_url = str(item.get("thumbnail_url") or "").strip()
                    if not url:
                        continue
                    if url not in candidate_urls:
                        candidate_urls.append(url)
                    if preview_url:
                        candidate_preview_urls.setdefault(url, preview_url)
                    candidate_sources.setdefault(url, "baidu")
            if len(candidate_urls) >= IMAGE_CANDIDATE_POOL_TARGET:
                break

        valid_images = await self._validate_urls(candidate_urls)
        valid_images = await self._rerank_valid_images(
            title=title,
            category_id=category_id,
            valid_images=valid_images,
            preview_url_map=candidate_preview_urls,
        )
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
        return AsyncImageResolutionResult(
            main_image=main_image,
            detail_images=detail_images,
            main_image_source=candidate_sources.get(main_image, "") if main_image else "",
            detail_image_sources=[candidate_sources.get(url, "") for url in detail_images],
            source_queries=source_queries,
            all_valid_urls=[img.url for img in valid_images],
        )

    async def fetch_baidu_candidates(
        self,
        query: str,
        *,
        context: SearchRelevanceContext | None = None,
    ) -> list[dict[str, str]]:
        query = query.strip()
        if not query:
            return []
        try:
            items = await self.baidu_image_client.fetch_images(query, limit=IMAGE_BAIDU_FETCH_LIMIT)
        except Exception:
            return []
        candidates: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for item in items:
            if self._is_blocked_search_result(item):
                continue
            if context is not None and not self._is_relevant_search_result(item, context):
                continue
            url = normalize_storable_image_url(str(item.get("image_url") or "").strip())
            if self._is_blocked_image_url(url):
                continue
            if url and url not in seen_urls:
                candidate = dict(item)
                candidate["image_url"] = url
                candidates.append(candidate)
                seen_urls.add(url)
        return candidates

    async def fetch_baidu_images(
        self,
        query: str,
        *,
        context: SearchRelevanceContext | None = None,
    ) -> list[str]:
        items = await self.fetch_baidu_candidates(query, context=context)
        return [
            normalize_storable_image_url(str(item.get("image_url") or "").strip())
            for item in items
            if normalize_storable_image_url(str(item.get("image_url") or "").strip())
        ]

    def _build_queries(
        self,
        title: str,
        image_keywords: list[str],
        keywords: list[str],
        category_id: int,
    ) -> list[str]:
        queries: list[str] = []
        seen: set[str] = set()
        derived_queries = self._build_derived_queries(title, image_keywords, keywords, category_id)

        def _push(raw: str) -> None:
            value = str(raw or "").strip()
            if not value:
                return
            query = value[:IMAGE_TITLE_QUERY_MAX_LEN]
            if query in seen:
                return
            queries.append(query)
            seen.add(query)

        for raw in derived_queries:
            _push(raw)
            if len(queries) >= IMAGE_QUERY_LIMIT:
                return queries
        _push(title)
        if len(queries) >= IMAGE_QUERY_LIMIT:
            return queries

        for raw in [*image_keywords, *keywords]:
            value = str(raw or "").strip()
            if not value:
                continue
            _push(value)
            if len(queries) >= IMAGE_QUERY_LIMIT:
                break
        return queries

    def _build_derived_queries(
        self,
        title: str,
        image_keywords: list[str],
        keywords: list[str],
        category_id: int,
    ) -> list[str]:
        source_text = " ".join([title, *image_keywords, *keywords])
        city = next(iter(self._extract_expected_cities([source_text], category_id)), "")
        quoted_terms = re.findall(r"[“\"]([^”\"]{2,12})[”\"]", title)
        carrier_terms = [term for term in IMAGE_CARRIER_KEYWORDS if term in source_text]
        material_terms = [term for term in IMAGE_MATERIAL_HINTS if term in source_text]

        variants: list[str] = []
        if category_id == 128 and carrier_terms:
            if city and quoted_terms:
                variants.append(f"{city} {quoted_terms[0]} {carrier_terms[0]}")
            if quoted_terms:
                variants.append(f"{quoted_terms[0]} {carrier_terms[0]}")
            if city:
                variants.append(f"{city} {carrier_terms[0]}")
        elif category_id == 129 and carrier_terms:
            display_hint = self._get_display_hint(carrier_terms[0])
            if material_terms:
                variants.append(f"{material_terms[0]} {carrier_terms[0]} {display_hint}")
            if quoted_terms:
                variants.append(f"{quoted_terms[0]} {carrier_terms[0]} {display_hint}")
            if "屏风" in carrier_terms[0]:
                variants.append("苏绣 屏风 成品")
        elif category_id in {126, 127}:
            food_terms = [term for term in FOOD_KEYWORDS if term in source_text]
            if city and food_terms:
                variants.append(f"{city} {food_terms[0]}")

        deduped: list[str] = []
        seen = set()
        for item in variants:
            value = item.strip()
            if not value or value in seen:
                continue
            deduped.append(value)
            seen.add(value)
        return deduped[:3]

    def _build_search_context(
        self,
        *,
        title: str,
        image_keywords: list[str],
        category_id: int,
        keywords: list[str],
    ) -> SearchRelevanceContext:
        parts = [title, *image_keywords, *keywords]
        return SearchRelevanceContext(
            category_id=category_id,
            query_terms=tuple(self._extract_query_terms(parts)),
            expected_cities=tuple(self._extract_expected_cities(parts, category_id)),
        )

    def _is_blocked_search_result(self, item: dict[str, str]) -> bool:
        meta_text = " ".join(
            str(item.get(field) or "").strip().lower()
            for field in ("title", "desc", "source_page")
        )
        if not meta_text:
            return False
        return any(token in meta_text for token in IMAGE_BING_META_BLOCKLIST)

    def _is_relevant_search_result(
        self, item: dict[str, str], context: SearchRelevanceContext
    ) -> bool:
        meta_text = self._build_meta_text(item)
        if not meta_text:
            return True

        city_hits = {city for city in JIANGSU_HINTS if city.lower() in meta_text}
        query_hits = self._count_keyword_hits(meta_text, context.query_terms)
        if (
            context.expected_cities
            and city_hits
            and not any(city in city_hits for city in context.expected_cities)
        ):
            return False

        # If the search result already strongly matches the query terms, keep it.
        # This avoids treating food results that contain words like "手工" as craft-only noise.
        if query_hits > 0:
            return True

        football_hits = self._count_keyword_hits(meta_text, FOOTBALL_KEYWORDS)
        craft_hits = self._count_keyword_hits(meta_text, CRAFT_KEYWORDS)
        food_hits = self._count_keyword_hits(meta_text, FOOD_KEYWORDS)

        if context.category_id == 128 and football_hits == 0 and (food_hits > 0 or craft_hits > 0):
            return False
        if context.category_id == 129 and craft_hits == 0 and (food_hits > 0 or football_hits > 0):
            return False
        if context.category_id in {126, 127} and food_hits == 0 and (craft_hits > 0 or football_hits > 0):
            return False

        if query_hits > 0:
            return True
        if context.category_id == 128 and football_hits > 0:
            return True
        if context.category_id == 129 and craft_hits > 0:
            return True
        if context.category_id in {126, 127} and food_hits > 0:
            return True
        if context.expected_cities and any(city in meta_text for city in context.expected_cities):
            return True
        return True

    async def _validate_urls(self, urls: list[str]) -> list[AsyncImageProbe]:
        results = await asyncio.gather(*[self._probe_url(url) for url in urls], return_exceptions=True)
        valid_images: list[AsyncImageProbe] = []
        for result in results:
            if isinstance(result, AsyncImageProbe):
                valid_images.append(result)
        return valid_images

    async def _probe_url(self, url: str) -> AsyncImageProbe | None:
        if url in self.validation_cache:
            return self.validation_cache[url]

        async def _request() -> AsyncImageProbe | None:
            async with self.http_client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = (response.headers.get("Content-Type") or "").lower()
                if not content_type.startswith("image/"):
                    return None
                if self._is_blocked_image_url(url):
                    return None
                content_length = int(response.headers.get("Content-Length") or 0)
                size = 0
                async for chunk in response.aiter_bytes(chunk_size=2048):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size >= self.min_bytes:
                        break
                if max(content_length, size) < self.min_bytes:
                    return None
                is_gif = "gif" in content_type or url.lower().endswith(".gif")
                return AsyncImageProbe(
                    url=url,
                    content_type=content_type,
                    size=max(content_length, size),
                    is_gif=is_gif,
                )

        try:
            probe = await async_retry_call(_request, retries=self.retries)
        except Exception:
            probe = None

        self.validation_cache[url] = probe
        return probe

    async def _rerank_valid_images(
        self,
        *,
        title: str,
        category_id: int,
        valid_images: list[AsyncImageProbe],
        preview_url_map: dict[str, str] | None = None,
    ) -> list[AsyncImageProbe]:
        if len(valid_images) < 2:
            return valid_images

        static_images = [img for img in valid_images if not img.is_gif]
        gif_images = [img for img in valid_images if img.is_gif]
        if len(static_images) < 2:
            return valid_images

        rerank_result = await asyncio.to_thread(
            self.clip_reranker.rerank_urls,
            title=title,
            category_id=category_id,
            candidate_urls=[img.url for img in static_images],
            preview_url_map=preview_url_map,
        )
        if not rerank_result.applied:
            return valid_images

        static_map = {img.url: img for img in static_images}
        reordered_static = [
            static_map[url]
            for url in rerank_result.ranked_urls
            if url in static_map
        ]
        if len(reordered_static) != len(static_images):
            return valid_images
        return reordered_static + gif_images

    def _build_meta_text(self, item: dict[str, str]) -> str:
        parts = [
            str(item.get("title") or "").strip().lower(),
            str(item.get("desc") or "").strip().lower(),
            str(item.get("source_page") or "").strip().lower(),
            str(item.get("image_url") or "").strip().lower(),
            str(item.get("thumbnail_url") or "").strip().lower(),
        ]
        return " ".join(part for part in parts if part)

    def _extract_expected_cities(self, parts: list[str], category_id: int) -> list[str]:
        source_text = " ".join(str(part).lower() for part in parts if part)
        matches: list[str] = []
        for city in CITY_POOL + SUZHOU_HINTS:
            city_lower = city.lower()
            if city_lower in source_text and city_lower not in matches:
                matches.append(city_lower)
        return matches

    def _extract_query_terms(self, parts: list[str]) -> list[str]:
        terms: list[str] = []
        seen: set[str] = set()
        known_terms = (
            CITY_POOL
            + SUZHOU_HINTS
            + FOOD_KEYWORDS
            + FOOTBALL_KEYWORDS
            + CRAFT_KEYWORDS
            + IMAGE_CARRIER_KEYWORDS
            + IMAGE_MATERIAL_HINTS
        )

        for part in parts:
            text = str(part or "").strip().lower()
            if not text:
                continue
            for known in known_terms:
                token = known.lower()
                if token in text and token not in seen:
                    terms.append(token)
                    seen.add(token)

            for chunk in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,16}", text):
                for token in self._expand_text_chunk(chunk):
                    if token in seen or token in IMAGE_QUERY_TERM_BLOCKLIST:
                        continue
                    terms.append(token)
                    seen.add(token)

        terms.sort(key=len, reverse=True)
        return terms[:20]

    def _expand_text_chunk(self, chunk: str) -> list[str]:
        token = chunk.strip().lower()
        if len(token) < 2:
            return []
        if len(token) <= 8:
            return [token]
        variants = [token]
        for size in (4, 3, 2):
            if len(token) >= size:
                variants.append(token[:size])
                variants.append(token[-size:])
        deduped: list[str] = []
        seen = set()
        for item in variants:
            if item in seen or item in IMAGE_QUERY_TERM_BLOCKLIST or len(item) < 2:
                continue
            deduped.append(item)
            seen.add(item)
        return deduped

    def _count_keyword_hits(self, text: str, terms: list[str] | tuple[str, ...]) -> int:
        return sum(1 for term in terms if term and term.lower() in text)

    def _get_display_hint(self, carrier: str) -> str:
        if carrier in IMAGE_FLAT_DISPLAY_CARRIERS:
            return "平铺"
        if carrier in IMAGE_FINISHED_DISPLAY_CARRIERS:
            return "成品"
        return "实物"

    def _is_blocked_image_url(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        if any(token in host for token in IMAGE_URL_HOST_BLOCKLIST):
            return True
        if any(token in path for token in IMAGE_URL_PATH_BLOCKLIST):
            return True
        return False
