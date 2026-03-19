from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

try:
    from rapidfuzz.fuzz import ratio as rapidfuzz_ratio
except Exception:  # pragma: no cover - graceful fallback
    rapidfuzz_ratio = None


def normalize_title(text: str) -> str:
    text = (text or "").strip().lower()
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"[\s\-_,.;:，。；：、!！?？'\"“”‘’（）()\[\]{}<>《》/\\|]+", "", text)
    return text


def similarity_ratio(left: str, right: str) -> float:
    if rapidfuzz_ratio is not None:
        return rapidfuzz_ratio(left, right) / 100.0
    return SequenceMatcher(None, left, right).ratio()


def extract_json_array_payload(raw_text: str) -> list[dict[str, Any]]:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("empty_response")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("json_array_not_found")

    payload = text[start : end + 1]
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError("payload_is_not_array")
    normalized: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized

