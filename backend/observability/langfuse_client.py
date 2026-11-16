"""Gyaan AI - Langfuse Client Adapter.

Provides official, version-compatible Langfuse 4.x telemetry integration for
multi-agent educational workflows. Operates in zero-failure mode: if credentials
are missing, disabled, or if remote telemetry fails, learning workflows continue
uninterrupted.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, Optional
import uuid

from backend.observability.redaction import redact_sensitive_data

logger = logging.getLogger("gyaan_ai.observability.langfuse")


def _is_truthy(val: Optional[str]) -> bool:
    """Checks whether an environment variable string represents True."""
    if not val:
        return False
    return val.strip().lower() in ("1", "true", "yes", "on", "enable", "enabled")


def normalize_trace_id(tid: Optional[str]) -> str:
    """Ensures a trace ID is a valid 32-character lowercase hex string compliant with W3C / Langfuse."""
    if not tid:
        return uuid.uuid4().hex

    clean = tid.replace("-", "").replace("_", "").lower()
    if len(clean) == 32:
        try:
            int(clean, 16)
            return clean
        except ValueError:
            pass

    # If it is a prefixed or arbitrary ID, hash/deterministic hex or generate uuid
    import hashlib
    return hashlib.md5(tid.encode("utf-8")).hexdigest()


class LangfuseManager:
    """Manages official Langfuse client lifecycle and telemetry event dispatch."""

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._enabled: bool = False
        self._lock = threading.Lock()
        self._active_spans: Dict[str, Any] = {}
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initializes the official Langfuse client using environment credentials."""
        enabled_env = os.environ.get("LANGFUSE_ENABLED")
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"

        # Explicit disable check
        if enabled_env is not None and not _is_truthy(enabled_env):
            self._enabled = False
            self._client = None
            logger.info("Langfuse observability is explicitly disabled via LANGFUSE_ENABLED.")
            return

        # Check if genuine credentials exist
        if not public_key or not secret_key:
            self._enabled = False
            self._client = None
            logger.info("Langfuse credentials not configured; operating in disabled/mock-free mode.")
            return

        try:
            from langfuse import Langfuse
            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
                tracing_enabled=True,
                debug=False,
            )
            self._enabled = True
            logger.info("Official Langfuse client initialized successfully for host: %s", host)
        except Exception as exc:
            logger.warning("Failed to initialize Langfuse client (non-critical): %s", exc)
            self._client = None
            self._enabled = False

    def is_enabled(self) -> bool:
        """Returns True only if Langfuse is configured, enabled, and initialized."""
        return self._enabled and self._client is not None

    def status(self) -> str:
        """Returns the operational status of the Langfuse client."""
        if not self._enabled:
            return "disabled"
        return "enabled" if self._client is not None else "error"

    def start_span(
        self,
        trace_id: str,
        name: str,
        span_type: str = "span",
        input_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent_span_id: Optional[str] = None,
    ) -> Optional[str]:
        """Starts a new Langfuse observation span associated with the root trace_id."""
        if not self.is_enabled():
            return None

        clean_trace_id = normalize_trace_id(trace_id)
        sanitized_input = redact_sensitive_data(input_data or {})
        sanitized_meta = redact_sensitive_data(metadata or {})

        try:
            trace_context = {"trace_id": clean_trace_id}
            if parent_span_id:
                clean_parent = parent_span_id[-16:] if len(parent_span_id) >= 16 else parent_span_id.zfill(16)
                trace_context["parent_span_id"] = clean_parent

            span_obj = self._client.start_observation(
                name=name,
                as_type="generation" if span_type in ("llm", "generation") else "span",
                trace_context=trace_context,
                input=sanitized_input,
                metadata=sanitized_meta,
            )

            span_id = span_obj.id
            with self._lock:
                self._active_spans[span_id] = span_obj

            return span_id
        except Exception as exc:
            logger.debug("Failed to start Langfuse observation span (non-critical): %s", exc)
            return None

    def end_span(
        self,
        span_id: Optional[str],
        output_data: Optional[Dict[str, Any]] = None,
        status: str = "completed",
        error: Optional[str] = None,
        token_usage: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Ends an active Langfuse observation span, recording output, errors, and genuine tokens."""
        if not span_id or not self.is_enabled():
            return

        with self._lock:
            span_obj = self._active_spans.pop(span_id, None)

        if not span_obj:
            return

        sanitized_output = redact_sensitive_data(output_data or {})
        level = "ERROR" if status == "failed" or error else "DEFAULT"

        update_kwargs: Dict[str, Any] = {
            "output": sanitized_output,
            "level": level,
        }
        if error:
            update_kwargs["status_message"] = str(error)

        # Only pass token usage if genuinely available from model provider
        if token_usage and isinstance(token_usage, dict):
            update_kwargs["usage_details"] = token_usage

        try:
            span_obj.update(**update_kwargs)
            span_obj.end()
        except Exception as exc:
            logger.debug("Failed to complete Langfuse span (non-critical): %s", exc)

    def start_task_observation(
        self,
        trace_id: str,
        parent_span_id: Optional[str],
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """Starts an agent-level task observation directly returning the observation object.

        Privacy guarantee: input=None, output=None, usage_details=None.
        Zero-failure guarantee: Telemetry exceptions are caught and never raise into learning workflows.
        """
        if not self.is_enabled():
            return None

        clean_trace_id = normalize_trace_id(trace_id)
        sanitized_meta = redact_sensitive_data(metadata or {})

        try:
            trace_context: Dict[str, str] = {"trace_id": clean_trace_id}
            if parent_span_id:
                clean_parent = parent_span_id[-16:] if len(parent_span_id) >= 16 else parent_span_id.zfill(16)
                trace_context["parent_span_id"] = clean_parent

            span_obj = self._client.start_observation(
                name=name,
                as_type="agent",
                trace_context=trace_context,
                metadata=sanitized_meta,
            )
            return span_obj
        except Exception as exc:
            logger.debug("Failed to start Langfuse task observation (non-critical): %s", exc)
            return None

    def end_task_observation(
        self,
        span_obj: Any,
        end_time_ns: Optional[int] = None,
        status_message: str = "SUCCESS",
        level: str = "DEFAULT",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Ends an active agent-level task observation.

        Privacy guarantee: output=None, usage_details=None.
        Zero-failure guarantee: Telemetry exceptions are shielded and non-blocking.
        """
        if not span_obj or not self.is_enabled():
            return

        sanitized_meta = redact_sensitive_data(metadata or {})
        try:
            span_obj.update(
                level=level,
                status_message=status_message,
                output=None,
                metadata=sanitized_meta,
                usage_details=None,
            )
            if end_time_ns is not None:
                span_obj.end(end_time=end_time_ns)
            else:
                span_obj.end()
        except Exception as exc:
            logger.debug("Failed to end Langfuse task observation (non-critical): %s", exc)

    def flush(self) -> None:
        """Flushes telemetry buffer in a non-blocking try-catch."""
        if not self.is_enabled():
            return
        try:
            self._client.flush()
        except Exception as exc:
            logger.debug("Langfuse flush encountered error (non-critical): %s", exc)

    def shutdown(self) -> None:
        """Gracefully shuts down Langfuse background threads."""
        if not self.is_enabled():
            return
        try:
            self._client.shutdown()
        except Exception as exc:
            logger.debug("Langfuse shutdown encountered error (non-critical): %s", exc)


# Global singleton instance
langfuse_manager = LangfuseManager()
