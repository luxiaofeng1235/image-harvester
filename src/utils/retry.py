import time
from typing import Callable, Type, Tuple


def retry(
    attempts: int = 3,
    backoff: float = 0.5,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
):
    def decorator(fn: Callable):
        def wrapper(*args, **kwargs):
            delay = backoff
            for i in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except exceptions:
                    if i >= attempts - 1:
                        raise
                    time.sleep(delay)
                    delay *= 2
        return wrapper
    return decorator
