"""Gyaan AI - Observability & Monitoring FastAPI Router.

Provides REST endpoints for querying live multi-agent execution telemetry,
distributed traces, agent statuses, error records, and Langfuse connectivity.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from backend.observability.langfuse_client import langfuse_manager
from backend.observability.logger import JSONL_LOG_PATH
from backend.observability.schemas import (
    AgentStatusRecord,
    ObservabilityHealth,
    ObservabilityMetrics,
    TraceRecord,
)
from backend.observability.store import observability_store

logger = logging.getLogger("gyaan_ai.observability.service")

observability_router = APIRouter(
    prefix="/api/v1/observability",
    tags=["Observability & Monitoring"],
)


@observability_router.get("/health", response_model=ObservabilityHealth)
async def get_observability_health() -> ObservabilityHealth:
    """Returns the operational readiness and capacity of the observability subsystem."""
    traces_count = len(observability_store._traces_map)
    events_count = len(observability_store._events_deque)
    log_exists = JSONL_LOG_PATH.exists()

    return ObservabilityHealth(
        status="healthy",
        subsystem="Observability, Monitoring & Callbacks",
        version="Phase 4.0",
        langfuse_configured=bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")),
        langfuse_status=langfuse_manager.status(),
        buffered_traces=traces_count,
        buffered_events=events_count,
        log_file_present=log_exists,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@observability_router.get("/status")
async def get_observability_status() -> Dict[str, Any]:
    """Returns high-level runtime status of agents, telemetry buffers, and Langfuse integration."""
    metrics = observability_store.get_metrics()
    return {
        "status": "online",
        "subsystem": "Gyaan AI Observability Subsystem",
        "langfuse": {
            "status": langfuse_manager.status(),
            "enabled": langfuse_manager.is_enabled(),
        },
        "telemetry": {
            "active_traces": metrics.total_traces,
            "recorded_spans": metrics.total_spans,
            "recorded_events": metrics.total_events,
            "recorded_errors": metrics.total_errors,
            "error_rate": metrics.error_rate,
            "avg_trace_duration_ms": metrics.avg_trace_duration_ms,
        },
        "log_destination": str(JSONL_LOG_PATH),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@observability_router.get("/metrics", response_model=ObservabilityMetrics)
async def get_observability_metrics() -> ObservabilityMetrics:
    """Returns aggregated execution metrics across all recorded educational workflows."""
    return observability_store.get_metrics()


@observability_router.get("/traces", response_model=List[TraceRecord])
async def list_traces(
    limit: int = Query(50, ge=1, le=200, description="Max traces to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    status: Optional[str] = Query(None, description="Filter by status: started, completed, failed"),
) -> List[TraceRecord]:
    """Returns paginated distributed trace records in reverse chronological order."""
    return observability_store.list_traces(limit=limit, offset=offset, status=status)


@observability_router.get("/traces/{trace_id}", response_model=TraceRecord)
async def get_trace_by_id(trace_id: str) -> TraceRecord:
    """Retrieves a specific root trace record including all its child execution spans."""
    trace = observability_store.get_trace(trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace with ID '{trace_id}' was not found in active telemetry buffer.",
        )
    return trace


@observability_router.get("/agents", response_model=List[AgentStatusRecord])
async def get_agent_statuses() -> List[AgentStatusRecord]:
    """Returns operational telemetry, activity history, and error counts for all canonical agents."""
    return observability_store.get_agent_statuses()


@observability_router.get("/errors")
async def get_recent_errors(
    limit: int = Query(50, ge=1, le=200, description="Max error events to return"),
) -> List[Dict[str, Any]]:
    """Returns recent recorded operational failures and exceptions."""
    return observability_store.get_errors(limit=limit)
