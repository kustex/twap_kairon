import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str = "twap", log_file: str = "twap.log", level=logging.INFO, max_bytes=1_000_000, backup_count=5):
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        logger.addHandler(handler)
    logger.propagate = False

    return logger
