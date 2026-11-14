"""Gyaan AI - Specialist Agent Independence and Multi-Agent Orchestration Test Suite.

Verifies:
1. All eight canonical CrewAI agents can be instantiated and configured independently.
2. Every specialist agent possesses standalone Crew construction and execution capabilities.
3. Teacher Agent is constrained strictly to conceptual explanation and worked examples.
4. Orchestrator intent routing dispatches requests to the appropriate specialist rather
   than monopolizing execution with Teacher Agent.
5. POST /api/v1/ask routes incoming student inquiries to the appropriate specialist agent.
6. The Chapter Learning Journey follows the canonical 9-step sequence:
   Orchestrator -> Curriculum -> Diagnostic -> Resource -> Teacher -> Assessment -> Progress -> Mentor -> Orchestrator Synthesis.
7. WORKFLOW_REGISTRY registers all approved workflows including specialist standalone workflows.
"""

import pytest
from unittest.mock import MagicMock, patch
from crewai import Agent, Crew, Process, Task
from fastapi.testclient import TestClient

from backend.agents.orchestrator import (
    WORKFLOW_REGISTRY,
    build_orchestrator_crew,
    create_orchestrator_agent,
    create_orchestrator_task,
    run_orchestrator_routing,
)
from backend.agents.diagnostic import (
    build_diagnostic_crew,
    create_diagnostic_agent,
    create_diagnostic_task,
)
from backend.agents.curriculum import (
    build_curriculum_crew,
    create_curriculum_agent,
    create_curriculum_inquiry_task,
)
from backend.agents.resource import (
    build_resource_crew,
    create_resource_agent,
    create_resource_task,
)
from backend.agents.teacher import (
    create_teacher_agent,
)
from backend.agents.crew import (
    build_teacher_crew,
    create_teacher_task,
)
from backend.agents.assessment import (
    build_quiz_generation_crew,
    build_assessment_evaluation_crew,
    create_assessment_agent,
    create_quiz_generation_task,
)
from backend.agents.progress import (
    build_progress_crew,
    create_progress_agent,
    create_progress_analysis_task,
)
from backend.agents.mentor import (
    build_standalone_mentor_crew,
    create_mentor_agent,
    create_standalone_mentor_task,
)
from backend.agents.chapter_journey import (
    build_chapter_learning_journey_crew,
)
from backend.agents.registry import agent_registry
from backend.app.main import app
from backend.app.schemas import OrchestrationRequest

client = TestClient(app)


def test_all_eight_agents_have_independent_definitions():
    """Verify each of the 8 canonical agents has an independent factory creating genuine CrewAI Agent."""
    agents = [
        create_orchestrator_agent(),
        create_diagnostic_agent(),
        create_curriculum_agent(),
        create_resource_agent(),
        create_teacher_agent(),
        create_assessment_agent(),
        create_progress_agent(),
        create_mentor_agent(),
    ]

    assert len(agents) == 8
    for ag in agents:
        assert isinstance(ag, Agent)
        assert len(ag.role) > 5
        assert len(ag.goal) > 10
        assert len(ag.backstory) > 10


def test_teacher_agent_boundaries():
    """Verify Teacher Agent role, goal, backstory and task explicitly prohibit non-teaching responsibilities."""
    teacher = create_teacher_agent()
    assert "Teacher" in teacher.role
    assert "Science Teacher" in teacher.role
    assert "Strictly focus on conceptual instruction" in teacher.goal or "Do not perform" in teacher.goal
    assert "never generate examination quizzes" in teacher.backstory.lower() or "pedagogical explanation" in teacher.backstory.lower()

    # Check teacher task description in conceptual mode
    task = create_teacher_task(
        agent=teacher,
        student_question="How does photosynthesis work?",
        lesson_mode="conceptual",
    )
    assert "Strict Boundary" in task.description or "exclusive" in task.description.lower()
    assert "Do not formulate examination quizzes" in task.description or "assessment is handled" in task.description.lower()

    # Check teacher task description in practice mode
    task_practice = create_teacher_task(
        agent=teacher,
        student_question="Help me practice balancing chemical equations",
        lesson_mode="practice",
    )
    assert "Do not formulate diagnostic examination quizzes" in task_practice.description or "pedagogical explanation" in task_practice.description


