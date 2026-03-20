from __future__ import annotations

import time
from typing import Callable, TypeVar


T = TypeVar("T")


def retry_call(
    func: Callable[[], T],
    retries: int,
    delays: list[float] | None = None,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    if retries < 1:
        raise ValueError("retries must be >= 1")

    delays = delays or [1, 2, 4]
    last_error: BaseException | None = None

    for attempt in range(1, retries + 1):
        try:
            return func()
        except retry_exceptions as exc:
            last_error = exc
            if attempt >= retries:
                break
            delay = delays[min(attempt - 1, len(delays) - 1)]
            time.sleep(delay)

    assert last_error is not None
    raise last_error

