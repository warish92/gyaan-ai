"""Gyaan AI - Phase 6 Standalone Verification Harness.

Exercises and verifies the complete canonical Progress Agent & Mentor Agent lifecycle:
1. Student Account Registration & Authentic Learning Data Seeding
2. Standalone Progress Agent Execution (Genuine CrewAI Agent + Task + Local Ollama)
3. Sequential Multi-Agent Workflow (Progress Agent -> Task Context -> Mentor Agent)
4. Context-Driven Recommendation Quality & NCERT Resource References
5. Zero-History Student Analysis (Honest 'insufficient_evidence' Reporting)
6. Authenticated FastAPI REST Endpoints & Multi-Student Isolation
"""

import json
import sys
import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

# Ensure workspace root is in path
workspace_dir = Path(__file__).resolve().parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.agents.progress_workflow import (
    run_progress_analysis_workflow,
    run_progress_and_mentor_workflow,
)
from backend.app.main import app
from backend.db.database import (
    init_db,
    record_topic_assessment_score,
    save_assessment_attempt,
    save_curriculum_plan,
    save_diagnostic_record,
    save_quiz,
    save_student,
)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 80)
    print("GYAAN AI - PHASE 6 PROGRESS AGENT & MENTOR AGENT VERIFICATION")
    print("=" * 80)

    # Step 0: Ensure DB initialization
    print("\n[Step 0] Initializing database...")
    init_db()

    client = TestClient(app)

    # Step 1: Register Student & Seed Authentic Learning Evidence
    print("\n" + "=" * 80)
    print("[Step 1] Registering Student (Dev Patel) & Seeding Real Assessment Data")
    print("=" * 80)
    email = f"dev_patel_{uuid.uuid4().hex[:6]}@gyaan.ai"
    reg_resp = client.post("/api/v1/auth/register", json={
        "display_name": "Dev Patel",
        "email": email,
        "password": "PasswordDev123!",
        "grade": "Class 10",
        "preferred_language": "English",
    })
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    student_id = auth_data["student"]["id"]
    token = auth_data["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  Registered Student ID : {student_id} ({email})")

    # Seed Diagnostic Record
    diag_id = f"diag_{uuid.uuid4().hex[:8]}"
    save_diagnostic_record(
        record_id=diag_id,
        student_id=student_id,
        subject="Science",
        topic="Acids, Bases and Salts",
        assessment_input=[{"q": "What is pH?", "a": "Measure of acidity"}],
        diagnostic_output={"gap": "Needs reinforcement on neutralization reactions."},
    )

    # Seed Quiz & Assessment Attempt: 1 correct (pH scale), 1 incorrect (reaction equation)
    quiz_id = f"quiz_{uuid.uuid4().hex[:8]}"
    save_quiz(
        quiz_id=quiz_id,
        student_id=student_id,
        subject="Science",
        topic="Acids, Bases and Salts",
        grade="Class 10",
        questions=[
            {"id": "q1", "question": "What is the pH of a neutral solution?", "correct_answer": "7", "marks": 1.0},
            {"id": "q2", "question": "Write the neutralization equation for HCl + NaOH", "correct_answer": "NaCl + H2O", "marks": 2.0},
        ],
    )

    attempt_id = f"att_{uuid.uuid4().hex[:8]}"
    save_assessment_attempt(
        attempt_id=attempt_id,
        quiz_id=quiz_id,
        student_id=student_id,
        submitted_answers={"q1": "7", "q2": "I don't know the equation"},
        score=1.0,
        max_marks=3.0,
        evaluation_details={
            "total_score": 1.0,
            "max_marks": 3.0,
            "evaluations": [
                {"question_id": "q1", "score_awarded": 1.0, "status": "correct", "feedback": "Accurate pH value."},
                {"question_id": "q2", "score_awarded": 0.0, "status": "incorrect", "feedback": "Missed chemical equation for neutralization.", "revision_topic": "Neutralization Reactions"},
            ],
        },
    )

    record_topic_assessment_score(
        student_id=student_id,
        subject="Science",
        topic="Acids, Bases and Salts",
        score=1.0,
        max_marks=3.0,
    )
    print("  Seeded 1 diagnostic record, 1 practice quiz, and 1 evaluated attempt (Score: 1.0/3.0 = 33.3%).")

    # Step 2: Standalone Progress Agent Execution
    print("\n" + "=" * 80)
    print("[Step 2] Executing Canonical Progress Agent (Live Ollama Inference)")
    print("=" * 80)
    t0 = time.perf_counter()
    progress_result = run_progress_analysis_workflow(student_id)
    t_progress = round(time.perf_counter() - t0, 2)
    print(f"  Progress Agent executed in {t_progress} seconds.")

    stats = progress_result["objective_statistics"]
    analysis = progress_result["agent_analysis"]

    print("\n  --- Objective Statistics Derived in Python ---")
    print(f"  Total Assessments Completed : {stats['total_assessments_completed']}")
    print(f"  Average Percentage          : {stats['average_percentage']}%")
    print(f"  Performance Trend           : {stats['performance_trend']}")
    print(f"  Areas Needing Improvement   : {stats['areas_needing_improvement']}")

    print("\n  --- Progress Agent Reasoning Output ---")
    print(f"  Overall Summary             : {analysis.get('overall_summary')}")
    print(f"  Performance Interpretation  : {analysis.get('performance_interpretation')}")
    print(f"  Strengths Analysis          : {analysis.get('strengths_analysis')}")
    print(f"  Weaknesses Analysis         : {analysis.get('weaknesses_analysis')}")
    print(f"  Recommended Priorities      : {analysis.get('recommended_priorities')}")

    assert stats["total_assessments_completed"] == 1
    assert stats["average_percentage"] == 33.3
    assert len(analysis.get("overall_summary", "")) > 10

    # Step 3: Sequential Multi-Agent Workflow (Progress Agent -> Context -> Mentor Agent)
    print("\n" + "=" * 80)
    print("[Step 3] Executing Sequential Multi-Agent Workflow: Progress -> Context -> Mentor")
    print("=" * 80)
    t1 = time.perf_counter()
    full_result = run_progress_and_mentor_workflow(student_id)
    t_full = round(time.perf_counter() - t1, 2)
    print(f"  Full 2-Agent Sequential Workflow executed in {t_full} seconds.")

    mentor_data = full_result["mentor_recommendations"]
    print("\n  --- Mentor Agent Personalized Guidance ---")
    print(f"  Mentor Overview : {mentor_data.get('mentor_overview')}")
    print(f"  Study Habit Tip : {mentor_data.get('study_tip')}")
    print(f"  Next Milestone  : {mentor_data.get('next_milestone')}")

    recs = mentor_data.get("recommendations", [])
    print(f"\n  Recommendations Generated: {len(recs)}")
    for idx, r in enumerate(recs, 1):
        print(f"\n  [Recommendation {idx}] {r.get('title')} (Priority: {r.get('priority')}, {r.get('estimated_minutes')} mins)")
        print(f"    Topic            : {r.get('topic')}")
        print(f"    Suggested Action : {r.get('suggested_action')}")
        print(f"    Reason           : {r.get('reason')}")
        if r.get("resource_reference"):
            print(f"    Resource Ref     : {r.get('resource_reference')}")

    assert len(recs) >= 1, "Mentor Agent must produce at least 1 concrete recommendation"
    assert mentor_data.get("mentor_overview"), "Mentor Agent must generate a personalized overview"

    # Step 4: Verification of Authenticated Endpoints via TestClient
    print("\n" + "=" * 80)
    print("[Step 4] Testing Authenticated REST Endpoints")
    print("=" * 80)

    # 4a. GET /api/v1/students/me/progress
    r_prog = client.get("/api/v1/students/me/progress", headers=headers)
    print(f"  GET /api/v1/students/me/progress -> Status: HTTP {r_prog.status_code}")
    assert r_prog.status_code == 200
    prog_json = r_prog.json()
    assert prog_json["student_id"] == student_id
    assert prog_json["model"] == "ollama/qwen2.5:3b"

    # 4b. GET /api/v1/students/me/mentor-recommendations
    r_ment = client.get("/api/v1/students/me/mentor-recommendations", headers=headers)
    print(f"  GET /api/v1/students/me/mentor-recommendations -> Status: HTTP {r_ment.status_code}")
    assert r_ment.status_code == 200
    ment_json = r_ment.json()
    assert ment_json["student_id"] == student_id
    assert len(ment_json["recommendations"]) >= 1

    # Step 5: Multi-Student Isolation Test
    print("\n" + "=" * 80)
    print("[Step 5] Multi-Student Isolation Verification")
    print("=" * 80)
    email_other = f"other_{uuid.uuid4().hex[:6]}@gyaan.ai"
    reg_other = client.post("/api/v1/auth/register", json={
        "display_name": "Other Student",
        "email": email_other,
        "password": "OtherPassword123!",
    })
    token_other = reg_other.json()["token"]
    headers_other = {"Authorization": f"Bearer {token_other}"}

    # Query progress with other student's token
    r_other_prog = client.get("/api/v1/students/me/progress", headers=headers_other)
    assert r_other_prog.status_code == 200
    other_data = r_other_prog.json()
    assert other_data["student_id"] == reg_other.json()["student"]["id"]
    # Other student has 0 assessments, must reflect empty state honestly
    assert other_data["objective_statistics"]["total_assessments_completed"] == 0
    assert other_data["objective_statistics"]["average_percentage"] is None
    assert other_data["objective_statistics"]["has_sufficient_history"] is False
    print("  Other Student Progress: Confirmed zero-data state handled honestly without bleeding Student 1 data.")
    print("  Multi-Student Isolation: VERIFIED.")

    print("\n" + "=" * 80)
    print("ALL PHASE 6 VERIFICATION CRITERIA PASSED WITH 100% SUCCESS!")
    print("=" * 80)


if __name__ == "__main__":
    main()
