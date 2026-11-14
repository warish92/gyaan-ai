"""Gyaan AI - Dynamic Multi-Agent Orchestration & Freeform Question Routing Test Suite.

Validates:
1. Dynamic semantic intent classification for arbitrary, unseen questions across all 8 agents.
2. Authentic CrewAI Crew construction: Crew(agents=[specialist], tasks=[task], process=Process.sequential).
3. Specialist agent isolation: Teacher Agent is never loaded with non-tutoring responsibilities.
4. Ambiguous / out-of-scope query clarification (never defaulting to Teacher Agent).
5. Multi-agent coordination and task context chaining (Progress + Mentor, Diagnostic + Curriculum).
6. POST /api/v1/ask integration returning enriched AskResponse with executing specialist agent name.
"""

import sys
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.agents.orchestrator import (
    classify_educational_intent,
    WORKFLOW_REGISTRY,
    OrchestrationRequest,
    RoutingDecision,
)
from backend.agents.crew import build_educational_crew, build_teacher_crew
from backend.agents.teacher import create_teacher_agent
from backend.agents.diagnostic import create_diagnostic_agent
from backend.agents.curriculum import create_curriculum_agent
from backend.agents.resource import create_resource_agent
from backend.agents.assessment import create_assessment_agent
from backend.agents.progress import create_progress_agent
from backend.agents.mentor import create_mentor_agent
from backend.agents.orchestrator import create_orchestrator_agent
from crewai import Agent, Crew, Process, Task

client = TestClient(app)


# ==============================================================================
# 1. Semantic Intent Routing for Arbitrary / Unseen Queries
# ==============================================================================

def test_unseen_teacher_concept_question_routing():
    """Verify arbitrary unseen concept inquiries route specifically to Teacher Agent."""
    unseen_queries = [
        "Explain photosynthesis in simple language.",
        "How does a concave mirror form a virtual and magnified image?",
        "What is the chemical difference between baking soda and washing soda?",
        "Why do stars twinkle at night while planets do not?",
        "Derive the formula for equivalent resistance of resistors in parallel.",
    ]
    for q in unseen_queries:
        wf, agents, reason, clar_req, clar_q = classify_educational_intent(q)
        assert wf == "teacher_answer", f"Failed for query: {q}"
        assert agents == ["Teacher Agent"], f"Wrong agents for query: {q}"
        assert clar_req is False


def test_unseen_assessment_quiz_question_routing():
    """Verify unseen quiz and practice test inquiries route to Assessment Agent."""
    unseen_queries = [
        "Create a 20-question test on chemical reactions.",
        "Test me on electricity and Ohm's law with 5 questions.",
        "Generate a practice quiz for Class 10 Life Processes.",
        "Give me practice questions and MCQs for metals and non-metals.",
        "Prepare a board-style practice test on magnetic effects of electric current.",
    ]
    for q in unseen_queries:
        wf, agents, reason, clar_req, clar_q = classify_educational_intent(q)
        assert wf == "quiz_generation", f"Failed for query: {q}"
        assert "Assessment Agent" in agents, f"Assessment Agent missing for query: {q}"
        assert clar_req is False


def test_unseen_diagnostic_evaluation_routing():
    """Verify unseen diagnostic and misconception queries route to Diagnostic Agent."""
    unseen_queries = [
        "Analyse my answers and identify my weak concepts.",
        "Where did I go wrong in explaining why rust forms?",
        "Why is my answer incorrect about concave lenses?",
        "Diagnose my misconceptions in chemical equation balancing.",
        "Check my reasoning: is it true that arteries always carry oxygenated blood?",
    ]
    for q in unseen_queries:
        wf, agents, reason, clar_req, clar_q = classify_educational_intent(q)
        assert wf == "diagnostic_evaluation", f"Failed for query: {q}"
        assert agents == ["Diagnostic Agent"], f"Diagnostic Agent missing for query: {q}"
        assert clar_req is False


