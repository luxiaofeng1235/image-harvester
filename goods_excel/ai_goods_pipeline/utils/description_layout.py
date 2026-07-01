from __future__ import annotations

import hashlib
from html import escape as html_escape
from html import unescape as html_unescape
import re
from typing import Any

from ai_goods_pipeline.utils.image_url import normalize_storable_image_url


LAYOUT_VARIANT_POOLS = {
    126: {
        "intro_labels": ["产品简介", "选品摘要", "商品说明", "风味介绍", "产品小结"],
        "points_labels": ["风味亮点", "推荐理由", "产品看点", "选品重点", "食用亮点"],
        "attrs_labels": ["规格信息", "基础信息", "规格参数", "产品信息"],
        "detail_labels": ["商品展示", "图文展示", "细节展示", "产品展示"],
    },
    127: {
        "intro_labels": ["产品简介", "商品说明", "选品摘要", "食材说明", "商品小结"],
        "points_labels": ["食材亮点", "产品看点", "食用参考", "选品重点", "产品优势"],
        "attrs_labels": ["规格与储存", "基础信息", "规格信息", "产品参数"],
        "detail_labels": ["商品展示", "图文展示", "细节展示", "产品展示"],
    },
    128: {
        "intro_labels": ["商品简介", "产品说明", "设计摘要", "使用说明"],
        "points_labels": ["设计亮点", "使用看点", "产品亮点", "选品重点"],
        "attrs_labels": ["产品信息", "规格参数", "基础参数", "产品规格"],
        "detail_labels": ["商品展示", "图文展示", "细节展示", "产品展示"],
    },
    129: {
        "intro_labels": ["商品简介", "产品说明", "作品摘要", "工艺说明", "选品小结"],
        "points_labels": ["工艺亮点", "选品看点", "细节亮点", "产品亮点", "工艺细节"],
        "attrs_labels": ["规格信息", "基础参数", "产品信息", "规格参数"],
        "detail_labels": ["商品展示", "图文展示", "细节展示", "产品展示"],
    },
}

INTRO_STYLES = ["inline", "block"]
POINT_STYLES = ["numbered", "bullet", "tagged", "lead"]
ATTR_STYLES = ["line", "paired"]
SECTION_ORDERS = [False, True]

ATTR_DISPLAY_ORDER = {
    126: ["产地城市", "规格", "包装形式", "适用场景"],
    127: ["产地城市", "规格", "包装形式", "储存方式"],
    128: ["城市主题", "材质", "规格尺寸", "适用场景"],
    129: ["工艺类别", "核心材质", "规格尺寸", "适用场景"],
}

# CSS class 名称（集中定义，方便前端调整时统一修改）
CSS_DESCRIPTION_CONTAINER = "product-description"
CSS_DETAIL_CONTAINER = "product-detail"


def build_description_html(
    *,
    title: str = "",
    category_id: int = 0,
    subtitle: str,
    selling_points: list[str],
    attrs: dict[str, Any],
    detail_images: list[str],
    variation_seed: str = "",
) -> str:
    intro = str(subtitle or "").strip()
    clean_points = [str(point).strip() for point in selling_points if str(point).strip()]
    clean_attrs = _normalize_attrs(attrs, category_id=category_id)
    clean_images = [
        normalize_storable_image_url(str(url).strip())
        for url in detail_images
        if normalize_storable_image_url(str(url).strip())
    ]
    variant = _choose_layout_variant(
        title=title,
        category_id=category_id,
        subtitle=subtitle,
        variation_seed=variation_seed,
    )

    sections = [f'<div class="{CSS_DESCRIPTION_CONTAINER}">']
    if intro:
        if variant["intro_style"] == "block":
            sections.append(f"  <p><strong>{html_escape(variant['intro_label'])}</strong></p>")
            sections.append(f"  <p>{html_escape(intro)}</p>")
        else:
            sections.append(
                f"  <p><strong>{html_escape(variant['intro_label'])}</strong>：{html_escape(intro)}</p>"
            )
    if variant["attrs_first"]:
        _append_attrs_sections(
            sections,
            clean_attrs,
            str(variant["attrs_label"]),
            str(variant["attrs_style"]),
        )
        _append_points_sections(sections, clean_points, str(variant["points_label"]), str(variant["point_style"]))
    else:
        _append_points_sections(sections, clean_points, str(variant["points_label"]), str(variant["point_style"]))
        _append_attrs_sections(
            sections,
            clean_attrs,
            str(variant["attrs_label"]),
            str(variant["attrs_style"]),
        )
    sections.append("</div>")

    if clean_images:
        sections.append(f'<div class="{CSS_DETAIL_CONTAINER}">')
        sections.append(f"  <p><strong>{html_escape(str(variant['detail_label']))}</strong></p>")
        for url in clean_images:
            sections.append(f'  <img src="{html_escape(url)}" />')
        sections.append("</div>")
    return "\n".join(sections)


