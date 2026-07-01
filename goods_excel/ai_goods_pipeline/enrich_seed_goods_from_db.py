from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any


if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from ai_goods_pipeline.clients.async_image_client import AsyncImageClient
from ai_goods_pipeline.clients.async_oss_client import AsyncOSSImageUploader
from ai_goods_pipeline.clients.async_qwen_client import (
    AsyncQwenClient,
    AsyncQwenClientError,
    AsyncQwenParseError,
)
from ai_goods_pipeline.config import load_settings
from ai_goods_pipeline.utils.batch_meta import normalize_batch_id
from ai_goods_pipeline.prompts.seed_enrichment import build_seed_enrichment_prompts
from ai_goods_pipeline.utils.description_layout import build_description_html
from ai_goods_pipeline.utils.logger import setup_logger
from ai_goods_pipeline.utils.text import normalize_title
from ai_goods_pipeline.writers.async_db_writer import AsyncDBWriter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Async enrich seed goods from DB with Qwen and image crawling."
    )
    parser.add_argument("--category-id", type=int, required=True)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--ids", type=str, default="")
    parser.add_argument(
        "--missing-mode",
        type=str,
        default="either",
        choices=["either", "image", "description", "both", "none"],
        help="Which missing fields should be queried from DB.",
    )
    parser.add_argument("--model", type=str, default="")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--dry-run", type=int, default=0)
    parser.add_argument("--force-image-refresh", type=int, default=0)
    parser.add_argument("--batch-id", type=str, default="")
    return parser.parse_args()


def parse_ids(raw_ids: str) -> list[int]:
    ids: list[int] = []
    for chunk in (raw_ids or "").split(","):
        text = chunk.strip()
        if not text:
            continue
        ids.append(int(text))
    return ids


def sanitize_enrichment_item(
    raw_item: dict[str, Any], *, expected_title: str, expected_price: float
) -> dict[str, Any]:
    item = raw_item if isinstance(raw_item, dict) else {}
    title = str(item.get("title") or "").strip()
    price_raw = item.get("price")
    try:
        price = round(float(price_raw), 2)
    except Exception:
        price = 0.0
    subtitle = str(item.get("subtitle") or "").strip()
    selling_points = [
        str(point).strip()
        for point in (item.get("selling_points") or [])
        if str(point).strip()
    ]
    attrs_raw = item.get("attrs") or {}
    attrs = (
        {
            str(key).strip(): str(value).strip()
            for key, value in attrs_raw.items()
            if str(key).strip() and str(value).strip()
        }
        if isinstance(attrs_raw, dict)
        else {}
    )
    image_keywords = [
        str(keyword).strip()
        for keyword in (item.get("image_keywords") or [])
        if str(keyword).strip()
    ]

    if title != expected_title:
        raise ValueError("title_changed")
    if round(float(expected_price), 2) != price:
        raise ValueError("price_changed")
    if not subtitle:
        raise ValueError("empty_subtitle")
    if len(selling_points) < 3:
        raise ValueError("insufficient_selling_points")
    if len(attrs) < 3:
        raise ValueError("insufficient_attrs")
    if not image_keywords:
        raise ValueError("empty_image_keywords")

    return {
        "title": title,
        "price": price,
        "subtitle": subtitle,
        "selling_points": selling_points[:5],
        "attrs": attrs,
        "image_keywords": image_keywords[:3],
    }


def build_image_reuse_key(*, category_id: int, title: str, image_keywords: list[str]) -> str:
    for seed in [*image_keywords, title]:
        normalized = normalize_title(str(seed or "").strip())
        if normalized:
            return f"{category_id}:{normalized}"
    return f"{category_id}:"