def test_unseen_curriculum_inquiry_routing():
    """Verify unseen syllabus and roadmap queries route to Curriculum Agent."""
    unseen_queries = [
        "Show me the CBSE Class 10 science syllabus.",
        "What is the curriculum roadmap and chapter breakdown for Chemistry?",
        "What are the prerequisites for studying Heredity and Evolution?",
        "What chapters should I study before Electricity in Class 10?",
        "Outline the CBSE course structure and learning objectives for Real Numbers.",
    ]
    for q in unseen_queries:
        wf, agents, reason, clar_req, clar_q = classify_educational_intent(q)
        assert wf == "curriculum_inquiry", f"Failed for query: {q}"
        assert agents == ["Curriculum Agent"], f"Curriculum Agent missing for query: {q}"
        assert clar_req is False


def test_unseen_resource_search_routing():
    """Verify unseen study material and NCERT reference queries route to Resource Agent."""
    unseen_queries = [
        "Find good learning resources for electricity.",
        "Where can I find verified NCERT study notes for Carbon and its Compounds?",
        "Show me textbook diagrams and reference summaries for the human heart.",
        "Recommend reference books and study materials for CBSE Class 10 Physics.",
        "Find official revision notes and textbook excerpts on acids, bases, and salts.",
    ]
    for q in unseen_queries:
        wf, agents, reason, clar_req, clar_q = classify_educational_intent(q)
        assert wf == "resource_search", f"Failed for query: {q}"
        assert agents == ["Resource Agent"], f"Resource Agent missing for query: {q}"
        assert clar_req is False


def test_unseen_progress_analysis_routing():
    """Verify unseen progress tracking queries route to Progress Agent."""
    unseen_queries = [
        "Show my progress in mathematics.",
        "How am I performing in science assessments?",
        "What are my past quiz scores and mastery history?",
        "How many practice quizzes have I completed this week?",
        "Show my learning analytics and accuracy trends.",
    ]
    for q in unseen_queries:
        wf, agents, reason, clar_req, clar_q = classify_educational_intent(q)
        assert wf == "progress_analysis", f"Failed for query: {q}"
        assert agents == ["Progress Agent"], f"Progress Agent missing for query: {q}"
        assert clar_req is False


def test_unseen_mentor_guidance_routing():
    """Verify unseen study coaching and revision strategy queries route to Mentor Agent."""
    unseen_queries = [
        "Create a 30-day revision strategy.",
        "How should I prepare for CBSE Class 10 board exams?",
        "Give me a daily study timetable and habit plan for Science and Math.",
        "How do I manage time and exam stress during revision?",
        "What are the best study habits for scoring 95+ in Class 10 boards?",
    ]
    for q in unseen_queries:
        wf, agents, reason, clar_req, clar_q = classify_educational_intent(q)
        assert wf == "study_guidance", f"Failed for query: {q}"
        assert agents == ["Mentor Agent"], f"Mentor Agent missing for query: {q}"
        assert clar_req is False


def test_multi_intent_progress_and_mentor_routing():
    """Verify multi-intent questions (Progress + Mentor) route to combined workflow."""
    multi_intent_queries = [
        "What should I study next based on my performance?",
        "How am I doing in Science and what should I revise next?",
        "Review my progress and give me a personalized study plan.",
        "Based on my quiz scores, recommend what topics I should focus on next.",
    ]
    for q in multi_intent_queries:
        wf, agents, reason, clar_req, clar_q = classify_educational_intent(q)
        assert wf == "progress_and_mentoring", f"Failed for query: {q}"
        assert "Progress Agent" in agents and "Mentor Agent" in agents
        assert clar_req is False


def test_ambiguous_and_out_of_scope_trigger_clarification():
    """Verify ambiguous, chat, or out-of-scope requests trigger clarification and NEVER route to Teacher."""
    invalid_queries = [
        "help",
        "help me",
        "please help",
        "hi",
        "hello",
        "who are you",
        "book a flight to Mumbai",
        "order a cheese pizza",
        "how is the weather in Delhi today",
    ]
    for q in invalid_queries:
        wf, agents, reason, clar_req, clar_q = classify_educational_intent(q)
        assert clar_req is True, f"Expected clarification for query: '{q}'"
        assert wf == "clarification_needed"
        assert "Teacher Agent" not in agents
        assert clar_q is not None and len(clar_q) > 20


