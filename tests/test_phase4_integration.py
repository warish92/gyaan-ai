"""Live End-to-End Integration Tests for Phase 4: Resource Agent & Assessment Agent.

Tests live execution through FastAPI against local Ollama (qwen2.5:3b):
1. Educational Resource Retrieval (POST /api/v1/resources)
2. Practice Quiz Generation (POST /api/v1/quizzes)
3. Quiz Submission & Answer Evaluation (POST /api/v1/assessments/submit)
4. Student Assessment History (GET /api/v1/assessments/history/{student_id})
"""

import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure workspace root is in path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.app.main import app
from backend.db.database import (
    create_session,
    create_student_account,
    get_quiz,
    get_student_assessment_history,
)
from backend.services.auth_service import (
    generate_session_token,
    hash_password,
    hash_session_token,
)

client = TestClient(app)


@pytest.mark.integration
def test_live_resources_endpoint():
    """Verify live Resource Agent execution and local NCERT retrieval via POST /api/v1/resources."""
    payload = {
        "grade": "Class 10",
        "subject": "Science",
        "topic": "Acids, Bases and Salts",
        "learning_objective": "Understand pH scale, indicators, and neutralization.",
    }
    response = client.post("/api/v1/resources", json=payload)
    assert response.status_code == 200, f"Resource workflow failed: {response.text}"

    data = response.json()
    assert "workflow_id" in data
    assert data["is_verified"] is True
    assert "Verified Local" in data["source_type"]
    assert len(data["sources"]) >= 1
    assert len(data["resource_recommendation"]) > 50
    assert data["model"] == "ollama/qwen2.5:3b"


@pytest.mark.integration
def test_live_quiz_generation_and_evaluation_cycle():
    """Verify live end-to-end cycle: Quiz generation -> Student submission -> History retrieval."""
    test_student_id = f"student_integ_{uuid.uuid4().hex[:6]}"

    # Setup authenticated student account & session (required for history ownership verification per SEC-FIND-01)
    email = f"{test_student_id}@example.com"
    pw_hash = hash_password("IntegPassword2026!")
    create_student_account(
        student_id=test_student_id,
        email=email,
        password_hash=pw_hash,
        display_name="Integ Student",
        grade="Class 10",
        preferred_language="English",
    )
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    create_session(
        session_id=f"sess_{uuid.uuid4().hex[:8]}",
        student_id=test_student_id,
        token_hash=token_hash,
        expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    )
    auth_headers = {"Authorization": f"Bearer {raw_token}"}

    # Step 1: Generate Quiz
    quiz_payload = {
        "student_id": test_student_id,
        "grade": "Class 10",
        "subject": "Science",
        "topic": "Acids, Bases and Salts",
        "num_questions": 2,
        "question_types": ["mcq", "short_answer"],
        "learning_objectives": "Assess understanding of neutralization reactions and pH values.",
    }
    quiz_resp = client.post("/api/v1/quizzes", json=quiz_payload)
    assert quiz_resp.status_code == 200, f"Quiz generation failed: {quiz_resp.text}"

    quiz_data = quiz_resp.json()
    quiz_id = quiz_data["quiz_id"]
    assert quiz_id.startswith("quiz_")
    assert quiz_data["student_id"] == test_student_id
    assert len(quiz_data["questions"]) >= 1
    assert quiz_data["is_verified_source"] is True

    # SECURITY CHECK: Student-facing response must NOT reveal correct answers or rubrics
    for q in quiz_data["questions"]:
        assert "correct_answer" not in q, "Security breach: correct_answer exposed in student response!"
        assert "explanation" not in q, "Security breach: explanation exposed in student response!"
        assert "id" in q
        assert "question" in q

    # Verify complete quiz with answer keys was persisted to SQLite
    stored_quiz = get_quiz(quiz_id)
    assert stored_quiz is not None
    assert len(stored_quiz["questions"]) == len(quiz_data["questions"])
    assert "correct_answer" in stored_quiz["questions"][0]

    # Step 2: Submit Answers for Evaluation
    # Prepare student answers for each returned question
    submitted_answers = {}
    for q in quiz_data["questions"]:
        qid = q["id"]
        if q["type"] == "mcq" and q.get("options"):
            # Choose the first option or a plausible answer
            submitted_answers[qid] = q["options"][0]
        else:
            submitted_answers[qid] = "Neutralization produces salt and water."

    submit_payload = {
        "quiz_id": quiz_id,
        "student_id": test_student_id,
        "answers": submitted_answers,
    }
    eval_resp = client.post("/api/v1/assessments/submit", json=submit_payload)
    assert eval_resp.status_code == 200, f"Assessment submission failed: {eval_resp.text}"

    eval_data = eval_resp.json()
    assert eval_data["attempt_id"].startswith("att_")
    assert eval_data["quiz_id"] == quiz_id
    assert eval_data["student_id"] == test_student_id
    assert "total_score" in eval_data
    assert "max_marks" in eval_data
    assert "percentage" in eval_data
    assert len(eval_data["evaluations"]) == len(quiz_data["questions"])
    assert len(eval_data["overall_feedback"]) > 10
    assert eval_data["persisted"] is True

    # Step 3: Query Student Assessment History (requires authenticated student per SEC-FIND-01)
    history_resp = client.get(
        f"/api/v1/assessments/history/{test_student_id}",
        headers=auth_headers,
    )
    assert history_resp.status_code == 200, f"History retrieval failed: {history_resp.text}"

    history_data = history_resp.json()
    assert history_data["student_id"] == test_student_id
    assert history_data["total_attempts"] >= 1
    assert history_data["attempts"][0]["quiz_id"] == quiz_id
    assert history_data["attempts"][0]["attempt_id"] == eval_data["attempt_id"]
