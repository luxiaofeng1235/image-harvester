from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
import time


class _ElapsedTimeFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self._started_at = time.perf_counter()

    def filter(self, record: logging.LogRecord) -> bool:
        record.elapsed_seconds = time.perf_counter() - self._started_at
        return True


def setup_logger(logs_dir: Path, run_id: str | None = None) -> tuple[logging.Logger, Path, str]:
    run_key = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"run_{run_key}.log"
    logger = logging.getLogger(f"ai_goods_pipeline.{run_key}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s +%(elapsed_seconds).3fs [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    elapsed_filter = _ElapsedTimeFilter()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(elapsed_filter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(elapsed_filter)
    logger.addHandler(stream_handler)
    return logger, log_path, run_key

