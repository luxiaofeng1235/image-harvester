from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from ai_goods_pipeline.async_pipeline import AsyncAIGoodsPipeline
from ai_goods_pipeline.config import load_settings
from ai_goods_pipeline.pipeline import GenerationTask
from ai_goods_pipeline.prompts.category_profiles import get_category_profile
from ai_goods_pipeline.utils.batch_meta import normalize_batch_id
from ai_goods_pipeline.utils.logger import setup_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI 商品自动生成采集入库")
    parser.add_argument("--category-id", type=int)
    parser.add_argument("--keywords", type=str, help="逗号分隔关键词")
    parser.add_argument("--count", type=int, help="最终成功商品数量")
    parser.add_argument("--shop-id", type=int, default=0)
    parser.add_argument("--model", type=str, default="")
    parser.add_argument("--fallback-model", type=str, default="")
    parser.add_argument("--write-db", type=int, default=1)
    parser.add_argument("--dry-run", type=int, default=0)
    parser.add_argument("--export-excel", type=int, default=0)
    parser.add_argument("--city-strategy", type=str, default="balanced")
    parser.add_argument("--batch-id", type=str, default="")
    parser.add_argument("--check-runtime", type=int, default=0)
    return parser.parse_args()


async def amain() -> int:
    args = parse_args()
    settings = load_settings()
    logger, log_path, run_id = setup_logger(settings.logs_dir)
    batch_id = normalize_batch_id(args.batch_id, fallback=run_id)
    pipeline = AsyncAIGoodsPipeline(settings=settings, logger=logger, run_id=run_id, log_path=log_path)
    try:
        if args.check_runtime:
            print(
                json.dumps(
                    {
                        "run_id": run_id,
                        "batch_id": batch_id,
                        "runtime_status": await pipeline.image_client.runtime_status(),
                        "log": str(log_path),
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        if args.category_id is None:
            raise SystemExit("--category-id 不能为空")
        if args.count is None or args.count <= 0:
            raise SystemExit("--count 必须大于 0")
        if not args.keywords or not args.keywords.strip():
            raise SystemExit("--keywords 不能为空")

        keywords = [keyword.strip() for keyword in args.keywords.split(",") if keyword.strip()]
        if not keywords:
            raise SystemExit("--keywords 不能为空")

        profile = get_category_profile(args.category_id)
        task = GenerationTask(
            category_id=args.category_id,
            keywords=keywords,
            count=args.count,
            shop_id=args.shop_id,
            model=args.model or str(profile["default_model"]),
            fallback_model=args.fallback_model or str(profile["fallback_model"]),
            write_db=bool(args.write_db),
            dry_run=bool(args.dry_run),
            export_excel=bool(args.export_excel),
            city_strategy=args.city_strategy,
            batch_id=batch_id,
        )
        result = await pipeline.run(task)
        print(
            (
                f"run_id={result.run_id} batch_id={batch_id} requested={result.requested_count} "
                f"success={result.success_count} inserted={result.inserted_count} "
                f"failures={result.failure_count} "
                f"log={result.log_path} failures_log={result.failure_log_path} "
                f"report={result.report_path}"
            )
        )
        print("quality_report=" + json.dumps(result.quality_report, ensure_ascii=False))
    finally:
        await pipeline.close()
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    raise SystemExit(main())
