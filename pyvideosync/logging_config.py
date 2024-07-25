import os
import logging
import pytz
from datetime import datetime

central = pytz.timezone("US/Central")


def get_current_ts() -> str:
    return datetime.now(central).strftime("%Y%m%d_%H%M%S")


def configure_logging(log_dir: str) -> logging.Logger:
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    current_time = get_current_ts()
    log_file_path = os.path.join(log_dir, f"log_{current_time}.log")

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    c_handler = logging.StreamHandler()
    f_handler = logging.FileHandler(log_file_path)

    c_handler.setLevel(logging.INFO)
    f_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    c_handler.setFormatter(formatter)
    f_handler.setFormatter(formatter)

    logger.addHandler(c_handler)
    logger.addHandler(f_handler)

    return logger
