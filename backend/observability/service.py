"""Gyaan AI - Observability & Monitoring FastAPI Router.

Provides REST endpoints for querying live multi-agent execution telemetry,
distributed traces, agent statuses, error records, and Langfuse connectivity.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hmac
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status

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


def verify_observability_access(request: Request) -> Dict[str, Any]:
    """Verify that caller has administrative, internal, or active authenticated access to system telemetry."""
    # 1. Check internal token
    internal_header = request.headers.get("X-Internal-Token") or request.headers.get("X-A2A-Internal-Token")
    expected_secret = os.environ.get("A2A_INTERNAL_SECRET")
    if internal_header and expected_secret and hmac.compare_digest(internal_header.strip(), expected_secret.strip()):
        return {"id": "internal_telemetry", "role": "internal"}

    # 2. Check Bearer token or HttpOnly cookie
    raw_token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        raw_token = auth_header[7:].strip()
    if not raw_token:
        raw_token = request.cookies.get("gyaan_auth_token")

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access system telemetry and observability records.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from backend.services.auth_service import hash_session_token
    from backend.db.database import get_session_by_token_hash

    try:
        token_hash = hash_session_token(raw_token)
        session = get_session_by_token_hash(token_hash)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked session token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        expires_at_dt = datetime.fromisoformat(session["expires_at"])
        if expires_at_dt < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session token has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return session
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token format.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@observability_router.get("/status")
async def get_observability_status(request: Request) -> Dict[str, Any]:
    """Returns high-level runtime status of agents, telemetry buffers, and Langfuse integration."""
    verify_observability_access(request)
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
async def get_observability_metrics(request: Request) -> ObservabilityMetrics:
    """Returns aggregated execution metrics across all recorded educational workflows."""
    verify_observability_access(request)
    return observability_store.get_metrics()


@observability_router.get("/traces", response_model=List[TraceRecord])
async def list_traces(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="Max traces to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    status: Optional[str] = Query(None, description="Filter by status: started, completed, failed"),
) -> List[TraceRecord]:
    """Returns paginated distributed trace records in reverse chronological order."""
    verify_observability_access(request)
    return observability_store.list_traces(limit=limit, offset=offset, status=status)


@observability_router.get("/traces/{trace_id}", response_model=TraceRecord)
async def get_trace_by_id(trace_id: str, request: Request) -> TraceRecord:
    """Retrieves a specific root trace record including all its child execution spans."""
    verify_observability_access(request)
    trace = observability_store.get_trace(trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace with ID '{trace_id}' was not found in active telemetry buffer.",
        )
    return trace


@observability_router.get("/agents", response_model=List[AgentStatusRecord])
async def get_agent_statuses(request: Request) -> List[AgentStatusRecord]:
    """Returns operational telemetry, activity history, and error counts for all canonical agents."""
    verify_observability_access(request)
    return observability_store.get_agent_statuses()


@observability_router.get("/errors")
async def get_recent_errors(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="Max error events to return"),
) -> List[Dict[str, Any]]:
    """Returns recent recorded operational failures and exceptions."""
    verify_observability_access(request)
    return observability_store.get_errors(limit=limit)
