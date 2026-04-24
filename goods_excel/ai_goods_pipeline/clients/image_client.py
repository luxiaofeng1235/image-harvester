from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import re
import threading
from urllib.parse import urlparse

import requests

from ai_goods_pipeline.clients.baidu_image_client import BaiduImageClient
from ai_goods_pipeline.clients.bing_image_client import BingImageClient
from ai_goods_pipeline.clients.clip_image_reranker import ClipImageReranker
from ai_goods_pipeline.constants import (
    CITY_POOL,
    CRAFT_KEYWORDS,
    FOOD_KEYWORDS,
    FOOTBALL_KEYWORDS,
    IMAGE_BAIDU_FETCH_LIMIT,
    IMAGE_BING_META_BLOCKLIST,
    IMAGE_BING_FETCH_LIMIT,
    IMAGE_CANDIDATE_POOL_TARGET,
    IMAGE_DETAIL_COUNT,
    IMAGE_QUERY_LIMIT,
    IMAGE_TITLE_QUERY_MAX_LEN,
    JIANGSU_HINTS,
    SUZHOU_HINTS,
    IMAGE_URL_HOST_BLOCKLIST,
    IMAGE_URL_PATH_BLOCKLIST,
)
from ai_goods_pipeline.enums.image_semantics import (
    IMAGE_CARRIER_KEYWORDS,
    IMAGE_FINISHED_DISPLAY_CARRIERS,
    IMAGE_FLAT_DISPLAY_CARRIERS,
    IMAGE_MATERIAL_HINTS,
    IMAGE_QUERY_TERM_BLOCKLIST,
)
from ai_goods_pipeline.utils.image_decode import probe_image_content, probe_image_header
from ai_goods_pipeline.utils.image_url import normalize_storable_image_url
from ai_goods_pipeline.utils.image_validation_cache import (
    load_validation_cache,
    save_validation_cache,
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
    width: int
    height: int
    fully_validated: bool = True


@dataclass(slots=True)
class ImageResolutionResult:
    main_image: str
    detail_images: list[str]
    main_image_source: str
    detail_image_sources: list[str]
    source_queries: list[str]
    all_valid_urls: list[str]


@dataclass(slots=True)
class SearchRelevanceContext:
    category_id: int
    query: str
    query_terms: tuple[str, ...]
    expected_cities: tuple[str, ...]


class ImageClient:
    def __init__(
        self,
        *,
        timeout: int,
        retries: int,
        min_bytes: int,
        allow_gif_as_main: bool,
        enable_bing: bool,
        enable_clip_rerank: bool,
        clip_model_name: str,
        clip_min_score: float,
        clip_max_candidates: int,
        clip_category_ids: tuple[int, ...],
        probe_range_bytes: int,
        validation_workers: int,
        validation_cache_path: str,
        validation_cache_max_entries: int,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.min_bytes = min_bytes
        self.allow_gif_as_main = allow_gif_as_main
        self.enable_bing = enable_bing
        self.probe_range_bytes = max(0, probe_range_bytes)
        self.validation_workers = max(1, validation_workers)
        self.validation_cache_path = Path(validation_cache_path).expanduser() if validation_cache_path else None
        self.validation_cache_max_entries = max(0, validation_cache_max_entries)
        self.baidu_image_client = BaiduImageClient(timeout=timeout)
        self.bing_image_client = BingImageClient(timeout=timeout)
        self.clip_reranker = ClipImageReranker(
            enabled=enable_clip_rerank,
            model_name=clip_model_name,
            min_score=clip_min_score,
            max_candidates=clip_max_candidates,
            category_ids=clip_category_ids,
            timeout=timeout,
            user_agent=USER_AGENT,
        )
        self._cache_lock = threading.Lock()
        self.validation_cache = self._load_validation_cache()

    def resolve_images(
        self,
        *,
        title: str,
        image_keywords: list[str],
        category_id: int,
        keywords: list[str],
    ) -> ImageResolutionResult:
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

        search_queries = self._build_queries(title, image_keywords, keywords, category_id)
        for query in search_queries:
            baidu_items = self.fetch_baidu_candidates(query, context=search_context)
            if baidu_items:
                source_queries.append(f"baidu_images:{query}")
                for item in baidu_items:
                    preview_url = str(item.get("thumbnail_url") or "").strip()
                    for url in self._extract_baidu_candidate_urls(item):
                        if url not in candidate_urls:
                            candidate_urls.append(url)
                        if preview_url:
                            candidate_preview_urls.setdefault(url, preview_url)
                        candidate_sources.setdefault(url, "baidu")
            if len(candidate_urls) >= IMAGE_CANDIDATE_POOL_TARGET:
                break

            if self.enable_bing:
                bing_items = self.fetch_bing_candidates(query, context=search_context)
                if bing_items:
                    source_queries.append(f"bing_images:{query}")
                    for item in bing_items:
                        url = normalize_storable_image_url(str(item.get("image_url") or "").strip())
                        preview_url = str(item.get("thumbnail_url") or "").strip()
                        if not url:
                            continue
                        if url not in candidate_urls:
                            candidate_urls.append(url)
                        if preview_url:
                            candidate_preview_urls.setdefault(url, preview_url)
                        candidate_sources.setdefault(url, "bing")
                if len(candidate_urls) >= IMAGE_CANDIDATE_POOL_TARGET:
                    break

        valid_images = self._validate_urls(candidate_urls)
        ordered_valid_urls = [img.url for img in valid_images]
        valid_images = self._rerank_valid_images(
            title=title,
            category_id=category_id,
            valid_images=valid_images,
            preview_url_map=candidate_preview_urls,
        )
        valid_images = self._confirm_selected_images(valid_images)
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
        main_image_source = candidate_sources.get(main_image, "") if main_image else ""
        detail_image_sources = [candidate_sources.get(url, "") for url in detail_images]
        return ImageResolutionResult(
            main_image=main_image,
            detail_images=detail_images,
            main_image_source=main_image_source,
            detail_image_sources=detail_image_sources,
            source_queries=source_queries,
            all_valid_urls=ordered_valid_urls,
        )

    def fetch_bing_candidates(
        self,
        query: str,
        *,
        context: SearchRelevanceContext | None = None,
    ) -> list[dict[str, str]]:
        if not self.enable_bing:
            return []
        query = query.strip()
        if not query:
            return []
        try:
            items = self.bing_image_client.fetch_images(query, limit=IMAGE_BING_FETCH_LIMIT)
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

    def fetch_bing_images(
        self,
        query: str,
        *,
        context: SearchRelevanceContext | None = None,
    ) -> list[str]:
        return [
            normalize_storable_image_url(str(item.get("image_url") or "").strip())
            for item in self.fetch_bing_candidates(query, context=context)
            if normalize_storable_image_url(str(item.get("image_url") or "").strip())
        ]

    def fetch_baidu_candidates(
        self,
        query: str,
        *,
        context: SearchRelevanceContext | None = None,
    ) -> list[dict[str, str]]:
        query = query.strip()
        if not query:
            return []
        try:
            items = self.baidu_image_client.fetch_images(query, limit=IMAGE_BAIDU_FETCH_LIMIT)
        except Exception:
            return []
        candidates: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for item in items:
            if self._is_blocked_search_result(item):
                continue
            if context is not None and not self._is_relevant_search_result(item, context):
                continue
            candidate = dict(item)
            candidate["raw_image_url"] = normalize_storable_image_url(
                str(item.get("raw_image_url") or "").strip()
            )
            candidate["thumbnail_url"] = normalize_storable_image_url(
                str(item.get("thumbnail_url") or "").strip()
            )
            candidate["data_imgurl"] = normalize_storable_image_url(
                str(item.get("data_imgurl") or "").strip()
            )
            candidate["image_url"] = normalize_storable_image_url(
                str(item.get("image_url") or "").strip()
            )
            candidate_urls = self._extract_baidu_candidate_urls(candidate)
            if not candidate_urls:
                continue
            primary_url = candidate_urls[0]
            if primary_url in seen_urls:
                continue
            candidate["image_url"] = primary_url
            candidates.append(candidate)
            seen_urls.add(primary_url)
        return candidates

    def fetch_baidu_images(
        self,
        query: str,
        *,
        context: SearchRelevanceContext | None = None,
    ) -> list[str]:
        return [
            normalize_storable_image_url(str(item.get("image_url") or "").strip())
            for item in self.fetch_baidu_candidates(query, context=context)
            if normalize_storable_image_url(str(item.get("image_url") or "").strip())
        ]

    def runtime_status(self) -> dict[str, bool]:
        baidu_render_ready = self.baidu_image_client.can_render()
        self.baidu_image_client.close_browser()
        bing_render_ready = False
        if self.enable_bing:
            bing_render_ready = self.bing_image_client.can_render()
            self.bing_image_client.close_browser()
        return {
            "bing_enabled": self.enable_bing,
            "baidu_render_ready": baidu_render_ready,
            "bing_render_ready": bing_render_ready,
            "clip_rerank_enabled": self.clip_reranker.runtime_status()["enabled"],
            "clip_rerank_deps_ready": self.clip_reranker.runtime_status()["deps_ready"],
            "clip_rerank_model": self.clip_reranker.runtime_status()["model_name"],
            "clip_rerank_last_error": self.clip_reranker.runtime_status()["last_error"],
        }

    def close(self) -> None:
        try:
            self._persist_validation_cache()
        except Exception:
            pass
        self.baidu_image_client.close()
        self.bing_image_client.close()

    def _build_queries(
        self,
        title: str,
        image_keywords: list[str],
        keywords: list[str],
        category_id: int,
    ) -> list[str]:
        queries: list[str] = []
        seen: set[str] = set()
        scoped_keywords = self._scoped_image_keywords(image_keywords)
        derived_queries = self._build_derived_queries(
            title,
            scoped_keywords,
            keywords,
            category_id,
        )

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

        for raw in scoped_keywords:
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
        source_text = " ".join([title, *self._scoped_image_keywords(image_keywords)])
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
        parts = [title, *self._scoped_image_keywords(image_keywords)]
        query_terms = tuple(self._extract_query_terms(parts))
        expected_cities = tuple(self._extract_expected_cities(parts, category_id))
        return SearchRelevanceContext(
            category_id=category_id,
            query=str(title).strip(),
            query_terms=query_terms,
            expected_cities=expected_cities,
        )

    def _scoped_image_keywords(self, image_keywords: list[str]) -> list[str]:
        scoped: list[str] = []
        seen: set[str] = set()
        for raw in image_keywords:
            value = str(raw or "").strip()
            if not value or value in seen:
                continue
            scoped.append(value)
            seen.add(value)
        return scoped[:3]

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
        if context.category_id == 128 and football_hits > 0 and self._matches_expected_city(meta_text, context):
            return True
        if context.category_id == 129 and craft_hits > 0:
            return True
        if (
            context.category_id in {126, 127}
            and food_hits > 0
            and self._matches_expected_city(meta_text, context)
        ):
            return True
        return False

    def _matches_expected_city(
        self,
        meta_text: str,
        context: SearchRelevanceContext,
    ) -> bool:
        if not context.expected_cities:
            return True
        return any(city in meta_text for city in context.expected_cities)

    def _build_meta_text(self, item: dict[str, str]) -> str:
        parts = [
            str(item.get("title") or "").strip().lower(),
            str(item.get("desc") or "").strip().lower(),
            str(item.get("source_page") or "").strip().lower(),
            str(item.get("image_url") or "").strip().lower(),
            str(item.get("thumbnail_url") or "").strip().lower(),
            str(item.get("data_imgurl") or "").strip().lower(),
        ]
        return " ".join(part for part in parts if part)

    def _extract_baidu_candidate_urls(self, item: dict[str, str]) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for raw_url in (
            str(item.get("image_url") or "").strip(),
            str(item.get("raw_image_url") or "").strip(),
            str(item.get("thumbnail_url") or "").strip(),
            str(item.get("data_imgurl") or "").strip(),
        ):
            url = normalize_storable_image_url(raw_url)
            if not url or url in seen or self._is_blocked_image_url(url):
                continue
            urls.append(url)
            seen.add(url)
        return urls

    def _extract_expected_cities(
        self, parts: list[str], category_id: int
    ) -> list[str]:
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

    def _validate_urls(self, urls: list[str]) -> list[ImageProbe]:
        if len(urls) <= 1 or self.validation_workers <= 1:
            return [probe for url in urls if (probe := self._probe_url(url)) is not None]

        with ThreadPoolExecutor(max_workers=min(self.validation_workers, len(urls))) as executor:
            results = list(executor.map(self._probe_url, urls))
        return [probe for probe in results if probe is not None]

    def _rerank_valid_images(
        self,
        *,
        title: str,
        category_id: int,
        valid_images: list[ImageProbe],
        preview_url_map: dict[str, str] | None = None,
    ) -> list[ImageProbe]:
        if len(valid_images) < 2:
            return valid_images

        static_images = [img for img in valid_images if not img.is_gif]
        gif_images = [img for img in valid_images if img.is_gif]
        if len(static_images) < 2:
            return valid_images

        rerank_result = self.clip_reranker.rerank_urls(
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

    def _probe_url(self, url: str) -> ImageProbe | None:
        return self._probe_url_internal(url, require_full=False)

    def _probe_url_internal(self, url: str, *, require_full: bool) -> ImageProbe | None:
        cached_probe, cached_exists = self._get_cached_probe(url)
        if cached_exists and (cached_probe is None or not require_full or cached_probe.fully_validated):
            return cached_probe

        def _request() -> tuple[ImageProbe | None, bool]:
            return self._request_probe(url, require_full=require_full)

        try:
            probe, cacheable = retry_call(_request, retries=self.retries)
        except Exception:
            return None

        if cacheable:
            self._set_cached_probe(url, probe)
        return probe

    def _request_probe(self, url: str, *, require_full: bool) -> tuple[ImageProbe | None, bool]:
        if self._is_blocked_image_url(url):
            return None, True

        allow_partial = not require_full and self.probe_range_bytes > 0
        request_headers = self._build_request_headers(url, allow_partial=allow_partial)
        response = requests.get(
            url,
            headers=request_headers,
            timeout=self.timeout,
        )
        if response.status_code in (403, 404, 410):
            return None, True
        response.raise_for_status()

        content_type = (response.headers.get("Content-Type") or "").lower()
        if not content_type.startswith("image/"):
            return None, True

        content = response.content
        size = self._resolve_response_size(response, content)
        if size < self.min_bytes:
            return None, True

        if allow_partial and response.status_code == 206:
            header_probe = probe_image_header(content)
            if header_probe is not None:
                width, height, image_format = header_probe
                return (
                    ImageProbe(
                        url=url,
                        content_type=content_type,
                        size=size,
                        is_gif=self._is_gif(url, content_type, image_format),
                        width=width,
                        height=height,
                        fully_validated=False,
                    ),
                    True,
                )

        decoded = probe_image_content(content)
        if decoded is None:
            if allow_partial and response.status_code == 206:
                return self._request_probe(url, require_full=True)
            return None, True

        width, height, image_format = decoded
        return (
            ImageProbe(
                url=url,
                content_type=content_type,
                size=size,
                is_gif=self._is_gif(url, content_type, image_format),
                width=width,
                height=height,
                fully_validated=True,
            ),
            True,
        )

    def _confirm_selected_images(self, valid_images: list[ImageProbe]) -> list[ImageProbe]:
        if not valid_images:
            return []
        target_count = IMAGE_DETAIL_COUNT + 1
        confirmed: list[ImageProbe] = []
        for probe in valid_images:
            full_probe = self._probe_url_internal(probe.url, require_full=True)
            if full_probe is None:
                continue
            confirmed.append(full_probe)
            if len(confirmed) >= target_count:
                break
        return confirmed

    def _build_request_headers(self, url: str, *, allow_partial: bool) -> dict[str, str]:
        headers = {"User-Agent": USER_AGENT}
        referer = self._guess_referer(url)
        if referer:
            headers["Referer"] = referer
        if allow_partial:
            partial_bytes = max(self.probe_range_bytes, self.min_bytes)
            headers["Range"] = f"bytes=0-{partial_bytes - 1}"
        return headers

    def _resolve_response_size(self, response: requests.Response, content: bytes) -> int:
        try:
            content_length = int(response.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            content_length = 0
        content_range = str(response.headers.get("Content-Range") or "").strip()
        if "/" in content_range:
            total_text = content_range.rsplit("/", 1)[-1].strip()
            if total_text.isdigit():
                return max(int(total_text), len(content), content_length)
        return max(content_length, len(content))

    def _is_gif(self, url: str, content_type: str, image_format: str) -> bool:
        return (
            "gif" in content_type
            or image_format == "gif"
            or url.lower().endswith(".gif")
        )

    def _get_cached_probe(self, url: str) -> tuple[ImageProbe | None, bool]:
        with self._cache_lock:
            if url not in self.validation_cache:
                return None, False
            return self.validation_cache[url], True

    def _set_cached_probe(self, url: str, probe: ImageProbe | None) -> None:
        with self._cache_lock:
            self.validation_cache[url] = probe

    def _load_validation_cache(self) -> dict[str, ImageProbe | None]:
        raw_cache = load_validation_cache(self.validation_cache_path)
        parsed: dict[str, ImageProbe | None] = {}
        for url, payload in raw_cache.items():
            parsed[url] = self._deserialize_probe(payload)
        return parsed

    def _persist_validation_cache(self) -> None:
        payload = {
            url: self._serialize_probe(probe)
            for url, probe in self.validation_cache.items()
        }
        save_validation_cache(
            self.validation_cache_path,
            payload,
            max_entries=self.validation_cache_max_entries,
        )

    def _serialize_probe(self, probe: ImageProbe | None) -> dict[str, object] | None:
        if probe is None:
            return None
        return {
            "url": probe.url,
            "content_type": probe.content_type,
            "size": probe.size,
            "is_gif": probe.is_gif,
            "width": probe.width,
            "height": probe.height,
            "fully_validated": probe.fully_validated,
        }

    def _deserialize_probe(self, payload: dict[str, object] | None) -> ImageProbe | None:
        if payload is None or not isinstance(payload, dict):
            return None
        url = str(payload.get("url") or "").strip()
        content_type = str(payload.get("content_type") or "").strip().lower()
        try:
            size = int(payload.get("size") or 0)
            width = int(payload.get("width") or 0)
            height = int(payload.get("height") or 0)
        except (TypeError, ValueError):
            return None
        if not url or size <= 0 or width <= 0 or height <= 0:
            return None
        return ImageProbe(
            url=url,
            content_type=content_type,
            size=size,
            is_gif=bool(payload.get("is_gif")),
            width=width,
            height=height,
            fully_validated=bool(payload.get("fully_validated", True)),
        )

    @staticmethod
    def _guess_referer(url: str) -> str:
        host = (urlparse(url).netloc or "").lower()
        if "baidu" in host or "bdstatic" in host or "bcebos" in host or "bdimg" in host:
            return "https://image.baidu.com/"
        if "bing" in host or "bing.net" in host:
            return "https://cn.bing.com/"
        return ""

    def _is_blocked_image_url(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        if any(token in host for token in IMAGE_URL_HOST_BLOCKLIST):
            return True
        if any(token in path for token in IMAGE_URL_PATH_BLOCKLIST):
            return True
        return False
