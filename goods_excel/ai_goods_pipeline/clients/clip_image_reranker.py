from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
from threading import Lock

import requests
from PIL import Image, ImageFile, UnidentifiedImageError

from ai_goods_pipeline.enums.image_semantics import (
    IMAGE_CARRIER_KEYWORDS,
    IMAGE_FINISHED_DISPLAY_CARRIERS,
    IMAGE_FLAT_DISPLAY_CARRIERS,
    IMAGE_MATERIAL_HINTS,
)

try:
    import torch
    from transformers import AutoModel, AutoProcessor
except Exception:  # pragma: no cover - optional dependency
    torch = None
    AutoModel = None
    AutoProcessor = None


ImageFile.LOAD_TRUNCATED_IMAGES = True


@dataclass(slots=True)
class ClipRerankResult:
    applied: bool
    reason: str
    ranked_urls: list[str]
    scores: dict[str, float]


class ClipImageReranker:
    def __init__(
        self,
        *,
        enabled: bool,
        model_name: str,
        min_score: float,
        max_candidates: int,
        category_ids: tuple[int, ...],
        timeout: int,
        user_agent: str,
    ) -> None:
        self.enabled = enabled
        self.model_name = model_name
        self.min_score = min_score
        self.max_candidates = max(1, max_candidates)
        self.category_ids = tuple(category_ids)
        self.timeout = timeout
        self.user_agent = user_agent
        self._device = "cpu"
        self._model = None
        self._processor = None
        self._model_lock = Lock()
        self._last_error = ""

    def runtime_status(self) -> dict[str, object]:
        local_model_dir = self._resolve_local_model_dir()
        return {
            "enabled": self.enabled,
            "category_ids": self.category_ids,
            "model_name": self.model_name,
            "local_model_dir": local_model_dir,
            "local_model_dir_exists": bool(local_model_dir and Path(local_model_dir).is_dir()),
            "deps_ready": self._deps_ready(),
            "model_loaded": self._model is not None and self._processor is not None,
            "last_error": self._last_error,
        }

    def rerank_urls(
        self,
        *,
        title: str,
        category_id: int,
        candidate_urls: list[str],
    ) -> ClipRerankResult:
        original_urls = [str(url).strip() for url in candidate_urls if str(url).strip()]
        if not original_urls:
            return ClipRerankResult(
                applied=False,
                reason="empty_candidates",
                ranked_urls=[],
                scores={},
            )
        if not self.enabled:
            return ClipRerankResult(
                applied=False,
                reason="disabled",
                ranked_urls=original_urls,
                scores={},
            )
        if self.category_ids and category_id not in self.category_ids:
            return ClipRerankResult(
                applied=False,
                reason="category_not_enabled",
                ranked_urls=original_urls,
                scores={},
            )
        if not self._deps_ready():
            return ClipRerankResult(
                applied=False,
                reason="deps_unavailable",
                ranked_urls=original_urls,
                scores={},
            )

        model, processor = self._ensure_model()
        if model is None or processor is None:
            return ClipRerankResult(
                applied=False,
                reason="model_unavailable",
                ranked_urls=original_urls,
                scores={},
            )

        prompts = self._build_prompts(title=title, category_id=category_id)
        limited_urls = original_urls[: self.max_candidates]
        images: list[Image.Image] = []
        image_urls: list[str] = []
        for url in limited_urls:
            image = self._download_image(url)
            if image is None:
                continue
            images.append(image)
            image_urls.append(url)

        if len(image_urls) < 2:
            return ClipRerankResult(
                applied=False,
                reason="insufficient_images",
                ranked_urls=original_urls,
                scores={},
            )

        try:
            score_values = self._score_images(images=images, prompts=prompts)
        except Exception as exc:  # pragma: no cover - runtime dependent
            self._last_error = str(exc)
            return ClipRerankResult(
                applied=False,
                reason="score_failed",
                ranked_urls=original_urls,
                scores={},
            )

        score_map = {
            url: round(float(score), 4)
            for url, score in zip(image_urls, score_values, strict=False)
        }
        kept_urls = [
            url
            for url, score in sorted(
                score_map.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            if score >= self.min_score
        ]
        if not kept_urls:
            return ClipRerankResult(
                applied=False,
                reason="below_threshold",
                ranked_urls=original_urls,
                scores=score_map,
            )

        kept_set = set(kept_urls)
        ranked_urls = kept_urls + [url for url in original_urls if url not in kept_set]
        return ClipRerankResult(
            applied=True,
            reason="reranked",
            ranked_urls=ranked_urls,
            scores=score_map,
        )

    def _deps_ready(self) -> bool:
        if torch is None or AutoModel is None or AutoProcessor is None:
            self._last_error = "transformers_or_torch_missing"
            return False
        return True

    def _ensure_model(self):
        if self._model is not None and self._processor is not None:
            return self._model, self._processor
        with self._model_lock:
            if self._model is not None and self._processor is not None:
                return self._model, self._processor
            if not self._deps_ready():
                return None, None
            local_model_dir = self._resolve_local_model_dir()
            if not local_model_dir:
                return None, None
            try:
                self._processor, self._model = self._load_from_pretrained(local_model_dir)
            except Exception as exc:  # pragma: no cover - runtime dependent
                self._last_error = f"local_model_load_failed:{exc}"
                self._model = None
                self._processor = None
                return None, None
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model.to(self._device)
            self._model.eval()
            return self._model, self._processor

    def _resolve_local_model_dir(self) -> str | None:
        candidate = Path(str(self.model_name or "")).expanduser()
        if not candidate.is_dir():
            self._last_error = f"local_model_dir_missing:{candidate}"
            return None
        return str(candidate.resolve())

    def _load_from_pretrained(self, model_dir: str):
        processor = AutoProcessor.from_pretrained(
            model_dir,
            local_files_only=True,
        )
        model = AutoModel.from_pretrained(
            model_dir,
            local_files_only=True,
        )
        return processor, model

    def _download_image(self, url: str) -> Image.Image | None:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
            )
            response.raise_for_status()
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and not content_type.startswith("image/"):
                return None
            image = Image.open(BytesIO(response.content))
            return image.convert("RGB")
        except (
            OSError,
            UnidentifiedImageError,
            ValueError,
            requests.RequestException,
        ):
            return None

    def _score_images(self, *, images: list[Image.Image], prompts: list[str]) -> list[float]:
        if self._model is None or self._processor is None:
            raise RuntimeError("clip_model_not_loaded")
        if not hasattr(self._model, "get_image_features") or not hasattr(
            self._model, "get_text_features"
        ):
            raise RuntimeError("clip_feature_api_missing")

        with self._model_lock:
            image_inputs = self._processor(images=images, return_tensors="pt")
            text_inputs = self._processor(
                text=prompts,
                return_tensors="pt",
                padding=True,
                truncation=True,
            )
            image_inputs = self._move_to_device(image_inputs)
            text_inputs = self._move_to_device(text_inputs)

            with torch.no_grad():
                image_features = self._model.get_image_features(**image_inputs)
                text_features = self._model.get_text_features(**text_inputs)

            image_features = self._extract_feature_tensor(image_features)
            text_features = self._extract_feature_tensor(text_features)
            image_features = image_features / image_features.norm(
                p=2,
                dim=-1,
                keepdim=True,
            )
            text_features = text_features / text_features.norm(
                p=2,
                dim=-1,
                keepdim=True,
            )
            similarity = torch.matmul(image_features, text_features.T)
            return similarity.max(dim=1).values.cpu().tolist()

    def _move_to_device(self, payload: dict[str, object]) -> dict[str, object]:
        moved: dict[str, object] = {}
        for key, value in payload.items():
            moved[key] = value.to(self._device) if hasattr(value, "to") else value
        return moved

    def _extract_feature_tensor(self, value):
        if hasattr(value, "image_embeds") and value.image_embeds is not None:
            return value.image_embeds
        if hasattr(value, "text_embeds") and value.text_embeds is not None:
            return value.text_embeds
        if hasattr(value, "pooler_output") and value.pooler_output is not None:
            return value.pooler_output
        if hasattr(value, "last_hidden_state") and value.last_hidden_state is not None:
            return value.last_hidden_state[:, 0]
        if hasattr(value, "norm"):
            return value
        raise RuntimeError(f"unsupported_feature_output:{type(value).__name__}")

    def _build_prompts(self, *, title: str, category_id: int) -> list[str]:
        quoted_terms = re.findall(r"[“\"]([^”\"]{2,12})[”\"]", title)
        carrier_terms = [term for term in IMAGE_CARRIER_KEYWORDS if term in title]
        material_terms = [term for term in IMAGE_MATERIAL_HINTS if term in title]

        prompts = [
            f"电商商品主图 商品实物图 {title}",
        ]
        if category_id == 128:
            prompts.append(f"足球文创 商品实物图 {title}")
            if quoted_terms:
                prompts.append(f"{quoted_terms[0]} 吉祥物 商品实物图")
            if carrier_terms:
                prompts.append(f"{carrier_terms[0]} 商品实物图")
        elif category_id == 129:
            prompts.append(f"工艺品 商品实物图 {title}")
            if carrier_terms:
                display_hint = self._get_display_hint(carrier_terms[0])
                prompts.append(f"{carrier_terms[0]} {display_hint} 商品实物图")
            if material_terms and carrier_terms:
                prompts.append(f"{material_terms[0]} {carrier_terms[0]} 商品实物图")
        elif category_id in {126, 127}:
            prompts.append(f"食品特产 商品实物图 {title}")
            prompts.append(f"包装食品 商品实物图 {title}")
        else:
            prompts.append(f"商品实物图 {title}")

        deduped: list[str] = []
        seen = set()
        for prompt in prompts:
            value = prompt.strip()
            if not value or value in seen:
                continue
            deduped.append(value)
            seen.add(value)
        return deduped[:4]

    def _get_display_hint(self, carrier: str) -> str:
        if carrier in IMAGE_FLAT_DISPLAY_CARRIERS:
            return "平铺"
        if carrier in IMAGE_FINISHED_DISPLAY_CARRIERS:
            return "成品"
        return "实物"
