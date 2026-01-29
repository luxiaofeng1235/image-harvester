import re
from typing import Dict, List, Optional, Tuple, Union

Rule = Dict[str, Union[str, float, int]]

EXACT_RE = re.compile(r"^(\d{2,5})x(\d{2,5})$")
RATIO_RE = re.compile(r"^ratio=(\d+(?:\.\d+)?)(?:\u00b1|\+/-)(\d+(?:\.\d+)?)%$")
RANGE_RE = re.compile(r"^(w|h)(>=|<=|>|<|=)(\d{1,5})$")


def parse_size_rule(rule: Union[str, dict]) -> Rule:
    if isinstance(rule, dict):
        return rule
    rule = rule.strip()
    m = EXACT_RE.match(rule)
    if m:
        return {"type": "exact", "width": int(m.group(1)), "height": int(m.group(2))}

    m = RATIO_RE.match(rule)
    if m:
        return {
            "type": "ratio",
            "ratio": float(m.group(1)),
            "tolerance_percent": float(m.group(2)),
        }

    m = RANGE_RE.match(rule)
    if m:
        return {"type": "range", "ops": [(m.group(1), m.group(2), int(m.group(3)))]}

    if "," in rule:
        parts = [p.strip() for p in rule.split(",") if p.strip()]
        ops = []
        for part in parts:
            m = RANGE_RE.match(part)
            if not m:
                continue
            ops.append((m.group(1), m.group(2), int(m.group(3))))
        if ops:
            return {"type": "range", "ops": ops}

    raise ValueError(f"Invalid size rule: {rule}")


def parse_size_rules(rules: Optional[List[Union[str, dict]]]) -> List[Rule]:
    if not rules:
        return []
    return [parse_size_rule(r) for r in rules]


def _check_op(value: int, op: str, target: int) -> bool:
    if op == ">=":
        return value >= target
    if op == "<=":
        return value <= target
    if op == ">":
        return value > target
    if op == "<":
        return value < target
    if op == "=":
        return value == target
    return False


def match_size(width: int, height: int, rules: List[Rule]) -> bool:
    if not rules:
        return True
    for rule in rules:
        if rule.get("type") == "exact":
            if width == int(rule["width"]) and height == int(rule["height"]):
                return True
        elif rule.get("type") == "ratio":
            ratio = width / height if height else 0
            target = float(rule["ratio"])
            tol = float(rule.get("tolerance_percent", 0)) / 100.0
            if target == 0:
                continue
            if abs(ratio - target) <= target * tol:
                return True
        elif rule.get("type") == "range":
            ops: List[Tuple[str, str, int]] = rule.get("ops", [])  # type: ignore
            ok = True
            for axis, op, target in ops:
                val = width if axis == "w" else height
                if not _check_op(val, op, target):
                    ok = False
                    break
            if ok:
                return True
    return False


def size_bucket(width: int, height: int) -> str:
    return f"{width}-{height}"
