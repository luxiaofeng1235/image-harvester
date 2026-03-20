from __future__ import annotations

import json
import math
from typing import Iterable

from ai_goods_pipeline.constants import CATEGORY_PROFILES, CITY_POOL


def get_category_profile(category_id: int) -> dict[str, object]:
    if category_id not in CATEGORY_PROFILES:
        raise ValueError(f"Unsupported category_id: {category_id}")
    return CATEGORY_PROFILES[category_id]


def choose_candidate_count(remaining_count: int, batch_size: int) -> int:
    if remaining_count <= 0:
        return 0
    suggested = int(math.ceil(remaining_count * 1.3))
    return max(remaining_count, min(batch_size, suggested))


def select_history_guard_titles(
    history_titles: Iterable[str], keywords: list[str], limit: int = 60
) -> list[str]:
    keyword_text = " ".join(keywords).strip()
    if not keyword_text:
        return list(history_titles)[:limit]

    scored: list[tuple[int, str]] = []
    tokens = [token.strip().lower() for token in keywords if token.strip()]
    for title in history_titles:
        lower = title.lower()
        score = sum(1 for token in tokens if token in lower)
        if score > 0:
            scored.append((score, title))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [title for _, title in scored[:limit]]
    if len(selected) < limit:
        seen = set(selected)
        for title in history_titles:
            if title in seen:
                continue
            selected.append(title)
            if len(selected) >= limit:
                break
    return selected


def build_prompts(
    *,
    category_id: int,
    keywords: list[str],
    target_count: int,
    city_strategy: str,
    history_titles: list[str],
    system_prompt_base: str,
) -> tuple[str, str]:
    profile = get_category_profile(category_id)
    category_name = profile["name"]
    system_prompt = "\n".join(
        [
            system_prompt_base.strip(),
            "你必须严格返回 JSON 数组，不要返回 Markdown 代码块，不要返回解释说明。",
            "所有字段都必须能直接进入电商后台。",
            "禁止输出外链、联系方式、夸大承诺、官方授权、联名、疗效或无法验证的背书。",
            "必须主动避开历史标题中已经存在或高度相似的命名。",
            "优先生成可落库、可搜图、可销售的真实商品描述。",
            "不得虚构产地故事、非遗名录、地理标志、老字号、传承人、获奖、专利、机构合作、客户案例等无法核验信息。",
            "如果某个细节没有把握，必须改用保守且通用的真实描述，不要编造具体年份、机构名称、认证头衔或效果数据。",
        ]
    )

    schema = [
        {
            "title": "string",
            "subtitle": "string",
            "price": 99.00,
            "selling_points": ["卖点1", "卖点2", "卖点3"],
            "attrs": {"字段1": "值1", "字段2": "值2"},
            "image_keywords": ["关键词1", "关键词2"],
        }
    ]
    user_prompt = "\n".join(
        [
            f"当前任务分类: {category_id} - {category_name}",
            f"关键词: {', '.join(keywords)}",
            f"本轮需要生成的候选商品数量: {target_count}",
            f"城市策略: {city_strategy}",
            f"江苏城市池: {', '.join(CITY_POOL)}",
            "分类约束:",
            *[f"- {line}" for line in profile["profile"]],
            f"价格区间: {profile['price_min']} ~ {profile['price_normal_max']}，少量例外上限 {profile['price_hard_max']}",
            "命名和质量要求:",
            "- 必须优先生成贴近江苏本地市场、真实可售、可搜图的商品形态，不要脱离本土语境瞎编组合。",
            "- title 建议 14~28 个中文字符，不能空泛，不能堆砌营销词。",
            "- subtitle 要补充产地/工艺/风味/交付/场景信息，不能简单重复标题。",
            "- selling_points 固定输出 3~5 条字符串。",
            "- attrs 固定输出对象，value 只能是字符串或数字。",
            "- image_keywords 固定输出 1~3 个关键词，作为结构化标签保留，不能为空。",
            "- 城市、产地、工艺、材质、风味、交付方式之间必须彼此匹配，禁止生硬拼接。",
            "- 不要编造具体非遗名录、认证、老字号、官方合作、客户案例、传承人或大师背书。",
            "- 拿不准时使用保守表述，例如“地方风味”“传统工艺”“礼赠场景”“标准交付版”，不要写死无法核验的细节。",
            "历史标题黑名单（必须避开重复或高相似命名）:",
            json.dumps(history_titles, ensure_ascii=False),
            "输出 schema 示例:",
            json.dumps(schema, ensure_ascii=False),
            "请在输出前自行检查：分类是否正确、价格是否合理、字段是否完整、是否像真实商品、是否避开历史重复。",
            "只返回 JSON 数组。",
        ]
    )
    return system_prompt, user_prompt
