"""Gyaan AI - Workflows Package.

Exposes canonical multi-agent CrewAI workflows:
- chapter_learning_journey: Complete 8-agent sequential learning journey with adaptive loop
- teacher_tutoring: Single-agent Socratic tutoring
- learning_plan: Diagnostic + Curriculum planning
- progress_mentoring: Progress analysis + Mentoring recommendations
"""

from workflows.chapter_learning_journey import (
    build_chapter_learning_journey_crew,
    run_chapter_learning_journey,
)
from backend.agents.crew import build_teacher_crew
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
from backend.agents.orchestrator import build_orchestrator_crew

__all__ = [
    # Canonical 8-Agent Chapter Learning Journey
    "build_chapter_learning_journey_crew",
    "run_chapter_learning_journey",
    # Specialized Workflows
    "build_teacher_crew",
    "build_learning_plan_crew",
    "run_learning_plan_workflow",
    "run_resource_workflow",
    "run_quiz_generation_workflow",
    "run_answer_evaluation_workflow",
    "build_progress_mentor_crew",
    "run_progress_analysis_workflow",
    "run_progress_and_mentor_workflow",
    "build_orchestrator_crew",
]
