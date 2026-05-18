import os
import sys
from pathlib import Path

from loguru import logger


_logger_initialized = False


def init_logger(log_path: Path) -> None:
    global _logger_initialized
    if _logger_initialized:
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=level)
    logger.add(log_path, rotation="10 MB", retention="30 days", level=level)
    _logger_initialized = True
