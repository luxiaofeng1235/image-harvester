from __future__ import annotations

import json
import time
from dataclasses import dataclass
from html import escape as html_escape
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
from ai_goods_pipeline.constants import IMAGE_DETAIL_COUNT, IMAGE_REQUIRED_TOTAL
from ai_goods_pipeline.prompts.category_profiles import (
    build_prompts,
    choose_candidate_count,
    get_category_profile,
    select_history_guard_titles,
)
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


@dataclass(slots=True)
class PipelineResult:
    run_id: str
    requested_count: int
    success_count: int
    inserted_count: int
    failure_count: int
    log_path: Path
    failure_log_path: Path
    records: list[dict[str, Any]]
    failures: list[dict[str, Any]]


class AIGoodsPipeline:
    def __init__(self, *, settings: Settings, logger, run_id: str, log_path: Path) -> None:
        self.settings = settings
        self.logger = logger
        self.run_id = run_id
        self.log_path = log_path
        self.failure_log_path = settings.logs_dir / f"failures_{run_id}.jsonl"
        self.qwen_client = QwenClient(
            open_url=settings.qwen_open_url,
            api_key=settings.qwen_key,
            temperature=settings.qwen_temperature,
            max_tokens=settings.qwen_max_tokens,
        )
        self.image_client = ImageClient(
            api_url=settings.image_api_url,
            timeout=settings.image_timeout,
            retries=settings.image_retry,
            min_bytes=settings.image_min_bytes,
            allow_gif_as_main=settings.image_allow_gif_as_main,
            preset_file=settings.ai_tech_preset_image_file,
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
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            bucket_name=settings.oss_bucket,
            endpoint=settings.oss_endpoint,
            view_domain=settings.oss_view_domain,
            prefix=settings.oss_prefix,
            timeout=settings.image_timeout,
        )

    def run(self, task: GenerationTask) -> PipelineResult:
        profile = get_category_profile(task.category_id)
        self.logger.info(
            "Start pipeline: category=%s(%s) count=%s keywords=%s dry_run=%s",
            task.category_id,
            profile["name"],
            task.count,
            ",".join(task.keywords),
            task.dry_run,
        )
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
            try:
                generation = self.qwen_client.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=next_model,
                )
            except QwenParseError as exc:
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
                attempted_candidates += 1
                validation = validator.validate(raw_item)
                if not validation.ok:
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
                        )
                    )
                    continue

                record, image_failure = self._materialize_record(task, validation, generation)
                if image_failure is not None:
                    failures.append(image_failure)
                if record is None:
                    continue

                records.append(record)
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
            records=records,
            failures=failures,
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
            return None, entry
        available_total = 1 + len(image_result.detail_images)
        if len(image_result.detail_images) < IMAGE_DETAIL_COUNT or available_total < IMAGE_REQUIRED_TOTAL:
            entry = self._failure_entry(
                task=task,
                candidate_title=item["title"],
                normalized_title=validation.normalized_title,
                fail_stage="image",
                fail_reason=f"insufficient_images:{available_total}/{IMAGE_REQUIRED_TOTAL}",
                image_keywords=item["image_keywords"],
                raw_model_output=json.dumps(item, ensure_ascii=False),
            )
            entry["source_queries"] = image_result.source_queries
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
            return None, entry

        description = self._build_description_html(
            selling_points=item["selling_points"],
            attrs=item["attrs"],
            detail_images=detail_images,
        )
        return {
            "goods_name": item["title"],
            "sub_title": item["subtitle"],
            "category_id": task.category_id,
            "image": main_image,
            "price": item["price"],
            "description": description,
            "en_name": "",
            "create_time": now,
            "update_time": now,
            "selling_points": item["selling_points"],
            "attrs": item["attrs"],
            "image_keywords": item["image_keywords"],
            "detail_images": detail_images,
            "model_used": generation.model,
            "source_queries": image_result.source_queries,
        }, None

    def _build_description_html(
        self,
        *,
        selling_points: list[str],
        attrs: dict[str, Any],
        detail_images: list[str],
    ) -> str:
        selling_points_text = "；".join(html_escape(point) for point in selling_points)
        attrs_text = "；".join(
            f"{html_escape(str(key))}：{html_escape(str(value))}" for key, value in attrs.items()
        )
        sections = [
            '<div class="product-description">',
            f"  <p><strong>商品亮点</strong>：{selling_points_text}</p>",
            f"  <p><strong>规格属性</strong>：{attrs_text}</p>",
            "</div>",
        ]
        if detail_images:
            sections.append('<div class="product-detail">')
            for url in detail_images:
                sections.append(f'  <p><img src="{html_escape(url)}" /></p>')
            sections.append("</div>")
        return "\n".join(sections)

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
            "created_at": int(time.time()),
        }

    def _write_failures(self, failures: list[dict[str, Any]]) -> None:
        if not failures and self.failure_log_path.exists():
            return
        with self.failure_log_path.open("w", encoding="utf-8") as handle:
            for entry in failures:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

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
