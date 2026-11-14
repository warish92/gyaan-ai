"""Gyaan AI - Observability, Monitoring & Langfuse Pydantic Schemas.

Defines standardized Pydantic v2 domain schemas for distributed trace records,
child execution spans, lifecycle events, telemetry metrics, and health indicators.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SpanType(str, Enum):
    """Categorical classification of an execution span."""
    WORKFLOW = "workflow"
    CREW = "crew"
    AGENT = "agent"
    TASK = "task"
    TOOL = "tool"
    ADK = "adk"
    A2A = "a2a"
    MCP = "mcp"
    SYSTEM = "system"


class SpanStatus(str, Enum):
    """Execution status of a span or trace."""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TokenUsage(BaseModel):
    """Genuine token usage details when reported by the model provider."""
    model_config = ConfigDict(extra="ignore")

    prompt_tokens: Optional[int] = Field(None, ge=0, description="Tokens used in prompt")
    completion_tokens: Optional[int] = Field(None, ge=0, description="Tokens generated in completion")
    total_tokens: Optional[int] = Field(None, ge=0, description="Total tokens utilized")
    cost_usd: Optional[float] = Field(None, ge=0.0, description="Calculated USD cost if known")
    is_estimated: bool = Field(default=False, description="Whether usage was estimated rather than exact")


class SpanRecord(BaseModel):
    """Discrete unit of work within a distributed trace."""
    model_config = ConfigDict(extra="ignore")

    span_id: str = Field(..., description="Unique span identifier")
    parent_span_id: Optional[str] = Field(None, description="Parent span ID if nested")
    trace_id: str = Field(..., description="Associated root trace identifier")
    name: str = Field(..., description="Human-readable name of the operation")
    span_type: str = Field(default="system", description="Type of span: workflow, agent, task, tool, etc.")
    agent_name: Optional[str] = Field(None, description="Canonical name of the agent responsible")
    task_name: Optional[str] = Field(None, description="Name of the task being executed")
    status: str = Field(default="started", description="Execution status: started, completed, failed")
    start_time: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of span start"
    )
    end_time: Optional[str] = Field(None, description="ISO 8601 UTC timestamp of span completion")
    duration_ms: Optional[float] = Field(None, ge=0.0, description="Execution duration in milliseconds")
    input_data: Optional[Dict[str, Any]] = Field(None, description="Sanitized input arguments or prompt context")
    output_data: Optional[Dict[str, Any]] = Field(None, description="Sanitized output results")
    error: Optional[str] = Field(None, description="Error message if span failed")
    error_category: Optional[str] = Field(None, description="Categorical error code if applicable")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom execution metadata and tags")
    token_usage: Optional[TokenUsage] = Field(None, description="Token usage data when genuinely available")


class TraceRecord(BaseModel):
    """Root trace representing an end-to-end educational operation or workflow."""
    model_config = ConfigDict(extra="ignore")

    trace_id: str = Field(..., description="Globally unique root trace identifier")
    root_name: str = Field(..., description="Name of the originating workflow or endpoint")
    workflow_id: Optional[str] = Field(None, description="Workflow identifier if registered")
    student_id: Optional[str] = Field(None, description="Sanitized student identifier")
    session_id: Optional[str] = Field(None, description="Learning session identifier")
    status: str = Field(default="started", description="Trace status: started, completed, failed")
    start_time: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of trace start"
    )
    end_time: Optional[str] = Field(None, description="ISO 8601 UTC timestamp of trace completion")
    duration_ms: Optional[float] = Field(None, ge=0.0, description="Total trace execution duration in milliseconds")
    total_spans: int = Field(default=0, ge=0, description="Count of spans recorded under this trace")
    error_count: int = Field(default=0, ge=0, description="Count of failed spans in this trace")
    spans: List[SpanRecord] = Field(default_factory=list, description="Ordered list of child spans")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Root trace metadata and correlation context")


class ObservabilityEvent(BaseModel):
    """Point-in-time lifecycle event emitted during multi-agent execution."""
    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(..., description="Unique event identifier")
    trace_id: str = Field(..., description="Associated root trace ID")
    span_id: Optional[str] = Field(None, description="Associated span ID if applicable")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of event"
    )
    event_type: str = Field(..., description="Event type: agent_start, task_complete, mcp_call, etc.")
    agent_name: Optional[str] = Field(None, description="Originating agent name")
    task_name: Optional[str] = Field(None, description="Originating task name")
    component: str = Field(default="crewai", description="Subsystem component: crewai, adk, a2a, mcp, api")
    level: str = Field(default="INFO", description="Log level: INFO, WARNING, ERROR")
    message: str = Field(default="", description="Descriptive human-readable event message")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Sanitized event payload")


class AgentStatusRecord(BaseModel):
    """Telemetry and operational status for an individual canonical agent."""
    model_config = ConfigDict(extra="ignore")

    agent_name: str = Field(..., description="Canonical agent name")
    canonical_role: str = Field(..., description="Educational role and responsibility")
    total_invocations: int = Field(default=0, ge=0, description="Total invocations recorded")
    total_errors: int = Field(default=0, ge=0, description="Total errors recorded")
    last_active: Optional[str] = Field(None, description="ISO 8601 UTC timestamp of last activity")
    avg_duration_ms: float = Field(default=0.0, ge=0.0, description="Average span duration in ms")
    status: str = Field(default="idle", description="Current status: idle, active, error")


class ObservabilityMetrics(BaseModel):
    """Aggregated system metrics across all observed traces and spans."""
    model_config = ConfigDict(extra="ignore")

    total_traces: int = Field(default=0, ge=0, description="Total root traces recorded")
    total_spans: int = Field(default=0, ge=0, description="Total child spans recorded")
    total_events: int = Field(default=0, ge=0, description="Total lifecycle events recorded")
    total_errors: int = Field(default=0, ge=0, description="Total error events or failed spans")
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Error rate percentage (0.0 to 1.0)")
    avg_trace_duration_ms: float = Field(default=0.0, ge=0.0, description="Average trace duration in milliseconds")
    traces_by_status: Dict[str, int] = Field(default_factory=dict, description="Count of traces per status")
    spans_by_type: Dict[str, int] = Field(default_factory=dict, description="Count of spans per span type")
    agent_activity: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Summary per agent")


class ObservabilityHealth(BaseModel):
    """Subsystem health, connectivity, and capacity indicators."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(default="healthy", description="Status: healthy, degraded, offline")
    subsystem: str = Field(default="Observability, Monitoring & Callbacks")
    version: str = Field(default="Phase 4.0")
    langfuse_configured: bool = Field(default=False, description="Whether Langfuse credentials are provided")
    langfuse_status: str = Field(default="disabled", description="Langfuse status: enabled, disabled, unreachable")
    buffered_traces: int = Field(default=0, ge=0, description="Number of traces in bounded buffer")
    buffered_events: int = Field(default=0, ge=0, description="Number of events in bounded buffer")
    log_file_present: bool = Field(default=False, description="Whether JSONL log file is writable")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of health check"
    )
