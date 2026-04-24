from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

from ai_goods_pipeline.clients.async_image_client import AsyncImageClient
from ai_goods_pipeline.clients.async_oss_client import AsyncOSSImageUploader
from ai_goods_pipeline.clients.async_qwen_client import (
    AsyncQwenClient,
    AsyncQwenClientError,
    AsyncQwenGenerationResult,
    AsyncQwenParseError,
)
from ai_goods_pipeline.config import Settings
from ai_goods_pipeline.enums.source_types import SOURCE_AI_GENERATE
from ai_goods_pipeline.pipeline import AIGoodsPipeline, GenerationTask, PipelineResult
from ai_goods_pipeline.prompts.category_profiles import (
    build_prompts,
    choose_candidate_count,
    get_category_profile,
    select_history_guard_titles,
)
from ai_goods_pipeline.utils.batch_meta import build_source_note, normalize_batch_id
from ai_goods_pipeline.utils.image_url import normalize_storable_image_url
from ai_goods_pipeline.utils.text import normalize_title
from ai_goods_pipeline.validators.goods_validator import GoodsValidator, ValidationResult
from ai_goods_pipeline.writers.async_db_writer import AsyncDBWriter


class AsyncAIGoodsPipeline(AIGoodsPipeline):
    def __init__(self, *, settings: Settings, logger, run_id: str, log_path: Path) -> None:
        self.settings = settings
        self.logger = logger
        self.run_id = run_id
        self.log_path = log_path
        self.failure_log_path = settings.logs_dir / f"failures_{run_id}.jsonl"
        self.report_path = settings.logs_dir / f"report_{run_id}.json"
        self.qwen_client = AsyncQwenClient(
            open_url=settings.qwen_open_url,
            api_key=settings.qwen_key,
            temperature=settings.qwen_temperature,
            max_tokens=settings.qwen_max_tokens,
        )
        self.image_client = AsyncImageClient(
            timeout=settings.image_timeout,
            retries=settings.image_retry,
            min_bytes=settings.image_min_bytes,
            allow_gif_as_main=settings.image_allow_gif_as_main,
            enable_bing=settings.image_enable_bing,
            enable_clip_rerank=settings.image_enable_clip_rerank,
            clip_model_name=settings.image_clip_model,
            clip_min_score=settings.image_clip_min_score,
            clip_max_candidates=settings.image_clip_max_candidates,
            clip_category_ids=settings.image_clip_category_ids,
            probe_range_bytes=settings.image_probe_range_bytes,
            validation_cache_path=settings.image_validation_cache_path,
            validation_cache_max_entries=settings.image_validation_cache_max_entries,
        )
        self.db_writer = AsyncDBWriter(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            charset=settings.db_charset,
            table=settings.db_table,
            pool_maxsize=max(2, settings.qwen_batch_size + 1),
        )
        self.oss_uploader = AsyncOSSImageUploader(
            enabled=settings.oss_enabled,
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            bucket_name=settings.oss_bucket,
            endpoint=settings.oss_endpoint,
            view_domain=settings.oss_view_domain,
            prefix=settings.oss_prefix,
            object_acl=settings.oss_object_acl,
            timeout=settings.image_timeout,
            max_concurrency=max(2, settings.image_validation_workers),
        )
        self._runtime_logged = False
        self._batch_main_images: set[str] = set()
        self._batch_detail_groups: set[tuple[str, ...]] = set()
        self._batch_media_groups: set[tuple[str, ...]] = set()

    async def close(self) -> None:
        await self.image_client.close()
        await self.qwen_client.close()
        await self.db_writer.close()
        await self.oss_uploader.close()

    async def run(self, task: GenerationTask) -> PipelineResult:
        run_started_at = time.perf_counter()
        self._reset_batch_media_registry()
        profile = get_category_profile(task.category_id)
        self.logger.info(
            "Start async pipeline: category=%s(%s) count=%s keywords=%s dry_run=%s",
            task.category_id,
            profile["name"],
            task.count,
            ",".join(task.keywords),
            task.dry_run,
        )
        await self._log_runtime_status()
        history_titles = await self.db_writer.fetch_existing_titles()
        validator = GoodsValidator(
            category_id=task.category_id,
            history_titles=history_titles,
            target_count=task.count,
            similarity_threshold=self.settings.title_similarity_threshold,
            city_strategy=task.city_strategy,
        )
        failures: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        attempted_candidates = 0
        max_attempts = max(30, task.count * self.settings.task_max_attempts_multiplier)
        next_model = task.model
        candidate_durations: list[float] = []
        success_durations: list[float] = []
        model_batch_durations: list[float] = []

        while len(records) < task.count and attempted_candidates < max_attempts:
            remaining = task.count - len(records)
            candidate_count = choose_candidate_count(remaining, self.settings.qwen_batch_size)
            history_guard_titles = select_history_guard_titles(
                history_titles + [record["goods_name"] for record in records],
                task.keywords,
                limit=60,
            )
            system_prompt, user_prompt = build_prompts(
                category_id=task.category_id,
                keywords=task.keywords,
                target_count=candidate_count,
                city_strategy=task.city_strategy,
                history_titles=history_guard_titles,
                system_prompt_base=self.settings.qwen_system_prompt,
                style_seed=(
                    f"{self.run_id}:{normalize_batch_id(task.batch_id, fallback=self.run_id)}:"
                    f"{attempted_candidates}:{len(records)}"
                ),
            )

            batch_added = 0
            generation_started_at = time.perf_counter()
            try:
                generation = await self.qwen_client.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=next_model,
                )
                model_batch_durations.append(time.perf_counter() - generation_started_at)
            except AsyncQwenParseError as exc:
                model_batch_durations.append(time.perf_counter() - generation_started_at)
                failures.append(
                    self._failure_entry(
                        task=task,
                        fail_stage="qwen_parse",
                        fail_reason=str(exc),
                        raw_model_output=exc.raw_content,
                    )
                )
                self.logger.warning("Model parse failure with %s: %s", next_model, exc)
                next_model = task.fallback_model if next_model != task.fallback_model else task.model
                continue
            except AsyncQwenClientError as exc:
                model_batch_durations.append(time.perf_counter() - generation_started_at)
                failures.append(
                    self._failure_entry(
                        task=task,
                        fail_stage="qwen_request",
                        fail_reason=str(exc),
                    )
                )
                self.logger.warning("Model request failure with %s: %s", next_model, exc)
                next_model = task.fallback_model if next_model != task.fallback_model else task.model
                continue

            for raw_item in generation.items:
                if len(records) >= task.count or attempted_candidates >= max_attempts:
                    break
                candidate_started_at = time.perf_counter()
                attempted_candidates += 1
                validation = validator.validate(raw_item)
                if not validation.ok:
                    candidate_duration = time.perf_counter() - candidate_started_at
                    candidate_durations.append(candidate_duration)
                    failures.append(
                        self._failure_entry(
                            task=task,
                            candidate_title=self._safe_title(raw_item),
                            normalized_title=validation.normalized_title,
                            fail_stage="validate",
                            fail_reason=validation.reason,
                            retry_count=0,
                            similarity_score=validation.similarity_score,
                            matched_history_title=validation.matched_history_title,
                            image_keywords=self._safe_image_keywords(raw_item),
                            raw_model_output=json.dumps(raw_item, ensure_ascii=False),
                            candidate_duration_seconds=candidate_duration,
                        )
                    )
                    continue

                record, image_failure = await self._materialize_record(task, validation, generation)
                candidate_duration = time.perf_counter() - candidate_started_at
                candidate_durations.append(candidate_duration)
                if image_failure is not None:
                    image_failure["candidate_duration_seconds"] = round(candidate_duration, 3)
                    failures.append(image_failure)
                if record is None:
                    continue

                record["processing_duration_seconds"] = round(candidate_duration, 3)
                records.append(record)
                success_durations.append(candidate_duration)
                validator.register_success(validation)
                batch_added += 1
                self.logger.info(
                    "Accepted item %s/%s: %s",
                    len(records),
                    task.count,
                    record["goods_name"],
                )

            if batch_added == 0:
                next_model = task.fallback_model if next_model != task.fallback_model else task.model
            else:
                next_model = task.model

        inserted_count = 0
        if task.write_db and not task.dry_run and records:
            inserted_count = await self.db_writer.insert_goods(records)
            self.logger.info("Inserted %s rows into %s", inserted_count, self.settings.db_table)
        else:
            self.logger.info("Skip DB insert: write_db=%s dry_run=%s", task.write_db, task.dry_run)

        self._write_failures(failures)
        total_duration_seconds = time.perf_counter() - run_started_at
        quality_report = self._build_quality_report(
            task=task,
            category_name=str(profile["name"]),
            records=records,
            failures=failures,
            attempted_candidates=attempted_candidates,
            inserted_count=inserted_count,
            total_duration_seconds=total_duration_seconds,
            candidate_durations=candidate_durations,
            success_durations=success_durations,
            model_batch_durations=model_batch_durations,
        )
        self._write_quality_report(quality_report)
        self._log_quality_report_summary(quality_report)
        self.logger.info(
            "Async pipeline done: success=%s failures=%s inserted=%s attempted=%s",
            len(records),
            len(failures),
            inserted_count,
            attempted_candidates,
        )
        if task.export_excel:
            self.logger.info("export_excel flag ignored in current DB-first build")

        return PipelineResult(
            run_id=self.run_id,
            requested_count=task.count,
            success_count=len(records),
            inserted_count=inserted_count,
            failure_count=len(failures),
            log_path=self.log_path,
            failure_log_path=self.failure_log_path,
            report_path=self.report_path,
            records=records,
            failures=failures,
            quality_report=quality_report,
        )

    async def _materialize_record(
        self,
        task: GenerationTask,
        validation: ValidationResult,
        generation: AsyncQwenGenerationResult,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        assert validation.item is not None
        item = validation.item
        image_pool_key = self._build_image_pool_key(task, item)
        image_result = await self.image_client.resolve_images(
            title=item["title"],
            image_keywords=item["image_keywords"],
            category_id=task.category_id,
            keywords=task.keywords,
            reuse_key=image_pool_key,
            exclude_urls=self._collect_reserved_media_urls(),
        )
        if not image_result.main_image:
            entry = self._failure_entry(
                task=task,
                candidate_title=item["title"],
                normalized_title=validation.normalized_title,
                fail_stage="image",
                fail_reason="no_valid_main_image",
                image_keywords=item["image_keywords"],
                raw_model_output=json.dumps(item, ensure_ascii=False),
            )
            entry["source_queries"] = image_result.source_queries
            entry["all_valid_urls"] = image_result.all_valid_urls
            return None, entry

        now = int(time.time())
        source_main_image = image_result.main_image
        source_detail_images = list(image_result.detail_images)
        duplicate_reason = self._check_batch_media_reuse(
            main_image=source_main_image,
            detail_images=source_detail_images,
        )
        if duplicate_reason:
            entry = self._failure_entry(
                task=task,
                candidate_title=item["title"],
                normalized_title=validation.normalized_title,
                fail_stage="image",
                fail_reason=duplicate_reason,
                image_keywords=item["image_keywords"],
                raw_model_output=json.dumps(item, ensure_ascii=False),
            )
            entry["source_queries"] = image_result.source_queries
            entry["all_valid_urls"] = image_result.all_valid_urls
            return None, entry

        main_image = source_main_image
        detail_images = list(source_detail_images)
        try:
            main_task = (
                self.oss_uploader.upload_url(main_image)
                if str(main_image or "").strip()
                else asyncio.sleep(0, result="")
            )
            detail_task = (
                self.oss_uploader.upload_urls(detail_images, force_upload=True)
                if detail_images
                else asyncio.sleep(0, result=[])
            )
            uploaded_main, uploaded_details = await asyncio.gather(main_task, detail_task)
            main_image = str(uploaded_main or "").strip()
            detail_images = list(uploaded_details or [])
        except Exception as exc:
            entry = self._failure_entry(
                task=task,
                candidate_title=item["title"],
                normalized_title=validation.normalized_title,
                fail_stage="oss_upload",
                fail_reason=str(exc),
                image_keywords=item["image_keywords"],
                raw_model_output=json.dumps(item, ensure_ascii=False),
            )
            entry["source_queries"] = image_result.source_queries
            entry["all_valid_urls"] = image_result.all_valid_urls
            return None, entry

        self._register_batch_media(
            main_image=source_main_image,
            detail_images=source_detail_images,
        )

        description = self._build_description_html(
            title=item["title"],
            category_id=task.category_id,
            subtitle=item["subtitle"],
            selling_points=item["selling_points"],
            attrs=item["attrs"],
            detail_images=detail_images,
            variation_seed=f"{self.run_id}:{normalize_batch_id(task.batch_id, fallback=self.run_id)}",
        )
        batch_id = normalize_batch_id(task.batch_id, fallback=self.run_id)
        return {
            "goods_name": item["title"],
            "sub_title": item["subtitle"],
            "shop_id": task.shop_id,
            "category_id": task.category_id,
            "image": main_image,
            "price": item["price"],
            "description": description,
            "en_name": "",
            "batch_id": batch_id,
            "last_batch_id": batch_id,
            "source_type": SOURCE_AI_GENERATE,
            "source_note": build_source_note(
                [
                    f"batch_id={batch_id}",
                    f"keywords={','.join(task.keywords)}",
                    f"model={generation.model}",
                ]
            ),
            "create_time": now,
            "update_time": now,
            "selling_points": item["selling_points"],
            "attrs": item["attrs"],
            "image_keywords": item["image_keywords"],
            "detail_images": detail_images,
            "model_used": generation.model,
            "main_image_source": image_result.main_image_source,
            "detail_image_sources": image_result.detail_image_sources,
            "source_queries": image_result.source_queries,
        }, None

    def _build_image_pool_key(self, task: GenerationTask, item: dict[str, Any]) -> str:
        seeds = [
            str(item.get("title") or "").strip(),
            *[
                str(keyword or "").strip()
                for keyword in (item.get("image_keywords") or [])
                if str(keyword or "").strip()
            ],
        ]
        for seed in seeds:
            pool_seed = self._extract_image_pool_seed(seed)
            if pool_seed:
                return f"{task.category_id}:{pool_seed}"
        return f"{task.category_id}:{normalize_title(str(item.get('title') or '').strip())}"

    def _extract_image_pool_seed(self, text: str) -> str:
        chunks = [
            normalize_title(chunk)
            for chunk in re.split(r"[\s/|｜·•（）()\-—_]+", str(text or "").strip())
            if normalize_title(chunk)
        ]
        if chunks:
            return chunks[0]
        return normalize_title(str(text or "").strip())

    def _collect_reserved_media_urls(self) -> set[str]:
        reserved: set[str] = set()
        for url in self._batch_main_images:
            normalized = normalize_storable_image_url(url)
            if normalized:
                reserved.add(normalized)
        for group in self._batch_detail_groups:
            for url in group:
                normalized = normalize_storable_image_url(url)
                if normalized:
                    reserved.add(normalized)
        return reserved

    async def _log_runtime_status(self) -> None:
        if self._runtime_logged:
            return
        self._runtime_logged = True
        runtime_status = await self.image_client.runtime_status()
        self.logger.info(
            "Image runtime status: baidu_render_ready=%s bing_enabled=%s bing_render_ready=%s clip_rerank_enabled=%s clip_rerank_deps_ready=%s clip_rerank_model=%s",
            runtime_status["baidu_render_ready"],
            runtime_status["bing_enabled"],
            runtime_status["bing_render_ready"],
            runtime_status["clip_rerank_enabled"],
            runtime_status["clip_rerank_deps_ready"],
            runtime_status["clip_rerank_model"],
        )
        if not runtime_status["baidu_render_ready"]:
            self.logger.warning(
                "Baidu first-screen rendering unavailable; Baidu source may return empty results."
            )
        if self.settings.image_enable_bing:
            self.logger.warning(
                "Bing image search is enabled in config, but async direct generation currently uses Baidu only."
            )
        else:
            self.logger.info("Bing image search disabled by config; current pipeline uses Baidu only.")
        if runtime_status["clip_rerank_enabled"] and not runtime_status["clip_rerank_deps_ready"]:
            self.logger.warning(
                "CLIP rerank enabled but unavailable: %s",
                runtime_status["clip_rerank_last_error"] or "dependency_missing",
            )
