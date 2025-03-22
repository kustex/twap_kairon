import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logger(name: str = "twap", log_file: str = "twap.log", level=logging.INFO, max_bytes=1_000_000, backup_count=5):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / log_file

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        logger.addHandler(handler)
    logger.propagate = False

    return logger
