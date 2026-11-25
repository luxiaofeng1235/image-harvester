"""
============================================
图片客户端基类 - 同步/异步客户端共享逻辑
============================================
提取同步和异步图片客户端的公共逻辑，避免代码重复。
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ai_goods_pipeline.constants import (
    CITY_POOL,
    CRAFT_KEYWORDS,
    FOOD_KEYWORDS,
    FOOTBALL_KEYWORDS,
    IMAGE_BING_META_BLOCKLIST,
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
from ai_goods_pipeline.utils.image_url import normalize_storable_image_url
from ai_goods_pipeline.utils.image_validation_cache import (
    load_validation_cache,
    save_validation_cache,
)


@dataclass(slots=True)
class SearchRelevanceContext:
    """搜索相关性上下文，用于过滤不相关的图片结果。"""
    category_id: int
    query: str
    query_terms: tuple[str, ...]
    expected_cities: tuple[str, ...]


class BaseImageClient:
    """图片客户端基类，包含同步和异步客户端的共享逻辑。"""

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
        self.validation_cache: dict[str, Any] = self._load_validation_cache()
        self.resolution_pool_cache: OrderedDict[str, Any] = OrderedDict()

    # ─── URL 过滤 ───

    def _is_blocked_image_url(self, url: str) -> bool:
        """检查 URL 是否被屏蔽（含 @、黑名单域名/路径）。"""
        # 拒绝含 @ 的 URL（不规范的外链）
        if "@" in url:
            return True
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        if any(token in host for token in IMAGE_URL_HOST_BLOCKLIST):
            return True
        if any(token in path for token in IMAGE_URL_PATH_BLOCKLIST):
            return True
        return False

    def _extract_baidu_candidate_urls(self, item: dict[str, str]) -> list[str]:
        """从百度搜索结果中提取候选图片 URL。"""
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

    # ─── 搜索上下文构建 ───

    def _build_search_context(
        self,
        *,
        title: str,
        image_keywords: list[str],
        category_id: int,
        keywords: list[str],
    ) -> SearchRelevanceContext:
        """构建搜索相关性上下文。"""
        parts = [title] + list(image_keywords or []) + list(keywords or [])
        query_terms = tuple(self._extract_query_terms(parts))
        expected_cities = tuple(self._extract_expected_cities(parts, category_id))
        return SearchRelevanceContext(
            category_id=category_id,
            query=title,
            query_terms=query_terms,
            expected_cities=expected_cities,
        )

    def _build_queries(
        self,
        title: str,
        image_keywords: list[str],
        keywords: list[str],
        category_id: int,
    ) -> list[str]:
        """构建搜索关键词列表。"""
        queries: list[str] = []
        seen: set[str] = set()

        # 1. 标题 + 城市
        city_query = self._build_city_query(title, category_id)
        if city_query and city_query not in seen:
            queries.append(city_query)
            seen.add(city_query)

        # 2. 完整标题
        if title not in seen:
            queries.append(title)
            seen.add(title)

        # 3. 图片关键词
        for kw in image_keywords or []:
            kw = str(kw or "").strip()
            if kw and kw not in seen:
                queries.append(kw)
                seen.add(kw)

        return queries[:IMAGE_QUERY_LIMIT]

    def _build_city_query(self, title: str, category_id: int) -> str:
        """构建带城市的搜索词。"""
        cities = self._extract_expected_cities([title], category_id)
        if not cities:
            return title
        city = cities[0]
        # 提取标题中的核心词（去掉城市名）
        core = title.replace(city, "").strip()
        if not core:
            return title
        return f"{city} {core}"

    def _extract_expected_cities(self, parts: list[str], category_id: int) -> list[str]:
        """从文本中提取期望的城市名。"""
        source_text = " ".join(str(part).lower() for part in parts if part)
        matches: list[str] = []
        for city in CITY_POOL + SUZHOU_HINTS:
            city_lower = city.lower()
            if city_lower in source_text and city_lower not in matches:
                matches.append(city_lower)
        return matches

    def _extract_query_terms(self, parts: list[str]) -> list[str]:
        """从文本中提取搜索关键词。"""
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
                if chunk not in seen and chunk not in IMAGE_QUERY_TERM_BLOCKLIST:
                    terms.append(chunk)
                    seen.add(chunk)

        return terms[:IMAGE_TITLE_QUERY_MAX_LEN]

    # ─── 相关性检查 ───

    def _is_blocked_search_result(self, item: dict[str, str]) -> bool:
        """检查搜索结果是否被屏蔽。"""
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
        """检查搜索结果是否与查询相关。"""
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
        # 当没有足够的元数据做判断时，保留结果而不是过滤
        if not city_hits and query_hits == 0 and football_hits == 0 and craft_hits == 0 and food_hits == 0:
            return True
        return False

    def _build_meta_text(self, item: dict[str, str]) -> str:
        """构建搜索结果的元文本。"""
        parts = [
            str(item.get("title") or "").strip().lower(),
            str(item.get("desc") or "").strip().lower(),
            str(item.get("source_page") or "").strip().lower(),
            str(item.get("image_url") or "").strip().lower(),
            str(item.get("thumbnail_url") or "").strip().lower(),
            str(item.get("data_imgurl") or "").strip().lower(),
        ]
        return " ".join(part for part in parts if part)

    def _count_keyword_hits(self, text: str, keywords: tuple[str, ...] | list[str]) -> int:
        """计算文本中命中关键词的数量。"""
        text_lower = text.lower()
        return sum(1 for kw in keywords if kw.lower() in text_lower)

    def _matches_expected_city(self, meta_text: str, context: SearchRelevanceContext) -> bool:
        """检查元文本是否匹配期望城市。"""
        if not context.expected_cities:
            return True
        return any(city in meta_text for city in context.expected_cities)

    # ─── 验证缓存管理 ───

    def _load_validation_cache(self) -> dict[str, Any]:
        """加载验证缓存。"""
        if not self.validation_cache_path:
            return {}
        return load_validation_cache(self.validation_cache_path)

    def _save_validation_cache(self) -> None:
        """保存验证缓存。"""
        if not self.validation_cache_path:
            return
        if self.validation_cache_max_entries > 0:
            items = list(self.validation_cache.items())[-self.validation_cache_max_entries:]
            self.validation_cache = dict(items)
        save_validation_cache(self.validation_cache_path, self.validation_cache)

    def _get_cached_probe(self, url: str) -> tuple[Any, bool]:
        """获取缓存的 probe 结果。"""
        if url not in self.validation_cache:
            return None, False
        cached = self.validation_cache[url]
        if cached is None:
            return None, True
        return cached, True

    def _set_cached_probe(self, url: str, probe: Any) -> None:
        """设置缓存的 probe 结果。"""
        self.validation_cache[url] = probe
        self._save_validation_cache()

    def _evict_resolution_pool_cache(self) -> None:
        """淘汰最旧的解析池缓存。"""
        if len(self.resolution_pool_cache) <= 500:
            return
        keys_to_remove = list(self.resolution_pool_cache.keys())[:100]
        for key in keys_to_remove:
            del self.resolution_pool_cache[key]

    # ─── Probe 序列化 ───

    def _serialize_probe(self, probe: Any) -> dict[str, Any] | None:
        """序列化 probe 对象。"""
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

    def _deserialize_probe(self, payload: dict[str, Any] | None) -> Any:
        """反序列化 probe 对象（子类需实现）。"""
        raise NotImplementedError

    # ─── 图片选择 ───

    def _confirm_selected_images(self, valid_images: list[Any]) -> list[Any]:
        """确认选中的图片（同步版本）。"""
        return valid_images
