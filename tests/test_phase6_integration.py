"""Live End-to-End Integration Tests for Phase 6: Progress Agent & Mentor Agent.

Tests live execution through FastAPI against local Ollama (qwen2.5:3b):
1. Progress Analysis (GET /api/v1/students/me/progress)
2. Personalized Mentoring Recommendations (GET /api/v1/students/me/mentor-recommendations)
3. Consolidated Progress + Mentoring (GET /api/v1/students/me/progress-mentoring)
"""

import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure workspace root is in path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.app.main import app
from backend.db.database import (
    init_db,
    record_topic_assessment_score,
    save_assessment_attempt,
    save_quiz,
)

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_integration_db():
    init_db()


@pytest.mark.integration
def test_live_progress_endpoint():
    """Verify live Progress Agent execution and objective stats interpretation via GET /api/v1/students/me/progress."""
    email = f"integ_prog_{uuid.uuid4().hex[:6]}@gyaan.ai"
    reg_resp = client.post("/api/v1/auth/register", json={
        "display_name": "Progress Integration Student",
        "email": email,
        "password": "Password123!",
        "grade": "Class 10",
        "preferred_language": "English",
    })
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    student_id = auth_data["student"]["id"]
    headers = {"Authorization": f"Bearer {auth_data['token']}"}

    # Seed an assessment attempt
    quiz_id = f"quiz_prog_{uuid.uuid4().hex[:6]}"
    save_quiz(
        quiz_id=quiz_id,
        student_id=student_id,
        subject="Science",
        topic="Acids, Bases and Salts",
        grade="Class 10",
        questions=[{"id": "q1", "marks": 1.0}],
    )
    save_assessment_attempt(
        attempt_id=f"att_prog_{uuid.uuid4().hex[:6]}",
        quiz_id=quiz_id,
        student_id=student_id,
        submitted_answers={"q1": "7"},
        score=1.0,
        max_marks=1.0,
        evaluation_details={"evaluations": [{"question_id": "q1", "score_awarded": 1.0, "status": "correct"}]},
    )
    record_topic_assessment_score(
        student_id=student_id,
        subject="Science",
        topic="Acids, Bases and Salts",
        score=1.0,
        max_marks=1.0,
    )

    # Call endpoint
    resp = client.get("/api/v1/students/me/progress", headers=headers)
    assert resp.status_code == 200, f"Progress endpoint failed: {resp.text}"

    data = resp.json()
    assert data["student_id"] == student_id
    assert data["model"] == "ollama/qwen2.5:3b"
    assert len(data["overall_summary"]) > 10
    assert data["objective_statistics"]["total_assessments_completed"] >= 1
    assert data["duration_ms"] > 0


@pytest.mark.integration
def test_live_mentor_recommendations_endpoint():
    """Verify live sequential Progress -> Mentor workflow via GET /api/v1/students/me/mentor-recommendations."""
    email = f"integ_mentor_{uuid.uuid4().hex[:6]}@gyaan.ai"
    reg_resp = client.post("/api/v1/auth/register", json={
        "display_name": "Mentor Integration Student",
        "email": email,
        "password": "Password123!",
        "grade": "Class 10",
        "preferred_language": "English",
    })
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    student_id = auth_data["student"]["id"]
    headers = {"Authorization": f"Bearer {auth_data['token']}"}

    # Call endpoint
    resp = client.get("/api/v1/students/me/mentor-recommendations", headers=headers)
    assert resp.status_code == 200, f"Mentor endpoint failed: {resp.text}"

    data = resp.json()
    assert data["student_id"] == student_id
    assert data["model"] == "ollama/qwen2.5:3b"
    assert len(data["mentor_overview"]) > 10
    assert len(data["recommendations"]) >= 1
    rec = data["recommendations"][0]
    assert "title" in rec
    assert "suggested_action" in rec
    assert data["duration_ms"] > 0
