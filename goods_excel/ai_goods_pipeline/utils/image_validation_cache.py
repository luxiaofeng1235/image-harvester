from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def load_validation_cache(path: Path | None) -> dict[str, dict[str, Any] | None]:
    if path is None or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(payload, dict):
        return {}

    cache: dict[str, dict[str, Any] | None] = {}
    for raw_url, raw_value in payload.items():
        url = str(raw_url or "").strip()
        if not url:
            continue
        if raw_value is None:
            cache[url] = None
            continue
        if isinstance(raw_value, dict):
            cache[url] = dict(raw_value)
    return cache


def save_validation_cache(
    path: Path | None,
    entries: dict[str, dict[str, Any] | None],
    *,
    max_entries: int,
) -> None:
    if path is None:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    merged = load_validation_cache(path)
    for raw_url, raw_value in entries.items():
        url = str(raw_url or "").strip()
        if not url:
            continue
        merged.pop(url, None)
        merged[url] = raw_value

    if max_entries > 0 and len(merged) > max_entries:
        merged = dict(list(merged.items())[-max_entries:])

    tmp_name = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as handle:
            tmp_name = handle.name
            json.dump(merged, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        Path(tmp_name).replace(path)
    finally:
        if tmp_name:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass
