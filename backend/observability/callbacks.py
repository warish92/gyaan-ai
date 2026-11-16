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
_gyaan_workflow_active_var: contextvars.ContextVar[bool] = contextvars.ContextVar("gyaan_workflow_active", default=False)

# W3C traceparent regex: 00-{32hex}-{16hex}-{2hex}
TRACEPARENT_REGEX = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$", re.IGNORECASE)
HEX_32_REGEX = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)

EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)

# ------------------------------------------------------------------------------
# Canonical Agent Mappings & Static Task Allowlist
# ------------------------------------------------------------------------------
EXACT_CANONICAL_ROLES = {
    "Educational AI Workflow Orchestrator",
    "Evidence-Based Student Learning Diagnostic Specialist",
    "Evidence-Grounded Curriculum Planning Specialist",
    "Educational Resource Retrieval Specialist",
    "Class 10 CBSE Science Teacher and Concept Specialist",
    "Educational Assessment and Feedback Specialist",
    "Student Learning Progress Analyst",
    "Personalized Student Learning Mentor",
}

CANONICAL_ROLE_TO_LABEL = {
    "Educational AI Workflow Orchestrator": "Orchestrator",
    "Evidence-Based Student Learning Diagnostic Specialist": "Diagnostic Specialist",
    "Evidence-Grounded Curriculum Planning Specialist": "Curriculum Specialist",
    "Educational Resource Retrieval Specialist": "Resource Specialist",
    "Class 10 CBSE Science Teacher and Concept Specialist": "Teacher Specialist",
    "Educational Assessment and Feedback Specialist": "Assessment Specialist",
    "Student Learning Progress Analyst": "Progress Specialist",
    "Personalized Student Learning Mentor": "Mentor Specialist",
}

CANONICAL_SPECIALIST_STATIC_TASK_NAMES = {
    "Educational AI Workflow Orchestrator": "workflow_routing_task",
    "Evidence-Based Student Learning Diagnostic Specialist": "learning_diagnostic_task",
    "Evidence-Grounded Curriculum Planning Specialist": "curriculum_sequencing_task",
    "Educational Resource Retrieval Specialist": "resource_retrieval_task",
    "Class 10 CBSE Science Teacher and Concept Specialist": "concept_instruction_task",
    "Educational Assessment and Feedback Specialist": "assessment_evaluation_task",
    "Student Learning Progress Analyst": "progress_analysis_task",
    "Personalized Student Learning Mentor": "pedagogical_mentoring_task",
}


def datetime_to_nanoseconds_exact(dt: datetime) -> int:
    """Converts naive local or timezone-aware datetimes to integer nanoseconds since Unix epoch.

    Guarantees zero floating-point precision loss using integer timedelta decomposition.
    """
    if dt.tzinfo is None:
        dt_utc = dt.astimezone(timezone.utc)
    else:
        dt_utc = dt.astimezone(timezone.utc)

    delta = dt_utc - EPOCH_UTC
    total_seconds = delta.days * 86400 + delta.seconds
    return (total_seconds * 1_000_000_000) + (delta.microseconds * 1_000)


def is_gyaan_workflow_active() -> bool:
    """Returns True if execution is currently inside an authorized Gyaan AI workflow."""
    return _gyaan_workflow_active_var.get()


def set_gyaan_workflow_active(active: bool = True) -> contextvars.Token:
    """Sets the Gyaan AI workflow active flag and returns the reset token."""
    return _gyaan_workflow_active_var.set(active)


def reset_gyaan_workflow_active(token: contextvars.Token) -> None:
    """Resets the Gyaan AI workflow active contextvar back to its prior state."""
    _gyaan_workflow_active_var.reset(token)


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

            # Ensure Gyaan AI workflow active flag is set for child tasks
            _gyaan_workflow_active_var.set(True)

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


