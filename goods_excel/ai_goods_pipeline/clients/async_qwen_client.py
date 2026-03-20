from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ai_goods_pipeline.utils.async_retry import async_retry_call
from ai_goods_pipeline.utils.text import extract_json_array_payload


class AsyncQwenClientError(Exception):
    """Base error for async Qwen API issues."""


class AsyncQwenParseError(AsyncQwenClientError):
    """Raised when the model output cannot be parsed as a JSON array."""

    def __init__(self, message: str, raw_content: str = "") -> None:
        super().__init__(message)
        self.raw_content = raw_content


@dataclass(slots=True)
class AsyncQwenGenerationResult:
    model: str
    raw_content: str
    items: list[dict[str, Any]]
    response_payload: dict[str, Any]


class AsyncQwenClient:
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
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self) -> None:
        await self.client.aclose()

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
    ) -> AsyncQwenGenerationResult:
        async def _request() -> dict[str, Any]:
            response = await self.client.post(
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
            )
            response.raise_for_status()
            return response.json()

        try:
            payload = await async_retry_call(_request, retries=3)
        except Exception as exc:
            raise AsyncQwenClientError(f"qwen_request_failed: {exc}") from exc

        try:
            raw_content = payload["choices"][0]["message"]["content"]
        except Exception as exc:
            raise AsyncQwenClientError("qwen_response_missing_content") from exc

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
            raise AsyncQwenParseError(str(exc), raw_content=raw_content) from exc

        return AsyncQwenGenerationResult(
            model=model,
            raw_content=raw_content,
            items=items,
            response_payload=payload,
        )
