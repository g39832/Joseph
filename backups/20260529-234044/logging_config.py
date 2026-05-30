"""
configs/logging_config.py
--------------------------
Centralized logging configuration for JOSEPH.

Sets up:
- Console handler (colored, human-readable)
- File handler (rotating, machine-readable)
- Per-module log levels

Import and call setup_logging() once at startup in main.py.
"""

import logging
import logging.handlers
from pathlib import Path

from configs.settings import settings


def setup_logging() -> None:
    """
    Configure the logging system for JOSEPH.

    Creates:
    - A rotating file log at logs/joseph.log (10MB max, 5 backups)
    - A console log for INFO+ messages

    Call this ONCE at the very start of main.py before anything else.
    """
    # Ensure log directory exists
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything; handlers filter

    # ------------------------------------------------------------------ #
    # File Handler — rotating, captures DEBUG+
    # ------------------------------------------------------------------ #
    file_handler = None
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(settings.LOG_FILE),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    except Exception as e:
        # In restricted environments the log file may be unwritable.
        # Fall back to console-only logging so startup still succeeds.
        logging.getLogger(__name__).warning(f"File logging disabled: {e}")

    # ------------------------------------------------------------------ #
    # Console Handler — INFO+ only, cleaner format
    # ------------------------------------------------------------------ #
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    console_handler.setFormatter(
        logging.Formatter(
            fmt="%(levelname)-8s %(name)s: %(message)s",
        )
    )

    # Add handlers to root logger
    if file_handler:
        root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # ------------------------------------------------------------------ #
    # Silence noisy third-party loggers
    # ------------------------------------------------------------------ #
    noisy_loggers = [
        "httpx",
        "httpcore",
        "urllib3",
        "asyncio",
        "chromadb",
        "chromadb.telemetry",
        "onnxruntime",
        "sentence_transformers",
        "transformers",
        "torch",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Logging initialized — level={settings.LOG_LEVEL}, "
        f"file={settings.LOG_FILE}"
    )
