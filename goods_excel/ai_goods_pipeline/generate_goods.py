from __future__ import annotations

import argparse
import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from ai_goods_pipeline.config import load_settings
from ai_goods_pipeline.pipeline import AIGoodsPipeline, GenerationTask
from ai_goods_pipeline.prompts.category_profiles import get_category_profile
from ai_goods_pipeline.utils.logger import setup_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI 商品自动生成采集入库")
    parser.add_argument("--category-id", type=int, required=True)
    parser.add_argument("--keywords", type=str, required=True, help="逗号分隔关键词")
    parser.add_argument("--count", type=int, required=True, help="最终成功商品数量")
    parser.add_argument("--model", type=str, default="")
    parser.add_argument("--fallback-model", type=str, default="")
    parser.add_argument("--write-db", type=int, default=1)
    parser.add_argument("--dry-run", type=int, default=0)
    parser.add_argument("--export-excel", type=int, default=0)
    parser.add_argument("--city-strategy", type=str, default="balanced")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.count <= 0:
        raise SystemExit("--count 必须大于 0")

    keywords = [keyword.strip() for keyword in args.keywords.split(",") if keyword.strip()]
    if not keywords:
        raise SystemExit("--keywords 不能为空")

    settings = load_settings()
    logger, log_path, run_id = setup_logger(settings.logs_dir)
    profile = get_category_profile(args.category_id)
    task = GenerationTask(
        category_id=args.category_id,
        keywords=keywords,
        count=args.count,
        model=args.model or str(profile["default_model"]),
        fallback_model=args.fallback_model or str(profile["fallback_model"]),
        write_db=bool(args.write_db),
        dry_run=bool(args.dry_run),
        export_excel=bool(args.export_excel),
        city_strategy=args.city_strategy,
    )
    pipeline = AIGoodsPipeline(settings=settings, logger=logger, run_id=run_id, log_path=log_path)
    result = pipeline.run(task)
    print(
        (
            f"run_id={result.run_id} requested={result.requested_count} "
            f"success={result.success_count} inserted={result.inserted_count} "
            f"failures={result.failure_count} "
            f"log={result.log_path} failures_log={result.failure_log_path}"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
