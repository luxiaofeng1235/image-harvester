from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from ai_goods_pipeline.utils.retry import retry_call
from ai_goods_pipeline.utils.text import extract_json_array_payload


class QwenClientError(Exception):
    """Base error for Qwen API issues."""


class QwenParseError(QwenClientError):
    """Raised when the model output cannot be parsed as a JSON array."""

    def __init__(self, message: str, raw_content: str = "") -> None:
        super().__init__(message)
        self.raw_content = raw_content


@dataclass(slots=True)
class QwenGenerationResult:
    model: str
    raw_content: str
    items: list[dict[str, Any]]
    response_payload: dict[str, Any]


class QwenClient:
    def __init__(
        self,
        *,
        open_url: str,
        api_key: str,
        temperature: float,
        max_tokens: int,
        timeout: int = 60,
    ) -> None:
        self.open_url = open_url
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.session = requests.Session()

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
    ) -> QwenGenerationResult:
        def _request() -> dict[str, Any]:
            response = self.session.post(
                self.open_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

        try:
            payload = retry_call(_request, retries=3)
        except Exception as exc:  # pragma: no cover - network dependent
            raise QwenClientError(f"qwen_request_failed: {exc}") from exc

        try:
            raw_content = payload["choices"][0]["message"]["content"]
        except Exception as exc:
            raise QwenClientError("qwen_response_missing_content") from exc

        if isinstance(raw_content, list):
            raw_content = "".join(
                str(block.get("text", ""))
                for block in raw_content
                if isinstance(block, dict)
            )
        raw_content = str(raw_content)

        try:
            items = extract_json_array_payload(raw_content)
        except Exception as exc:
            raise QwenParseError(str(exc), raw_content=raw_content) from exc

        return QwenGenerationResult(
            model=model,
            raw_content=raw_content,
            items=items,
            response_payload=payload,
        )
