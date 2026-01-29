import logging
from pathlib import Path
from typing import Optional


def setup_logging(
    log_dir: Path,
    level: str = "INFO",
    name: Optional[str] = None,
    log_file: Optional[Path] = None,
) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    if log_file is None:
        log_file = log_dir / "run.log"

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    return logger
