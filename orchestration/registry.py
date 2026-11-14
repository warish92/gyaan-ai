"""Gyaan AI - Central Workflow Registry.

Declares canonical approved workflows and their executing agents.
"""

from typing import Dict
from backend.agents.orchestrator import WORKFLOW_REGISTRY, WorkflowDescriptor
from backend.agents.registry import agent_registry, AgentRegistry, AgentMetadata

__all__ = [
    "WORKFLOW_REGISTRY",
    "WorkflowDescriptor",
    "agent_registry",
    "AgentRegistry",
    "AgentMetadata",
]