# ==============================================================================
# 2. Authentic CrewAI Construction & Specialist Inclusion
# ==============================================================================

def test_build_educational_crew_constructs_authentic_crew():
    """Verify build_educational_crew creates genuine CrewAI Agent, Task, and Crew objects."""
    # Teacher Crew
    t_crew, t_agents, t_tasks = build_educational_crew(
        workflow_id="teacher_answer",
        student_question="Explain Ohm's law with circuit diagram.",
        grade="Class 10",
        subject="Science",
    )
    assert isinstance(t_crew, Crew)
    assert len(t_crew.agents) == 1
    assert t_crew.agents[0].role == "Class 10 CBSE Science Teacher and Concept Specialist"
    assert len(t_crew.tasks) == 1
    assert t_crew.process == Process.sequential

    # Assessment Crew
    q_crew, q_agents, q_tasks = build_educational_crew(
        workflow_id="quiz_generation",
        student_question="Create a 5-question test on acids.",
        grade="Class 10",
        subject="Science",
    )
    assert isinstance(q_crew, Crew)
    assert any("Assessment" in a.role for a in q_crew.agents)
    assert any("Resource" in a.role for a in q_crew.agents)
    assert len(q_crew.tasks) == 2
    # Verify task context passing
    assert q_crew.tasks[1].context is not None

    # Curriculum Crew
    c_crew, c_agents, c_tasks = build_educational_crew(
        workflow_id="curriculum_inquiry",
        student_question="Show CBSE Science syllabus.",
        grade="Class 10",
        subject="Science",
    )
    assert isinstance(c_crew, Crew)
    assert "Curriculum" in c_crew.agents[0].role

    # Diagnostic Crew
    d_crew, d_agents, d_tasks = build_educational_crew(
        workflow_id="diagnostic_evaluation",
        student_question="Check why my answer about rust was wrong.",
        grade="Class 10",
        subject="Science",
    )
    assert isinstance(d_crew, Crew)
    assert "Diagnostic" in d_crew.agents[0].role

    # Resource Crew
    r_crew, r_agents, r_tasks = build_educational_crew(
        workflow_id="resource_search",
        student_question="Find NCERT notes for electricity.",
        grade="Class 10",
        subject="Science",
    )
    assert isinstance(r_crew, Crew)
    assert "Resource" in r_crew.agents[0].role

    # Progress Crew
    p_crew, p_agents, p_tasks = build_educational_crew(
        workflow_id="progress_analysis",
        student_question="Show my progress analytics.",
        grade="Class 10",
        subject="Science",
    )
    assert isinstance(p_crew, Crew)
    assert "Progress" in p_crew.agents[0].role

    # Mentor Crew
    m_crew, m_agents, m_tasks = build_educational_crew(
        workflow_id="study_guidance",
        student_question="How should I plan 30-day revision?",
        grade="Class 10",
        subject="Science",
    )
    assert isinstance(m_crew, Crew)
    assert "Mentor" in m_crew.agents[0].role


def test_multi_agent_crews_pass_context_sequentially():
    """Verify multi-agent Crews chain task outputs via CrewAI context."""
    # Progress + Mentor workflow
    pm_crew, pm_agents, pm_tasks = build_educational_crew(
        workflow_id="progress_and_mentoring",
        student_question="What should I study next based on my performance?",
        grade="Class 10",
        subject="Science",
    )
    assert isinstance(pm_crew, Crew)
    assert len(pm_crew.agents) == 2
    assert len(pm_crew.tasks) == 2
    # Verify second task receives first task's context
    assert pm_crew.tasks[1].context is not None
    assert pm_crew.tasks[0] in pm_crew.tasks[1].context

    # Diagnostic + Curriculum workflow
    dc_crew, dc_agents, dc_tasks = build_educational_crew(
        workflow_id="diagnostic_curriculum",
        student_question="Diagnose my gaps and give me a learning plan.",
        grade="Class 10",
        subject="Science",
    )
    assert isinstance(dc_crew, Crew)
    assert len(dc_crew.agents) == 2
    assert len(dc_crew.tasks) == 2
    assert dc_crew.tasks[1].context is not None
    assert dc_crew.tasks[0] in dc_crew.tasks[1].context


