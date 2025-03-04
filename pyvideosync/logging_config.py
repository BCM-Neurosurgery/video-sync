import os
import logging
import pytz
from datetime import datetime

central = pytz.timezone("US/Central")


def get_current_ts() -> str:
    return datetime.now(central).strftime("%Y%m%d_%H%M%S")


def configure_logging(log_dir: str) -> logging.Logger:
    """
    Configures and returns a logger with both console and file handlers.

    This function creates a logger that logs messages to both the console (stdout) and
    a log file stored in the specified directory. The log file is named using the
    current timestamp. The function ensures the log directory exists before creating
    the log file.

    Args:
        log_dir (str): The directory where log files will be stored.

    Returns:
        logging.Logger: A configured logger instance.

    Logging Levels:
        - Console handler (`StreamHandler`): Logs messages at INFO level and above.
        - File handler (`FileHandler`): Logs messages at DEBUG level and above.

    Log Format:
        - "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
          Example: "2025-03-04 12:00:00,000 - module_name - INFO - Log message"

    Notes:
        - Uses the `get_current_ts()` function to generate a timestamp for the log filename.
        - Ensures the log directory exists before writing logs.
    """
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
