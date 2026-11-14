"""Gyaan AI - Observability, Monitoring, Callbacks & Langfuse Integration.

Phase 4 Observability Architecture:
- Thread-safe bounded in-memory trace and span store.
- Structured JSON logging with size-bounded log rotation.
- PII and sensitive credential redaction.
- CrewAI task, step, and crew lifecycle callbacks.
- Official Langfuse SDK integration with zero-impact fallback.
- Cross-framework trace propagation across CrewAI, ADK, A2A, and MCP.
- FastAPI monitoring and metrics REST endpoints.
"""

from backend.observability.callbacks import (
    attach_crewai_callbacks,
    create_crewai_kickoff_callbacks,
    create_crewai_step_callback,
    create_crewai_task_callback,
    extract_http_trace_context,
    get_current_span_id,
    get_current_trace_id,
    reset_span_id,
    reset_trace_id,
    set_current_span_id,
    set_current_trace_id,
    trace_scope,
)
from backend.observability.langfuse_client import LangfuseManager, langfuse_manager, normalize_trace_id
from backend.observability.logger import (
    JSONL_LOG_PATH,
    get_observability_logger,
    log_observability_event,
    obs_logger,
)
from backend.observability.redaction import pseudonymize_student_id, redact_sensitive_data
from backend.observability.schemas import (
    AgentStatusRecord,
    ObservabilityEvent,
    ObservabilityHealth,
    ObservabilityMetrics,
    SpanRecord,
    SpanStatus,
    SpanType,
    TokenUsage,
    TraceRecord,
)
from backend.observability.service import observability_router
from backend.observability.store import ObservabilityStore, observability_store

__all__ = [
    "observability_router",
    "observability_store",
    "ObservabilityStore",
    "langfuse_manager",
    "LangfuseManager",
    "normalize_trace_id",
    "get_observability_logger",
    "log_observability_event",
    "obs_logger",
    "JSONL_LOG_PATH",
    "redact_sensitive_data",
    "pseudonymize_student_id",
    "trace_scope",
    "get_current_trace_id",
    "set_current_trace_id",
    "get_current_span_id",
    "set_current_span_id",
    "reset_trace_id",
    "reset_span_id",
    "extract_http_trace_context",
    "attach_crewai_callbacks",
    "create_crewai_task_callback",
    "create_crewai_step_callback",
    "create_crewai_kickoff_callbacks",
    "TraceRecord",
    "SpanRecord",
    "ObservabilityEvent",
    "TokenUsage",
    "ObservabilityMetrics",
    "AgentStatusRecord",
    "ObservabilityHealth",
    "SpanType",
    "SpanStatus",
]
