"""Gyaan AI - Google Agent Development Kit (ADK) Module.

Provides genuine Google ADK multi-agent capabilities alongside the existing CrewAI architecture.
"""

from backend.adk.api import adk_router
from backend.adk.config import get_adk_model
from backend.adk.agents.learning_analysis_agent import (
    create_learning_intelligence_agent,
)
from backend.adk.services.adk_runner import (
    ADKLearningIntelligenceService,
    adk_learning_service,
)

__all__ = [
    "adk_router",
    "get_adk_model",
    "create_learning_intelligence_agent",
    "ADKLearningIntelligenceService",
    "adk_learning_service",
]