# ==============================================================================
# 3. API Integration: Free-form Queries to /api/v1/ask
# ==============================================================================

def test_api_ask_returns_specialist_metadata_for_unseen_questions():
    """Verify POST /api/v1/ask dynamically dispatches and returns executing specialist agent metadata."""
    # 1. Unseen Quiz Generation Question
    mock_quiz_result = MagicMock()
    mock_quiz_result.raw = "### CBSE Practice Quiz\n1. What is Ohm's law?\n2. Calculate equivalent resistance."
    with patch("backend.agents.assessment.build_quiz_generation_crew") as mock_quiz_builder:
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_quiz_result
        mock_quiz_builder.return_value = (mock_crew, MagicMock())

        res = client.post("/api/v1/ask", json={
            "question": "Create a 20-question test on chemical reactions.",
            "subject": "Chemistry",
            "grade": "Class 10",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["workflow_executed"] == "quiz_generation"
        assert "Assessment Agent" in data["agent_name"]
        assert "Resource Agent" in data["selected_agents"]
        assert "Assessment Agent" in data["selected_agents"]

    # 2. Unseen Curriculum Roadmap Question
    mock_curr_result = MagicMock()
    mock_curr_result.raw = "### CBSE Curriculum Roadmap\n- Prerequisites: Atoms and Molecules\n- Objectives: Chemical Equations"
    with patch("backend.agents.curriculum.build_curriculum_crew") as mock_curr_builder:
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_curr_result
        mock_curr_builder.return_value = (mock_crew, MagicMock())

        res = client.post("/api/v1/ask", json={
            "question": "Show me the CBSE Class 10 science syllabus and roadmap.",
            "subject": "Science",
            "grade": "Class 10",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["workflow_executed"] == "curriculum_inquiry"
        assert "Curriculum Agent" in data["agent_name"]
        assert "Curriculum Agent" in data["selected_agents"]

    # 3. Unseen Study Guidance Question
    mock_mentor_result = MagicMock()
    mock_mentor_result.raw = "### 30-Day Revision Strategy\n- Week 1: Core Physics concepts\n- Week 2: Chemistry equations"
    with patch("backend.agents.mentor.build_standalone_mentor_crew") as mock_mentor_builder:
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_mentor_result
        mock_mentor_builder.return_value = (mock_crew, MagicMock())

        res = client.post("/api/v1/ask", json={
            "question": "Create a 30-day revision strategy for board exams.",
            "subject": "Science",
            "grade": "Class 10",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["workflow_executed"] == "study_guidance"
        assert "Mentor Agent" in data["agent_name"]
        assert "Mentor Agent" in data["selected_agents"]

    # 4. Unseen Diagnostic Question
    mock_diag_result = MagicMock()
    mock_diag_result.raw = "### Diagnostic Gap Report\n- Demonstrated: Knows iron rusts\n- Misconception: Ignored role of moisture"
    with patch("backend.agents.diagnostic.build_diagnostic_crew") as mock_diag_builder:
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_diag_result
        mock_diag_builder.return_value = (mock_crew, MagicMock())

        res = client.post("/api/v1/ask", json={
            "question": "Analyse my answers and identify my weak concepts in rust formation.",
            "subject": "Chemistry",
            "grade": "Class 10",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["workflow_executed"] == "diagnostic_evaluation"
        assert "Diagnostic Agent" in data["agent_name"]
        assert "Diagnostic Agent" in data["selected_agents"]

    # 5. Ambiguous Question triggers Clarification
    res_amb = client.post("/api/v1/ask", json={
        "question": "help me",
    })
    assert res_amb.status_code == 200
    data_amb = res_amb.json()
    assert data_amb["workflow_executed"] == "clarification_needed"
    assert "Orchestrator Agent" in data_amb["agent_name"]
    assert "help with" in data_amb["answer"].lower()