def _normalize_attrs(attrs: dict[str, Any], *, category_id: int) -> list[tuple[str, str]]:
    ordered_keys = ATTR_DISPLAY_ORDER.get(category_id, [])
    normalized = [
        (str(key).strip(), str(value).strip())
        for key, value in attrs.items()
        if str(key).strip() and str(value).strip()
    ]
    if not ordered_keys:
        return normalized
    priority = {key: index for index, key in enumerate(ordered_keys)}
    return sorted(
        normalized,
        key=lambda item: (priority.get(item[0], len(priority)), item[0]),
    )


def _choose_layout_variant(
    *,
    title: str,
    category_id: int,
    subtitle: str = "",
    variation_seed: str = "",
) -> dict[str, Any]:
    pools = LAYOUT_VARIANT_POOLS.get(category_id) or LAYOUT_VARIANT_POOLS.get(126) or {}
    if not pools:
        return {
            "intro_label": "商品简介",
            "points_label": "核心亮点",
            "attrs_label": "规格信息",
            "detail_label": "商品展示",
            "intro_style": "inline",
            "point_style": "numbered",
            "attrs_style": "line",
            "attrs_first": False,
        }
    token = f"{variation_seed}:{category_id}:{title.strip()}:{subtitle.strip()}".encode("utf-8")
    digest = hashlib.md5(token).hexdigest()
    return {
        "intro_label": _pick_by_digest(pools["intro_labels"], digest[0:8]),
        "points_label": _pick_by_digest(pools["points_labels"], digest[8:16]),
        "attrs_label": _pick_by_digest(pools["attrs_labels"], digest[16:24]),
        "detail_label": _pick_by_digest(pools["detail_labels"], digest[24:32]),
        "intro_style": _pick_by_digest(INTRO_STYLES, digest[4:12]),
        "point_style": _pick_by_digest(POINT_STYLES, digest[12:20]),
        "attrs_style": _pick_by_digest(ATTR_STYLES, digest[20:28]),
        "attrs_first": _pick_by_digest(SECTION_ORDERS, digest[28:32]),
    }


def _pick_by_digest(options: list[Any], digest_chunk: str) -> Any:
    if not options:
        raise ValueError("options must not be empty")
    return options[int(digest_chunk, 16) % len(options)]


def _append_points_sections(
    sections: list[str],
    points: list[str],
    label: str,
    point_style: str,
) -> None:
    if not points:
        return
    sections.append(f"  <p><strong>{html_escape(label)}</strong></p>")
    for index, point in enumerate(points, 1):
        text = html_escape(point)
        if point_style == "bullet":
            sections.append(f"  <p>• {text}</p>")
        elif point_style == "tagged":
            sections.append(f"  <p><strong>亮点{index}</strong>：{text}</p>")
        elif point_style == "lead":
            sections.append(f"  <p><strong>其{_to_cn_index(index)}</strong>：{text}</p>")
        else:
            sections.append(f"  <p>{index}. {text}</p>")


def _append_attrs_sections(
    sections: list[str],
    attrs: list[tuple[str, str]],
    label: str,
    attrs_style: str,
) -> None:
    if not attrs:
        return
    sections.append(f"  <p><strong>{html_escape(label)}</strong></p>")
    if attrs_style == "paired":
        buffer: list[str] = []
        for key, value in attrs:
            buffer.append(f"{html_escape(key)}：{html_escape(value)}")
            if len(buffer) == 2:
                sections.append(f"  <p>{' / '.join(buffer)}</p>")
                buffer = []
        if buffer:
            sections.append(f"  <p>{' / '.join(buffer)}</p>")
        return
    for key, value in attrs:
        sections.append(f"  <p>{html_escape(key)}：{html_escape(value)}</p>")


def _to_cn_index(index: int) -> str:
    return {1: "一", 2: "二", 3: "三", 4: "四", 5: "五"}.get(index, str(index))


def parse_legacy_description(description: str) -> tuple[list[str], dict[str, str], list[str]]:
    text = str(description or "")
    selling_points = _extract_legacy_selling_points(text)
    attrs = _extract_legacy_attrs(text)
    detail_images = _extract_image_urls(text)
    return selling_points, attrs, detail_images


def _extract_legacy_selling_points(description: str) -> list[str]:
    match = re.search(r"<strong>商品亮点</strong>：(.+?)</p>", description, re.S)
    if not match:
        return []
    raw = _strip_html(match.group(1))
    parts = re.split(r"[；;]\s*", raw)
    return [item.strip() for item in parts if item.strip()]


def _extract_legacy_attrs(description: str) -> dict[str, str]:
    match = re.search(r"<strong>规格属性</strong>：(.+?)</p>", description, re.S)
    if not match:
        return {}
    raw = _strip_html(match.group(1))
    parts = re.split(r"[；;]\s*", raw)
    attrs: dict[str, str] = {}
    for item in parts:
        chunk = item.strip()
        if not chunk:
            continue
        if "：" in chunk:
            key, value = chunk.split("：", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                attrs[key] = value
        elif ":" in chunk:
            key, value = chunk.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                attrs[key] = value
    return attrs


def _extract_image_urls(description: str) -> list[str]:
    urls = re.findall(r'<img[^>]+src="([^"]+)"', description, re.I)
    return [html_unescape(url.strip()) for url in urls if url.strip()]


def _strip_html(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", "", value or "")
    return html_unescape(no_tags).strip()
