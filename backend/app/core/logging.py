"""Structured logging setup.

EntryX uses JSON-format structured logs at INFO+ so that every subsystem
(API, WS, trading, AI) can be correlated via request/connection IDs. Secrets
never pass through the logger.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "user_id", "connection_id", "component", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class RedactingFilter(logging.Filter):
    """Redact sensitive fields from log records."""

    SENSITIVE_PATTERNS = [
        "password",
        "secret",
        "token",
        "authorization",
        "api_key",
        "access_token",
        "encryption_key",
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern in self.SENSITIVE_PATTERNS:
                idx = record.msg.lower().find(pattern)
                if idx != -1:
                    record.msg = record.msg[:idx + len(pattern)] + "=[REDACTED]"
                    break
        return True


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def get_logger(name: str, component: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if component:
        logger = logging.LoggerAdapter(logger, {"component": component})
    return logger
