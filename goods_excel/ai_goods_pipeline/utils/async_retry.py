from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar


T = TypeVar("T")


async def async_retry_call(
    func: Callable[[], Awaitable[T]],
    retries: int,
    delays: list[float] | None = None,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    if retries < 1:
        raise ValueError("retries must be >= 1")

    delays = delays or [0.5, 1, 2]
    last_error: BaseException | None = None

    for attempt in range(1, retries + 1):
        try:
            return await func()
        except retry_exceptions as exc:
            last_error = exc
            if attempt >= retries:
                break
            delay = delays[min(attempt - 1, len(delays) - 1)]
            await asyncio.sleep(delay)

    assert last_error is not None
    raise last_error