async def maybe_upload_images(
    *,
    main_image: str,
    detail_images: list[str],
    dry_run: bool,
    oss_uploader: AsyncOSSImageUploader | None,
) -> tuple[str, list[str], list[str]]:
    if dry_run or oss_uploader is None:
        return main_image, detail_images, []

    warnings: list[str] = []
    main_task = (
        oss_uploader.upload_url(main_image)
        if str(main_image or "").strip()
        else asyncio.sleep(0, result="")
    )
    detail_task = (
        oss_uploader.upload_urls(detail_images, force_upload=True)
        if detail_images
        else asyncio.sleep(0, result=[])
    )
    uploaded_main, uploaded_details = await asyncio.gather(
        main_task,
        detail_task,
        return_exceptions=True,
    )

    final_main = main_image
    final_details = detail_images
    if isinstance(uploaded_main, Exception):
        warnings.append(f"main_image_upload_failed:{uploaded_main}")
        final_main = ""
    else:
        final_main = str(uploaded_main or "").strip()

    if isinstance(uploaded_details, Exception):
        warnings.append(f"detail_images_upload_failed:{uploaded_details}")
        final_details = []
    else:
        final_details = list(uploaded_details)

    return final_main, final_details, warnings


async def process_one_row(
    *,
    row: dict[str, Any],
    settings,
    model: str,
    dry_run: bool,
    force_image_refresh: bool,
    qwen_client: AsyncQwenClient,
    image_client: AsyncImageClient,
    db_writer: AsyncDBWriter,
    oss_uploader: AsyncOSSImageUploader | None,
    batch_id: str,
    run_id: str,
) -> dict[str, Any]:
    row_id = int(row["id"])
    title = str(row["goods_name"] or "").strip()
    price = float(row["price"])
    category_id = int(row["category_id"])
    existing_sub_title = str(row.get("sub_title") or "").strip()
    existing_image = str(row.get("image") or "").strip()
    existing_description = str(row.get("description") or "").strip()

    need_image = force_image_refresh or not existing_image
    need_description = not existing_description
    need_subtitle = not existing_sub_title
    started_at = time.perf_counter()

    qwen_payload = None
    final_sub_title = existing_sub_title
    final_description = existing_description
    final_image = existing_image
    detail_images: list[str] = []
    source_queries: list[str] = []
    warnings: list[str] = []

    if need_image or need_description or need_subtitle:
        if force_image_refresh and need_image and not need_description and not need_subtitle:
            qwen_payload = {"image_keywords": [title]}
        else:
            system_prompt, user_prompt = build_seed_enrichment_prompts(
                category_id=category_id,
                title=title,
                price=price,
                system_prompt_base=settings.qwen_system_prompt,
                style_seed=f"{run_id}:{batch_id}:{row_id}",
            )
            generation = await qwen_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
            )
            if not generation.items:
                raise ValueError("empty_qwen_items")
            qwen_payload = sanitize_enrichment_item(
                generation.items[0],
                expected_title=title,
                expected_price=price,
            )
            if need_subtitle:
                final_sub_title = qwen_payload["subtitle"]

    if need_image or need_description:
        if qwen_payload is None:
            raise ValueError("missing_qwen_payload_for_image_or_description")
        resolved_main_image = ""
        try:
            image_result = await image_client.resolve_images(
                title=title,
                image_keywords=qwen_payload["image_keywords"],
                category_id=category_id,
                keywords=[title],
                reuse_key=build_image_reuse_key(
                    category_id=category_id,
                    title=title,
                    image_keywords=list(qwen_payload["image_keywords"] or []),
                ),
            )
            source_queries = image_result.source_queries
            resolved_main_image = str(image_result.main_image or "").strip()
            detail_images = list(image_result.detail_images or [])
            if resolved_main_image or detail_images:
                uploaded_main_image, detail_images, upload_warnings = await maybe_upload_images(
                    main_image=resolved_main_image,
                    detail_images=detail_images,
                    dry_run=dry_run,
                    oss_uploader=oss_uploader,
                )
                warnings.extend(upload_warnings)
                if need_image and uploaded_main_image:
                    final_image = uploaded_main_image
            elif need_image and not final_image:
                warnings.append("no_valid_main_image")
        except Exception as exc:
            warnings.append(f"image_stage_failed:{exc}")
            detail_images = []

        if need_description:
            final_description = build_description_html(
                title=title,
                category_id=category_id,
                subtitle=qwen_payload["subtitle"],
                selling_points=qwen_payload["selling_points"],
                attrs=qwen_payload["attrs"],
                detail_images=detail_images,
                variation_seed=f"{run_id}:{batch_id}:{row_id}",
            )

    update_payload = {
        "sub_title": final_sub_title,
        "image": final_image,
        "description": final_description,
        "last_batch_id": normalize_batch_id(batch_id, fallback=batch_id),
    }
    if not dry_run:
        await db_writer.update_goods_enrichment(goods_id=row_id, **update_payload)

    return {
        "id": row_id,
        "title": title,
        "ok": True,
        "updated": not dry_run,
        "duration_seconds": round(time.perf_counter() - started_at, 3),
        "source_queries": source_queries,
        "warnings": warnings,
        "preview": update_payload if dry_run else {},
    }


