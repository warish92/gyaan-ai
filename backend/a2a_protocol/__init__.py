"""Gyaan AI - Agent-to-Agent (A2A) Protocol Subsystem.

Provides bidirectional interoperability between the CrewAI multi-agent architecture
and Google Agent Development Kit (ADK) architecture using the official A2A protocol.
"""

from backend.a2a_protocol.schemas import (
    A2AErrorResponse,
    A2ATaskMetadata,
    AgentExecutionMetadata,
    LearningAnalysisA2ARequest,
    LearningAnalysisA2AResponse,
    LearningAnalysisArtifact,
)
from backend.a2a_protocol.client import (
    A2AClientError,
    A2AAuthenticationError,
    A2ADiscoveryError,
    A2AOrchestratorClient,
    A2AServerError,
    A2ATimeoutError,
    A2AValidationError,
    a2a_orchestrator_client,
)
from backend.a2a_protocol.server import (
    a2a_router,
    a2a_task_store,
    build_learning_intelligence_agent_card,
)

__all__ = [
    "A2AClientError",
    "A2AAuthenticationError",
    "A2ADiscoveryError",
    "A2AErrorResponse",
    "A2AOrchestratorClient",
    "A2AServerError",
    "A2ATaskMetadata",
    "A2ATimeoutError",
    "A2AValidationError",
    "AgentExecutionMetadata",
    "LearningAnalysisA2ARequest",
    "LearningAnalysisA2AResponse",
    "LearningAnalysisArtifact",
    "a2a_orchestrator_client",
    "a2a_router",
    "a2a_task_store",
    "build_learning_intelligence_agent_card",
]
