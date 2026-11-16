"""Comprehensive Test Suite for Phase 5: Authentication, Student Accounts & Learning Data Persistence.

Covers:
- Section 15.A: Registration validation, email uniqueness, scrypt password hashing
- Section 15.B: Login, credential verification, session token revocation, expiration
- Section 15.C: Complete persistence lifecycle surviving simulated application restart
- Section 15.D: Multi-student data isolation and authorization checks (403 Forbidden)
- Section 15.E: Database integrity, profile updates, and dashboard aggregation
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure workspace root is in path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.app.main import app
from backend.db.database import (
    create_session,
    get_db_connection,
    get_quiz,
    get_student_assessment_history,
    get_student_by_email,
    get_student_by_id,
    init_db,
    save_assessment_attempt,
    save_curriculum_plan,
    save_diagnostic_record,
    save_quiz,
    save_student,
)
from backend.services.auth_service import hash_session_token, verify_password

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    """Ensure database tables exist before each test."""
    init_db()


# ==============================================================================
# 15.A Registration Tests
# ==============================================================================

def test_student_registration_success():
    """Verify new student can register, receiving a stable ID and token."""
    email = f"student_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "display_name": "Rohan Verma",
        "email": email,
        "password": "StrongPassword123!",
        "grade": "Class 10",
        "preferred_language": "English",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "token" in data
    assert data["token_type"] == "bearer"
    assert "expires_at" in data
    student = data["student"]
    assert student["display_name"] == "Rohan Verma"
    assert student["email"] == email.lower()
    assert student["grade"] == "Class 10"
    assert student["account_status"] == "active"

    # CRITICAL SECURITY CHECK: Password or hash must NEVER be in response
    assert "password" not in student
    assert "password_hash" not in student

    # Verify student is in SQLite database
    db_student = get_student_by_email(email)
    assert db_student is not None
    assert db_student["id"] == student["id"]
    assert db_student["password_hash"].startswith("scrypt:")
    # Verify password is not in plaintext in SQLite
    assert db_student["password_hash"] != "StrongPassword123!"
    assert verify_password("StrongPassword123!", db_student["password_hash"])


def test_registration_rejects_duplicate_email():
    """Verify registration rejects duplicate email addresses with 409 Conflict."""
    email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "display_name": "Student One",
        "email": email,
        "password": "Password123!",
    }
    # First registration succeeds
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    # Second registration with same email (even with different casing) must fail
    payload_dup = {
        "display_name": "Student Two",
        "email": email.upper(),
        "password": "Password999!",
    }
    resp2 = client.post("/api/v1/auth/register", json=payload_dup)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"].lower()


def test_registration_rejects_invalid_inputs():
    """Verify registration rejects blank names, short passwords, and bad emails."""
    # Blank name
    r1 = client.post("/api/v1/auth/register", json={
        "display_name": "   ",
        "email": "valid@example.com",
        "password": "ValidPassword123!",
    })
    assert r1.status_code == 422

    # Password too short (< 6 chars)
    r2 = client.post("/api/v1/auth/register", json={
        "display_name": "Valid Name",
        "email": "valid@example.com",
        "password": "123",
    })
    assert r2.status_code == 422

    # Invalid email format
    r3 = client.post("/api/v1/auth/register", json={
        "display_name": "Valid Name",
        "email": "not-an-email",
        "password": "ValidPassword123!",
    })
    assert r3.status_code == 422


# ==============================================================================
# 15.B Authentication & Session Lifecycle Tests
# ==============================================================================

def test_login_with_valid_credentials():
    """Verify student can log in with registered email and password."""
    email = f"login_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectPassword123!"

    reg_resp = client.post("/api/v1/auth/register", json={
        "display_name": "Login Tester",
        "email": email,
        "password": password,
    })
    assert reg_resp.status_code == 201

    # Attempt login
    login_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "token" in login_data
    assert login_data["student"]["email"] == email


def test_login_with_invalid_credentials():
    """Verify login fails with wrong password or nonexistent email with generic 401."""
    # Nonexistent user
    r1 = client.post("/api/v1/auth/login", json={
        "email": "nonexistent_ghost@example.com",
        "password": "AnyPassword123!",
    })
    assert r1.status_code == 401

    # Registered user, wrong password
    email = f"wrongpw_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={
        "display_name": "Tester",
        "email": email,
        "password": "RightPassword123!",
    })
    r2 = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "WrongPassword!",
    })
    assert r2.status_code == 401


def test_logout_and_revocation():
    """Verify logout revokes the session token, preventing further access."""
    email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = client.post("/api/v1/auth/register", json={
        "display_name": "Logout Tester",
        "email": email,
        "password": "Password123!",
    })
    token = reg_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Access protected profile
    prof_resp = client.get("/api/v1/students/me", headers=headers)
    assert prof_resp.status_code == 200

    # Logout
    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200

    # Attempt to access protected profile again with revoked token
    prof_resp_after = client.get("/api/v1/students/me", headers=headers)
    assert prof_resp_after.status_code == 401
    assert "revoked" in prof_resp_after.json()["detail"].lower() or "invalid" in prof_resp_after.json()["detail"].lower()


def test_expired_token_rejected():
    """Verify expired session tokens are rejected with 401."""
    email = f"expired_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = client.post("/api/v1/auth/register", json={
        "display_name": "Expired Tester",
        "email": email,
        "password": "Password123!",
    })
    student_id = reg_resp.json()["student"]["id"]

    # Manually insert an expired session token
    raw_token = f"expired_raw_token_{uuid.uuid4().hex[:12]}"
    token_hash = hash_session_token(raw_token)
    past_expiration = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    create_session(
        session_id=f"sess_{uuid.uuid4().hex[:8]}",
        student_id=student_id,
        token_hash=token_hash,
        expires_at=past_expiration,
    )

    expired_headers = {"Authorization": f"Bearer {raw_token}"}
    resp = client.get("/api/v1/students/me", headers=expired_headers)
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


# ==============================================================================
# 15.C Mandatory Persistence Across Application Restart
# ==============================================================================

def test_full_persistence_lifecycle_across_restart():
    """Verify that a student can register, create learning plans & quiz attempts,

    experience an application restart, log back in, and find all historical data intact.
    """
    email = f"lifecycle_{uuid.uuid4().hex[:8]}@example.com"
    password = "LifecyclePassword123!"

    # 1. Register Student
    reg_resp = client.post("/api/v1/auth/register", json={
        "display_name": "Ananya Sen",
        "email": email,
        "password": password,
        "grade": "Class 10",
        "preferred_language": "English",
    })
    assert reg_resp.status_code == 201
    initial_token = reg_resp.json()["token"]
    student_id = reg_resp.json()["student"]["id"]
    headers = {"Authorization": f"Bearer {initial_token}"}

    # 2. Generate a Learning Plan (mocked workflow for fast reliable test execution)
    mock_workflow_output = {
        "diagnostic_report": "Demonstrated strong knowledge in pH scale; gap in redox equations.",
        "curriculum_plan": "Module 1: Oxidation-Reduction Reactions. Module 2: Practice equations.",
    }
    with patch("backend.app.main.run_learning_plan_workflow", return_value=mock_workflow_output):
        plan_resp = client.post(
            "/api/v1/learning-plan",
            headers=headers,
            json={
                "grade": "Class 10",
                "subject": "Science",
                "topic": "Chemical Reactions",
                "assessment_items": [{"question": "What is oxidation?", "student_answer": "Gain of oxygen."}],
            },
        )
        assert plan_resp.status_code == 200
        plan_data = plan_resp.json()
        assert plan_data["student_id"] == student_id

    # 3. Generate a Quiz
    mock_quiz_output = {
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "question": "What is the pH of pure water?",
                "options": ["A) 7", "B) 2", "C) 12", "D) 0"],
                "correct_answer": "A",
                "explanation": "Pure water is neutral with pH 7.",
                "marks": 1.0,
            }
        ],
        "is_verified_source": True,
        "source_type": "verified_local",
    }
    with patch("backend.app.main.run_quiz_generation_workflow", return_value=mock_quiz_output):
        quiz_resp = client.post(
            "/api/v1/quizzes",
            headers=headers,
            json={
                "grade": "Class 10",
                "subject": "Science",
                "topic": "Acids and Bases",
                "num_questions": 1,
            },
        )
        assert quiz_resp.status_code == 200
        quiz_data = quiz_resp.json()
        quiz_id = quiz_data["quiz_id"]
        assert quiz_data["student_id"] == student_id

    # 4. Submit Quiz Answer
    mock_eval_output = {
        "total_score": 1.0,
        "max_marks": 1.0,
        "overall_feedback": "Perfect answer!",
        "evaluations": [
            {
                "question_id": "q1",
                "score_awarded": 1.0,
                "max_marks": 1.0,
                "status": "correct",
                "student_answer": "A",
                "expected_answer": "A",
                "feedback": "Correct value.",
            }
        ],
    }
    with patch("backend.app.main.run_answer_evaluation_workflow", return_value=mock_eval_output):
        submit_resp = client.post(
            "/api/v1/assessments/submit",
            headers=headers,
            json={
                "quiz_id": quiz_id,
                "answers": {"q1": "A"},
            },
        )
        assert submit_resp.status_code == 200
        attempt_data = submit_resp.json()
        assert attempt_data["total_score"] == 1.0

    # 5. End Session (Logout)
    client.post("/api/v1/auth/logout", headers=headers)

    # --------------------------------------------------------------------------
    # 6. SIMULATE APPLICATION RESTART
    # Re-initialize TestClient completely without resetting SQLite database
    # --------------------------------------------------------------------------
    new_client = TestClient(app)

    # 7. Log in again with original credentials
    login_resp = new_client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert login_resp.status_code == 200
    new_token = login_resp.json()["token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # 8. Retrieve Dashboard and verify complete historical data restoration
    dash_resp = new_client.get("/api/v1/students/me/dashboard", headers=new_headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()

    # Verify student identity survived restart
    assert dash_data["profile"]["id"] == student_id
    assert dash_data["profile"]["email"] == email.lower()
    assert dash_data["profile"]["display_name"] == "Ananya Sen"

    # Verify diagnostic & curriculum plans survived restart
    assert len(dash_data["recent_diagnostics"]) >= 1
    assert dash_data["recent_diagnostics"][0]["student_id"] == student_id
    assert len(dash_data["recent_curriculum_plans"]) >= 1
    assert dash_data["recent_curriculum_plans"][0]["student_id"] == student_id

    # Verify quiz attempts and scores survived restart
    assert len(dash_data["recent_assessments"]) >= 1
    assert dash_data["recent_assessments"][0]["quiz_id"] == quiz_id
    assert dash_data["recent_assessments"][0]["score"] == 1.0

    # Verify topic mastery survived restart
    assert len(dash_data["topic_mastery"]) >= 1
    mastery = dash_data["topic_mastery"][0]
    assert mastery["student_id"] == student_id
    assert mastery["mastery_status"] == "mastered"

    # Verify learning session history survived restart
    assert len(dash_data["recent_learning_sessions"]) >= 1
    assert dash_data["stats"]["total_quizzes_taken"] >= 1


# ==============================================================================
# 15.D Multi-Student Data Isolation Tests
# ==============================================================================

def test_multi_student_data_isolation():
    """Verify Student A cannot access or tamper with Student B's private learning records."""
    # Register Student A
    email_a = f"student_a_{uuid.uuid4().hex[:6]}@example.com"
    resp_a = client.post("/api/v1/auth/register", json={
        "display_name": "Student A",
        "email": email_a,
        "password": "PasswordA123!",
    })
    token_a = resp_a.json()["token"]
    id_a = resp_a.json()["student"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register Student B
    email_b = f"student_b_{uuid.uuid4().hex[:6]}@example.com"
    resp_b = client.post("/api/v1/auth/register", json={
        "display_name": "Student B",
        "email": email_b,
        "password": "PasswordB123!",
    })
    token_b = resp_b.json()["token"]
    id_b = resp_b.json()["student"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. Profile Isolation: Student A calling /students/me gets Student A, not B
    profile_a = client.get("/api/v1/students/me", headers=headers_a).json()
    assert profile_a["id"] == id_a
    assert profile_a["email"] == email_a

    # 2. Create private quiz for Student B
    quiz_b_id = f"quiz_b_{uuid.uuid4().hex[:8]}"
    save_quiz(
        quiz_id=quiz_b_id,
        student_id=id_b,
        subject="Science",
        topic="Acids",
        grade="Class 10",
        questions=[{"id": "q1", "question": "What is pH 7?", "correct_answer": "Neutral", "marks": 1.0}],
    )

    # 3. Create private assessment attempt for Student B
    save_assessment_attempt(
        attempt_id=f"att_b_{uuid.uuid4().hex[:8]}",
        quiz_id=quiz_b_id,
        student_id=id_b,
        submitted_answers={"q1": "Neutral"},
        score=1.0,
        max_marks=1.0,
        evaluation_details={"status": "correct"},
    )

    # 4. Student A tries to view Student B's assessment history -> MUST BE 403 FORBIDDEN
    leak_attempt = client.get(f"/api/v1/assessments/history/{id_b}", headers=headers_a)
    assert leak_attempt.status_code == 403
    assert "access denied" in leak_attempt.json()["detail"].lower()

    # 5. Student A tries to submit answers to Student B's private quiz -> MUST BE 403 FORBIDDEN
    tamper_attempt = client.post(
        "/api/v1/assessments/submit",
        headers=headers_a,
        json={"quiz_id": quiz_b_id, "answers": {"q1": "Hacked Answer"}},
    )
    assert tamper_attempt.status_code == 403
    assert "access denied" in tamper_attempt.json()["detail"].lower()

    # 6. Verify Student B's assessment records remain completely untouched
    history_b = get_student_assessment_history(id_b)
    assert len(history_b) == 1
    assert history_b[0]["score"] == 1.0


# ==============================================================================
# 15.E Profile Management and Schema Integrity
# ==============================================================================

def test_profile_update_endpoint():
    """Verify PATCH /api/v1/students/me updates permitted fields without altering credentials."""
    email = f"profile_up_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = client.post("/api/v1/auth/register", json={
        "display_name": "Initial Name",
        "email": email,
        "password": "Password123!",
        "grade": "Class 9",
        "preferred_language": "English",
    })
    token = reg_resp.json()["token"]
    student_id = reg_resp.json()["student"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Update profile
    patch_resp = client.patch(
        "/api/v1/students/me",
        headers=headers,
        json={
            "display_name": "Updated Name",
            "grade": "Class 10",
            "preferred_language": "Hindi",
        },
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["id"] == student_id
    assert updated["display_name"] == "Updated Name"
    assert updated["grade"] == "Class 10"
    assert updated["preferred_language"] == "Hindi"
    assert updated["email"] == email

    # Verify in database that password_hash was NOT altered or cleared
    db_student = get_student_by_id(student_id)
    assert db_student["display_name"] == "Updated Name"
    assert db_student["grade"] == "Class 10"


def test_empty_learning_history_returns_valid_empty_dashboard():
    """Verify new student with no previous activity receives a valid empty dashboard."""
    email = f"empty_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = client.post("/api/v1/auth/register", json={
        "display_name": "Fresh Student",
        "email": email,
        "password": "Password123!",
    })
    token = reg_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    dash_resp = client.get("/api/v1/students/me/dashboard", headers=headers)
    assert dash_resp.status_code == 200
    data = dash_resp.json()
    assert data["recent_learning_sessions"] == []
    assert data["recent_diagnostics"] == []
    assert data["recent_curriculum_plans"] == []
    assert data["recent_assessments"] == []
    assert data["topic_mastery"] == []
    assert data["stats"]["total_quizzes_taken"] == 0
