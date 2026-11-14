"""Structured JSON logging (AGENTS.md §8).

Every line carries ``request_id`` and ``stage``. Never pass file bytes, the full
question text (at INFO or above) or secrets as fields. As a last line of defence,
the formatter masks the values of known secret environment variables.

    from blueprint_qa.common.log import get_logger, log_event
    log = get_logger(__name__)
    log_event(log, "llm_call", request_id=rid, stage=Stage.QUESTION, tokens_in=120)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

from blueprint_qa.contracts import Stage

SECRET_ENV_VARS: tuple[str, ...] = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
_FIELDS_ATTR = "bp_fields"
_configured = False


def _mask_secrets(text: str) -> str:
    for name in SECRET_ENV_VARS:
        value = os.environ.get(name)
        if value and len(value) >= 8:
            text = text.replace(value, "***")
    return text


class JsonFormatter(logging.Formatter):
    """Render a record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": None,
            "stage": None,
        }
        fields = getattr(record, _FIELDS_ATTR, None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return _mask_secrets(json.dumps(payload, ensure_ascii=False, default=str))


def configure_logging(level: str | None = None) -> None:
    """Install the JSON handler on the ``blueprint_qa`` logger (idempotent)."""
    global _configured
    root = logging.getLogger("blueprint_qa")
    root.setLevel((level or os.environ.get("BP_LOG_LEVEL") or "INFO").upper())
    if not _configured:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
        root.propagate = False
        _configured = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name if name.startswith("blueprint_qa") else f"blueprint_qa.{name}")


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    request_id: str,
    stage: Stage,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Log one structured event with the mandatory ``request_id`` and ``stage``."""
    data: dict[str, Any] = {"request_id": request_id, "stage": stage.value, **fields}
    logger.log(level, event, extra={_FIELDS_ATTR: data})
