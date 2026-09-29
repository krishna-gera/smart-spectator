"""
Smart Spectator - Structured Logging and Log Rotation Module
Conforms to Sections 22 & 23 of Master Implementation Prompt.
Never logs tokens, passwords, private recordings, or raw Authorization headers.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
from typing import Optional

from services.hub_backend.config import settings

# Regex patterns to sanitize sensitive credentials
SENSITIVE_PATTERNS = [
    (re.compile(r"ss_tok_[a-zA-Z0-9_\-]+"), "ss_tok_***REDACTED***"),
    (re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]+"), r"\1***REDACTED***"),
    (re.compile(r"('auth_token'|\"auth_token\"):\s*['\"][^'\"]+['\"]"), r"\1: '***REDACTED***'"),
    (re.compile(r"('password'|\"password\"):\s*['\"][^'\"]+['\"]"), r"\1: '***REDACTED***'"),
    (re.compile(r"('verification_code'|\"verification_code\"):\s*['\"][^'\"]+['\"]"), r"\1: '***REDACTED***'"),
]


class SensitiveDataFilter(logging.Filter):
    """Sanitizes log messages by masking authentication tokens, passwords, and secrets."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            sanitized = record.msg
            for pattern, repl in SENSITIVE_PATTERNS:
                sanitized = pattern.sub(repl, sanitized)
            record.msg = sanitized
        return True


def setup_logging(
    log_dir: Optional[Path] = None,
    log_level: Optional[str] = None,
    max_bytes: Optional[int] = None,
    backup_count: Optional[int] = None,
) -> logging.Logger:
    """
    Configures structured console and rotating file logging for the Hub backend.
    """
    target_dir = log_dir or settings.LOGS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "hub.log"

    level_str = log_level or settings.LOG_LEVEL
    level = getattr(logging, level_str.upper(), logging.INFO)

    file_max_bytes = max_bytes or settings.LOG_MAX_BYTES
    file_backup_count = backup_count or settings.LOG_BACKUP_COUNT

    logger = logging.getLogger("smart_spectator")
    logger.setLevel(level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] [%(module)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        data_filter = SensitiveDataFilter()

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(data_filter)
        logger.addHandler(console_handler)

        # Rotating file handler
        try:
            file_handler = RotatingFileHandler(
                filename=str(log_file),
                maxBytes=file_max_bytes,
                backupCount=file_backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(data_filter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Fallback to console only if filesystem permission prevents file log
            logger.warning(f"Could not initialize rotating file logger at {log_file}: {e}")

    return logger


# Global logger instance
logger = setup_logging()
