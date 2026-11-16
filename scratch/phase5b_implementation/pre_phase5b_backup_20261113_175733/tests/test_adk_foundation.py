"""Gyaan AI - Google ADK Foundation Test Suite.

Verifies:
- Test 1: Google ADK installation and package imports.
- Test 2: Genuine Google ADK Agent construction and attribute verification.
- Test 3: Structured Pydantic request/response validation.
- Test 4: Rejection of malformed / invalid requests.
- Test 5: Session isolation between different students.
- Test 6: Model failure and timeout resilience.
- Test 7: FastAPI endpoint integration (/api/v1/adk/health & /learning-analysis).
- Test 8: CrewAI regression (all eight canonical specialist agents operational).
"""

import asyncio
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import google.adk
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.models.lite_llm import LiteLlm

from backend.adk.config import get_adk_model
from backend.adk.agents.learning_analysis_agent import (
    create_learning_intelligence_agent,
)
from backend.adk.schemas.adk_messages import (
    AssessmentEvidence,
    DiagnosticEvidence,
    LearningIntelligenceRequest,
    LearningIntelligenceResponse,
    TopicPerformance,
)
from backend.adk.services.adk_runner import (
    ADKLearningIntelligenceService,
    adk_learning_service,
)
from backend.app.main import app

# CrewAI Canonical Agent factories for regression verification
from backend.agents.orchestrator import create_orchestrator_agent
from backend.agents.diagnostic import create_diagnostic_agent
from backend.agents.curriculum import create_curriculum_agent
from backend.agents.resource import create_resource_agent
from backend.agents.teacher import create_teacher_agent
from backend.agents.assessment import create_assessment_agent
from backend.agents.progress import create_progress_agent
from backend.agents.mentor import create_mentor_agent
from backend.agents.registry import agent_registry


def test_01_adk_installation():
    """TEST 1: Verify Google ADK package imports successfully with valid version."""
    assert hasattr(google.adk, "__version__")
    version = google.adk.__version__
    assert version == "2.14.0"
    assert issubclass(Agent, object)
    assert issubclass(Runner, object)
    assert issubclass(LiteLlm, object)


def test_02_adk_agent_construction():
    """TEST 2: Verify Learning Intelligence Agent is a genuine Google ADK Agent."""
    agent = create_learning_intelligence_agent()
    assert isinstance(agent, Agent)
    assert agent.name == "learning_intelligence_agent"
    assert "Learning Intelligence" in agent.instruction
    assert isinstance(agent.model, LiteLlm)
    assert "qwen2.5:3b" in agent.model.model


def test_03_adk_schemas_validation():
    """TEST 3: Verify structured Pydantic models validate realistic student evidence."""
    diag = DiagnosticEvidence(
        topic_id="chem_react_types",
        topic_name="Types of Chemical Reactions",
        probes_evaluated=5,
        score=2.0,
        accuracy_pct=40.0,
        identified_misconceptions=["Thermal decomposition confused with physical melting"],
        mastery_status="struggling",
    )
    assert diag.score == 2.0
    assert diag.accuracy_pct == 40.0

    att = AssessmentEvidence(
        assessment_type="practice_set",
        total_questions=10,
        correct_answers=6,
        percentage=60.0,
        recurring_errors=["Unbalanced oxygen atoms in decomposition equations"],
    )
    assert att.percentage == 60.0

    tp = TopicPerformance(
        topic_id="chem_react_types",
        topic_name="Types of Chemical Reactions",
        attempts=2,
        average_score=50.0,
        current_mastery_level="developing",
        struggle_indicators=["Balancing stoichiometric coefficients"],
    )

    req = LearningIntelligenceRequest(
        student_id="student_adk_001",
        chapter_id="ch_chemical_reactions",
        chapter_name="Chemical Reactions and Equations",
        learning_objectives=["Identify combination, decomposition, displacement reactions"],
        diagnostic_evidence=diag,
        assessment_evidence=[att],
        topic_performances=[tp],
    )
    assert req.student_id == "student_adk_001"
    assert req.chapter_name == "Chemical Reactions and Equations"


