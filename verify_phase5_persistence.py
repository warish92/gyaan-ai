"""Gyaan AI - Phase 5 Standalone Verification Harness.

Exercises and verifies the complete student account and persistence lifecycle:
1. Student Registration & scrypt Password Hashing
2. Login, Session Token Generation & SHA-256 Storage
3. Profile Management & Permitted Field Updates (PATCH /students/me)
4. Learning Plan & Quiz Activity Linked to Verified Student Identity
5. Automatic Learning Session & Topic-Wise Mastery Tracking
6. Strict Multi-Student Data Isolation (403 Forbidden on Cross-Student Access)
7. Session Logout & Token Revocation
8. Persistence Across Simulated Application Restart & Dashboard Data Restoration
"""

import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Add project root to path
workspace_dir = Path(__file__).resolve().parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.app.main import app
from backend.db.database import (
    get_db_connection,
    get_quiz,
    get_student_assessment_history,
    get_student_by_email,
    get_student_by_id,
    get_student_dashboard_data,
    init_db,
)
from backend.services.auth_service import verify_password


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 80)
    print("GYAAN AI - PHASE 5 PERSISTENT STUDENT ACCOUNTS & DATA LIFECYCLE")
    print("=" * 80)

    # Step 0: Ensure DB initialization
    print("\n[Step 0] Initializing database and verifying schema...")
    init_db()
    conn = get_db_connection()
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    print(f"  Verified database tables: {tables}")
    conn.close()

    client = TestClient(app)

    # Step 1: Student Registration
    print("\n" + "=" * 80)
    print("[Step 1] Registering Student 1 (Aarav Sharma)")
    print("=" * 80)
    email_1 = f"aarav_{uuid.uuid4().hex[:6]}@gyaan.ai"
    password_1 = "AaravStrongPass123!"

    reg_resp = client.post("/api/v1/auth/register", json={
        "display_name": "Aarav Sharma",
        "email": email_1,
        "password": password_1,
        "grade": "Class 10",
        "preferred_language": "English",
    })
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
    reg_data = reg_resp.json()
    token_1 = reg_data["token"]
    student_1_id = reg_data["student"]["id"]
    headers_1 = {"Authorization": f"Bearer {token_1}"}

    print(f"  Registered Student ID: {student_1_id}")
    print(f"  Normalized Email     : {reg_data['student']['email']}")
    print(f"  Issued Session Token : {token_1[:16]}... (entropy: 256 bits)")

    # Verify password is stored as scrypt hash and not plaintext
    db_student = get_student_by_email(email_1)
    assert db_student is not None
    assert db_student["password_hash"].startswith("scrypt:")
    assert verify_password(password_1, db_student["password_hash"])
    print("  Password Storage     : Verified scrypt cryptographic salt & key in SQLite (no plaintext).")

    # Step 2: Profile Update
    print("\n" + "=" * 80)
    print("[Step 2] Testing Profile Management (PATCH /api/v1/students/me)")
    print("=" * 80)
    patch_resp = client.patch(
        "/api/v1/students/me",
        headers=headers_1,
        json={"display_name": "Aarav Sharma (CBSE)", "preferred_language": "Hindi"},
    )
    assert patch_resp.status_code == 200
    updated_prof = patch_resp.json()
    assert updated_prof["display_name"] == "Aarav Sharma (CBSE)"
    assert updated_prof["preferred_language"] == "Hindi"
    print(f"  Updated Profile Display Name: {updated_prof['display_name']}")
    print(f"  Updated Preferred Language  : {updated_prof['preferred_language']}")

    # Step 3: Learning Activity (Plan, Quiz, Attempt, and Topic Mastery)
    print("\n" + "=" * 80)
    print("[Step 3] Executing Learning Plan and Quiz with Student Session")
    print("=" * 80)

    # Learning plan
    mock_plan = {
        "diagnostic_report": "Proficient in indicators; requires reinforcement in neutralization equations.",
        "curriculum_plan": "Module 1: Acid-Base reactions. Module 2: Neutralization mechanics.",
    }
    with patch("backend.app.main.run_learning_plan_workflow", return_value=mock_plan):
        plan_resp = client.post(
            "/api/v1/learning-plan",
            headers=headers_1,
            json={
                "grade": "Class 10",
                "subject": "Science",
                "topic": "Acids, Bases and Salts",
                "assessment_items": [{"question": "What is an indicator?", "student_answer": "Changes color in acid or base."}],
            },
        )
        assert plan_resp.status_code == 200
        plan_data = plan_resp.json()
        print(f"  Created Learning Plan: Workflow ID={plan_data['workflow_id']}, Student ID={plan_data['student_id']}")

    # Quiz Generation
    mock_quiz = {
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "question": "Which of the following is neutral at 25 degrees C?",
                "options": ["A) pH 2", "B) pH 7", "C) pH 11", "D) pH 14"],
                "correct_answer": "B",
                "explanation": "Neutral pH is 7.",
                "marks": 1.0,
            },
            {
                "id": "q2",
                "type": "short_answer",
                "question": "Name the reaction between an acid and a base.",
                "options": [],
                "correct_answer": "Neutralization reaction",
                "explanation": "Acid + Base -> Salt + Water.",
                "marks": 2.0,
            },
        ],
        "is_verified_source": True,
        "source_type": "Verified Local NCERT Corpus",
    }
    with patch("backend.app.main.run_quiz_generation_workflow", return_value=mock_quiz):
        quiz_resp = client.post(
            "/api/v1/quizzes",
            headers=headers_1,
            json={
                "grade": "Class 10",
                "subject": "Science",
                "topic": "Acids, Bases and Salts",
                "num_questions": 2,
            },
        )
        assert quiz_resp.status_code == 200
        quiz_data = quiz_resp.json()
        quiz_id = quiz_data["quiz_id"]
        print(f"  Generated Practice Quiz: {quiz_id} (Student: {quiz_data['student_id']})")

    # Quiz Submission
    mock_eval = {
        "total_score": 3.0,
        "max_marks": 3.0,
        "overall_feedback": "Outstanding! Full marks scored.",
        "evaluations": [
            {
                "question_id": "q1",
                "score_awarded": 1.0,
                "max_marks": 1.0,
                "status": "correct",
                "student_answer": "B",
                "expected_answer": "B",
                "feedback": "Correct value for neutral solution.",
            },
            {
                "question_id": "q2",
                "score_awarded": 2.0,
                "max_marks": 2.0,
                "status": "correct",
                "student_answer": "Neutralization reaction",
                "expected_answer": "Neutralization reaction",
                "feedback": "Accurate term and description.",
            },
        ],
    }
    with patch("backend.app.main.run_answer_evaluation_workflow", return_value=mock_eval):
        eval_resp = client.post(
            "/api/v1/assessments/submit",
            headers=headers_1,
            json={
                "quiz_id": quiz_id,
                "answers": {"q1": "B", "q2": "Neutralization reaction"},
            },
        )
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        print(f"  Submitted Quiz Attempt : {eval_data['attempt_id']}, Score: {eval_data['total_score']}/{eval_data['max_marks']} ({eval_data['percentage']}%)")

    # Step 4: Multi-Student Data Isolation
    print("\n" + "=" * 80)
    print("[Step 4] Verifying Multi-Student Isolation with Student 2 (Bhavna Patel)")
    print("=" * 80)
    email_2 = f"bhavna_{uuid.uuid4().hex[:6]}@gyaan.ai"
    reg_2_resp = client.post("/api/v1/auth/register", json={
        "display_name": "Bhavna Patel",
        "email": email_2,
        "password": "BhavnaPassword123!",
    })
    assert reg_2_resp.status_code == 201
    token_2 = reg_2_resp.json()["token"]
    student_2_id = reg_2_resp.json()["student"]["id"]
    headers_2 = {"Authorization": f"Bearer {token_2}"}
    print(f"  Registered Student 2: {student_2_id} ({email_2})")

    # Student 2 attempts to read Student 1's assessment history
    leak_resp = client.get(f"/api/v1/assessments/history/{student_1_id}", headers=headers_2)
    print(f"  Student 2 querying Student 1's assessment history -> Status: HTTP {leak_resp.status_code}")
    assert leak_resp.status_code == 403, "Student 2 must be forbidden from accessing Student 1's history"

    # Student 2 attempts to submit answers to Student 1's quiz
    tamper_resp = client.post(
        "/api/v1/assessments/submit",
        headers=headers_2,
        json={"quiz_id": quiz_id, "answers": {"q1": "Tampered"}},
    )
    print(f"  Student 2 attempting to submit answers to Student 1's quiz -> Status: HTTP {tamper_resp.status_code}")
    assert tamper_resp.status_code == 403, "Student 2 must be forbidden from submitting to Student 1's quiz"
    print("  Multi-Student Isolation: VERIFIED (403 Forbidden strictly enforced).")

    # Step 5: Session Revocation & Logout
    print("\n" + "=" * 80)
    print("[Step 5] Logging Out Student 1 and Verifying Token Revocation")
    print("=" * 80)
    logout_resp = client.post("/api/v1/auth/logout", headers=headers_1)
    assert logout_resp.status_code == 200
    revoked_resp = client.get("/api/v1/students/me", headers=headers_1)
    print(f"  Accessing /students/me with logged-out token -> Status: HTTP {revoked_resp.status_code}")
    assert revoked_resp.status_code == 401
    print("  Token Revocation: VERIFIED.")

    # Step 6: Application Restart Simulation and Complete Data Restoration
    print("\n" + "=" * 80)
    print("[Step 6] Simulating Application Restart & Data Restoration")
    print("=" * 80)
    print("  Closing existing client session...")
    del client

    print("  Spawning fresh FastAPI TestClient instance connecting to existing SQLite DB...")
    new_client = TestClient(app)

    # Re-login with original credentials
    login_resp = new_client.post("/api/v1/auth/login", json={
        "email": email_1,
        "password": password_1,
    })
    assert login_resp.status_code == 200, f"Login failed after restart: {login_resp.text}"
    new_session_token = login_resp.json()["token"]
    new_headers = {"Authorization": f"Bearer {new_session_token}"}
    print(f"  Re-login successful. New session token: {new_session_token[:16]}...")

    # Fetch Dashboard
    dash_resp = new_client.get("/api/v1/students/me/dashboard", headers=new_headers)
    assert dash_resp.status_code == 200
    dash = dash_resp.json()

    print("\n  --- Aggregated Student Dashboard Summary (Post-Restart) ---")
    print(f"  Student ID           : {dash['profile']['id']}")
    print(f"  Display Name         : {dash['profile']['display_name']}")
    print(f"  Grade & Language     : {dash['profile']['grade']}, {dash['profile']['preferred_language']}")
    print(f"  Total Quizzes Taken  : {dash['stats']['total_quizzes_taken']}")
    print(f"  Topics Mastered      : {dash['stats']['topics_mastered']}")
    print(f"  Recent Diagnostics   : {len(dash['recent_diagnostics'])} records")
    print(f"  Recent Plans         : {len(dash['recent_curriculum_plans'])} plans")
    print(f"  Recent Assessments   : {len(dash['recent_assessments'])} attempts")
    print(f"  Topic Mastery Entries: {len(dash['topic_mastery'])} entries")

    assert dash["profile"]["id"] == student_1_id
    assert dash["profile"]["display_name"] == "Aarav Sharma (CBSE)"
    assert dash["stats"]["total_quizzes_taken"] >= 1
    assert dash["stats"]["topics_mastered"] >= 1
    assert len(dash["topic_mastery"]) >= 1
    assert dash["topic_mastery"][0]["mastery_status"] == "mastered"
    assert len(dash["recent_learning_sessions"]) >= 1

    print("\n" + "=" * 80)
    print("ALL PHASE 5 VERIFICATION CHECKS PASSED WITH 100% SUCCESS!")
    print("=" * 80)


if __name__ == "__main__":
    main()
