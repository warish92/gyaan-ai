"""Unit tests for Canonical Orchestrator Agent and Workflow Dispatching in Gyaan AI.

Tests:
1. Routing schema validation (Pydantic models)
2. Workflow registry integrity (all canonical workflows present & configured)
3. Allowlisted workflow validation & unknown route rejection
4. Clarification-required handling
5. Empty & excessively long request rejection
6. Authentication enforcement on protected workflows (progress_analysis, personalized_mentoring)
7. Unauthenticated access permitted on public workflows (teacher_answer, resource_search, etc.)
8. Malformed model output recovery & graceful fallback
9. Missing workflow inputs handling
10. Safe downstream failure handling
11. End-to-end response schema compliance
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from pydantic import ValidationError

from backend.agents.orchestrator import (
    WORKFLOW_REGISTRY,
    create_orchestrator_agent,
    create_orchestrator_task,
    clean_json_payload,
    execute_orchestrated_pipeline,
    run_orchestrator_routing,
)
from backend.app.schemas import (
    OrchestrationRequest,
    OrchestrationResponse,
    RoutingDecision,
)
from fastapi import HTTPException


# ==============================================================================
# 1. Routing Schema & Model Validation Tests
# ==============================================================================

def test_routing_decision_schema_valid():
    """Verify that RoutingDecision parses a valid payload correctly."""
    data = {
        "request_id": "req-123",
        "detected_intent": "Understand photosynthesis process",
        "selected_workflow": "teacher_answer",
        "selected_agents": ["Teacher Agent"],
        "normalized_request": "Explain photosynthesis in detail",
        "clarification_required": False,
        "clarification_question": None,
        "routing_reason": "Tutoring question regarding biological concept.",
        "extracted_parameters": {"topic": "Photosynthesis", "subject": "Biology"},
    }
    decision = RoutingDecision(**data)
    assert decision.request_id == "req-123"
    assert decision.selected_workflow == "teacher_answer"
    assert decision.selected_agents == ["Teacher Agent"]
    assert not decision.clarification_required
    assert decision.extracted_parameters["topic"] == "Photosynthesis"


def test_orchestration_request_validation():
    """Verify validation on OrchestrationRequest for min/max length and empty strings."""
    # Valid request
    req = OrchestrationRequest(request="Explain acids and bases")
    assert req.request == "Explain acids and bases"
    assert req.grade == "Class 10"

    # Reject empty or whitespace
    with pytest.raises(ValidationError):
        OrchestrationRequest(request="   ")

    # Reject too short
    with pytest.raises(ValidationError):
        OrchestrationRequest(request="ab")

    # Reject overly long request (> 2000 chars)
    with pytest.raises(ValidationError):
        OrchestrationRequest(request="a" * 2001)


# ==============================================================================
# 2. Workflow Registry Integrity Tests
# ==============================================================================

def test_workflow_registry_contains_all_canonical_workflows():
    """Verify that WORKFLOW_REGISTRY contains all canonical workflows with proper descriptors."""
    canonical_workflows = [
        "teacher_answer",
        "diagnostic_curriculum",
        "resource_search",
        "quiz_generation",
        "assessment_evaluation",
        "progress_analysis",
        "personalized_mentoring",
        "progress_and_mentoring",
    ]
    for wf in canonical_workflows:
        assert wf in WORKFLOW_REGISTRY, f"Workflow '{wf}' missing from WORKFLOW_REGISTRY."
        desc = WORKFLOW_REGISTRY[wf]
        assert desc.workflow_id == wf
        assert desc.name
        assert desc.description
        assert len(desc.agents) >= 1
        assert callable(desc.handler)


def test_workflow_registry_auth_requirements():
    """Verify that private data workflows require authentication, while public ones do not."""
    protected_workflows = ["progress_analysis", "personalized_mentoring", "progress_and_mentoring"]
    public_workflows = ["teacher_answer", "diagnostic_curriculum", "resource_search", "quiz_generation"]

    for wf in protected_workflows:
        assert WORKFLOW_REGISTRY[wf].requires_auth is True, f"'{wf}' must require authentication."

    for wf in public_workflows:
        assert WORKFLOW_REGISTRY[wf].requires_auth is False, f"'{wf}' should not strictly mandate auth."


# ==============================================================================
# 3. Orchestrator Agent Construction
# ==============================================================================

def test_create_orchestrator_agent():
    """Verify that the Orchestrator Agent has canonical role, goal, and backstory."""
    agent = create_orchestrator_agent()

    assert agent.role == "Educational AI Workflow Orchestrator"
    assert "Interpret the student's educational request" in agent.goal
    assert "educational AI coordinator" in agent.backstory
    assert agent.allow_delegation is False


def test_create_orchestrator_task():
    """Verify that create_orchestrator_task incorporates approved workflows and instructions."""
    agent = create_orchestrator_agent()
    task = create_orchestrator_task(
        agent=agent,
        user_request="Can you test me on chemical reactions?",
        grade="Class 10",
        subject="Chemistry",
        language="English",
    )
    desc = task.description
    assert "APPROVED REGISTERED WORKFLOWS:" in desc
    assert "teacher_answer" in desc
    assert "quiz_generation" in desc
    assert "progress_and_mentoring" in desc
    assert "Can you test me on chemical reactions?" in desc


# ==============================================================================
# 4. Unknown Route Rejection & Allowlisted Dispatch
# ==============================================================================

def test_unknown_workflow_rejected_by_dispatcher():
    """Verify that if the model produces an unapproved workflow, it is rejected safely."""
    req = OrchestrationRequest(request="Do something random")
    invalid_routing = RoutingDecision(
        request_id="req-999",
        detected_intent="Unknown",
        selected_workflow="unregistered_hack_workflow",
        selected_agents=["FakeAgent"],
        normalized_request="Do something random",
        clarification_required=False,
        clarification_question=None,
        routing_reason="Invalid",
    )

    with patch("backend.agents.orchestrator.run_orchestrator_routing", return_value=invalid_routing):
        with pytest.raises(ValueError, match="not an approved registered workflow"):
            execute_orchestrated_pipeline(req)


# ==============================================================================
# 5. Clarification Required Behavior
# ==============================================================================

def test_clarification_required_short_circuits_execution():
    """Verify that clarification-required requests return immediately without invoking downstream workflows."""
    req = OrchestrationRequest(request="asdfghjkl ???")
    clarification_routing = RoutingDecision(
        request_id="req-clarify",
        detected_intent="Unclear or gibberish input",
        selected_workflow="teacher_answer",
        selected_agents=["Teacher Agent"],
        normalized_request="asdfghjkl ???",
        clarification_required=True,
        clarification_question="Could you please specify which science topic you want help with?",
        routing_reason="Request lacks intelligible educational inquiry.",
    )

    with patch("backend.agents.orchestrator.run_orchestrator_routing", return_value=clarification_routing):
        response = execute_orchestrated_pipeline(req)
        assert response.status == "clarification_needed"
        assert response.clarification_required is True
        assert response.clarification_question == "Could you please specify which science topic you want help with?"
        assert response.result is None


# ==============================================================================
# 6. Authentication Enforcement on Protected Workflows
# ==============================================================================

def test_protected_workflow_rejects_unauthenticated_student():
    """Verify that attempting to execute progress_analysis without authentication raises HTTP 401."""
    req = OrchestrationRequest(request="Show my learning progress and quiz scores")
    progress_routing = RoutingDecision(
        request_id="req-progress",
        detected_intent="Review student learning progress",
        selected_workflow="progress_analysis",
        selected_agents=["Progress Agent"],
        normalized_request="Show my learning progress",
        clarification_required=False,
        clarification_question=None,
        routing_reason="Student wants to review progress analytics.",
    )

    with patch("backend.agents.orchestrator.run_orchestrator_routing", return_value=progress_routing):
        with pytest.raises(HTTPException) as exc_info:
            execute_orchestrated_pipeline(request=req, current_student=None)
        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail


def test_protected_workflow_succeeds_with_authenticated_student():
    """Verify that authenticated students can execute protected progress workflows."""
    req = OrchestrationRequest(request="Show my learning progress and quiz scores")
    current_student = {
        "id": "student-verified-123",
        "display_name": "Rohan",
        "grade": "Class 10",
        "email": "rohan@test.com",
    }
    progress_routing = RoutingDecision(
        request_id="req-progress-auth",
        detected_intent="Review student learning progress",
        selected_workflow="progress_analysis",
        selected_agents=["Progress Agent"],
        normalized_request="Show my learning progress",
        clarification_required=False,
        clarification_question=None,
        routing_reason="Student wants to review progress analytics.",
    )

    mock_result = {
        "student_id": "student-verified-123",
        "objective_statistics": {"total_quizzes_generated": 3, "overall_average_score": 85.0},
        "progress_report": {"overall_summary": "Great progress."},
    }

    with patch("backend.agents.orchestrator.run_orchestrator_routing", return_value=progress_routing):
        with patch("backend.agents.orchestrator.run_progress_analysis_workflow", return_value={"objective_statistics": mock_result["objective_statistics"], "agent_analysis": mock_result["progress_report"]}):
            resp = execute_orchestrated_pipeline(request=req, current_student=current_student)
            assert resp.status == "success"
            assert resp.selected_workflow == "progress_analysis"
            assert resp.result["student_id"] == "student-verified-123"


# ==============================================================================
# 7. Public Workflows Execute Unauthenticated
# ==============================================================================

def test_teacher_answer_workflow_executes_unauthenticated():
    """Verify that public tutoring workflows can execute without a student account."""
    req = OrchestrationRequest(request="What is Newton's First Law?")
    teacher_routing = RoutingDecision(
        request_id="req-tutoring",
        detected_intent="Concept tutoring inquiry",
        selected_workflow="teacher_answer",
        selected_agents=["Teacher Agent"],
        normalized_request="What is Newton's First Law?",
        clarification_required=False,
        clarification_question=None,
        routing_reason="Student is asking for concept explanation.",
    )

    mock_crew = MagicMock()
    mock_crew.kickoff.return_value = MagicMock(raw="An object will remain at rest or in uniform motion...")

    with patch("backend.agents.orchestrator.run_orchestrator_routing", return_value=teacher_routing):
        with patch("backend.agents.orchestrator.build_teacher_crew", return_value=mock_crew):
            resp = execute_orchestrated_pipeline(request=req, current_student=None)
            assert resp.status == "success"
            assert resp.selected_workflow == "teacher_answer"
            assert "An object will remain at rest" in resp.result["answer"]


# ==============================================================================
# 8. Malformed Output Recovery & JSON Repair
# ==============================================================================

def test_clean_json_payload_handles_markdown_and_repair():
    """Verify that clean_json_payload strips markdown code fences and repairs minor JSON defects."""
    # Markdown block
    raw_markdown = '```json\n{"selected_workflow": "teacher_answer", "detected_intent": "tutoring"}\n```'
    parsed = clean_json_payload(raw_markdown)
    assert parsed["selected_workflow"] == "teacher_answer"

    # Trailing comma repaired by json_repair
    raw_broken = '{"selected_workflow": "quiz_generation", "detected_intent": "practice",}'
    parsed_broken = clean_json_payload(raw_broken)
    assert parsed_broken["selected_workflow"] == "quiz_generation"
