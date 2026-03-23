from __future__ import annotations

import re
from typing import Iterable


BATCH_ID_MAX_LEN = 32
SOURCE_NOTE_MAX_LEN = 255


def normalize_batch_id(value: str, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        text = str(fallback or "").strip()
    text = re.sub(r"[^0-9A-Za-z_-]+", "_", text)
    return text[:BATCH_ID_MAX_LEN]


def build_source_note(parts: Iterable[str]) -> str:
    text = " | ".join(str(part).strip() for part in parts if str(part).strip())
    return text[:SOURCE_NOTE_MAX_LEN]
