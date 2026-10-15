"""Logging utilities for the Visual Impairment Support System (VISS)."""

import logging
import sys


def setup_logger(name: str = "viss", level: str = "INFO") -> logging.Logger:
    """Configures and returns a structured logger for the application.

    Args:
        name: Logger hierarchy name.
        level: Logging level string ('DEBUG', 'INFO', 'WARNING', 'ERROR').

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if setup_logger is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    return logger
