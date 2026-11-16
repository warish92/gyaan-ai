"""Gyaan AI - Google ADK FastAPI Router.

Provides isolated REST endpoints for Google ADK execution, health inspection,
and evidence-based learning intelligence analysis.
"""

from datetime import datetime, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException, status

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
) -> LearningIntelligenceResponse:
    """Execute the Google ADK Learning Intelligence Agent on structured student evidence."""
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
