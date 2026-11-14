"""Gyaan AI Agents Package."""

from backend.agents.registry import (
    agent_registry,
    AgentRegistry,
    AgentMetadata,
)
from backend.agents.teacher import create_teacher_agent
from backend.agents.crew import build_teacher_crew
from backend.agents.diagnostic import create_diagnostic_agent, create_diagnostic_task
from backend.agents.curriculum import create_curriculum_agent, create_curriculum_task
from backend.agents.resource import create_resource_agent, create_resource_task
from backend.agents.assessment import (
    create_assessment_agent,
    create_quiz_generation_task,
    create_answer_evaluation_task,
)
from backend.agents.progress import create_progress_agent, create_progress_analysis_task
from backend.agents.mentor import create_mentor_agent, create_mentor_recommendation_task
from backend.agents.workflow import (
    build_learning_plan_crew,
    run_learning_plan_workflow,
    run_resource_workflow,
    run_quiz_generation_workflow,
    run_answer_evaluation_workflow,
)
from backend.agents.progress_workflow import (
    build_progress_mentor_crew,
    run_progress_analysis_workflow,
    run_progress_and_mentor_workflow,
)
from backend.agents.orchestrator import (
    create_orchestrator_agent,
    create_orchestrator_task,
    build_orchestrator_crew,
    run_orchestrator_routing,
    execute_orchestrated_pipeline,
    WORKFLOW_REGISTRY,
    WorkflowDescriptor,
)

__all__ = [
    "agent_registry",
    "AgentRegistry",
    "AgentMetadata",
    "create_teacher_agent",
    "build_teacher_crew",
    "create_diagnostic_agent",
    "create_diagnostic_task",
    "create_curriculum_agent",
    "create_curriculum_task",
    "create_resource_agent",
    "create_resource_task",
    "create_assessment_agent",
    "create_quiz_generation_task",
    "create_answer_evaluation_task",
    "create_progress_agent",
    "create_progress_analysis_task",
    "create_mentor_agent",
    "create_mentor_recommendation_task",
    "create_orchestrator_agent",
    "create_orchestrator_task",
    "build_orchestrator_crew",
    "run_orchestrator_routing",
    "execute_orchestrated_pipeline",
    "WORKFLOW_REGISTRY",
    "WorkflowDescriptor",
    "build_learning_plan_crew",
    "run_learning_plan_workflow",
    "run_resource_workflow",
    "run_quiz_generation_workflow",
    "run_answer_evaluation_workflow",
    "build_progress_mentor_crew",
    "run_progress_analysis_workflow",
    "run_progress_and_mentor_workflow",
]

