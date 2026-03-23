from __future__ import annotations

import hashlib


CATEGORY_DESCRIPTION_ANGLES = {
    126: [
        "从地方风味切入，先写口感或味型，再补包装与送礼场景",
        "从产地与原料切入，强调江苏城市来源与食材特点",
        "从规格与礼盒形态切入，突出适合走访、待客、伴手礼",
        "从节令食用场景切入，补充早餐、茶歇、家宴、年节等使用语境",
        "从产品特色切入，强调熟食、茶礼、糕点、干货的差异化卖点",
    ],
    127: [
        "从鲜度与原料切入，先写食材状态，再写烹饪或食用场景",
        "从产地与季节感切入，突出江苏城市、水域、田间来源",
        "从规格与储存切入，强调日常囤货、家常烹饪、冷藏保鲜等信息",
        "从口感与做法切入，补充清炒、煲汤、蒸煮、凉拌等使用方式",
        "从家庭采购视角切入，描述适合买菜、备菜、送长辈或日常餐桌",
    ],
    128: [
        "从城市主题和视觉识别切入，突出桌面摆放或观赛应援效果",
        "从材质与结构切入，强调便携、悬挂、陈列、收纳等使用体验",
        "从场景切入，写观赛、打卡、助威、伴手礼交换等具体语境",
        "从礼品属性切入，突出轻量、好送、好带、适合球迷收藏",
    ],
    129: [
        "从工艺与做工切入，先写工艺方法，再写成品观感与用途",
        "从材质与器型切入，突出原料、手感、线条、比例与陈列效果",
        "从使用场景切入，强调茶席、书房、家居、礼赠等实际语境",
        "从细节体验切入，描述触感、开合、摆放、把玩或观赏感受",
        "从中式审美气质切入，但保持电商商品口吻，不写空泛辞藻",
    ],
}

CATEGORY_DESCRIPTION_TONES = {
    126: ["偏生活化", "偏选品说明", "偏送礼导购", "偏风味介绍"],
    127: ["偏食材说明", "偏家常采购", "偏鲜货介绍", "偏烹饪场景"],
    128: ["偏文创导购", "偏场景化介绍", "偏球迷周边说明"],
    129: ["偏工艺说明", "偏器物导购", "偏中式生活方式"],
}


def build_batch_description_style_block(
    *,
    category_id: int,
    seed_text: str,
    target_count: int = 0,
) -> list[str]:
    angles = _rotate_items(CATEGORY_DESCRIPTION_ANGLES.get(category_id, []), seed_text)
    tones = _rotate_items(CATEGORY_DESCRIPTION_TONES.get(category_id, []), seed_text)
    lines = [
        "描述风格要求:",
        "- 本轮 subtitle 和 selling_points 要像人工编辑分别写出的商品说明，不要整批套同一套句式和语序。",
        "- 同一批次至少主动切换 3 种不同切入角度，不要每条都先写产地再写规格再写场景。",
    ]
    if angles:
        lines.append(f"- 本轮可轮换的切入角度参考: {'；'.join(angles[:4])}。")
        if target_count > 1:
            plan = [
                f"第{index + 1}条优先偏向{angles[index % len(angles)]}"
                for index in range(min(target_count, 6))
            ]
            lines.append(f"- 若本轮输出多条商品，请按顺序轮换描述重心: {'；'.join(plan)}。")
    if tones:
        lines.append(f"- 本轮可轮换的表达口吻参考: {'、'.join(tones[:3])}。")
    return lines


def build_single_description_style_block(
    *,
    category_id: int,
    title: str,
    seed_text: str,
) -> list[str]:
    base = f"{seed_text}:{title.strip()}"
    angles = _rotate_items(CATEGORY_DESCRIPTION_ANGLES.get(category_id, []), base)
    tones = _rotate_items(CATEGORY_DESCRIPTION_TONES.get(category_id, []), base)
    lines = [
        "- 这条商品的文案不要套通用模板句，保持像人工单独写的商品详情摘要。",
    ]
    if angles:
        lines.append(f"- 这条优先采用的描述切入角度: {angles[0]}。")
    if len(angles) > 1:
        lines.append(f"- 次优先可参考的补充角度: {angles[1]}。")
    if tones:
        lines.append(f"- 表达口吻建议: {tones[0]}。")
    return lines


def _rotate_items(items: list[str], seed_text: str) -> list[str]:
    if not items:
        return []
    digest = hashlib.md5(seed_text.encode('utf-8')).hexdigest()
    offset = int(digest[:8], 16) % len(items)
    return items[offset:] + items[:offset]
