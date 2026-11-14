"""Gyaan AI - Centralized CrewAI Lifecycle Callbacks & Distributed Trace Context.

Provides:
1. Concurrency-safe distributed trace context propagation via `contextvars.ContextVar`.
2. HTTP trace context extraction conforming to W3C `traceparent` and `X-Trace-Id`.
3. Context manager `trace_scope` for wrapping agent, task, tool, and workflow operations.
4. Privacy-conscious CrewAI callback factories for task, step, and crew kickoff lifecycles.
   (Strictly excludes hidden reasoning, chain-of-thought, and raw conversation text).
5. Centralized `attach_crewai_callbacks` helper for instrumenting all canonical agents.
"""

from __future__ import annotations

from contextlib import contextmanager
import contextvars
from datetime import datetime, timezone
import logging
import re
import time
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple
import uuid

from backend.observability.langfuse_client import langfuse_manager, normalize_trace_id
from backend.observability.logger import log_observability_event
from backend.observability.redaction import pseudonymize_student_id, redact_sensitive_data
from backend.observability.schemas import ObservabilityEvent, SpanRecord, TraceRecord
from backend.observability.store import observability_store

logger = logging.getLogger("gyaan_ai.observability.callbacks")

# Concurrency-safe ContextVar storage for distributed trace correlation
_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("gyaan_trace_id", default=None)
_span_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("gyaan_span_id", default=None)

# W3C traceparent regex: 00-{32hex}-{16hex}-{2hex}
TRACEPARENT_REGEX = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$", re.IGNORECASE)
HEX_32_REGEX = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


def get_current_trace_id() -> Optional[str]:
    """Retrieves the active root trace ID from concurrency-safe contextvars."""
    return _trace_id_var.get()


def set_current_trace_id(trace_id: Optional[str]) -> contextvars.Token:
    """Sets the active root trace ID in concurrency-safe contextvars."""
    return _trace_id_var.set(trace_id)


def get_current_span_id() -> Optional[str]:
    """Retrieves the active parent span ID from concurrency-safe contextvars."""
    return _span_id_var.get()


def set_current_span_id(span_id: Optional[str]) -> contextvars.Token:
    """Sets the active parent span ID in concurrency-safe contextvars."""
    return _span_id_var.set(span_id)


def reset_trace_id(token: contextvars.Token) -> None:
    """Resets the trace ID contextvar back to its prior state."""
    _trace_id_var.reset(token)


def reset_span_id(token: contextvars.Token) -> None:
    """Resets the span ID contextvar back to its prior state."""
    _span_id_var.reset(token)


