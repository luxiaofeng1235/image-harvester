from __future__ import annotations

from collections import Counter
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_goods_pipeline.clients.image_client import ImageClient
from ai_goods_pipeline.clients.oss_client import OSSImageUploader
from ai_goods_pipeline.clients.qwen_client import (
    QwenClient,
    QwenClientError,
    QwenGenerationResult,
    QwenParseError,
)
from ai_goods_pipeline.config import Settings
from ai_goods_pipeline.enums.source_types import SOURCE_AI_GENERATE
from ai_goods_pipeline.prompts.category_profiles import (
    build_prompts,
    choose_candidate_count,
    get_category_profile,
    select_history_guard_titles,
)
from ai_goods_pipeline.utils.batch_meta import build_source_note, normalize_batch_id
from ai_goods_pipeline.utils.description_layout import build_description_html
from ai_goods_pipeline.validators.goods_validator import GoodsValidator, ValidationResult
from ai_goods_pipeline.writers.db_writer import DBWriter


@dataclass(slots=True)
class GenerationTask:
    category_id: int
    keywords: list[str]
    count: int
    model: str
    fallback_model: str
    write_db: bool
    dry_run: bool
    export_excel: bool
    city_strategy: str
    batch_id: str = ""


@dataclass(slots=True)
class PipelineResult:
    run_id: str
    requested_count: int
    success_count: int
    inserted_count: int
    failure_count: int
    log_path: Path
    failure_log_path: Path
    report_path: Path
    records: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    quality_report: dict[str, Any]


