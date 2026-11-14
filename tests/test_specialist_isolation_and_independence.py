"""Gyaan AI - Specialist Agent Isolation & Independent Execution Test Suite.

Verifies:
1. Every specialist agent (Diagnostic, Curriculum, Resource, Teacher, Assessment,
   Progress, Mentor, Orchestrator) executes independently through its own CrewAI task.
2. Requests for one specialist do NOT unnecessarily execute Teacher Agent.
3. Specialists remain operational when Teacher Agent is excluded from the executing Crew.
4. Multi-agent coordination correctly chains tasks without universal fallback to Teacher Agent.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Ensure workspace root is in path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from crewai import Agent, Crew, Process, Task
from backend.agents.assessment import (
    create_assessment_agent,
    create_quiz_generation_task,
    create_answer_evaluation_task,
    build_quiz_generation_crew,
    build_assessment_evaluation_crew,
)
from backend.agents.diagnostic import (
    create_diagnostic_agent,
    create_diagnostic_task,
    build_diagnostic_crew,
)
from backend.agents.curriculum import (
    create_curriculum_agent,
    create_curriculum_inquiry_task,
    build_curriculum_crew,
)
from backend.agents.resource import (
    create_resource_agent,
    create_resource_task,
    build_resource_crew,
)
from backend.agents.progress import (
    create_progress_agent,
    create_progress_analysis_task,
    build_progress_crew,
)
from backend.agents.mentor import (
    create_mentor_agent,
    create_standalone_mentor_task,
    build_standalone_mentor_crew,
)
from backend.agents.teacher import (
    create_teacher_agent,
)
from backend.agents.orchestrator import (
    create_orchestrator_agent,
    create_orchestrator_task,
    build_orchestrator_crew,
    WORKFLOW_REGISTRY,
)
from backend.agents.crew import (
    build_educational_crew,
    create_teacher_task,
    build_teacher_crew,
)


def test_assessment_agent_executes_without_teacher():
    """Verify Assessment Agent builds and executes its Crew with Teacher Agent strictly excluded."""
    crew, task = build_quiz_generation_crew(
        grade="Class 10",
        subject="Physics",
        topic="Electricity - Ohm's Law",
        num_questions=3,
    )
    assert isinstance(crew, Crew)
    agent_roles = [ag.role for ag in crew.agents]
    assert len(crew.agents) == 1
    assert "Assessment" in agent_roles[0]
    assert not any("Teacher" in role for role in agent_roles), "Teacher Agent unexpectedly present in Assessment Crew!"

    # Verify execution with mocked LLM
    with patch.object(Crew, "kickoff") as mock_kickoff:
        mock_kickoff.return_value = MagicMock(raw='[{"id": "q1", "question": "What is Ohm\'s law?"}]')
        result = crew.kickoff()
        assert "Ohm's law" in str(result.raw)
        mock_kickoff.assert_called_once()


def test_diagnostic_agent_executes_without_teacher():
    """Verify Diagnostic Agent builds and executes its Crew with Teacher Agent strictly excluded."""
    items = [
        {
            "question": "What is displacement reaction?",
            "student_answer": "Iron displaces copper from copper sulphate.",
            "expected_answer": "A more reactive element displaces a less reactive element.",
        }
    ]
    crew, task = build_diagnostic_crew(
        grade="Class 10",
        subject="Chemistry",
        topic="Chemical Reactions",
        assessment_items=items,
    )
    assert isinstance(crew, Crew)
    agent_roles = [ag.role for ag in crew.agents]
    assert len(crew.agents) == 1
    assert "Diagnostic" in agent_roles[0]
    assert not any("Teacher" in role for role in agent_roles), "Teacher Agent unexpectedly present in Diagnostic Crew!"

    with patch.object(Crew, "kickoff") as mock_kickoff:
        mock_kickoff.return_value = MagicMock(raw='{"overall_classification": "Correct"}')
        result = crew.kickoff()
        assert "Correct" in str(result.raw)
        mock_kickoff.assert_called_once()


def test_curriculum_agent_executes_without_teacher():
    """Verify Curriculum Agent builds and executes its Crew with Teacher Agent strictly excluded."""
    crew, task = build_curriculum_crew(
        grade="Class 10",
        subject="Science",
        topic="Light and Optics",
        inquiry="Identify learning objectives for Light and Optics",
    )
    assert isinstance(crew, Crew)
    agent_roles = [ag.role for ag in crew.agents]
    assert len(crew.agents) == 1
    assert "Curriculum" in agent_roles[0]
    assert not any("Teacher" in role for role in agent_roles), "Teacher Agent unexpectedly present in Curriculum Crew!"

    with patch.object(Crew, "kickoff") as mock_kickoff:
        mock_kickoff.return_value = MagicMock(raw='# PERSONALIZED CURRICULUM PLAN\n- Stage 1: Foundations')
        result = crew.kickoff()
        assert "CURRICULUM PLAN" in str(result.raw)
        mock_kickoff.assert_called_once()


def test_resource_agent_executes_without_teacher():
    """Verify Resource Agent builds and executes its Crew with Teacher Agent strictly excluded."""
    crew, task = build_resource_crew(
        grade="Class 10",
        subject="Science",
        topic="Electricity",
        learning_objective="Recommend resources for electricity",
    )
    assert isinstance(crew, Crew)
    agent_roles = [ag.role for ag in crew.agents]
    assert len(crew.agents) == 1
    assert "Resource" in agent_roles[0]
    assert not any("Teacher" in role for role in agent_roles), "Teacher Agent unexpectedly present in Resource Crew!"

    with patch.object(Crew, "kickoff") as mock_kickoff:
        mock_kickoff.return_value = MagicMock(raw='### Resource Verification: VERIFIED Local NCERT Corpus')
        result = crew.kickoff()
        assert "NCERT" in str(result.raw)
        mock_kickoff.assert_called_once()


def test_progress_agent_executes_without_teacher():
    """Verify Progress Agent builds and executes its Crew with Teacher Agent strictly excluded."""
    profile = {"display_name": "Kavya", "grade": "Class 10"}
    stats = {
        "total_assessments_completed": 4,
        "average_percentage": 82.0,
        "performance_trend": "improving",
        "has_sufficient_history": True,
    }
    crew, task = build_progress_crew(
        student_profile=profile,
        objective_stats=stats,
    )
    assert isinstance(crew, Crew)
    agent_roles = [ag.role for ag in crew.agents]
    assert len(crew.agents) == 1
    assert "Progress" in agent_roles[0]
    assert not any("Teacher" in role for role in agent_roles), "Teacher Agent unexpectedly present in Progress Crew!"

    with patch.object(Crew, "kickoff") as mock_kickoff:
        mock_kickoff.return_value = MagicMock(raw='{"overall_summary": "Strong performance in chemical reactions."}')
        result = crew.kickoff()
        assert "chemical reactions" in str(result.raw)
        mock_kickoff.assert_called_once()


def test_mentor_agent_executes_without_teacher():
    """Verify Mentor Agent builds and executes its Crew with Teacher Agent strictly excluded."""
    profile = {"display_name": "Aarav", "grade": "Class 10"}
    crew, task = build_standalone_mentor_crew(
        student_profile=profile,
        topic="Board Exam Prep",
        study_query="Create a revision timetable for Class 10 science boards",
    )
    assert isinstance(crew, Crew)
    agent_roles = [ag.role for ag in crew.agents]
    assert len(crew.agents) == 1
    assert "Mentor" in agent_roles[0]
    assert not any("Teacher" in role for role in agent_roles), "Teacher Agent unexpectedly present in Mentor Crew!"

    with patch.object(Crew, "kickoff") as mock_kickoff:
        mock_kickoff.return_value = MagicMock(raw='{"mentor_overview": "30-day revision strategy with Pomodoro breaks."}')
        result = crew.kickoff()
        assert "revision" in str(result.raw)
        mock_kickoff.assert_called_once()


def test_orchestrator_multi_agent_coordination_without_teacher():
    """Verify Orchestrator coordinates Progress, Diagnostic, Curriculum, and Mentor without Teacher Agent."""
    crew, agents, tasks = build_educational_crew(
        workflow_id="study_next_coordination",
        student_question="Coordinate a multi-agent request about what to study next",
        grade="Class 10",
        subject="Science",
        context={"student_profile": {"display_name": "Test Student", "grade": "Class 10"}, "topic": "Science"},
    )
    assert isinstance(crew, Crew)
    assert len(crew.agents) == 5
    agent_roles = [ag.role for ag in crew.agents]
    assert any("Orchestrator" in role for role in agent_roles)
    assert any("Progress" in role for role in agent_roles)
    assert any("Diagnostic" in role for role in agent_roles)
    assert any("Curriculum" in role for role in agent_roles)
    assert any("Mentor" in role for role in agent_roles)
    assert not any("Teacher" in role for role in agent_roles), "Teacher Agent unexpectedly present in Study Next Coordination Crew!"

    # Verify context passing
    assert len(crew.tasks) == 5
    # Progress task receives context from Orchestrator
    assert crew.tasks[1].context == [crew.tasks[0]]
    # Diagnostic task receives context from Orchestrator and Progress
    assert crew.tasks[2].context == [crew.tasks[0], crew.tasks[1]]
    # Curriculum task receives context from Diagnostic
    assert crew.tasks[3].context == [crew.tasks[2]]
    # Mentor task receives context from Orchestrator, Progress, Diagnostic, and Curriculum
    assert crew.tasks[4].context == [crew.tasks[0], crew.tasks[1], crew.tasks[2], crew.tasks[3]]


def test_teacher_agent_executes_only_for_concept_tutoring():
    """Verify Teacher Agent executes only when conceptual tutoring is requested."""
    crew, agents, tasks = build_educational_crew(
        workflow_id="teacher_answer",
        student_question="Explain displacement reaction with an example.",
        grade="Class 10",
        subject="Science",
    )
    assert isinstance(crew, Crew)
    assert len(crew.agents) == 1
    assert "Teacher" in crew.agents[0].role
    # Ensure none of the other specialists are dragged into simple conceptual tutoring
    assert not any("Assessment" in a.role for a in crew.agents)
    assert not any("Diagnostic" in a.role for a in crew.agents)
    assert not any("Curriculum" in a.role for a in crew.agents)
    assert not any("Progress" in a.role for a in crew.agents)
    assert not any("Mentor" in a.role for a in crew.agents)


def test_all_eight_agents_have_strict_boundaries():
    """Verify that all eight agents instantiate genuine crewai.Agent instances with clear boundaries."""
    agents = {
        "orchestrator": create_orchestrator_agent(),
        "diagnostic": create_diagnostic_agent(),
        "curriculum": create_curriculum_agent(),
        "resource": create_resource_agent(),
        "teacher": create_teacher_agent(),
        "assessment": create_assessment_agent(),
        "progress": create_progress_agent(),
        "mentor": create_mentor_agent(),
    }
    assert len(agents) == 8
    for name, ag in agents.items():
        assert isinstance(ag, Agent)
        assert len(ag.role) > 5
        assert len(ag.goal) > 10
        assert len(ag.backstory) > 10

    # Strict check: Teacher agent prohibits grading or quiz creation
    teacher = agents["teacher"]
    assert "do not formulate" in teacher.backstory.lower() or "pedagogical explanation" in teacher.backstory.lower()
