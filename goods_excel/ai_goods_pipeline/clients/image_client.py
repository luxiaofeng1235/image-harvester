from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

import requests

from ai_goods_pipeline.clients.baidu_image_client import BaiduImageClient
from ai_goods_pipeline.clients.bing_image_client import BingImageClient
from ai_goods_pipeline.constants import (
    CITY_POOL,
    CRAFT_KEYWORDS,
    FOOD_KEYWORDS,
    FOOTBALL_KEYWORDS,
    IMAGE_CARRIER_KEYWORDS,
    IMAGE_BAIDU_FETCH_LIMIT,
    IMAGE_BING_META_BLOCKLIST,
    IMAGE_BING_FETCH_LIMIT,
    IMAGE_CANDIDATE_POOL_TARGET,
    IMAGE_DETAIL_COUNT,
    IMAGE_MATERIAL_HINTS,
    IMAGE_QUERY_LIMIT,
    IMAGE_QUERY_TERM_BLOCKLIST,
    IMAGE_TITLE_QUERY_MAX_LEN,
    JIANGSU_HINTS,
    SUZHOU_HINTS,
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
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.min_bytes = min_bytes
        self.allow_gif_as_main = allow_gif_as_main
        self.enable_bing = enable_bing
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
            baidu_urls = self.fetch_baidu_images(query, context=search_context)
            if baidu_urls:
                source_queries.append(f"baidu_images:{query}")
                for url in baidu_urls:
                    if url not in candidate_urls:
                        candidate_urls.append(url)
                    candidate_sources.setdefault(url, "baidu")
            if len(candidate_urls) >= IMAGE_CANDIDATE_POOL_TARGET:
                break

            if self.enable_bing:
                bing_urls = self.fetch_bing_images(query, context=search_context)
                if bing_urls:
                    source_queries.append(f"bing_images:{query}")
                    for url in bing_urls:
                        if url not in candidate_urls:
                            candidate_urls.append(url)
                        candidate_sources.setdefault(url, "bing")
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
        main_image_source = candidate_sources.get(main_image, "") if main_image else ""
        detail_image_sources = [candidate_sources.get(url, "") for url in detail_images]
        return ImageResolutionResult(
            main_image=main_image,
            detail_images=detail_images,
            main_image_source=main_image_source,
            detail_image_sources=detail_image_sources,
            source_queries=source_queries,
            all_valid_urls=[img.url for img in valid_images],
        )

    def fetch_bing_images(
        self,
        query: str,
        *,
        context: SearchRelevanceContext | None = None,
    ) -> list[str]:
        if not self.enable_bing:
            return []
        query = query.strip()
        if not query:
            return []
        try:
            items = self.bing_image_client.fetch_images(query, limit=IMAGE_BING_FETCH_LIMIT)
        except Exception:
            return []
        finally:
            self.bing_image_client.close_browser()
        urls: list[str] = []
        for item in items:
            if self._is_blocked_search_result(item):
                continue
            if context is not None and not self._is_relevant_search_result(item, context):
                continue
            url = str(item.get("image_url") or "").strip()
            if self._is_blocked_image_url(url):
                continue
            if url and url not in urls:
                urls.append(url)
        return urls

    def fetch_baidu_images(
        self,
        query: str,
        *,
        context: SearchRelevanceContext | None = None,
    ) -> list[str]:
        query = query.strip()
        if not query:
            return []
        try:
            items = self.baidu_image_client.fetch_images(query, limit=IMAGE_BAIDU_FETCH_LIMIT)
        except Exception:
            return []
        finally:
            self.baidu_image_client.close_browser()
        urls: list[str] = []
        for item in items:
            if self._is_blocked_search_result(item):
                continue
            if context is not None and not self._is_relevant_search_result(item, context):
                continue
            url = str(item.get("image_url") or "").strip()
            if self._is_blocked_image_url(url):
                continue
            if url and url not in urls:
                urls.append(url)
        return urls

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
        }

    def close(self) -> None:
        try:
            self.session.close()
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
            display_hint = "实物"
            if carrier_terms[0] in {"长方丝巾", "丝巾", "方巾", "围巾", "手帕", "折扇", "丝带"}:
                display_hint = "平铺"
            elif carrier_terms[0] in {"屏风", "挂画", "摆件"}:
                display_hint = "成品"
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
        query_terms = tuple(self._extract_query_terms(parts))
        expected_cities = tuple(self._extract_expected_cities(parts, category_id))
        return SearchRelevanceContext(
            category_id=category_id,
            query=str(title).strip(),
            query_terms=query_terms,
            expected_cities=expected_cities,
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

    def _build_meta_text(self, item: dict[str, str]) -> str:
        parts = [
            str(item.get("title") or "").strip().lower(),
            str(item.get("desc") or "").strip().lower(),
            str(item.get("source_page") or "").strip().lower(),
            str(item.get("image_url") or "").strip().lower(),
            str(item.get("thumbnail_url") or "").strip().lower(),
        ]
        return " ".join(part for part in parts if part)

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
        known_terms = CITY_POOL + SUZHOU_HINTS + FOOD_KEYWORDS + FOOTBALL_KEYWORDS + CRAFT_KEYWORDS

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
