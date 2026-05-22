from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
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
from ai_goods_pipeline.utils.image_decode import probe_image_content, probe_image_header
from ai_goods_pipeline.utils.image_url import normalize_storable_image_url
from ai_goods_pipeline.utils.image_validation_cache import (
    load_validation_cache,
    save_validation_cache,
)
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
    width: int
    height: int
    fully_validated: bool = True


@dataclass(slots=True)
class AsyncImageResolutionResult:
    main_image: str
    detail_images: list[str]
    main_image_source: str
    detail_image_sources: list[str]
    source_queries: list[str]
    all_valid_urls: list[str]


@dataclass(slots=True)
class AsyncImageResolutionPool:
    source_queries: list[str]
    all_valid_urls: list[str]
    static_urls: list[str]
    gif_urls: list[str]
    candidate_sources: dict[str, str]


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
        enable_bing: bool = False,
        enable_clip_rerank: bool,
        clip_model_name: str,
        clip_min_score: float,
        clip_max_candidates: int,
        clip_category_ids: tuple[int, ...],
        probe_range_bytes: int,
        validation_workers: int = 8,
        validation_cache_path: str,
        validation_cache_max_entries: int,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.min_bytes = min_bytes
        self.allow_gif_as_main = allow_gif_as_main
        self.enable_bing = enable_bing
        self.probe_range_bytes = max(0, probe_range_bytes)
        # 并发验证上限：控制同时发出的图片验证请求数，避免目标服务器限流
        self.validation_workers = max(1, validation_workers)
        self.validation_cache_path = Path(validation_cache_path).expanduser() if validation_cache_path else None
        self.validation_cache_max_entries = max(0, validation_cache_max_entries)
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
        self.validation_cache = self._load_validation_cache()
        self.resolution_pool_cache: dict[str, AsyncImageResolutionPool] = {}
        self._resolution_pool_lock = asyncio.Lock()
        self._resolution_pool_inflight: dict[str, asyncio.Task[AsyncImageResolutionPool]] = {}

    async def close(self) -> None:
        async with self._resolution_pool_lock:
            inflight = list(self._resolution_pool_inflight.values())
            self._resolution_pool_inflight.clear()
        for task in inflight:
            task.cancel()
        if inflight:
            await asyncio.gather(*inflight, return_exceptions=True)
        try:
            self._persist_validation_cache()
        except Exception:
            pass
        await asyncio.gather(
            asyncio.wait_for(self.http_client.aclose(), timeout=3.0),
            asyncio.wait_for(self.baidu_image_client.close(), timeout=5.0),
            return_exceptions=True,
        )

    async def runtime_status(self) -> dict[str, bool | str]:
        baidu_render_ready = await self.baidu_image_client.can_render()
        await self.baidu_image_client.close()
        clip_runtime = self.clip_reranker.runtime_status()
        return {
            "bing_enabled": False,
            "baidu_render_ready": baidu_render_ready,
            "bing_render_ready": False,
            "clip_rerank_enabled": clip_runtime["enabled"],
            "clip_rerank_deps_ready": clip_runtime["deps_ready"],
            "clip_rerank_model": clip_runtime["model_name"],
            "clip_rerank_last_error": clip_runtime["last_error"],
        }

    async def resolve_images(
        self,
        *,
        title: str,
        image_keywords: list[str],
        category_id: int,
        keywords: list[str],
        reuse_key: str = "",
        exclude_urls: set[str] | None = None,
    ) -> AsyncImageResolutionResult:
        pool = await self._resolve_image_pool(
            title=title,
            image_keywords=image_keywords,
            category_id=category_id,
            keywords=keywords,
            reuse_key=reuse_key,
        )
        return await self._select_images_from_pool(pool, exclude_urls=exclude_urls)

    async def resolve_image_pool(
        self,
        *,
        title: str,
        image_keywords: list[str],
        category_id: int,
        keywords: list[str],
        reuse_key: str = "",
    ) -> AsyncImageResolutionPool:
        return await self._resolve_image_pool(
            title=title,
            image_keywords=image_keywords,
            category_id=category_id,
            keywords=keywords,
            reuse_key=reuse_key,
        )

    async def select_images_from_pool(
        self,
        pool: AsyncImageResolutionPool,
        *,
        exclude_urls: set[str] | None = None,
    ) -> AsyncImageResolutionResult:
        return await self._select_images_from_pool(pool, exclude_urls=exclude_urls)

    async def _resolve_image_pool(
        self,
        *,
        title: str,
        image_keywords: list[str],
        category_id: int,
        keywords: list[str],
        reuse_key: str = "",
    ) -> AsyncImageResolutionPool:
        cache_key = str(reuse_key or "").strip()
        if cache_key and cache_key in self.resolution_pool_cache:
            return self.resolution_pool_cache[cache_key]
        if cache_key:
            async with self._resolution_pool_lock:
                cached_pool = self.resolution_pool_cache.get(cache_key)
                if cached_pool is not None:
                    return cached_pool
                inflight_task = self._resolution_pool_inflight.get(cache_key)
                if inflight_task is None:
                    inflight_task = asyncio.create_task(
                        self._build_image_pool(
                            title=title,
                            image_keywords=image_keywords,
                            category_id=category_id,
                            keywords=keywords,
                        )
                    )
                    self._resolution_pool_inflight[cache_key] = inflight_task
            try:
                pool = await inflight_task
            finally:
                async with self._resolution_pool_lock:
                    if self._resolution_pool_inflight.get(cache_key) is inflight_task:
                        self._resolution_pool_inflight.pop(cache_key, None)
            self.resolution_pool_cache[cache_key] = pool
            return pool

        return await self._build_image_pool(
            title=title,
            image_keywords=image_keywords,
            category_id=category_id,
            keywords=keywords,
        )

    async def _build_image_pool(
        self,
        *,
        title: str,
        image_keywords: list[str],
        category_id: int,
        keywords: list[str],
    ) -> AsyncImageResolutionPool:
        """构建图片候选池：搜图 → 验证 → 预加载完整解码 → 返回池对象。

        流程：
        1. _build_queries 构建搜索关键词（title + image_keywords + 衍生词）
        2. 逐个关键词调百度搜图，收集候选 URL（达到 IMAGE_CANDIDATE_POOL_TARGET 即停止）
        3. _validate_urls 并发验证所有候选 URL 的有效性（Range 请求 + 文件头校验）
        4. _prevalidate_full 并发预验证完整图片解码（写入缓存，供后续 pick 时直接命中）
        5. 可选 CLIP 重排（对 128/129 分类开启，缩小候选范围后排序）
        """
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

        # 并发搜图：前 2 个查询并发发起，后续按需串行补搜
        queries = list(self._build_queries(title, image_keywords, keywords, category_id))

        def _collect_baidu_results(query: str, baidu_items: list[dict]) -> None:
            """将百度搜索结果合并到候选池。"""
            if not baidu_items:
                return
            source_queries.append(f"baidu_images:{query}")
            for item in baidu_items:
                preview_url = str(item.get("thumbnail_url") or "").strip()
                for url in self._extract_baidu_candidate_urls(item):
                    if url not in candidate_urls:
                        candidate_urls.append(url)
                    if preview_url:
                        candidate_preview_urls.setdefault(url, preview_url)
                    candidate_sources.setdefault(url, "baidu")

        # 前 2 个查询并发发起，充分利用百度并发 tab
        if len(queries) >= 2:
            first_two = queries[:2]
            remaining = queries[2:]
            results = await asyncio.gather(
                *[self.fetch_baidu_candidates(q, context=search_context) for q in first_two]
            )
            for query, items in zip(first_two, results):
                _collect_baidu_results(query, items)
        else:
            remaining = queries

        # 如果候选池还不够，串行补搜剩余查询
        if len(candidate_urls) < IMAGE_CANDIDATE_POOL_TARGET:
            for query in remaining:
                baidu_items = await self.fetch_baidu_candidates(query, context=search_context)
                _collect_baidu_results(query, baidu_items)
                if len(candidate_urls) >= IMAGE_CANDIDATE_POOL_TARGET:
                    break

        # 并发验证所有候选 URL 的有效性（Range 请求 + 文件头校验）
        valid_images = await self._validate_urls(candidate_urls)
        ordered_valid_urls = [img.url for img in valid_images]

        # 并发预验证完整图片解码，结果写入 validation_cache，
        # 后续 _pick_valid_urls 调用 _probe_url_internal(url, require_full=True) 时直接命中缓存
        await self._prevalidate_full(valid_images)

        # 可选 CLIP 重排（对 128/129 分类开启）
        valid_images = await self._rerank_valid_images(
            title=title,
            category_id=category_id,
            valid_images=valid_images,
            preview_url_map=candidate_preview_urls,
        )
        pool = AsyncImageResolutionPool(
            source_queries=source_queries,
            all_valid_urls=ordered_valid_urls,
            static_urls=[img.url for img in valid_images if not img.is_gif],
            gif_urls=[img.url for img in valid_images if img.is_gif],
            candidate_sources=dict(candidate_sources),
        )
        return pool

    async def _prevalidate_full(self, valid_images: list[AsyncImageProbe]) -> None:
        """并发预验证所有候选图片的完整字节解码，结果写入 validation_cache。

        作用：后续 _pick_valid_urls 调用 _probe_url_internal(url, require_full=True) 时
        直接命中缓存，避免逐个串行发网络请求。
        """
        urls = [img.url for img in valid_images if img.url]
        if not urls:
            return
        semaphore = asyncio.Semaphore(max(1, self.validation_workers))

        async def _limited_full(url: str):
            async with semaphore:
                return await self._probe_url_internal(url, require_full=True)

        await asyncio.gather(*[_limited_full(u) for u in urls], return_exceptions=True)

    async def _select_images_from_pool(
        self,
        pool: AsyncImageResolutionPool,
        *,
        exclude_urls: set[str] | None = None,
    ) -> AsyncImageResolutionResult:
        excluded = {
            normalize_storable_image_url(url)
            for url in (exclude_urls or set())
            if normalize_storable_image_url(url)
        }

        selected_urls: set[str] = set(excluded)
        main_image = await self._pick_first_valid_url(
            pool.static_urls,
            excluded_urls=selected_urls,
        )
        if main_image:
            selected_urls.add(main_image)
        elif self.allow_gif_as_main:
            main_image = await self._pick_first_valid_url(
                pool.gif_urls,
                excluded_urls=selected_urls,
            )
            if main_image:
                selected_urls.add(main_image)

        detail_images = await self._pick_valid_urls(
            pool.static_urls,
            excluded_urls=selected_urls,
            limit=IMAGE_DETAIL_COUNT,
        )
        selected_urls.update(detail_images)
        if len(detail_images) < IMAGE_DETAIL_COUNT:
            detail_images.extend(
                await self._pick_valid_urls(
                    pool.gif_urls,
                    excluded_urls=selected_urls,
                    limit=IMAGE_DETAIL_COUNT - len(detail_images),
                )
            )

        return AsyncImageResolutionResult(
            main_image=main_image,
            detail_images=detail_images,
            main_image_source=pool.candidate_sources.get(main_image, "") if main_image else "",
            detail_image_sources=[pool.candidate_sources.get(url, "") for url in detail_images],
            source_queries=pool.source_queries,
            all_valid_urls=pool.all_valid_urls,
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
        return SearchRelevanceContext(
            category_id=category_id,
            query_terms=tuple(self._extract_query_terms(parts)),
            expected_cities=tuple(self._extract_expected_cities(parts, category_id)),
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

    async def _validate_urls(self, urls: list[str]) -> list[AsyncImageProbe]:
        """并发验证所有候选 URL，使用 semaphore 限制并发数。

        原实现用 asyncio.gather 一次性并发所有 URL（无上限），
        当候选池有 20+ 个 URL 时会导致目标服务器限流或连接池耗尽。
        现在用 validation_workers 作为并发上限（默认 8）。
        """
        if not urls:
            return []
        semaphore = asyncio.Semaphore(max(1, self.validation_workers))

        async def _limited(url: str):
            async with semaphore:
                return await self._probe_url(url)

        results = await asyncio.gather(*[_limited(u) for u in urls], return_exceptions=True)
        valid_images: list[AsyncImageProbe] = []
        for result in results:
            if isinstance(result, AsyncImageProbe):
                valid_images.append(result)
        return valid_images

    async def _probe_url(self, url: str) -> AsyncImageProbe | None:
        return await self._probe_url_internal(url, require_full=False)

    async def _probe_url_internal(self, url: str, *, require_full: bool) -> AsyncImageProbe | None:
        if url in self.validation_cache:
            cached_probe = self.validation_cache[url]
            if cached_probe is None or not require_full or cached_probe.fully_validated:
                return cached_probe

        async def _request() -> tuple[AsyncImageProbe | None, bool]:
            return await self._request_probe(url, require_full=require_full)

        try:
            probe, cacheable = await async_retry_call(_request, retries=self.retries)
        except Exception:
            return None

        if cacheable:
            self.validation_cache[url] = probe
        return probe

    async def _request_probe(self, url: str, *, require_full: bool) -> tuple[AsyncImageProbe | None, bool]:
        if self._is_blocked_image_url(url):
            return None, True

        allow_partial = not require_full and self.probe_range_bytes > 0
        response = await self.http_client.get(
            url,
            headers=self._build_request_headers(url, allow_partial=allow_partial),
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
                    AsyncImageProbe(
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
                return await self._request_probe(url, require_full=True)
            return None, True

        width, height, image_format = decoded
        return (
            AsyncImageProbe(
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

    async def _pick_first_valid_url(
        self,
        ordered_urls: list[str],
        *,
        excluded_urls: set[str],
    ) -> str:
        picked = await self._pick_valid_urls(
            ordered_urls,
            excluded_urls=excluded_urls,
            limit=1,
        )
        return picked[0] if picked else ""

    async def _pick_valid_urls(
        self,
        ordered_urls: list[str],
        *,
        excluded_urls: set[str],
        limit: int,
    ) -> list[str]:
        if limit <= 0:
            return []

        picked: list[str] = []
        local_excluded = set(excluded_urls)
        for url in ordered_urls:
            normalized_url = normalize_storable_image_url(url)
            if not normalized_url or normalized_url in local_excluded:
                continue
            full_probe = await self._probe_url_internal(normalized_url, require_full=True)
            if full_probe is None:
                continue
            picked.append(full_probe.url)
            local_excluded.add(full_probe.url)
            if len(picked) >= limit:
                break
        return picked

    def _build_request_headers(self, url: str, *, allow_partial: bool) -> dict[str, str]:
        headers: dict[str, str] = {}
        referer = self._guess_referer(url)
        if referer:
            headers["Referer"] = referer
        if allow_partial:
            partial_bytes = max(self.probe_range_bytes, self.min_bytes)
            headers["Range"] = f"bytes=0-{partial_bytes - 1}"
        return headers

    def _resolve_response_size(self, response: httpx.Response, content: bytes) -> int:
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

    def _load_validation_cache(self) -> dict[str, AsyncImageProbe | None]:
        raw_cache = load_validation_cache(self.validation_cache_path)
        parsed: dict[str, AsyncImageProbe | None] = {}
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

    def _serialize_probe(self, probe: AsyncImageProbe | None) -> dict[str, object] | None:
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

    def _deserialize_probe(self, payload: dict[str, object] | None) -> AsyncImageProbe | None:
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
        return AsyncImageProbe(
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
