"""Gyaan AI - Canonical Agents Package.

Exposes the eight genuine CrewAI Agent factory functions powered by local Ollama.
"""

from backend.agents.registry import agent_registry, AgentRegistry, AgentMetadata
from backend.agents.orchestrator import create_orchestrator_agent
from backend.agents.diagnostic import create_diagnostic_agent
from backend.agents.curriculum import create_curriculum_agent
from backend.agents.resource import create_resource_agent
from backend.agents.teacher import create_teacher_agent, get_local_llm, LOCAL_MODEL, OLLAMA_BASE_URL
from backend.agents.assessment import create_assessment_agent
from backend.agents.progress import create_progress_agent
from backend.agents.mentor import create_mentor_agent

__all__ = [
    # Canonical Agent Registry
    "agent_registry",
    "AgentRegistry",
    "AgentMetadata",
    # Eight Canonical CrewAI Agents
    "create_orchestrator_agent",
    "create_diagnostic_agent",
    "create_curriculum_agent",
    "create_resource_agent",
    "create_teacher_agent",
    "create_assessment_agent",
    "create_progress_agent",
    "create_mentor_agent",
    # Local LLM Infrastructure
    "get_local_llm",
    "LOCAL_MODEL",
    "OLLAMA_BASE_URL",
]