def test_04_adk_invalid_input_rejection():
    """TEST 4: Verify malformed requests are rejected safely."""
    # Blank student ID rejected
    with pytest.raises(ValidationError):
        LearningIntelligenceRequest(
            student_id="   ",
            chapter_id="ch_1",
            chapter_name="Test",
        )

    # Invalid percentage (> 100) rejected
    with pytest.raises(ValidationError):
        AssessmentEvidence(
            assessment_type="quiz",
            total_questions=10,
            correct_answers=12,
            percentage=120.0,
        )

    # Negative total questions rejected
    with pytest.raises(ValidationError):
        AssessmentEvidence(
            assessment_type="quiz",
            total_questions=0,
            correct_answers=0,
            percentage=0.0,
        )


def test_05_adk_session_isolation():
    """TEST 5: Verify two different students cannot access each other's session state."""
    async def _test():
        service = ADKLearningIntelligenceService()

        # Student A creates a session
        session_a = await service.get_or_create_session(student_id="student_alice")
        assert session_a.id is not None
        assert service.is_session_owned_by_student("student_alice", session_a.id)

        # Student B attempts to access Student A's session
        with pytest.raises(PermissionError) as exc_info:
            await service.get_or_create_session(
                student_id="student_bob", session_id=session_a.id
            )
        assert "belongs to another student" in str(exc_info.value)

    asyncio.run(_test())


def test_06_adk_model_failure_handling():
    """TEST 6: Verify graceful recovery when model endpoint fails or times out."""
    async def _test():
        # Service configured with unreachable port and 1s timeout
        failing_service = ADKLearningIntelligenceService(
            api_base="http://127.0.0.1:59999",
            timeout_seconds=2,
        )

        req = LearningIntelligenceRequest(
            student_id="student_test_fail",
            chapter_id="ch_1",
            chapter_name="Chemical Reactions and Equations",
            learning_objectives=["Understand reactions"],
            query="Explain misconceptions",
        )

        response = await failing_service.analyze_learning(req)
        assert isinstance(response, LearningIntelligenceResponse)
        assert response.execution_status == "error"
        assert "Analysis failed" in response.summary
        assert response.confidence == 0.0
        assert response.execution_metadata.agent_framework == "Google ADK"

    asyncio.run(_test())


def test_07_fastapi_adk_health_endpoint():
    """TEST 7A: Verify GET /api/v1/adk/health returns healthy status and metadata."""
    client = TestClient(app)
    res = client.get("/api/v1/adk/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["adk_version"] == "2.14.0"
    assert data["framework"] == "Google Agent Development Kit (ADK)"
    assert "qwen2.5:3b" in data["model"]


def test_08_fastapi_adk_validation_error():
    """TEST 7B: Verify malformed payload returns HTTP 422 Unprocessable Entity."""
    client = TestClient(app)
    # Missing required chapter_id and chapter_name
    res = client.post("/api/v1/adk/learning-analysis", json={"student_id": "std_1"})
    assert res.status_code == 422


def test_09_crewai_regression():
    """TEST 9: Verify all eight canonical CrewAI specialist agents still construct and operate."""
    agents = [
        ("orchestrator", create_orchestrator_agent()),
        ("diagnostic", create_diagnostic_agent()),
        ("curriculum", create_curriculum_agent()),
        ("resource", create_resource_agent()),
        ("teacher", create_teacher_agent()),
        ("assessment", create_assessment_agent()),
        ("progress", create_progress_agent()),
        ("mentor", create_mentor_agent()),
    ]
    assert len(agents) == 8
    for name, agent in agents:
        assert agent is not None
        assert agent.role is not None
        assert agent.goal is not None
        assert agent.backstory is not None
        assert "qwen2.5:3b" in agent.llm.model

    # Check registry status
    all_metadata = agent_registry.get_all_agents()
    assert len(all_metadata) == 8
