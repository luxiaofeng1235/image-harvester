import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency
    yaml = None


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML not installed, cannot read YAML config")
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported config file type: {path}")


def _split_env_list(value: str) -> list:
    return [item.strip() for item in value.split(",") if item.strip()]


def apply_env_overrides(cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Simple env overrides for common top-level keys
    mapping = {
        "IMG_KEYWORDS": ("keywords", _split_env_list),
        "IMG_OUT": ("out", str),
        "IMG_COUNT": ("count", int),
        "IMG_SOURCES": ("sources", _split_env_list),
        "IMG_CONCURRENCY": ("concurrency", int),
        "IMG_RATE_LIMIT": ("rate_limit", float),
        "IMG_SIZES": ("sizes", _split_env_list),
        "IMG_DATE": ("date", str),
        "IMG_BLOCKED_DOMAINS": ("blocked_domains", _split_env_list),
    }

    out = dict(cfg)
    for env_key, (cfg_key, cast) in mapping.items():
        if env_key in os.environ and os.environ[env_key] != "":
            out[cfg_key] = cast(os.environ[env_key])

    return out


def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_and_merge_config(path: Optional[Path]) -> Dict[str, Any]:
    base = {}
    if path:
        base = load_config(path)
    env = apply_env_overrides(base)
    return deep_merge(base, env)
