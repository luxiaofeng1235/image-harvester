from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def setup_logger(logs_dir: Path, run_id: str | None = None) -> tuple[logging.Logger, Path, str]:
    run_key = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"run_{run_key}.log"
    logger = logging.getLogger(f"ai_goods_pipeline.{run_key}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger, log_path, run_key

