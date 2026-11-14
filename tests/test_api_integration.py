"""End-to-End Live Integration Test for Gyaan AI API with Genuine Local LLM.

Exercises the full pipeline:
FastAPI POST /api/v1/ask -> CrewAI Teacher Agent -> CrewAI Task -> Ollama (qwen2.5:3b) -> Response.
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

client = TestClient(app)


@pytest.mark.integration
def test_live_api_ask_with_genuine_crewai_and_ollama():
    """Verify live educational question execution through FastAPI and genuine CrewAI/Ollama."""
    payload = {
        "question": "What is the role of stomata in plant leaves for Class 10 CBSE?",
        "grade": "Class 10",
        "subject": "Biology",
        "language": "English",
    }

    response = client.post("/api/v1/ask", json=payload)
    assert response.status_code == 200, f"API call failed: {response.text}"

    data = response.json()
    assert "answer" in data
    assert "request_id" in data
    assert data["model"] == "ollama/qwen2.5:3b"
    assert data["status"] == "success"
    assert data["duration_ms"] > 0

    answer = data["answer"]
    assert len(answer) > 80, "Answer must be substantive"

    # Verify educational correctness
    lower_answer = answer.lower()
    has_relevant_concept = any(
        term in lower_answer
        for term in ["gas", "oxygen", "carbon dioxide", "guard cell", "transpiration", "pore", "leaf"]
    )
    assert has_relevant_concept, f"Answer does not discuss stomata concepts: {answer}"
