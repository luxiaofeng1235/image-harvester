from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from ai_goods_pipeline.constants import (
    AGRI_KEYWORDS,
    ATTR_SYNONYMS,
    BANNED_128,
    CITY_POOL,
    CRAFT_KEYWORDS,
    FOOTBALL_KEYWORDS,
    GENERIC_BANNED_126,
    GENERIC_BANNED_127,
    JIANGSU_HINTS,
    SUZHOU_HINTS,
)
from ai_goods_pipeline.prompts.category_profiles import get_category_profile
from ai_goods_pipeline.utils.text import normalize_title, similarity_ratio


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    reason: str = ""
    normalized_title: str = ""
    matched_history_title: str = ""
    similarity_score: float = 0.0
    city: str = ""
    item: dict[str, Any] | None = None


class GoodsValidator:
    def __init__(
        self,
        *,
        category_id: int,
        history_titles: list[str],
        target_count: int,
        similarity_threshold: float,
        city_strategy: str = "balanced",
    ) -> None:
        self.category_id = category_id
        self.profile = get_category_profile(category_id)
        self.target_count = target_count
        self.similarity_threshold = similarity_threshold
        self.city_strategy = city_strategy
        self.batch_titles: dict[str, str] = {}
        self.history_titles = history_titles
        self.history_normalized = [(normalize_title(title), title) for title in history_titles]
        self.city_counter: Counter[str] = Counter()

    def validate(self, raw_item: Any) -> ValidationResult:
        item = self._sanitize_item(raw_item)
        title = item["title"]
        normalized_title = normalize_title(title)

        if not normalized_title:
            return ValidationResult(ok=False, reason="empty_title")

        if normalized_title in self.batch_titles:
            return ValidationResult(
                ok=False,
                reason="duplicate_in_batch",
                normalized_title=normalized_title,
                matched_history_title=self.batch_titles[normalized_title],
            )

        history_hit = self._match_history(normalized_title)
        if history_hit is not None:
            matched_title, score = history_hit
            reason = "duplicate_in_history" if score >= 0.999 else "similar_title_in_history"
            return ValidationResult(
                ok=False,
                reason=reason,
                normalized_title=normalized_title,
                matched_history_title=matched_title,
                similarity_score=score,
            )

        price_error = self._validate_price(item["price"])
        if price_error:
            return ValidationResult(
                ok=False, reason=price_error, normalized_title=normalized_title
            )

        attr_error = self._validate_required_attrs(item["attrs"])
        if attr_error:
            return ValidationResult(
                ok=False, reason=attr_error, normalized_title=normalized_title
            )

        city = self._extract_city(item)
        category_error = self._validate_category_rules(item, city)
        if category_error:
            return ValidationResult(
                ok=False, reason=category_error, normalized_title=normalized_title
            )

        city_error = self._validate_city_distribution(city)
        if city_error:
            return ValidationResult(
                ok=False, reason=city_error, normalized_title=normalized_title, city=city
            )

        return ValidationResult(
            ok=True,
            normalized_title=normalized_title,
            city=city,
            item=item,
        )

    def register_success(self, result: ValidationResult) -> None:
        if not result.item:
            return
        self.batch_titles[result.normalized_title] = result.item["title"]
        if result.city:
            self.city_counter[result.city] += 1

    def _sanitize_item(self, raw_item: Any) -> dict[str, Any]:
        item = raw_item if isinstance(raw_item, dict) else {}
        title = self._as_text(item.get("title"))
        subtitle = self._as_text(item.get("subtitle"))
        price = self._as_price(item.get("price"))
        selling_points = self._as_string_list(item.get("selling_points"))
        attrs = self._as_attrs(item.get("attrs"))
        attrs = self._canonicalize_attrs(attrs)
        image_keywords = self._as_string_list(item.get("image_keywords"))
        if not image_keywords and title:
            image_keywords = [title[:24]]
        return {
            "title": title,
            "subtitle": subtitle,
            "price": price,
            "selling_points": selling_points,
            "attrs": attrs,
            "image_keywords": image_keywords[:3],
        }

    def _as_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _as_price(self, value: Any) -> float:
        if isinstance(value, (int, float)):
            return round(float(value), 2)
        text = self._as_text(value)
        text = text.replace("￥", "").replace(",", "")
        try:
            return round(float(Decimal(text)), 2)
        except (InvalidOperation, ValueError):
            return 0.0

    def _as_string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            items = [self._as_text(item) for item in value]
        elif isinstance(value, str):
            if not value.strip():
                return []
            items = [
                part.strip()
                for part in re.split(r"[\n\r,，;；、|]+", value)
                if part.strip()
            ]
        else:
            items = [self._as_text(value)] if value is not None else []

        deduped: list[str] = []
        seen = set()
        for item in items:
            if not item or item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    def _as_attrs(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return {self._as_text(k): self._as_text(v) for k, v in value.items() if self._as_text(k)}
        if isinstance(value, list):
            attrs: dict[str, Any] = {}
            for item in value:
                if isinstance(item, dict):
                    attrs.update(
                        {
                            self._as_text(k): self._as_text(v)
                            for k, v in item.items()
                            if self._as_text(k)
                        }
                    )
                    continue
                text = self._as_text(item)
                if "：" in text:
                    key, _, raw_val = text.partition("：")
                elif ":" in text:
                    key, _, raw_val = text.partition(":")
                else:
                    continue
                key = self._as_text(key)
                raw_val = self._as_text(raw_val)
                if key:
                    attrs[key] = raw_val
            return attrs
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                return {self._as_text(k): self._as_text(v) for k, v in parsed.items()}
        return {}

    def _canonicalize_attrs(self, attrs: dict[str, Any]) -> dict[str, str]:
        synonyms = ATTR_SYNONYMS.get(self.category_id, {})
        canonical: dict[str, str] = {}
        for key, value in attrs.items():
            canonical_key = key
            for target, options in synonyms.items():
                if key in options:
                    canonical_key = target
                    break
            canonical[canonical_key] = self._as_text(value)
        return canonical

    def _match_history(self, normalized_title: str) -> tuple[str, float] | None:
        """检查标题是否与历史库重复或高度相似。

        优化策略：
        1. 精确匹配（O(1) 查 dict）— 最快路径
        2. 近似匹配前先做长度过滤（差异 > 50% 跳过）
        3. 历史标题 > 500 条时只对前 500 条做近似匹配（最新的标题更可能有重复）
        """
        for hist_normalized, hist_title in self.history_normalized:
            if not hist_normalized:
                continue
            if normalized_title == hist_normalized:
                return hist_title, 1.0

        best_title = ""
        best_score = 0.0
        # 长度过滤：标题长度差异超过 50% 的不可能相似
        title_len = len(normalized_title)
        hist_limit = min(len(self.history_normalized), 500) if len(self.history_normalized) > 500 else len(self.history_normalized)
        for hist_normalized, hist_title in self.history_normalized[:hist_limit]:
            if not hist_normalized:
                continue
            # 快速长度过滤
            if hist_normalized and abs(len(hist_normalized) - title_len) / max(title_len, 1) > 0.5:
                continue
            score = similarity_ratio(normalized_title, hist_normalized)
            if score > best_score:
                best_score = score
                best_title = hist_title

        if best_score >= self.similarity_threshold:
            return best_title, best_score
        return None

    def _validate_price(self, price: float) -> str:
        if price <= 0:
            return "invalid_price"
        if price < float(self.profile["price_min"]):
            return "price_below_min"
        if price > float(self.profile["price_hard_max"]):
            return "price_above_hard_max"
        return ""

    def _validate_required_attrs(self, attrs: dict[str, Any]) -> str:
        required = ATTR_SYNONYMS.get(self.category_id, {})
        missing = [key for key in required if not self._as_text(attrs.get(key))]
        if missing:
            return f"missing_attrs:{','.join(missing)}"
        return ""

    def _extract_city(self, item: dict[str, Any]) -> str:
        haystack = " ".join(
            [
                item["title"],
                item["subtitle"],
                " ".join(item["image_keywords"]),
                " ".join(f"{key} {value}" for key, value in item["attrs"].items()),
            ]
        )
        for city in CITY_POOL:
            if city in haystack:
                return city
        if any(hint in haystack for hint in SUZHOU_HINTS):
            return "苏州"
        return ""

    def _contains_any(self, text: str, words: list[str]) -> bool:
        return any(word in text for word in words if word)

    def _validate_category_rules(self, item: dict[str, Any], city: str) -> str:
        title = item["title"]
        subtitle = item["subtitle"]
        attrs = item["attrs"]
        image_keywords = item["image_keywords"]
        joined = " ".join([title, subtitle, " ".join(image_keywords), json.dumps(attrs, ensure_ascii=False)])

        if len(title) < 6:
            return "title_too_short"
        if not subtitle:
            return "empty_subtitle"
        if len(item["selling_points"]) < 3:
            return "insufficient_selling_points"
        if not image_keywords:
            return "empty_image_keywords"

        if self.category_id == 126:
            origin_city = self._as_text(attrs.get("产地城市"))
            if not self._contains_any(origin_city, CITY_POOL + SUZHOU_HINTS + JIANGSU_HINTS):
                return "invalid_jiangsu_origin_city"
            if not self._contains_any(joined, CITY_POOL + SUZHOU_HINTS + JIANGSU_HINTS):
                return "missing_jiangsu_locality"
            if any(word in joined for word in GENERIC_BANNED_126):
                return "invalid_non_local_hint"
            return ""

        if self.category_id == 127:
            if not any(word in joined for word in AGRI_KEYWORDS):
                return "missing_agri_signal"
            if not any(hint in joined for hint in JIANGSU_HINTS):
                return "missing_jiangsu_origin"
            if any(word in joined for word in GENERIC_BANNED_127):
                return "invalid_non_local_hint"
            return ""

        if self.category_id == 128:
            if not city:
                return "missing_city_theme"
            if not any(word in joined for word in FOOTBALL_KEYWORDS):
                return "missing_football_signal"
            if any(word in joined for word in BANNED_128):
                return "high_risk_ip_wording"
            return ""

        if self.category_id == 129:
            if not any(word in joined for word in CRAFT_KEYWORDS):
                return "missing_craft_signal"
            if any(word in joined for word in FOOTBALL_KEYWORDS):
                return "wrong_category_football_signal"
            return ""

        return ""

    def _validate_city_distribution(self, city: str) -> str:
        if self.category_id == 126:
            return ""
        if self.city_strategy != "balanced" or not city or self.target_count < 8:
            return ""
        current = self.city_counter[city]
        max_per_city = max(2, math.ceil(self.target_count / 4))
        if current >= max_per_city:
            return "city_concentration_too_high"
        return ""