async def process_rows(
    rows: list[dict[str, Any]],
    *,
    settings,
    model: str,
    concurrency: int,
    dry_run: bool,
    force_image_refresh: bool,
    logger,
    batch_id: str,
    run_id: str,
    db_writer: AsyncDBWriter | None = None,
    qwen_client: AsyncQwenClient | None = None,
    image_client: AsyncImageClient | None = None,
    oss_uploader: AsyncOSSImageUploader | None = None,
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(max(1, concurrency))

    # 复用传入的客户端，避免每次新建连接池
    use_qwen = qwen_client if qwen_client is not None else AsyncQwenClient(
        open_url=settings.qwen_open_url,
        api_key=settings.qwen_key,
        temperature=settings.qwen_temperature,
        max_tokens=settings.qwen_max_tokens,
    )
    use_image = image_client if image_client is not None else AsyncImageClient(
        timeout=settings.image_timeout,
        retries=settings.image_retry,
        min_bytes=settings.image_min_bytes,
        allow_gif_as_main=settings.image_allow_gif_as_main,
        enable_clip_rerank=settings.image_enable_clip_rerank,
        clip_model_name=settings.image_clip_model,
        clip_min_score=settings.image_clip_min_score,
        clip_max_candidates=settings.image_clip_max_candidates,
        clip_category_ids=settings.image_clip_category_ids,
        probe_range_bytes=settings.image_probe_range_bytes,
        validation_cache_path=settings.image_validation_cache_path,
        validation_cache_max_entries=settings.image_validation_cache_max_entries,
    )
    _qwen_owned = qwen_client is None
    _image_owned = image_client is None
    if db_writer is None:
        db_writer = AsyncDBWriter(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            charset=settings.db_charset,
            table=settings.db_table,
            pool_maxsize=max(2, concurrency + 1),
        )
        _db_writer_owned = True
    else:
        _db_writer_owned = False
    use_oss = oss_uploader if oss_uploader is not None else (
        AsyncOSSImageUploader(
            enabled=settings.oss_enabled,
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            bucket_name=settings.oss_bucket,
            endpoint=settings.oss_endpoint,
            view_domain=settings.oss_view_domain,
            prefix=settings.oss_prefix,
            object_acl=settings.oss_object_acl,
            timeout=settings.image_timeout,
            max_concurrency=max(2, concurrency * 2),
        )
        if settings.oss_enabled
        else None
    )

    async def _runner(row: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            started_at = time.perf_counter()
            try:
                result = await process_one_row(
                    row=row,
                    settings=settings,
                    model=model,
                    dry_run=dry_run,
                    force_image_refresh=force_image_refresh,
                    qwen_client=use_qwen,
                    image_client=use_image,
                    db_writer=db_writer,
                    oss_uploader=use_oss,
                    batch_id=batch_id,
                    run_id=run_id,
                )
                logger.info(
                    "Processed seed goods id=%s ok=%s updated=%s duration=%.2fs title=%s",
                    result["id"],
                    result["ok"],
                    result["updated"],
                    result["duration_seconds"],
                    result["title"],
                )
                if result.get("warnings"):
                    logger.warning(
                        "Processed seed goods warnings id=%s title=%s warnings=%s",
                        result["id"],
                        result["title"],
                        "; ".join(str(item) for item in result["warnings"]),
                    )
                return result
            except (AsyncQwenClientError, AsyncQwenParseError, ValueError) as exc:
                logger.warning(
                    "Process seed goods failed id=%s title=%s error=%s",
                    row["id"],
                    row["goods_name"],
                    exc,
                )
                return {
                    "id": int(row["id"]),
                    "title": str(row["goods_name"] or "").strip(),
                    "ok": False,
                    "updated": False,
                    "duration_seconds": round(time.perf_counter() - started_at, 3),
                    "error": str(exc),
                }
            except Exception as exc:
                logger.exception(
                    "Process seed goods unexpected failure id=%s title=%s",
                    row["id"],
                    row["goods_name"],
                )
                return {
                    "id": int(row["id"]),
                    "title": str(row["goods_name"] or "").strip(),
                    "ok": False,
                    "updated": False,
                    "duration_seconds": round(time.perf_counter() - started_at, 3),
                    "error": str(exc),
                }

    try:
        return await asyncio.gather(*[_runner(row) for row in rows])
    finally:
        if _qwen_owned:
            await use_qwen.close()
        if _image_owned:
            await use_image.close()
        if _db_writer_owned:
            await db_writer.close()
        if _qwen_owned or _image_owned:
            # 只有自有客户端才需要关 oss_uploader（因为没用预建的）
            if oss_uploader is not None:
                await oss_uploader.close()
        _oss_owned = oss_uploader is None and settings.oss_enabled
        if _oss_owned and use_oss is not None:
            await use_oss.close()


def build_summary(
    *,
    category_id: int,
    model: str,
    dry_run: bool,
    force_image_refresh: bool,
    rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    started_at: float,
    concurrency: int,
) -> dict[str, Any]:
    success_count = sum(1 for item in results if item.get("ok"))
    updated_count = sum(1 for item in results if item.get("updated"))
    failed_items = [item for item in results if not item.get("ok")]
    return {
        "category_id": category_id,
        "model": model,
        "dry_run": dry_run,
        "force_image_refresh": force_image_refresh,
        "concurrency": concurrency,
        "selected_count": len(rows),
        "success_count": success_count,
        "updated_count": updated_count,
        "failure_count": len(failed_items),
        "total_duration_seconds": round(time.perf_counter() - started_at, 3),
        "results": results,
    }


async def amain() -> int:
    args = parse_args()
    if args.limit <= 0:
        raise SystemExit("--limit must be > 0")

    settings = load_settings()
    logger, log_path, run_id = setup_logger(settings.logs_dir)
    batch_id = normalize_batch_id(args.batch_id, fallback=run_id)
    db_writer = AsyncDBWriter(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset=settings.db_charset,
        table=settings.db_table,
        pool_maxsize=max(2, args.concurrency + 1),
    )
    try:
        ids = parse_ids(args.ids)
        rows = await db_writer.fetch_goods_for_enrichment(
            category_id=args.category_id,
            limit=args.limit,
            missing_mode=args.missing_mode,
            ids=ids or None,
        )
    except Exception:
        await db_writer.close()
        raise

    if not rows:
        await db_writer.close()
        print("selected=0 processed=0 updated=0 failed=0")
        return 0

    model = args.model or settings.qwen_model_default
    logger.info(
        "Start async seed enrichment: category=%s selected=%s missing_mode=%s concurrency=%s dry_run=%s model=%s",
        args.category_id,
        len(rows),
        args.missing_mode,
        args.concurrency,
        bool(args.dry_run),
        model,
    )
    started_at = time.perf_counter()
    try:
        results = await process_rows(
            rows,
            settings=settings,
            model=model,
            concurrency=args.concurrency,
            dry_run=bool(args.dry_run),
            force_image_refresh=bool(args.force_image_refresh),
            logger=logger,
            batch_id=batch_id,
            run_id=run_id,
            db_writer=db_writer,
        )
    finally:
        await db_writer.close()
    summary = build_summary(
        category_id=args.category_id,
        model=model,
        dry_run=bool(args.dry_run),
        force_image_refresh=bool(args.force_image_refresh),
        rows=rows,
        results=results,
        started_at=started_at,
        concurrency=args.concurrency,
    )
    print(
        (
            f"selected={summary['selected_count']} success={summary['success_count']} "
            f"updated={summary['updated_count']} failed={summary['failure_count']} "
            f"log={log_path} run_id={run_id} batch_id={batch_id}"
        )
    )
    print("summary=" + json.dumps(summary, ensure_ascii=False))
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    raise SystemExit(main())
