from __future__ import annotations

import json

from ai_goods_pipeline.prompts.description_styles import build_single_description_style_block


SEED_CATEGORY_HINTS = {
    126: [
        "这是人工已确认的地方特产/江苏特产种子商品，不要改写标题，只补全可销售文案。",
        "允许覆盖江苏不同城市的食品、熟食、茶品、酒水、干货、水果、礼盒等真实特产场景。",
        "subtitle 要补充产地、规格、风味、包装或送礼场景，不要重复标题。",
        "selling_points 优先写原料、风味、包装、工艺、食用或交付场景，不要写营养成分、功能效果、检测数据、百分比或无依据的“0添加”。",
        "attrs 至少包含 产地城市、规格、包装形式、适用场景。",
        "image_keywords 首个词优先写成“城市名 + 核心商品名”，方便搜图。",
    ],
    127: [
        "这是人工已确认的农副产品种子商品，不要改写标题，只补全可销售文案。",
        "subtitle 要补充产地、原料、净含量、储存方式或食用场景。",
        "selling_points 优先写鲜度、原料、规格、包装、储存与烹饪场景，不要写营养功效、检测指标、百分比、无依据的保鲜时长或功能承诺。",
        "attrs 至少包含 产地城市、规格、包装形式、储存方式。",
        "image_keywords 首个词优先写成“城市名 + 品类名”。",
    ],
    128: [
        "这是人工已确认的苏超纪念品种子商品，不要改写标题，只补全可销售文案。",
        "禁止补充官方授权、俱乐部联名、球员合作、赛事指定等高风险表述。",
        "subtitle 要补充材质、尺寸、便携性、使用场景中的至少一项。",
        "selling_points 优先写材质、结构、摆放/携带方式、场景和城市主题，不要写官方合作、限量编号、收藏升值等无法核验内容。",
        "attrs 至少包含 城市主题、材质、规格尺寸、适用场景。",
        "image_keywords 至少包含城市名、足球/苏超语义和具体载体名。",
    ],
    129: [
        "这是人工已确认的工艺产品种子商品，不要改写标题，只补全可销售文案。",
        "禁止臆造国家级非遗、大师监制、传承人、馆藏同款等无法核验的背书。",
        "subtitle 要补充工艺、材质、器型、用途或送礼场景中的至少一项。",
        "selling_points 优先写工艺、材质、器型、做工、用途和陈列场景，不要写紫外线阻隔率、材质百分比、收藏价值、检测数据或其他无法核验的硬指标。",
        "attrs 至少包含 工艺类别、核心材质、规格尺寸、适用场景。",
        "image_keywords 首个词优先写成“工艺名 + 材质 + 器物名”；有明确产地时再补城市名。",
        "可优先参考苏绣摆件、刺绣挂画、丝巾方巾、屏风、书签、折扇、紫砂壶等常见工艺产品方向。",
    ],
}


def get_seed_category_label(category_id: int) -> str:
    return {
        126: "江苏特产种子商品",
        127: "农副产品种子商品",
        128: "苏超纪念品种子商品",
        129: "工艺产品种子商品",
    }.get(category_id, f"{category_id} 类种子商品")


def build_seed_enrichment_prompts(
    *,
    category_id: int,
    title: str,
    price: float,
    system_prompt_base: str,
    style_seed: str = "",
) -> tuple[str, str]:
    category_label = get_seed_category_label(category_id)
    schema = [
        {
            "title": title,
            "subtitle": "string",
            "price": round(float(price), 2),
            "selling_points": ["卖点1", "卖点2", "卖点3"],
            "attrs": {"字段1": "值1", "字段2": "值2"},
            "image_keywords": ["关键词1", "关键词2"],
        }
    ]
    category_rules = SEED_CATEGORY_HINTS.get(category_id, [])
    style_rules = build_single_description_style_block(
        category_id=category_id,
        title=title,
        seed_text=style_seed or f"{category_id}:{title}:{round(float(price), 2)}",
    )
    system_prompt = "\n".join(
        [
            system_prompt_base.strip(),
            "你现在做的是“已有商品标题补全文案”任务，不是重新起标题。",
            "你必须严格返回 JSON 数组，不要返回 Markdown，不要返回解释说明。",
            "必须保留原始标题和价格，不得擅自改写标题，不得调整价格。",
            "不得虚构认证、官方背书、联名关系、非遗名录、传承人、大师头衔、销量数据、客户案例。",
            "若无法确认具体细节，使用保守且真实的通用表述。",
        ]
    )
    user_prompt = "\n".join(
        [
            f"任务类型: {category_label}",
            f"标题(必须原样保留): {title}",
            f"价格(必须保持一致): {round(float(price), 2)}",
            "补全要求:",
            "- 只补全 subtitle、selling_points、attrs、image_keywords。",
            "- title 必须与输入标题完全一致。",
            "- price 必须与输入价格完全一致。",
            "- subtitle 保持 1 句自然中文，补充具体信息，不要写成空泛广告语。",
            "- selling_points 固定输出 3~5 条，每条只表达一个明确卖点，避免句式高度重复。",
            "- 不要把每条商品都补成同一种模板句；可根据商品类型在产地、风味、原料、工艺、包装、食用方式、礼赠场景里选择 1~2 个最适合的重点来写。",
            "- 对 126/127 食品和农副产品，避免反复使用同一种“产地+规格+包装+场景”语序，尽量让不同商品的描述重心自然分散。",
            *style_rules,
            "- attrs 固定输出对象，value 只能是字符串或数字。",
            "- image_keywords 固定输出 1~3 个关键词，必须适合图片搜索。",
            "- 禁止输出功能性、保健性、疗效性、检测性、百分比、营养成分、添加剂、认证、官方背书等无法核验内容。",
            "- 禁止虚构具体指标，如紫外线阻隔率、营养含量、材质占比、保质期天数、收藏编号、销量奖项。",
            *[f"- {rule}" for rule in category_rules],
            "输出 schema 示例:",
            json.dumps(schema, ensure_ascii=False),
            "只返回 JSON 数组。",
        ]
    )
    return system_prompt, user_prompt
