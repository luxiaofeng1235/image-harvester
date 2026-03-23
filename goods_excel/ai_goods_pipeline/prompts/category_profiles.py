from __future__ import annotations

import json
import math
from typing import Iterable

from ai_goods_pipeline.constants import CATEGORY_PROFILES, CITY_POOL
from ai_goods_pipeline.prompts.demo_library import get_category_demo_prompt_block
from ai_goods_pipeline.prompts.description_styles import build_batch_description_style_block


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
            f"- attrs.产地城市 必须填写为以下江苏城市之一: {', '.join(CITY_POOL)}。",
            "- title 或 subtitle 至少一处出现明确江苏地域词，如 南京、苏州、扬州、无锡、徐州、淮安、盐城、镇江、宿迁、连云港、常州、泰州、南通。",
            "- 只生成可食用的江苏特产，优先熟食卤味、茶礼、酱菜、糖果糕点、肉脯、水产干货、酒水、节令礼盒、水果礼盒。",
            "- title 优先写成“核心商品词 + 1 个卖点热词”，例如“南京盐水鸭 真空熟食”“雨花茶 明前绿茶”，不要在 title 里堆规格、包装、场景和多重修饰词。",
            "- image_keywords 必须服务搜图，首个关键词优先写成“江苏城市名 + 核心商品名”，不要只写抽象词或营销词。",
            "- subtitle 要补充风味、原料、规格、包装或送礼场景信息，避免只写空泛修饰词。",
            "- 禁止写成其他省份特产，禁止混入工艺摆件、茶具香器、服务商品或无法判断来源的全国通货。",
            "126 可优先参考的安全方向:",
            "- 南京盐水鸭、桂花鸭、雨花茶，高邮双黄鸭蛋，靖江猪肉脯，扬州酱菜，阳澄湖大闸蟹，苏州碧螺春，太湖银鱼干，洋河蓝色经典，阳山水蜜桃。",
            "- 对不够确定的江苏特产，宁可采用保守的“江苏风味熟食/江苏特色糕点/江苏伴手礼/地方水产干货”表达，也不要虚构老字号、地理标志或历史典故。",
        ]
        if target_count >= 8:
            rules.append("- 批量生成时优先拉开茶品、熟食、酱菜、糖果糕点、干货、水产、酒水、水果礼盒等维度，不要只反复生成同一种鸭货或茶礼盒。")
        return rules

    if category_id == 127:
        rules = [
            "127 专属硬约束:",
            f"- attrs.产地城市 必须填写以下城市之一: {', '.join(CITY_POOL)}。",
            "- 必须是可食用的农副产品或农副加工品，优先时令蔬菜、水生蔬菜、鲜活水产、禽蛋禽肉、米面杂粮、海产干货、糖果甜酒、滋补食材。",
            "- title 优先写成“产地/品类主词 + 1 个状态或卖点热词”，例如“洪泽湖青虾 鲜活直发”“射阳大米 软糯清香”，不要写成长句。",
            "- subtitle 要补充原料、风味、净含量、储存方式或适用场景中的至少一项。",
            "- image_keywords 首个关键词优先写成“城市名 + 品类名”，提高搜图匹配度。",
            "- 禁止输出工艺摆件、服务套餐、纯文创纪念品、纯进口跨境商品。",
            "127 可优先参考的安全方向:",
            "- 苏州青、水芹、茭白、春笋、鸡头米、枇杷、杨梅、盐水鸭、草鸡、咸鸭蛋、大闸蟹、白虾、白鱼、文蛤、大米、花生米、甜酒酿、干百合。",
        ]
        if city_strategy == "balanced" and target_count >= 8:
            rules.append("- 若批量生成，优先覆盖 6 个以上不同江苏城市，再考虑同城扩展第二个农副品。")
        return rules

    if category_id == 128:
        rules = [
            "128 专属硬约束:",
            f"- 城市主题必须来自以下江苏城市之一: {', '.join(CITY_POOL)}。",
            "- 每条商品都要同时出现城市元素与足球/苏超/助威/纪念语义，不能只是普通旅游纪念品。",
            "- 载体优先车贴、冰箱贴、钥匙扣、徽章吧唧、贴纸、相框、水杯、帆布袋、挂件、亚克力摆件、迷你摆台、公仔等低客单纪念品。",
            "- title 优先写成“城市/IP主词 + 载体名 + 1 个纪念或应援热词”，不要在 title 里堆满场景、材质和包装。",
            "- image_keywords 至少包含城市名、足球/苏超语义和具体载体名。",
            "- 禁止输出官方授权、俱乐部联名、球员姓名、logo 复刻、赛事官方视觉等高风险表述。",
            "128 可优先参考的安全方向:",
            "- 队标磁吸车贴、城市限定冰箱贴、球迷应援徽章、公仔摆件、帆布包、钥匙扣、水杯、笔记本、桌面摆台、脸贴。",
        ]
        if city_strategy == "balanced" and target_count >= 8:
            rules.append("- 批量生成时尽量覆盖更多江苏城市，不要整批集中在南京、苏州两三个热点城市。")
        return rules

    if category_id == 129:
        rules = [
            "129 专属硬约束:",
            "- 工艺产品不强制要求江苏地域词，重点是工艺、材质、器型、载体和用途成立。",
            "- 工艺产品不等于非遗，拿不准时不要写非遗、大师、传承人，只写可确认的工艺、材质、器型和用途。",
            "- title 优先写成“工艺/材质 + 器型/载体 + 1 个卖点热词”，例如“原矿紫砂西施壶 手作款”“苏绣双面绣摆件 新中式”，不要把全部礼赠场景都堆进 title。",
            "- attrs 至少包含 工艺类别、核心材质、规格尺寸、适用场景，字段之间必须互相匹配。",
            "- image_keywords 首个关键词优先写成“工艺名 + 材质 + 器物名”；只有存在明确产地时再补城市名。",
            "- 禁止输出食品礼盒、苏超周边、服务套餐、纯装饰无工艺说明的普通摆件或空泛文创。",
            "129 可优先参考的安全方向:",
            "- 紫砂壶、西施壶、石瓢壶、提梁壶、秦权壶，苏绣摆件、挂画、屏风、团扇、书签、丝巾、围巾等。",
        ]
        if target_count >= 8:
            rules.append("- 批量生成时至少覆盖 3 种以上工艺方向，不要全部集中在同一种紫砂壶器型或同一种刺绣载体。")
        return rules

    return []


