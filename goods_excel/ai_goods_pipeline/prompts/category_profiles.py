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


def _build_category_extra_rules(
    *, category_id: int, target_count: int, city_strategy: str
) -> list[str]:
    if category_id == 126:
        rules = [
            "126 专属硬约束:",
            "- attrs.产地城市 必须固定填写为 苏州。",
            "- title 或 subtitle 至少一处出现“苏州/姑苏/阳澄湖/洞庭山/昆山/太仓/常熟/张家港/吴江”等苏州稳定地域词。",
            "- 只生成可食用的苏州特产，优先苏式糕点、茶礼、蜜饯果脯、酱菜、熟食卤味、水产干货、节令伴手礼。",
            "- image_keywords 必须服务搜图，首个关键词优先写成“苏州地域词 + 核心商品名”，不要只写抽象词或营销词。",
            "- subtitle 要补充风味、原料、规格、包装或送礼场景信息，避免只写空泛修饰词。",
            "- 禁止写成其他城市特产，禁止混入工艺摆件、茶具香器、服务商品或无法判断来源的全国通货。",
            "126 可优先参考的安全方向:",
            "- 苏州碧螺春茶礼盒、苏式糕点礼盒、苏州蜜饯果脯、阳澄湖水产干货、苏州酱菜伴手礼。",
            "- 对不够确定的苏州特产，宁可采用保守的“苏式糕点/苏州风味熟食/苏州伴手礼”表达，也不要虚构老字号、地理标志或历史典故。",
        ]
        if target_count >= 8:
            rules.append("- 批量生成时优先拉开糕点、茶品、熟食、干货、蜜饯、礼盒等品类维度，不要只反复生成同一种茶礼盒。")
        return rules

    if category_id == 127:
        rules = [
            "127 专属硬约束:",
            f"- attrs.产地城市 必须填写以下城市之一: {', '.join(CITY_POOL)}。",
            "- 必须是可食用的农副产品或农副加工品，优先粮油杂粮、菌菇干货、水产干货、禽肉制品、酱菜调味品、果干蜜饯、茶品。",
            "- title 应体现“产地 + 品类 + 状态/包装”，不要只写空泛礼盒，不要只有故事感没有商品形态。",
            "- subtitle 要补充原料、风味、净含量、储存方式或适用场景中的至少一项。",
            "- image_keywords 首个关键词优先写成“城市名 + 品类名”，提高搜图匹配度。",
            "- 禁止输出工艺摆件、服务套餐、纯文创纪念品、纯进口跨境商品。",
        ]
        if city_strategy == "balanced" and target_count >= 8:
            rules.append("- 若批量生成，优先覆盖 6 个以上不同江苏城市，再考虑同城扩展第二个农副品。")
        return rules

    if category_id == 128:
        rules = [
            "128 专属硬约束:",
            f"- 城市主题必须来自以下江苏城市之一: {', '.join(CITY_POOL)}。",
            "- 每条商品都要同时出现城市元素与足球/苏超/助威/纪念语义，不能只是普通旅游纪念品。",
            "- 载体优先冰箱贴、钥匙扣、徽章、贴纸、水杯、帆布袋、挂件、亚克力摆件、小旗帜等低客单纪念品。",
            "- image_keywords 至少包含城市名、足球/苏超语义和具体载体名。",
            "- 禁止输出官方授权、俱乐部联名、球员姓名、logo 复刻、赛事官方视觉等高风险表述。",
        ]
        if city_strategy == "balanced" and target_count >= 8:
            rules.append("- 批量生成时尽量覆盖更多江苏城市，不要整批集中在南京、苏州两三个热点城市。")
        return rules

    if category_id == 129:
        rules = [
            "129 专属硬约束:",
            "- 工艺产品不等于非遗，拿不准时不要写非遗、大师、传承人，只写可确认的工艺、材质、器型和用途。",
            "- title 应体现“工艺/材质 + 器型/载体 + 使用或礼赠场景”，不能只剩空泛装饰词。",
            "- attrs 至少包含 工艺类别、核心材质、规格尺寸、适用场景，字段之间必须互相匹配。",
            "- image_keywords 首个关键词优先写成“工艺名 + 材质 + 器物名”或“城市名 + 工艺名 + 器物名”。",
            "- 禁止输出食品礼盒、苏超周边、服务套餐、纯装饰无工艺说明的普通摆件。",
            "129 可优先参考的安全方向:",
            "- 宜兴紫砂杯、苏绣团扇、南京云锦领带、扬州漆器摆盘、常州梳篦礼盒。",
        ]
        if target_count >= 8:
            rules.append("- 批量生成时至少覆盖 3 种以上工艺方向，不要全部集中在同一种材质或器型。")
        return rules

    return []


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
    extra_rules = _build_category_extra_rules(
        category_id=category_id,
        target_count=target_count,
        city_strategy=city_strategy,
    )
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
            *extra_rules,
            "历史标题黑名单（必须避开重复或高相似命名）:",
            json.dumps(history_titles, ensure_ascii=False),
            "输出 schema 示例:",
            json.dumps(schema, ensure_ascii=False),
            "请在输出前自行检查：分类是否正确、价格是否合理、字段是否完整、是否像真实商品、是否避开历史重复。",
            "只返回 JSON 数组。",
        ]
    )
    return system_prompt, user_prompt
