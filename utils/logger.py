"""utils/logger.py — 结构化日志（输出到 stderr，不污染 stdout 判分）。"""

from __future__ import annotations

import logging
import sys

from config import CONFIG

_LEVEL = getattr(logging, str(CONFIG.get("log_level", "INFO")).upper(), logging.INFO)


def get_logger(name: str = "math_agent") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(_LEVEL)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