def extract_http_trace_context(headers: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    """Extracts and validates trace_id and parent_span_id from HTTP request headers.

    Supports:
    1. W3C `traceparent` header (format: 00-<trace_id>-<parent_span_id>-01)
    2. Custom `X-Trace-Id` / `X-Parent-Span-Id` headers

    Returns:
        Tuple[Optional[trace_id], Optional[parent_span_id]]
    """
    if not headers or not isinstance(headers, dict):
        return None, None

    # Case-insensitive header lookup
    normalized_headers = {str(k).lower(): str(v) for k, v in headers.items()}

    # 1. Check W3C traceparent
    traceparent = normalized_headers.get("traceparent")
    if traceparent:
        match = TRACEPARENT_REGEX.match(traceparent.strip())
        if match:
            return match.group(1).lower(), match.group(2).lower()

    # 2. Check X-Trace-Id / X-Parent-Span-Id
    x_trace_id = normalized_headers.get("x-trace-id")
    if x_trace_id:
        clean_tid = x_trace_id.strip().lower().replace("-", "")
        if HEX_32_REGEX.match(clean_tid):
            parent_sid = normalized_headers.get("x-parent-span-id")
            clean_parent = parent_sid.strip().lower() if parent_sid else None
            return clean_tid, clean_parent

    return None, None


@contextmanager
def trace_scope(
    name: str,
    span_type: str = "agent",
    agent_name: Optional[str] = None,
    task_name: Optional[str] = None,
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    input_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Generator[SpanRecord, None, None]:
    """Context manager for observing an execution span.

    Measures execution time, creates span records, emits structured lifecycle events,
    records errors on failure, updates the bounded in-memory store, and streams telemetry
    to Langfuse if configured.

    Uses `contextvars.ContextVar` to guarantee proper async/await and thread propagation.
    """
    resolved_trace_id = trace_id or get_current_trace_id() or uuid.uuid4().hex
    normalized_tid = normalize_trace_id(resolved_trace_id)
    resolved_parent_span = parent_span_id or get_current_span_id()
    span_id = uuid.uuid4().hex[:16]

    # Set contextvars and keep tokens for reset
    tok_trace = set_current_trace_id(normalized_tid)
    tok_span = set_current_span_id(span_id)

    start_time_iso = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()

    clean_input = redact_sensitive_data(input_data or {})
    clean_metadata = redact_sensitive_data(metadata or {})

    # Start span record
    span_record = SpanRecord(
        span_id=span_id,
        parent_span_id=resolved_parent_span,
        trace_id=normalized_tid,
        name=name,
        span_type=span_type,
        agent_name=agent_name,
        task_name=task_name,
        status="started",
        start_time=start_time_iso,
        input_data=clean_input,
        metadata=clean_metadata,
    )

    # Emit start event
    log_observability_event(
        event_type=f"{span_type}_start",
        message=f"Started {span_type}: '{name}'",
        trace_id=normalized_tid,
        span_id=span_id,
        agent_name=agent_name,
        task_name=task_name,
        component="crewai" if span_type in ("agent", "task", "crew") else span_type,
        status="started",
        details=clean_input,
    )

    # Start Langfuse span if enabled
    langfuse_span_id = langfuse_manager.start_span(
        trace_id=normalized_tid,
        name=name,
        span_type=span_type,
        input_data=clean_input,
        metadata=clean_metadata,
        parent_span_id=resolved_parent_span,
    )

    try:
        yield span_record

        # Mark completed if not explicitly marked failed
        if span_record.status == "started":
            span_record.status = "completed"

    except Exception as exc:
        span_record.status = "failed"
        span_record.error = str(exc)
        span_record.error_category = type(exc).__name__
        raise

    finally:
        t1 = time.perf_counter()
        duration_ms = (t1 - t0) * 1000.0

        end_time_iso = datetime.now(timezone.utc).isoformat()
        span_record.end_time = end_time_iso
        span_record.duration_ms = round(duration_ms, 2)

        # Update bounded store
        observability_store.add_span_to_trace(normalized_tid, span_record)

        # Emit completion / failure event
        is_error = span_record.status == "failed"
        log_observability_event(
            event_type=f"{span_type}_failure" if is_error else f"{span_type}_complete",
            message=f"{'Failed' if is_error else 'Completed'} {span_type}: '{name}' ({duration_ms:.2f}ms)",
            trace_id=normalized_tid,
            span_id=span_id,
            agent_name=agent_name,
            task_name=task_name,
            component="crewai" if span_type in ("agent", "task", "crew") else span_type,
            status=span_record.status,
            duration_ms=round(duration_ms, 2),
            error_category=span_record.error_category,
            level="ERROR" if is_error else "INFO",
            details=redact_sensitive_data(span_record.output_data or {}),
        )

        # End Langfuse span
        token_usage_dict = span_record.token_usage.model_dump() if span_record.token_usage else None
        langfuse_manager.end_span(
            span_id=langfuse_span_id,
            output_data=redact_sensitive_data(span_record.output_data),
            status=span_record.status,
            error=span_record.error,
            token_usage=token_usage_dict,
        )

        # Concurrency-safe contextvar reset
        reset_trace_id(tok_trace)
        reset_span_id(tok_span)


# ------------------------------------------------------------------------------
# Centralized CrewAI Callback Hook Factories
# ------------------------------------------------------------------------------

def create_crewai_task_callback(
    trace_id: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> Callable[[Any], None]:
    """Constructs a Task callback function conforming to CrewAI's `task_callback` specification.

    Executed by CrewAI after task completion.
    Privacy Guarantee: Never captures raw student conversations, answers, or sensitive output text.
    Records safe execution metadata (task name, duration, token usage if reported, success state).
    """
    def _task_callback(output: Any) -> None:
        try:
            resolved_tid = trace_id or get_current_trace_id() or uuid.uuid4().hex
            normalized_tid = normalize_trace_id(resolved_tid)
            parent_sid = get_current_span_id()

            task_name = getattr(output, "name", None) or getattr(output, "description", "CrewAI Task")
            if isinstance(task_name, str) and len(task_name) > 80:
                task_name = task_name[:80] + "..."

            # Capture token usage if reported on the CrewAI output object (zero fabrication)
            tokens_info = None
            if hasattr(output, "token_usage") and output.token_usage:
                tu = output.token_usage
                tokens_info = {
                    "total_tokens": getattr(tu, "total_tokens", None),
                    "prompt_tokens": getattr(tu, "prompt_tokens", None),
                    "completion_tokens": getattr(tu, "completion_tokens", None),
                }

            # Create an explicit span record for this agent task to ensure invocation tracking
            task_span_id = uuid.uuid4().hex[:16]
            task_span = SpanRecord(
                span_id=task_span_id,
                parent_span_id=parent_sid,
                trace_id=normalized_tid,
                name=f"task:{task_name}",
                span_type="task",
                agent_name=agent_name,
                task_name=task_name,
                status="completed",
                start_time=datetime.now(timezone.utc).isoformat(),
                end_time=datetime.now(timezone.utc).isoformat(),
                duration_ms=0.0,
                metadata={"tokens": tokens_info},
            )
            observability_store.add_span_to_trace(normalized_tid, task_span)

            # Emit safe task completed event
            log_observability_event(
                event_type="task_complete",
                message=f"CrewAI task completed: '{task_name}' by '{agent_name or 'Agent'}'",
                trace_id=normalized_tid,
                span_id=task_span_id,
                agent_name=agent_name,
                task_name=task_name,
                component="crewai",
                status="completed",
                details={
                    "task": task_name,
                    "has_output": output is not None,
                    "tokens": tokens_info,
                },
            )
        except Exception as cb_exc:
            logger.debug("Task callback execution shielded from failure: %s", cb_exc)

    return _task_callback


def create_crewai_step_callback(
    trace_id: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> Callable[[Any], None]:
    """Constructs a Step callback conforming to CrewAI's `step_callback` specification.

    Executed by CrewAI after each intermediate agent step.
    Strict Privacy Guarantee: Never captures hidden chain-of-thought, internal reasoning,
    or detailed thought previews. Only records safe operational metadata (step count, tool name).
    """
    def _step_callback(step: Any) -> None:
        try:
            resolved_tid = trace_id or get_current_trace_id() or uuid.uuid4().hex
            normalized_tid = normalize_trace_id(resolved_tid)
            parent_sid = get_current_span_id()

            # Identify if step is a tool invocation without capturing reasoning text
            tool_name = None
            if hasattr(step, "tool"):
                tool_name = getattr(step, "tool")
            elif hasattr(step, "tool_name"):
                tool_name = getattr(step, "tool_name")

            log_observability_event(
                event_type="agent_step",
                message=f"Agent step executed for: '{agent_name or 'Agent'}'" + (f" [Tool: {tool_name}]" if tool_name else ""),
                trace_id=normalized_tid,
                span_id=parent_sid,
                agent_name=agent_name,
                component="crewai",
                status="running",
                details={
                    "action": "tool_invoked" if tool_name else "reasoning_step",
                    "tool": tool_name,
                },
            )
        except Exception as cb_exc:
            logger.debug("Step callback execution shielded from failure: %s", cb_exc)

    return _step_callback


def create_crewai_kickoff_callbacks(
    trace_id: Optional[str] = None,
    crew_name: str = "EducationalCrew",
) -> Tuple[List[Callable[[Dict[str, Any]], Dict[str, Any]]], List[Callable[[Any], Any]]]:
    """Constructs before and after kickoff callbacks for Crew instances.

    Privacy Guarantee: Never logs raw input text, student queries, or raw output conversations.
    """
    def _before_kickoff(inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            resolved_tid = trace_id or get_current_trace_id() or uuid.uuid4().hex
            normalized_tid = normalize_trace_id(resolved_tid)

            # Record safe metadata only
            safe_inputs = {}
            if isinstance(inputs, dict):
                for k in ("subject", "grade", "chapter", "topic", "lesson_mode"):
                    if k in inputs and inputs[k]:
                        safe_inputs[k] = inputs[k]

            log_observability_event(
                event_type="crew_kickoff",
                message=f"Crew execution starting: '{crew_name}'",
                trace_id=normalized_tid,
                agent_name=crew_name,
                component="crewai",
                status="started",
                details=safe_inputs,
            )
        except Exception as cb_exc:
            logger.debug("Before kickoff callback shielded from failure: %s", cb_exc)
        return inputs

    def _after_kickoff(output: Any) -> Any:
        try:
            resolved_tid = trace_id or get_current_trace_id() or uuid.uuid4().hex
            normalized_tid = normalize_trace_id(resolved_tid)

            log_observability_event(
                event_type="crew_complete",
                message=f"Crew execution completed: '{crew_name}'",
                trace_id=normalized_tid,
                agent_name=crew_name,
                component="crewai",
                status="completed",
                details={"has_output": output is not None},
            )
        except Exception as cb_exc:
            logger.debug("After kickoff callback shielded from failure: %s", cb_exc)
        return output

    return [_before_kickoff], [_after_kickoff]


def attach_crewai_callbacks(
    crew_kwargs: Dict[str, Any],
    agent_name: str,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Centralized, idempotent lifecycle callback attachment for all CrewAI agents and crews.

    Ensures all eight canonical agents receive:
    - task_callback (for task completion and token telemetry)
    - step_callback (for intermediate operational steps without reasoning text)
    - before_kickoff_callbacks (for crew execution start)
    - after_kickoff_callbacks (for crew execution completion)

    Guarantees:
    - Idempotency: Never duplicates callbacks if already set.
    - Dynamic trace resolution: Resolves trace ID from contextvars at runtime if not set.
    - Non-blocking error shielding: Telemetry failures never interrupt educational workflows.
    """
    try:
        # Check idempotency
        if "task_callback" in crew_kwargs and crew_kwargs["task_callback"] is not None:
            return crew_kwargs

        crew_kwargs["task_callback"] = create_crewai_task_callback(trace_id=trace_id, agent_name=agent_name)
        crew_kwargs["step_callback"] = create_crewai_step_callback(trace_id=trace_id, agent_name=agent_name)

        before_cbs, after_cbs = create_crewai_kickoff_callbacks(trace_id=trace_id, crew_name=agent_name)
        crew_kwargs["before_kickoff_callbacks"] = before_cbs
        crew_kwargs["after_kickoff_callbacks"] = after_cbs

    except Exception as exc:
        logger.debug("Observability callback attachment shielded from failure: %s", exc)

    return crew_kwargs
