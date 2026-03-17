"""This module exists to configure consistent logging across the application. It sets up both console and file handlers so runs are auditable. Possible improvement: add rotating log files and structured JSON logs, but that is out of scope for now."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logger(level: str = "INFO", file_path: str = "logs/scraper.log") -> logging.Logger:
    # Ensure the log directory exists before configuring handlers.
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("frontier_safco_scraper")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    # Clear handlers to avoid duplicate logs in multi-run sessions.
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console output for local debugging and visibility.
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File output for audit and post-run review.
    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger