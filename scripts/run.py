import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import threading

from src.pipeline.dedupe import DedupeIndex
from src.pipeline.downloader import DownloadResult, download_and_filter
from src.pipeline.filters import parse_size_rules
from src.pipeline.stats import RunStats
from src.sources import BaiduImageSource
from src.utils.config import deep_merge, load_and_merge_config
from src.utils.logging import setup_logging


def _split_list(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


_SIZE_PART_RE = re.compile(r"^[wh](>=|<=|>|<|=)\\d{1,5}$")


def _split_size_args(entries: List[str]) -> List[str]:
    rules: List[str] = []
    for entry in entries:
        text = entry.strip()
        if not text:
            continue
        if "," in text:
            parts = [p.strip() for p in text.split(",") if p.strip()]
            if parts and all(_SIZE_PART_RE.match(p) for p in parts):
                rules.append(text)
            else:
                rules.extend(parts)
        else:
            rules.append(text)
    return rules

def _resolve_sources(cfg: Dict, cli_sources: List[str]) -> List[str]:
    if cli_sources:
        return cli_sources
    sources_cfg = cfg.get("sources")
    if isinstance(sources_cfg, list):
        return sources_cfg
    if isinstance(sources_cfg, dict):
        return [name for name, meta in sources_cfg.items() if meta.get("enabled", True)]
    return ["baidu"]


def _resolve_rate_limit(cfg: Dict, source_name: str) -> float:
    rl = cfg.get("rate_limit", 0.0)
    if isinstance(rl, dict):
        return float(rl.get(source_name, rl.get("default", 0.0)))
    return float(rl)


def _resolve_timeout(cfg: Dict) -> float:
    return float(cfg.get("timeout", 10))


def _resolve_fetch_overage(cfg: Dict) -> int:
    return int(cfg.get("fetch_overage", 2))


def _validate_required(cfg: Dict) -> None:
    missing = []
    for key in ("keywords", "out", "count"):
        if not cfg.get(key):
            missing.append(key)
    if missing:
        raise ValueError(f"Missing required parameters: {', '.join(missing)}")


def _build_sources(cfg: Dict, sources: List[str]) -> Dict[str, object]:
    timeout = _resolve_timeout(cfg)
    blocked = cfg.get("blocked_domains", [])
    out: Dict[str, object] = {}
    for name in sources:
        if name == "baidu":
            out[name] = BaiduImageSource(timeout=timeout, rate_limit=_resolve_rate_limit(cfg, name), blocked_domains=blocked)
    return out


def _merge_cli(cfg: Dict, args: argparse.Namespace) -> Dict:
    cli = {}
    if args.keywords:
        cli["keywords"] = _split_list(args.keywords)
    if args.out:
        cli["out"] = args.out
    if args.count is not None:
        cli["count"] = args.count
    if args.sizes:
        cli["sizes"] = _split_size_args(args.sizes)
    if args.date:
        cli["date"] = args.date
    if args.sources:
        cli["sources"] = _split_list(args.sources)
    if args.concurrency is not None:
        cli["concurrency"] = args.concurrency
    if args.rate_limit is not None:
        cli["rate_limit"] = args.rate_limit
    if args.blocked_domains:
        cli["blocked_domains"] = _split_list(args.blocked_domains)
    if args.strict_order:
        cli["strict_order"] = True
    return deep_merge(cfg, cli)


def main(argv: List[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    default_config = root / "config" / "default.yaml"

    parser = argparse.ArgumentParser(description="Multi-source image harvester (Baidu only for now)")
    parser.add_argument("--config", default=str(default_config))
    parser.add_argument("--keywords", help="Comma-separated keywords")
    parser.add_argument("--out", help="Output directory")
    parser.add_argument("--count", type=int, help="Target download count per keyword")
    parser.add_argument("--sizes", action="append", help="Size rules, comma-separated or repeated")
    parser.add_argument("--date", help="Override date (YYYY-MM-DD)")
    parser.add_argument("--sources", help="Comma-separated sources")
    parser.add_argument("--concurrency", type=int, help="Download concurrency")
    parser.add_argument("--rate-limit", type=float, help="Per-source rate limit seconds")
    parser.add_argument("--blocked-domains", help="Comma-separated blocked domains")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--strict-order", action="store_true", help="Download in source order (skip 404, keep order)")

    args = parser.parse_args(argv)

    cfg = load_and_merge_config(Path(args.config))
    cfg = _merge_cli(cfg, args)
    _validate_required(cfg)

    keywords = cfg.get("keywords", [])
    out_root = Path(cfg["out"]).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    date_str = cfg.get("date") or datetime.now().strftime("%Y%m%d")

    log_dir = Path(cfg.get("log_dir") or (root / "logs"))
    log_name = datetime.now().strftime("run-%Y%m%d-%H%M%S.log")
    level = "DEBUG" if args.debug else cfg.get("log_level", "INFO")
    logger = setup_logging(log_dir, level=level, name="image-harvester", log_file=log_dir / log_name)

    logger.info("Starting run: keywords=%s, out=%s, count=%s", keywords, out_root, cfg["count"])

    sources = _resolve_sources(cfg, args.sources.split(",") if args.sources else [])
    source_objs = _build_sources(cfg, sources)

    size_rules = parse_size_rules(cfg.get("sizes") or cfg.get("size_rules"))

    stats = RunStats()
    dedupe = DedupeIndex()

    fetch_overage = _resolve_fetch_overage(cfg)
    concurrency = int(cfg.get("concurrency", 8))
    strict_order = bool(cfg.get("strict_order", False))

    settings = {
        "timeout": _resolve_timeout(cfg),
        "probe_bytes": int(cfg.get("probe_bytes", 262144)),
        "hash_algo": cfg.get("hash_algo", "sha1"),
        "dedupe": cfg.get("dedupe", {"url": True, "content_hash": True}),
        "blocked_domains": cfg.get("blocked_domains", []),
        "date_str": date_str,
        "temp_dir": cfg.get("temp_dir"),
    }

    for keyword in keywords:
        urls: List[str] = []
        for name, source in source_objs.items():
            try:
                limit = int(cfg["count"]) * fetch_overage
                urls.extend(source.fetch_urls(keyword, limit))
            except Exception as e:
                logger.warning("source=%s keyword=%s fetch_failed=%s", name, keyword, e)
                stats.add_reason(f"fetch_failed:{name}")

        # URL de-dup
        seen = set()
        deduped = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        urls = deduped

        if not urls:
            logger.warning("keyword=%s no_urls_found", keyword)
            continue

        stats.total_urls += len(urls)

        logger.info("keyword=%s urls=%s", keyword, len(urls))

        saved_for_keyword = 0

        if strict_order:
            for url in urls:
                result = download_and_filter(url, out_root, keyword, size_rules, settings, dedupe)
                if result.status == "saved":
                    stats.saved += 1
                    saved_for_keyword += 1
                    if saved_for_keyword >= int(cfg["count"]):
                        break
                elif result.status == "filtered":
                    stats.filtered += 1
                    stats.add_reason(result.reason or "filtered")
                elif result.status == "duplicate":
                    stats.duplicates += 1
                    stats.add_reason(result.reason or "duplicate")
                elif result.status == "blocked":
                    stats.blocked += 1
                    stats.add_reason(result.reason or "blocked")
                else:
                    stats.errors += 1
                    stats.add_reason(result.reason or "error")
        else:
            stop_event = threading.Event()

            def _task(u: str):
                if stop_event.is_set():
                    return DownloadResult(status="skipped", url=u, reason="target_reached")
                return download_and_filter(u, out_root, keyword, size_rules, settings, dedupe)

            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = [pool.submit(_task, url) for url in urls]
                for future in as_completed(futures):
                    result = future.result()
                    if result.status == "saved":
                        stats.saved += 1
                        saved_for_keyword += 1
                        if saved_for_keyword >= int(cfg["count"]):
                            stop_event.set()
                            for f in futures:
                                f.cancel()
                    elif result.status == "filtered":
                        stats.filtered += 1
                        stats.add_reason(result.reason or "filtered")
                    elif result.status == "duplicate":
                        stats.duplicates += 1
                        stats.add_reason(result.reason or "duplicate")
                    elif result.status == "blocked":
                        stats.blocked += 1
                        stats.add_reason(result.reason or "blocked")
                    elif result.status == "skipped":
                        continue
                    else:
                        stats.errors += 1
                        stats.add_reason(result.reason or "error")

    summary = stats.as_dict()
    summary.update({
        "keywords": keywords,
        "date": date_str,
        "out": str(out_root),
    })

    summary_path = out_root / date_str / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Run complete. saved=%s filtered=%s duplicates=%s errors=%s", stats.saved, stats.filtered, stats.duplicates, stats.errors)
    logger.info("Summary written: %s", summary_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