def setup_class_level_task_instrumentation() -> None:
    """Idempotently instruments CrewAI Task.execute_sync at the class level.

    Enforces:
    1. Exact canonical role matching for all eight agents.
    2. Explicit Gyaan AI workflow ContextVar gating.
    3. Immutable static task-name allowlist.
    4. Correct Langfuse parent-child trace relationships.
    5. Privacy-safe metadata only (zero PII, zero raw student prompts/responses/descriptions).
    6. Omit token usage entirely from task observations.
    7. Bare raise for exceptions, preserving traceback and educational execution.
    8. Shielded non-blocking Langfuse telemetry.
    """
    import asyncio
    from crewai.task import Task
    from crewai.tasks.task_output import TaskOutput

    if getattr(Task, "_gyaan_class_instrumented", False):
        return

    original_execute_sync = Task.execute_sync

    def _instrumented_execute_sync(self: Task, *args: Any, **kwargs: Any) -> TaskOutput:
        # Gate 1: Gyaan AI workflow context must be active
        if not _gyaan_workflow_active_var.get():
            return original_execute_sync(self, *args, **kwargs)

        # Gate 2: Active Langfuse trace ID must be set
        active_trace_id = _trace_id_var.get()
        if not active_trace_id:
            return original_execute_sync(self, *args, **kwargs)

        # Gate 3: Agent role must strictly match canonical specialist set
        raw_role = getattr(self.agent, "role", None) if getattr(self, "agent", None) else None
        if raw_role not in EXACT_CANONICAL_ROLES:
            return original_execute_sync(self, *args, **kwargs)

        agent_label = CANONICAL_ROLE_TO_LABEL.get(raw_role, "Specialist Agent")
        static_task_name = CANONICAL_SPECIALIST_STATIC_TASK_NAMES.get(raw_role, "specialist_task")
        parent_obs_id = _span_id_var.get()

        span_obj = None
        if langfuse_manager.is_enabled():
            span_obj = langfuse_manager.start_task_observation(
                trace_id=active_trace_id,
                parent_span_id=parent_obs_id,
                name=f"agent:{agent_label}:{static_task_name}",
                metadata={
                    "agent_role": agent_label,
                    "task_name": static_task_name,
                    "model": "qwen2.5:3b",
                    "framework": "crewai",
                },
            )

        try:
            task_output: TaskOutput = original_execute_sync(self, *args, **kwargs)

            if span_obj:
                end_ns = datetime_to_nanoseconds_exact(self.end_time) if getattr(self, "end_time", None) else None
                langfuse_manager.end_task_observation(
                    span_obj=span_obj,
                    end_time_ns=end_ns,
                    status_message="SUCCESS",
                    level="DEFAULT",
                    metadata={
                        "crewai_task_execution_duration_seconds": getattr(self, "execution_duration", None),
                        "output_format": getattr(task_output, "output_format", "RAW"),
                        "output_character_count": len(task_output.raw) if hasattr(task_output, "raw") else 0,
                    },
                )

            return task_output

        except asyncio.CancelledError:
            if span_obj:
                langfuse_manager.end_task_observation(
                    span_obj=span_obj,
                    end_time_ns=None,
                    status_message="CANCELLED: Task execution cancelled by runtime",
                    level="ERROR",
                    metadata={"cancelled": True, "task_incomplete": True},
                )
            raise

        except (KeyboardInterrupt, SystemExit):
            if span_obj:
                try:
                    span_obj.end()
                except BaseException:
                    pass
            raise

        except Exception as exc:
            if span_obj:
                end_ns = datetime_to_nanoseconds_exact(self.end_time) if getattr(self, "end_time", None) else None
                langfuse_manager.end_task_observation(
                    span_obj=span_obj,
                    end_time_ns=end_ns,
                    status_message=f"{type(exc).__name__}: Execution failure",
                    level="ERROR",
                    metadata={
                        "error_type": type(exc).__name__,
                        "failure": True,
                        "task_incomplete": getattr(self, "end_time", None) is None,
                        "crewai_task_execution_duration_seconds": getattr(self, "execution_duration", None),
                    },
                )
            raise

    Task.execute_sync = _instrumented_execute_sync
    Task._gyaan_class_instrumented = True


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
        # Activate class-level CrewAI task execution telemetry
        setup_class_level_task_instrumentation()

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
