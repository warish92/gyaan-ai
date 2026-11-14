"""Gyaan AI - Structured JSON Observability Logger.

Provides standardized JSON log formatting, PII and secret redaction,
and size-bounded log rotation for distributed agent tracing.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from backend.observability.redaction import redact_sensitive_data

# Ensure logs directory exists
LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
JSONL_LOG_PATH = LOGS_DIR / "observability.jsonl"


class JsonObservabilityFormatter(logging.Formatter):
    """Formats log records as structured, single-line JSON with redacted content."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "component": getattr(record, "component", "crewai"),
            "agent_name": getattr(record, "agent_name", None),
            "task_name": getattr(record, "task_name", None),
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
            "event_type": getattr(record, "event_type", "log"),
            "status": getattr(record, "status", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "error_category": getattr(record, "error_category", None),
        }

        # Include custom extra metadata if supplied
        extra_data = getattr(record, "extra_data", None)
        if extra_data and isinstance(extra_data, dict):
            payload["details"] = extra_data

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Redact credentials and PII before serialization
        sanitized_payload = redact_sensitive_data(payload)
        return json.dumps(sanitized_payload)


_file_handler: Optional[RotatingFileHandler] = None


def get_observability_logger(name: str = "gyaan_ai.observability") -> logging.Logger:
    """Returns a configured logger with the structured JSON rotating file handler."""
    global _file_handler
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        if _file_handler is None:
            _file_handler = RotatingFileHandler(
                filename=str(JSONL_LOG_PATH),
                maxBytes=5 * 1024 * 1024,  # 5 MB per file
                backupCount=3,  # Keep up to 3 rolled backups
                encoding="utf-8",
            )
            _file_handler.setFormatter(JsonObservabilityFormatter())

        logger.addHandler(_file_handler)
        logger.setLevel(logging.INFO)

    return logger


obs_logger = get_observability_logger()


def log_observability_event(
    event_type: str,
    message: str,
    trace_id: str,
    span_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    task_name: Optional[str] = None,
    component: str = "crewai",
    status: Optional[str] = None,
    duration_ms: Optional[float] = None,
    error_category: Optional[str] = None,
    level: str = "INFO",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Emits a structured JSON log entry and registers an ObservabilityEvent in store."""
    from backend.observability.schemas import ObservabilityEvent
    from backend.observability.store import observability_store

    clean_details = redact_sensitive_data(details or {})

    # Emit via logging system
    extra = {
        "component": component,
        "agent_name": agent_name,
        "task_name": task_name,
        "trace_id": trace_id,
        "span_id": span_id,
        "event_type": event_type,
        "status": status,
        "duration_ms": duration_ms,
        "error_category": error_category,
        "extra_data": clean_details,
    }

    log_fn = obs_logger.info
    if level == "WARNING":
        log_fn = obs_logger.warning
    elif level in ("ERROR", "CRITICAL"):
        log_fn = obs_logger.error
    elif level == "DEBUG":
        log_fn = obs_logger.debug

    log_fn(message, extra=extra)

    # Record event into in-memory store
    event = ObservabilityEvent(
        event_id=f"evt_{uuid.uuid4().hex[:12]}",
        trace_id=trace_id,
        span_id=span_id,
        event_type=event_type,
        agent_name=agent_name,
        task_name=task_name,
        component=component,
        level=level,
        message=message,
        payload=clean_details,
    )
    observability_store.record_event(event)
