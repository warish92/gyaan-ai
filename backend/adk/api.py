"""Gyaan AI - Google ADK FastAPI Router.

Provides isolated REST endpoints for Google ADK execution, health inspection,
and evidence-based learning intelligence analysis.
"""

from datetime import datetime, timezone
import hmac
import logging
import os
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status

import google.adk
from backend.adk.config import ADK_MODEL_NAME
from backend.adk.schemas.adk_messages import (
    ADKHealthResponse,
    LearningIntelligenceRequest,
    LearningIntelligenceResponse,
)
from backend.adk.services.adk_runner import adk_learning_service

logger = logging.getLogger("gyaan_ai.adk.api")

adk_router = APIRouter(prefix="/api/v1/adk", tags=["Google ADK"])


def verify_adk_caller_auth(request: Request, student_id: str) -> Dict[str, Any]:
    """Verify that caller has valid session matching the student_id or valid internal service token."""
    # 1. Check internal token
    internal_header = request.headers.get("X-Internal-Token") or request.headers.get("X-A2A-Internal-Token")
    expected_secret = os.environ.get("A2A_INTERNAL_SECRET")
    if internal_header and expected_secret and hmac.compare_digest(internal_header.strip(), expected_secret.strip()):
        return {"id": "internal_service", "role": "internal"}

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
            detail="Authentication required for Google ADK learning intelligence analysis.",
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

        caller_student_id = session.get("student_id")
        if caller_student_id != student_id and session.get("role") not in ("admin", "teacher"):
            logger.warning(
                "ADK IDOR violation: authenticated student '%s' attempted analysis for '%s'",
                caller_student_id,
                student_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You cannot run learning intelligence analysis for another student.",
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


@adk_router.get("/health", response_model=ADKHealthResponse)
async def get_adk_health() -> ADKHealthResponse:
    """Check health and status of the Google ADK subsystem."""
    return ADKHealthResponse(
        status="healthy",
        adk_version=getattr(google.adk, "__version__", "2.14.0"),
        framework="Google Agent Development Kit (ADK)",
        model=ADK_MODEL_NAME,
        active_sessions_count=adk_learning_service.get_active_sessions_count(),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@adk_router.post("/learning-analysis", response_model=LearningIntelligenceResponse)
async def run_learning_analysis(
    request: LearningIntelligenceRequest,
    req: Request = None,
) -> LearningIntelligenceResponse:
    """Execute the Google ADK Learning Intelligence Agent on structured student evidence."""
    if req is not None:
        verify_adk_caller_auth(req, request.student_id)
    try:
        response = await adk_learning_service.analyze_learning(request)
        return response
    except PermissionError as pe:
        logger.warning("Session isolation violation: %s", str(pe))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(pe),
        )
    except ValueError as ve:
        logger.warning("Validation failure in ADK analysis: %s", str(ve))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as e:
        logger.exception("Unexpected error in ADK learning-analysis: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google ADK execution error: {type(e).__name__} - {str(e)}",
        )
