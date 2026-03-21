from __future__ import annotations

from html import escape as html_escape
from html import unescape as html_unescape
import re
from typing import Any


def build_description_html(
    *,
    subtitle: str,
    selling_points: list[str],
    attrs: dict[str, Any],
    detail_images: list[str],
) -> str:
    intro = str(subtitle or "").strip()
    clean_points = [str(point).strip() for point in selling_points if str(point).strip()]
    clean_attrs = [
        (str(key).strip(), str(value).strip())
        for key, value in attrs.items()
        if str(key).strip() and str(value).strip()
    ]
    clean_images = [str(url).strip() for url in detail_images if str(url).strip()]

    sections = ['<div class="product-description">']
    if intro:
        sections.append(f"  <p><strong>商品简介</strong>：{html_escape(intro)}</p>")
    if clean_points:
        sections.append("  <p><strong>核心亮点</strong></p>")
        for index, point in enumerate(clean_points, 1):
            sections.append(f"  <p>{index}. {html_escape(point)}</p>")
    if clean_attrs:
        sections.append("  <p><strong>规格信息</strong></p>")
        for key, value in clean_attrs:
            sections.append(f"  <p>{html_escape(key)}：{html_escape(value)}</p>")
    sections.append("</div>")

    if clean_images:
        sections.append('<div class="product-detail">')
        sections.append("  <p><strong>商品展示</strong></p>")
        for url in clean_images:
            sections.append(f'  <p><img src="{html_escape(url)}" /></p>')
        sections.append("</div>")
    return "\n".join(sections)


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