def _build_category_system_rules(category_id: int) -> list[str]:
    if category_id == 126:
        return [
            "126 类任务表示江苏特产，不是只生成苏州单城特产。",
        ]
    if category_id == 129:
        return [
            "129 类工艺产品不强制要求江苏地域词，允许生成工艺、材质、器型、用途成立的通用工艺礼品。",
        ]
    return []


def build_prompts(
    *,
    category_id: int,
    keywords: list[str],
    target_count: int,
    city_strategy: str,
    history_titles: list[str],
    system_prompt_base: str,
    style_seed: str = "",
) -> tuple[str, str]:
    profile = get_category_profile(category_id)
    category_name = profile["name"]
    system_rules = _build_category_system_rules(category_id)
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
            *system_rules,
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
    style_rules = build_batch_description_style_block(
        category_id=category_id,
        seed_text=style_seed or f"{category_id}:{','.join(keywords)}:{target_count}",
        target_count=target_count,
    )
    demo_block = get_category_demo_prompt_block(category_id, limit=10)
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
            "- title 建议控制在 8~18 个中文字符，优先使用“核心商品词 + 1 个卖点热词”的短标题结构，风格接近商品关键词/TDK，不要写成长句。",
            "- title 只放一个最关键卖点热词；规格、包装、送礼场景、更多修饰信息写入 subtitle 和 selling_points，不要继续堆在 title。",
            "- subtitle 要承接 2~4 个补充卖点，补充产地/工艺/风味/交付/场景信息，不能简单重复标题。",
            "- selling_points 固定输出 3~5 条字符串，每条只写一个明确卖点，避免整段堆砌和句式重复。",
            "- 同一批次不同商品的 subtitle 和 selling_points 不能反复套同一种句式模板，必须主动拉开表达重心，可以分别偏向产地、风味、原料、工艺、包装、食用方式、礼赠场景中的不同维度。",
            "- 对 126/127 食品类商品，不要把每条都写成“产地+原料+包装+场景”的同一语序；允许有的先写风味，有的先写规格，有的先写节令或吃法，但都要保持真实可售。",
            *style_rules,
            "- attrs 固定输出对象，value 只能是字符串或数字。",
            "- image_keywords 固定输出 1~3 个关键词，作为结构化标签保留，不能为空。",
            "- 城市、产地、工艺、材质、风味、交付方式之间必须彼此匹配，禁止生硬拼接。",
            "- 不要输出营养功效、功能承诺、检测数据、百分比、材质占比、保质期天数、官方授权、收藏升值等无法稳定核验的信息。",
            "- 不要编造具体非遗名录、认证、老字号、官方合作、客户案例、传承人或大师背书。",
            "- 拿不准时使用保守表述，例如“地方风味”“传统工艺”“礼赠场景”“标准交付版”，不要写死无法核验的细节。",
            *extra_rules,
            *demo_block,
            "历史标题黑名单（必须避开重复或高相似命名）:",
            json.dumps(history_titles, ensure_ascii=False),
            "输出 schema 示例:",
            json.dumps(schema, ensure_ascii=False),
            "请在输出前自行检查：分类是否正确、价格是否合理、字段是否完整、是否像真实商品、是否避开历史重复。",
            "只返回 JSON 数组。",
        ]
    )
    return system_prompt, user_prompt