class AIGoodsPipeline:
    def __init__(self, *, settings: Settings, logger, run_id: str, log_path: Path) -> None:
        self.settings = settings
        self.logger = logger
        self.run_id = run_id
        self.log_path = log_path
        self.failure_log_path = settings.logs_dir / f"failures_{run_id}.jsonl"
        self.report_path = settings.logs_dir / f"report_{run_id}.json"
        self.qwen_client = QwenClient(
            open_url=settings.qwen_open_url,
            api_key=settings.qwen_key,
            temperature=settings.qwen_temperature,
            max_tokens=settings.qwen_max_tokens,
        )
        self.image_client = ImageClient(
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
        )
        self.db_writer = DBWriter(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            charset=settings.db_charset,
            table=settings.db_table,
        )
        self.oss_uploader = OSSImageUploader(
            enabled=settings.oss_enabled,
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            bucket_name=settings.oss_bucket,
            endpoint=settings.oss_endpoint,
            view_domain=settings.oss_view_domain,
            prefix=settings.oss_prefix,
            timeout=settings.image_timeout,
        )
        self._runtime_logged = False

    def close(self) -> None:
        self.image_client.close()
        self.qwen_client.close()
        self.oss_uploader.close()

    def run(self, task: GenerationTask) -> PipelineResult:
        run_started_at = time.time()
        profile = get_category_profile(task.category_id)
        self.logger.info(
            "Start pipeline: category=%s(%s) count=%s keywords=%s dry_run=%s",
            task.category_id,
            profile["name"],
            task.count,
            ",".join(task.keywords),
            task.dry_run,
        )
        self._log_runtime_status()
        history_titles = self.db_writer.fetch_existing_titles()
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
            )

            batch_added = 0
            generation_started_at = time.time()
            try:
                generation = self.qwen_client.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=next_model,
                )
                model_batch_durations.append(time.time() - generation_started_at)
            except QwenParseError as exc:
                model_batch_durations.append(time.time() - generation_started_at)
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
            except QwenClientError as exc:
                model_batch_durations.append(time.time() - generation_started_at)
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
                candidate_started_at = time.time()
                attempted_candidates += 1
                validation = validator.validate(raw_item)
                if not validation.ok:
                    candidate_duration = time.time() - candidate_started_at
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

                record, image_failure = self._materialize_record(task, validation, generation)
                candidate_duration = time.time() - candidate_started_at
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
            inserted_count = self.db_writer.insert_goods(records)
            self.logger.info("Inserted %s rows into %s", inserted_count, self.settings.db_table)
        else:
            self.logger.info("Skip DB insert: write_db=%s dry_run=%s", task.write_db, task.dry_run)

        self._write_failures(failures)
        total_duration_seconds = time.time() - run_started_at
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
            "Pipeline done: success=%s failures=%s inserted=%s attempted=%s",
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

    def _materialize_record(
        self,
        task: GenerationTask,
        validation: ValidationResult,
        generation: QwenGenerationResult,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        assert validation.item is not None
        item = validation.item
        image_result = self.image_client.resolve_images(
            title=item["title"],
            image_keywords=item["image_keywords"],
            category_id=task.category_id,
            keywords=task.keywords,
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
        main_image = image_result.main_image
        detail_images = image_result.detail_images
        try:
            main_image = self.oss_uploader.upload_url(main_image)
            detail_images = self.oss_uploader.upload_urls(detail_images)
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

        description = self._build_description_html(
            subtitle=item["subtitle"],
            selling_points=item["selling_points"],
            attrs=item["attrs"],
            detail_images=detail_images,
        )
        batch_id = normalize_batch_id(task.batch_id, fallback=self.run_id)
        return {
            "goods_name": item["title"],
            "sub_title": item["subtitle"],
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

    def _log_runtime_status(self) -> None:
        if self._runtime_logged:
            return
        self._runtime_logged = True
        runtime_status = self.image_client.runtime_status()
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
        if not runtime_status["bing_enabled"]:
            self.logger.info("Bing image search disabled by config; current pipeline uses Baidu only.")
        elif not runtime_status["bing_render_ready"]:
            self.logger.warning(
                "Bing first-screen rendering unavailable; Bing may fallback to static HTML order."
            )
        if runtime_status["clip_rerank_enabled"] and not runtime_status["clip_rerank_deps_ready"]:
            self.logger.warning(
                "CLIP rerank enabled but unavailable: %s",
                runtime_status["clip_rerank_last_error"] or "dependency_missing",
            )

    def _build_description_html(
        self,
        *,
        subtitle: str,
        selling_points: list[str],
        attrs: dict[str, Any],
        detail_images: list[str],
    ) -> str:
        return build_description_html(
            subtitle=subtitle,
            selling_points=selling_points,
            attrs=attrs,
            detail_images=detail_images,
        )

    def _failure_entry(
        self,
        *,
        task: GenerationTask,
        candidate_title: str = "",
        normalized_title: str = "",
        fail_stage: str,
        fail_reason: str,
        retry_count: int = 0,
        similarity_score: float = 0.0,
        matched_history_title: str = "",
        image_keywords: list[str] | None = None,
        raw_model_output: str = "",
        candidate_duration_seconds: float = 0.0,
    ) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "category_id": task.category_id,
            "keywords": ",".join(task.keywords),
            "target_count": task.count,
            "candidate_title": candidate_title,
            "normalized_title": normalized_title,
            "fail_stage": fail_stage,
            "fail_reason": fail_reason,
            "retry_count": retry_count,
            "similarity_score": similarity_score,
            "matched_history_title": matched_history_title,
            "image_keywords": image_keywords or [],
            "raw_model_output": raw_model_output,
            "candidate_duration_seconds": round(candidate_duration_seconds, 3),
            "created_at": int(time.time()),
        }

    def _write_failures(self, failures: list[dict[str, Any]]) -> None:
        if not failures and self.failure_log_path.exists():
            return
        with self.failure_log_path.open("w", encoding="utf-8") as handle:
            for entry in failures:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _build_quality_report(
        self,
        *,
        task: GenerationTask,
        category_name: str,
        records: list[dict[str, Any]],
        failures: list[dict[str, Any]],
        attempted_candidates: int,
        inserted_count: int,
        total_duration_seconds: float,
        candidate_durations: list[float],
        success_durations: list[float],
        model_batch_durations: list[float],
    ) -> dict[str, Any]:
        success_count = len(records)
        failure_count = len(failures)
        requested_count = task.count
        failure_reason_counter = Counter(
            str(item.get("fail_reason") or "").strip()
            for item in failures
            if str(item.get("fail_reason") or "").strip()
        )
        fail_stage_counter = Counter(
            str(item.get("fail_stage") or "").strip()
            for item in failures
            if str(item.get("fail_stage") or "").strip()
        )
        selected_image_source_counter: Counter[str] = Counter()
        search_source_counter: Counter[str] = Counter()
        for record in records:
            main_source = str(record.get("main_image_source") or "").strip()
            if main_source:
                selected_image_source_counter[main_source] += 1
            for source in record.get("detail_image_sources") or []:
                source_name = str(source or "").strip()
                if source_name:
                    selected_image_source_counter[source_name] += 1
            for source_query in record.get("source_queries") or []:
                source_name = self._normalize_source_query(source_query)
                if source_name:
                    search_source_counter[source_name] += 1
        for failure in failures:
            for source_query in failure.get("source_queries") or []:
                source_name = self._normalize_source_query(source_query)
                if source_name:
                    search_source_counter[source_name] += 1

        return {
            "run_id": self.run_id,
            "category_id": task.category_id,
            "category_name": category_name,
            "keywords": task.keywords,
            "requested_count": requested_count,
            "success_count": success_count,
            "inserted_count": inserted_count,
            "failure_count": failure_count,
            "attempted_candidates": attempted_candidates,
            "success_rate": self._safe_ratio(success_count, requested_count),
            "attempted_success_rate": self._safe_ratio(success_count, attempted_candidates),
            "insert_rate": self._safe_ratio(inserted_count, success_count),
            "total_duration_seconds": round(total_duration_seconds, 3),
            "avg_duration_per_success_seconds": self._safe_average(total_duration_seconds, success_count),
            "avg_candidate_processing_seconds": self._safe_average(
                sum(candidate_durations), len(candidate_durations)
            ),
            "avg_success_processing_seconds": self._safe_average(
                sum(success_durations), len(success_durations)
            ),
            "avg_model_batch_duration_seconds": self._safe_average(
                sum(model_batch_durations), len(model_batch_durations)
            ),
            "failure_reason_distribution": self._sorted_counter_dict(failure_reason_counter),
            "fail_stage_distribution": self._sorted_counter_dict(fail_stage_counter),
            "image_source_distribution": self._sorted_counter_dict(selected_image_source_counter),
            "search_source_distribution": self._sorted_counter_dict(search_source_counter),
            "created_at": int(time.time()),
        }

    def _write_quality_report(self, report: dict[str, Any]) -> None:
        with self.report_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    def _log_quality_report_summary(self, report: dict[str, Any]) -> None:
        self.logger.info(
            (
                "Quality report: success_rate=%.2f%% attempted_success_rate=%.2f%% "
                "avg_per_success=%.2fs avg_candidate=%.2fs image_sources=%s top_failures=%s report=%s"
            ),
            float(report.get("success_rate", 0.0)) * 100.0,
            float(report.get("attempted_success_rate", 0.0)) * 100.0,
            float(report.get("avg_duration_per_success_seconds", 0.0)),
            float(report.get("avg_candidate_processing_seconds", 0.0)),
            self._format_counter_preview(report.get("image_source_distribution")),
            self._format_counter_preview(report.get("failure_reason_distribution")),
            self.report_path,
        )

    def _normalize_source_query(self, source_query: Any) -> str:
        text = str(source_query or "").strip()
        if not text:
            return ""
        prefix = text.split(":", 1)[0].strip().lower()
        return prefix.replace("_images", "")

    def _sorted_counter_dict(self, counter: Counter[str]) -> dict[str, int]:
        return {
            key: counter[key]
            for key, _ in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        }

    def _format_counter_preview(self, payload: Any, limit: int = 3) -> str:
        if not isinstance(payload, dict) or not payload:
            return "-"
        items: list[str] = []
        for index, (key, value) in enumerate(payload.items()):
            if index >= limit:
                break
            items.append(f"{key}:{value}")
        return ",".join(items) if items else "-"

    def _safe_average(self, total: float, count: int) -> float:
        if count <= 0:
            return 0.0
        return round(total / count, 3)

    def _safe_ratio(self, numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator, 4)

    def _safe_title(self, raw_item: Any) -> str:
        if isinstance(raw_item, dict):
            return str(raw_item.get("title") or "").strip()
        return ""

    def _safe_image_keywords(self, raw_item: Any) -> list[str]:
        if not isinstance(raw_item, dict):
            return []
        keywords = raw_item.get("image_keywords")
        if isinstance(keywords, list):
            return [str(item).strip() for item in keywords if str(item).strip()]
        if isinstance(keywords, str) and keywords.strip():
            return [keywords.strip()]
        return []