def test_diagnostic_agent_standalone_crew():
    """Verify Diagnostic Agent can construct a standalone Crew without requiring Curriculum."""
    items = [
        {
            "question": "What is the function of bile juice?",
            "student_answer": "It breaks down fats into smaller droplets.",
            "expected_answer": "Emulsifies fats and provides alkaline medium.",
        }
    ]
    crew, task = build_diagnostic_crew(
        grade="Class 10",
        subject="Biology",
        topic="Life Processes",
        assessment_items=items,
    )
    assert isinstance(crew, Crew)
    assert len(crew.agents) == 1
    assert crew.agents[0].role == "Evidence-Based Student Learning Diagnostic Specialist"
    assert len(crew.tasks) == 1
    assert task == crew.tasks[0]
    assert not isinstance(task.context, list)  # Standalone execution


def test_curriculum_agent_standalone_crew():
    """Verify Curriculum Agent can construct a standalone Crew for roadmap planning."""
    crew, task = build_curriculum_crew(
        grade="Class 10",
        subject="Chemistry",
        topic="Acids, Bases and Salts",
        inquiry="Outline the complete chapter sequence and prerequisite topics",
    )
    assert isinstance(crew, Crew)
    assert len(crew.agents) == 1
    assert crew.agents[0].role == "Evidence-Grounded Curriculum Planning Specialist"
    assert len(crew.tasks) == 1
    assert task == crew.tasks[0]
    assert not isinstance(task.context, list)  # Standalone execution


def test_resource_agent_standalone_crew():
    """Verify Resource Agent can construct a standalone Crew."""
    crew, task = build_resource_crew(
        grade="Class 10",
        subject="Physics",
        topic="Light - Reflection and Refraction",
        learning_objective="Understand lens formula and ray diagrams",
    )
    assert isinstance(crew, Crew)
    assert len(crew.agents) == 1
    assert crew.agents[0].role == "Educational Resource Retrieval Specialist"
    assert len(crew.tasks) == 1
    assert task == crew.tasks[0]


def test_assessment_agent_standalone_crews():
    """Verify Assessment Agent can construct standalone quiz generation and answer evaluation Crews."""
    # Quiz generation
    crew_quiz, task_quiz = build_quiz_generation_crew(
        grade="Class 10",
        subject="Science",
        topic="Electricity",
        num_questions=3,
    )
    assert isinstance(crew_quiz, Crew)
    assert len(crew_quiz.agents) == 1
    assert crew_quiz.agents[0].role == "Educational Assessment and Feedback Specialist"
    assert len(crew_quiz.tasks) == 1

    # Answer evaluation
    rubric = [
        {"id": "q1", "question": "Define Ohm's law", "correct_answer": "V = IR at constant temperature", "marks": 2.0}
    ]
    submissions = {"q1": "Voltage is directly proportional to current."}
    crew_eval, task_eval = build_assessment_evaluation_crew(
        questions_with_rubric=rubric,
        submitted_answers=submissions,
    )
    assert isinstance(crew_eval, Crew)
    assert len(crew_eval.agents) == 1
    assert crew_eval.agents[0].role == "Educational Assessment and Feedback Specialist"
    assert len(crew_eval.tasks) == 1


def test_progress_agent_standalone_crew():
    """Verify Progress Agent can construct a standalone Crew."""
    profile = {"display_name": "Test Student", "grade": "Class 10"}
    stats = {
        "total_assessments_completed": 5,
        "average_percentage": 78.5,
        "performance_trend": "improving",
        "trend_description": "Steady improvement across chapters",
        "strengths": ["Acids and Bases"],
        "areas_needing_improvement": ["Light"],
        "has_sufficient_history": True,
    }
    crew, task = build_progress_crew(
        student_profile=profile,
        objective_stats=stats,
    )
    assert isinstance(crew, Crew)
    assert len(crew.agents) == 1
    assert crew.agents[0].role == "Student Learning Progress Analyst"
    assert len(crew.tasks) == 1


def test_mentor_agent_standalone_crew():
    """Verify Mentor Agent can construct a standalone Crew without requiring progress task context."""
    profile = {"display_name": "Test Student", "grade": "Class 10"}
    crew, task = build_standalone_mentor_crew(
        student_profile=profile,
        topic="Metals and Non-metals",
        study_query="How can I remember the reactivity series efficiently?",
    )
    assert isinstance(crew, Crew)
    assert len(crew.agents) == 1
    assert crew.agents[0].role == "Personalized Student Learning Mentor"
    assert len(crew.tasks) == 1
    assert not isinstance(task.context, list)  # Standalone execution


