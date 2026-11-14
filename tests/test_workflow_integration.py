"""Live End-to-End Integration Test for Sequential Multi-Agent Workflow.

Exercises:
FastAPI POST /api/v1/learning-plan -> Diagnostic Agent -> Curriculum Agent (context) -> SQLite Persistence.
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure workspace root is in path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.app.main import app
from backend.db.database import get_diagnostic_record, get_curriculum_plan

client = TestClient(app)


@pytest.mark.integration
def test_live_learning_plan_endpoint_with_sequential_crew_and_sqlite():
    """Verify live multi-agent execution and SQLite persistence via /api/v1/learning-plan."""
    payload = {
        "student_id": "test_integration_student_01",
        "display_name": "Kavya",
        "grade": "Class 10",
        "subject": "Science",
        "topic": "Acids, Bases and Salts",
        "assessment_items": [
            {
                "question": "What is the difference between strong acids and weak acids in water?",
                "student_answer": "Strong acids completely break down into ions in water, while weak acids only partially ionize.",
                "expected_answer": "Strong acids dissociate completely into H+ (aq) ions. Weak acids dissociate only partially, establishing equilibrium.",
            },
            {
                "question": "What is the effect of dilution on the concentration of hydronium ions in an acid?",
                "student_answer": "Dilution makes the hydronium ion concentration increase because you add more liquid.",
                "expected_answer": "Dilution decreases the concentration of hydronium (H3O+) ions per unit volume.",
            },
        ],
    }

    response = client.post("/api/v1/learning-plan", json=payload)
    assert response.status_code == 200, f"Learning plan execution failed: {response.text}"

    data = response.json()
    assert "workflow_id" in data
    assert data["student_id"] == "test_integration_student_01"
    assert data["status"] == "success"
    assert data["model"] == "ollama/qwen2.5:3b"
    assert data["duration_ms"] > 0
    assert data["persisted"] is True
    assert data["diagnostic_id"] is not None
    assert data["plan_id"] is not None

    diag = data["diagnostic_report"]
    plan = data["curriculum_plan"]

    assert len(diag) > 100, "Diagnostic report must be substantive"
    assert len(plan) > 100, "Curriculum plan must be substantive"

    # Verify SQLite persistence
    persisted_diag = get_diagnostic_record(data["diagnostic_id"])
    assert persisted_diag is not None
    assert persisted_diag["student_id"] == "test_integration_student_01"
    assert persisted_diag["topic"] == "Acids, Bases and Salts"

    persisted_plan = get_curriculum_plan(data["plan_id"])
    assert persisted_plan is not None
    assert persisted_plan["diagnostic_id"] == data["diagnostic_id"]
