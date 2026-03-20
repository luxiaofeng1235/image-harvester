from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEMO_SEARCH_DIRS = [
    PROJECT_DIR / "doc" / "prompt_demos",
    PROJECT_DIR / "docs" / "prompt_demos",
    PROJECT_DIR,
]
CATEGORY_DEMO_FILENAMES = {
    126: "江苏特产.txt",
    127: "农副产品.txt",
    128: "苏超纪念品.txt",
    129: "工艺产品.txt",
}


def _strip_price_suffix(text: str) -> str:
    return re.sub(r"\s+\d+(?:\.\d+)?\s*$", "", text.strip())


def _select_evenly_spaced(items: list[str], limit: int) -> list[str]:
    if limit <= 0 or not items:
        return []
    if len(items) <= limit:
        return items

    selected: list[str] = []
    seen: set[str] = set()
    step = (len(items) - 1) / max(1, limit - 1)
    for idx in range(limit):
        item = items[round(idx * step)]
        if item in seen:
            continue
        selected.append(item)
        seen.add(item)

    if len(selected) < limit:
        for item in items:
            if item in seen:
                continue
            selected.append(item)
            seen.add(item)
            if len(selected) >= limit:
                break
    return selected[:limit]


@lru_cache(maxsize=None)
def load_category_demo_titles(category_id: int) -> tuple[str, ...]:
    filename = CATEGORY_DEMO_FILENAMES.get(category_id)
    if not filename:
        return ()

    for base_dir in DEMO_SEARCH_DIRS:
        file_path = base_dir / filename
        if not file_path.exists():
            continue
        lines = [
            _strip_price_suffix(line)
            for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return tuple(line for line in lines if line)
    return ()


def get_category_demo_prompt_block(category_id: int, limit: int = 10) -> list[str]:
    demo_titles = list(load_category_demo_titles(category_id))
    if not demo_titles:
        return []

    sampled = _select_evenly_spaced(demo_titles, limit=limit)
    return [
        "标准样本参考（只参考命名结构、品类颗粒度、常见载体和价格带，禁止直接照抄标题）:",
        *[f"- {title}" for title in sampled],
        "- 你生成的新标题必须与这些样本保持同等真实度和颗粒度，但不能与样本相同或高度相似。",
    ]
