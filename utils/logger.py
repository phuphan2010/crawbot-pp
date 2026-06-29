import sys
from pathlib import Path
from loguru import logger


def setup_logger(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "scraper.log",
        level=level,
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )

    debug_dir = log_dir / "debug"
    debug_dir.mkdir(exist_ok=True)