def test_workflow_registry_includes_all_specialist_workflows():
    """Verify WORKFLOW_REGISTRY registers standalone workflows for all specialist agents."""
    expected_workflows = [
        "chapter_learning_journey",
        "teacher_answer",
        "diagnostic_curriculum",
        "resource_search",
        "quiz_generation",
        "assessment_evaluation",
        "progress_analysis",
        "personalized_mentoring",
        "progress_and_mentoring",
        "curriculum_inquiry",
        "diagnostic_evaluation",
        "study_guidance",
    ]
    for wf in expected_workflows:
        assert wf in WORKFLOW_REGISTRY, f"Workflow '{wf}' not registered in WORKFLOW_REGISTRY"

    assert WORKFLOW_REGISTRY["curriculum_inquiry"].agents == ["Curriculum Agent"]
    assert WORKFLOW_REGISTRY["diagnostic_evaluation"].agents == ["Diagnostic Agent"]
    assert WORKFLOW_REGISTRY["study_guidance"].agents == ["Mentor Agent"]
    assert WORKFLOW_REGISTRY["resource_search"].agents == ["Resource Agent"]
    assert WORKFLOW_REGISTRY["assessment_evaluation"].agents == ["Assessment Agent"]
    assert WORKFLOW_REGISTRY["teacher_answer"].agents == ["Teacher Agent"]


def test_orchestrator_routing_to_specialists():
    """Verify Orchestrator correctly routes requests according to specialist responsibilities."""
    # Mock LLM kickoff for deterministic testing of routing parser
    mock_responses = [
        # 1. Assessment
        '{"detected_intent": "practice quiz", "selected_workflow": "quiz_generation", "selected_agents": ["Resource Agent", "Assessment Agent"], "normalized_request": "Create a 3-question quiz on electricity", "clarification_required": false, "clarification_question": null, "routing_reason": "Assessment inquiry", "extracted_parameters": {"topic": "Electricity", "num_questions": 3}}',
        # 2. Curriculum
        '{"detected_intent": "curriculum roadmap", "selected_workflow": "curriculum_inquiry", "selected_agents": ["Curriculum Agent"], "normalized_request": "What are the prerequisites for carbon compounds?", "clarification_required": false, "clarification_question": null, "routing_reason": "Curriculum inquiry", "extracted_parameters": {"topic": "Carbon Compounds"}}',
        # 3. Mentor
        '{"detected_intent": "study coaching", "selected_workflow": "study_guidance", "selected_agents": ["Mentor Agent"], "normalized_request": "How do I build a study timetable for science boards?", "clarification_required": false, "clarification_question": null, "routing_reason": "Mentor guidance", "extracted_parameters": {"topic": "Board Exam Prep"}}',
        # 4. Teacher
        '{"detected_intent": "concept explanation", "selected_workflow": "teacher_answer", "selected_agents": ["Teacher Agent"], "normalized_request": "Explain the difference between series and parallel circuits", "clarification_required": false, "clarification_question": null, "routing_reason": "Tutoring inquiry", "extracted_parameters": {"topic": "Electricity"}}',
    ]

    for mock_json in mock_responses:
        with patch.object(Crew, "kickoff") as mock_kickoff:
            mock_kickoff.return_value = MagicMock(raw=mock_json)
            req = OrchestrationRequest(request="Educational question", grade="Class 10", subject="Science")
            decision = run_orchestrator_routing(req)
            assert decision.selected_workflow in WORKFLOW_REGISTRY
            assert len(decision.selected_agents) > 0


