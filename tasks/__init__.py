"""Gyaan AI - Canonical Tasks Package.

Provides centralized exports for all CrewAI Task creation functions across the 8 agents.
"""

from backend.agents.chapter_journey import (
    create_orchestrator_journey_task,
    create_diagnostic_journey_task,
    create_curriculum_journey_task,
    create_resource_journey_task,
    create_teacher_journey_task,
    create_assessment_journey_task,
    create_progress_journey_task,
    create_mentor_journey_task,
)
from backend.agents.crew import create_teacher_task
from backend.agents.diagnostic import create_diagnostic_task
from backend.agents.curriculum import create_curriculum_task
from backend.agents.resource import create_resource_task
from backend.agents.assessment import (
    create_quiz_generation_task,
    create_answer_evaluation_task,
)
from backend.agents.progress import create_progress_analysis_task
from backend.agents.mentor import create_mentor_recommendation_task
from backend.agents.orchestrator import create_orchestrator_task

__all__ = [
    # Sequential Journey Tasks (Process.sequential with Context passing)
    "create_orchestrator_journey_task",
    "create_diagnostic_journey_task",
    "create_curriculum_journey_task",
    "create_resource_journey_task",
    "create_teacher_journey_task",
    "create_assessment_journey_task",
    "create_progress_journey_task",
    "create_mentor_journey_task",
    # Specialized Single/Dual-Agent Tasks
    "create_orchestrator_task",
    "create_teacher_task",
    "create_diagnostic_task",
    "create_curriculum_task",
    "create_resource_task",
    "create_quiz_generation_task",
    "create_answer_evaluation_task",
    "create_progress_analysis_task",
    "create_mentor_recommendation_task",
]
