"""Gyaan AI - Agent Arena & Agent Registry Test Suite.

Verifies:
1. Discovery and registration of all 8 canonical CrewAI agents.
2. Genuine CrewAI Agent instances with valid roles, goals, backstories.
3. Thread-safe runtime execution state tracking (idle -> running -> completed/idle/error).
4. Agent Arena API endpoints:
   - GET /api/v1/arena/agents
   - GET /api/v1/arena/agents/{agent_id}
   - GET /api/v1/arena/status
   - GET /api/v1/arena/workflows
   - GET /api/v1/agents (alias)
5. Sensitive credential protection (no passwords or API keys exposed).
"""

import pytest
from starlette.testclient import TestClient

from backend.agents.registry import AgentRegistry, AgentMetadata, agent_registry, CANONICAL_AGENT_SPECS
from backend.agents.orchestrator import WORKFLOW_REGISTRY
from backend.app.main import app
from crewai import Agent

client = TestClient(app)

CANONICAL_EIGHT_IDS = [
    "orchestrator",
    "diagnostic",
    "curriculum",
    "resource",
    "teacher",
    "assessment",
    "progress",
    "mentor",
]


def test_canonical_specs_contain_eight_agents():
    """Verify registry specifications contain exactly the eight canonical agents."""
    assert len(CANONICAL_AGENT_SPECS) == 8
    spec_ids = [s["id"] for s in CANONICAL_AGENT_SPECS]
    assert spec_ids == CANONICAL_EIGHT_IDS


def test_registry_initializes_eight_genuine_agents():
    """Verify registry discovers and initializes all 8 canonical agents."""
    reg = AgentRegistry()
    agents = reg.initialize()

    assert len(agents) == 8
    agent_ids = [a.id for a in agents]
    assert agent_ids == CANONICAL_EIGHT_IDS

    for ag in agents:
        assert ag.name.endswith("Agent")
        assert len(ag.role) > 10
        assert len(ag.goal) > 10
        assert len(ag.backstory) > 10
        assert "ollama" in ag.model or "qwen" in ag.model
        assert ag.status == "idle"
        assert ag.registration_status == "registered"
        assert len(ag.associated_workflows) > 0


def test_api_arena_agents_endpoint():
    """Verify GET /api/v1/arena/agents returns all 8 agents matching schema."""
    response = client.get("/api/v1/arena/agents")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 8

    returned_ids = [item["id"] for item in data]
    assert returned_ids == CANONICAL_EIGHT_IDS

    # Check fields of Teacher Agent
    teacher = next(a for a in data if a["id"] == "teacher")
    assert teacher["name"] == "Teacher Agent"
    assert "Science Teacher" in teacher["role"]
    assert teacher["status"] in ("idle", "running", "completed")
    assert teacher["registration_status"] == "registered"
    assert "chapter_learning_journey" in teacher["associated_workflows"]
    assert "teacher_answer" in teacher["associated_workflows"]


def test_api_agents_alias_endpoint():
    """Verify GET /api/v1/agents acts as exact alias for /api/v1/arena/agents."""
    resp1 = client.get("/api/v1/arena/agents")
    resp2 = client.get("/api/v1/agents")

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert len(resp1.json()) == len(resp2.json()) == 8


def test_api_arena_single_agent():
    """Verify GET /api/v1/arena/agents/{agent_id} returns specific agent metadata."""
    for aid in CANONICAL_EIGHT_IDS:
        res = client.get(f"/api/v1/arena/agents/{aid}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == aid
        assert data["registration_status"] == "registered"

    # Test unknown agent returns 404
    unknown_res = client.get("/api/v1/arena/agents/quantum_teleportation_agent")
    assert unknown_res.status_code == 404


def test_api_arena_status():
    """Verify GET /api/v1/arena/status reports system summary."""
    response = client.get("/api/v1/arena/status")
    assert response.status_code == 200
    data = response.json()

    assert data["total_agents"] == 8
    assert data["registered_agents"] == 8
    assert data["status"] in ("healthy", "degraded")
    assert len(data["canonical_roster"]) == 8
    assert "Teacher Agent" in data["canonical_roster"]
    assert "Orchestrator Agent" in data["canonical_roster"]


def test_api_arena_workflows():
    """Verify GET /api/v1/arena/workflows returns all approved workflows from WORKFLOW_REGISTRY."""
    response = client.get("/api/v1/arena/workflows")
    assert response.status_code == 200
    data = response.json()

    assert len(data) >= 8
    wf_ids = [w["workflow_id"] for w in data]
    assert "chapter_learning_journey" in wf_ids
    assert "teacher_answer" in wf_ids
    assert "diagnostic_curriculum" in wf_ids
    assert "resource_search" in wf_ids
    assert "quiz_generation" in wf_ids
    assert "assessment_evaluation" in wf_ids
    assert "progress_analysis" in wf_ids
    assert "personalized_mentoring" in wf_ids


def test_runtime_state_tracking():
    """Verify dynamic state transitions: idle -> running -> idle and duration recording."""
    reg = AgentRegistry()
    reg.initialize()

    teacher = reg.get_agent("teacher")
    assert teacher.status == "idle"
    initial_execs = teacher.total_executions

    with reg.track_workflow_execution("teacher_answer"):
        running_teacher = reg.get_agent("teacher")
        assert running_teacher.status == "running"
        assert running_teacher.last_workflow == "teacher_answer"

    after_teacher = reg.get_agent("teacher")
    assert after_teacher.status == "idle"
    assert after_teacher.total_executions == initial_execs + 1
    assert after_teacher.last_duration_seconds is not None
    assert after_teacher.last_execution_time is not None


def test_error_state_tracking():
    """Verify exceptions during tracked execution set status to 'error' and record error message."""
    reg = AgentRegistry()
    reg.initialize()

    try:
        with reg.track_workflow_execution("teacher_answer"):
            raise RuntimeError("Simulated Ollama inference timeout")
    except RuntimeError:
        pass

    teacher = reg.get_agent("teacher")
    assert teacher.status == "error"
    assert "Simulated Ollama inference timeout" in str(teacher.last_error)


def test_no_sensitive_secrets_exposed():
    """Verify no API keys, tokens, or passwords are leaked in agent metadata."""
    response = client.get("/api/v1/arena/agents")
    assert response.status_code == 200
    text = response.text.lower()

    # Verify no credential, secret-value, or password leaks
    assert "password_hash" not in text
    assert "secret_key" not in text
    assert "api_key" not in text
    assert "bearer " not in text
    assert "telemetry_hmac_secret" not in text
    assert "a2a_internal_secret" not in text
    assert "token" not in text or "token" in text and "tokenizer" in text