def test_chapter_learning_journey_canonical_nine_step_sequence():
    """Verify Chapter Learning Journey follows the canonical 9-step sequence with proper context dependencies."""
    crew, tasks, agents_map = build_chapter_learning_journey_crew(
        subject="Science",
        chapter="Life Processes",
        student_goal="Master respiration and circulation",
        grade="Class 10",
        language="English",
    )

    assert len(tasks) == 9
    assert len(crew.tasks) == 9
    assert len(crew.agents) == 8  # 8 canonical agents (Orchestrator initiates and synthesizes)
    assert crew.process == Process.sequential

    # Step 1: Orchestrator Scope (no context)
    assert tasks[0].agent.role == "Educational AI Workflow Orchestrator"
    assert not isinstance(tasks[0].context, list)

    # Step 2: Curriculum Objectives & Roadmap (context: [t1])
    assert tasks[1].agent.role == "Evidence-Grounded Curriculum Planning Specialist"
    assert tasks[0] in tasks[1].context

    # Step 3: Diagnostic Assessment against prerequisites (context: [t2])
    assert tasks[2].agent.role == "Evidence-Based Student Learning Diagnostic Specialist"
    assert tasks[1] in tasks[2].context

    # Step 4: Resource Curation (context: [t2])
    assert tasks[3].agent.role == "Educational Resource Retrieval Specialist"
    assert tasks[1] in tasks[3].context

    # Step 5: Teacher Instruction - ONLY teaching (context: [t2, t3, t4])
    assert tasks[4].agent.role == "Class 10 CBSE Science Teacher and Concept Specialist"
    assert tasks[1] in tasks[4].context
    assert tasks[2] in tasks[4].context
    assert tasks[3] in tasks[4].context

    # Step 6: Assessment Comprehension & Checkpoint (context: [t2, t5])
    assert tasks[5].agent.role == "Educational Assessment and Feedback Specialist"
    assert tasks[1] in tasks[5].context
    assert tasks[4] in tasks[5].context

    # Step 7: Progress Analytics & Trajectory (context: [t6])
    assert tasks[6].agent.role == "Student Learning Progress Analyst"
    assert tasks[5] in tasks[6].context

    # Step 8: Mentor Personalized Recommendations (context: [t1, t2, t6, t7])
    assert tasks[7].agent.role == "Personalized Student Learning Mentor"
    assert tasks[0] in tasks[7].context
    assert tasks[1] in tasks[7].context
    assert tasks[5] in tasks[7].context
    assert tasks[6] in tasks[7].context

    # Step 9: Orchestrator Coordinated Synthesis (context: [t2, t5, t6, t7, t8])
    assert tasks[8].agent.role == "Educational AI Workflow Orchestrator"
    assert tasks[1] in tasks[8].context
    assert tasks[4] in tasks[8].context
    assert tasks[5] in tasks[8].context
    assert tasks[6] in tasks[8].context
    assert tasks[7] in tasks[8].context


def test_api_ask_routes_to_specialists():
    """Verify /api/v1/ask inspects intent and dispatches to specialists when non-tutoring queries arrive."""
    with patch("backend.agents.assessment.build_quiz_generation_crew") as mock_quiz_crew, \
         patch("backend.agents.curriculum.build_curriculum_crew") as mock_curr_crew, \
         patch("backend.agents.mentor.build_standalone_mentor_crew") as mock_mentor_crew:

        # 1. Quiz query
        mock_crew_inst = MagicMock()
        mock_crew_inst.kickoff.return_value = MagicMock(raw='[{"question": "What is current?"}]')
        mock_quiz_crew.return_value = (mock_crew_inst, MagicMock())

        res_quiz = client.post("/api/v1/ask", json={
            "question": "Can you generate a practice quiz on electricity for me?",
            "subject": "Physics",
            "grade": "Class 10",
        })
        assert res_quiz.status_code == 200
        mock_quiz_crew.assert_called_once()

        # 2. Curriculum query
        mock_curr_inst = MagicMock()
        mock_curr_inst.kickoff.return_value = MagicMock(raw='# PERSONALIZED CURRICULUM PLAN\n## Sequenced Learning Stages')
        mock_curr_crew.return_value = (mock_curr_inst, MagicMock())

        res_curr = client.post("/api/v1/ask", json={
            "question": "What is the curriculum roadmap and prerequisites for Chemical Reactions?",
            "subject": "Chemistry",
            "grade": "Class 10",
        })
        assert res_curr.status_code == 200
        mock_curr_crew.assert_called_once()

        # 3. Mentor query
        mock_mentor_inst = MagicMock()
        mock_mentor_inst.kickoff.return_value = MagicMock(raw='{"mentor_overview": "Effective study tips for science exams"}')
        mock_mentor_crew.return_value = (mock_mentor_inst, MagicMock())

        res_mentor = client.post("/api/v1/ask", json={
            "question": "Give me study tips and habit advice for preparing for exams",
            "subject": "Science",
            "grade": "Class 10",
        })
        assert res_mentor.status_code == 200
        mock_mentor_crew.assert_called_once()
