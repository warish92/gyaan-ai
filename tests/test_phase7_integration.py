"""Integration tests for Phase 7: Canonical Orchestrator Agent with Live Ollama.

Executes genuine CrewAI Orchestrator Task against local Ollama (qwen2.5:3b).
Tagged with @pytest.mark.integration.
"""

import time
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.agents.orchestrator import (
    create_orchestrator_agent,
    create_orchestrator_task,
    run_orchestrator_routing,
    WORKFLOW_REGISTRY,
)
from backend.app.main import app
from backend.app.schemas import OrchestrationRequest
from backend.db.database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


@pytest.mark.integration
def test_live_orchestrator_routing_teacher_question():
    """Verify that a genuine CrewAI Orchestrator Agent accurately interprets and routes a science question."""
    req = OrchestrationRequest(
        request="Explain the difference between exothermic and endothermic reactions with examples.",
        grade="Class 10",
        subject="Chemistry",
    )

    start_time = time.perf_counter()
    decision = run_orchestrator_routing(request=req)
    elapsed = round(time.perf_counter() - start_time, 2)

    print(f"\n[Live Orchestrator Routing] Elapsed: {elapsed}s")
    print(f"Detected Intent: {decision.detected_intent}")
    print(f"Selected Workflow: {decision.selected_workflow}")
    print(f"Selected Agents: {decision.selected_agents}")
    print(f"Reason: {decision.routing_reason}")

    assert decision.selected_workflow == "teacher_answer"
    assert "Teacher Agent" in decision.selected_agents
    assert not decision.clarification_required
    assert decision.selected_workflow in WORKFLOW_REGISTRY


@pytest.mark.integration
def test_live_orchestrator_endpoint_full_pipeline():
    """Verify live POST /api/v1/orchestrate end-to-end execution with local Ollama."""
    start_time = time.perf_counter()
    resp = client.post(
        "/api/v1/orchestrate",
        json={
            "request": "What is the function of the human kidney according to NCERT Class 10?",
            "grade": "Class 10",
            "subject": "Biology",
            "language": "English",
        },
    )
    elapsed = round(time.perf_counter() - start_time, 2)

    assert resp.status_code == 200, f"Error: {resp.text}"
    data = resp.json()

    print(f"\n[Live Orchestrate API] Total duration: {elapsed}s | API duration_ms: {data['duration_ms']}")
    print(f"Selected Workflow: {data['selected_workflow']}")
    print(f"Answer snippet: {str(data.get('result', {}).get('answer', ''))[:100]}...")

    assert data["status"] == "success"
    assert data["selected_workflow"] == "teacher_answer"
    assert data["result"] is not None
    assert "answer" in data["result"]
    assert len(data["result"]["answer"]) > 20
