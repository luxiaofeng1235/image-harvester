from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
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
    parser.add_argument("--skip-images", type=int, default=0, help="1=只生成文案入库，不搜图不上传OSS")
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
            skip_images=bool(args.skip_images),  # Phase 1：先生成文案，不搜图
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

        # Phase 2：如果没开 skip-images，自动补图补详情
        if not args.skip_images and result.inserted_count > 0 and not args.dry_run:
            await _fill_images_for_batch(
                settings=settings, logger=logger, run_id=run_id,
                batch_id=batch_id, category_id=args.category_id,
                model=args.model or str(profile["default_model"]),
                concurrency=3,
            )
    finally:
        close_started_at = time.perf_counter()
        logger.info("amain finally: pipeline.close start")
        await pipeline.close()
        logger.info("amain finally: pipeline.close done duration=%.3fs", time.perf_counter() - close_started_at)
        current_task = asyncio.current_task()
        pending_tasks = [
            task
            for task in asyncio.all_tasks()
            if task is not current_task and not task.done()
        ]
        logger.info("amain finally: pending tasks before cleanup=%s", len(pending_tasks))
        if pending_tasks:
            for task in pending_tasks[:5]:
                logger.info("amain finally: pending task=%r", task)
            cleanup_started_at = time.perf_counter()
            for task in pending_tasks:
                task.cancel()
            done, still_pending = await asyncio.wait(pending_tasks, timeout=3.0)
            logger.info(
                "amain finally: pending cleanup done=%s remaining=%s duration=%.3fs",
                len(done),
                len(still_pending),
                time.perf_counter() - cleanup_started_at,
            )
    return 0


async def _fill_images_for_batch(
    *, settings, logger, run_id: str, batch_id: str,
    category_id: int, model: str, concurrency: int = 3,
) -> None:
    """Phase 2：从 enrich_seed_goods_from_db 调补图补详情逻辑。"""
    from ai_goods_pipeline.enrich_seed_goods_from_db import process_rows
    from ai_goods_pipeline.writers.async_db_writer import AsyncDBWriter

    db_writer = AsyncDBWriter(
        host=settings.db_host, port=settings.db_port,
        user=settings.db_user, password=settings.db_password,
        database=settings.db_name, charset=settings.db_charset,
        table=settings.db_table, pool_maxsize=max(2, concurrency + 1),
    )
    try:
        rows = await db_writer.fetch_goods_for_enrichment(
            category_id=category_id, limit=9999, missing_mode="both",
        )
        # 只处理当前 batch_id 的记录
        rows = [r for r in rows if str(r.get("batch_id") or "") == batch_id]
        if not rows:
            logger.info("Phase 2: no records found for batch_id=%s", batch_id)
            return

        logger.info("Phase 2 - Image fill: processing %s records for batch=%s", len(rows), batch_id)
        results = await process_rows(
            rows, settings=settings, model=model,
            concurrency=concurrency, dry_run=False,
            force_image_refresh=False, logger=logger,
            batch_id=batch_id, run_id=run_id,
        )
        ok = sum(1 for r in results if r.get("ok"))
        logger.info("Phase 2 done: %s/%s images filled", ok, len(rows))
    finally:
        await db_writer.close()


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    raise SystemExit(main())
