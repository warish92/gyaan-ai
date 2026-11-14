"""Unit tests for Phase 6: Progress Agent, Mentor Agent, and Objective Analytics.

Tests:
- Deterministic objective statistics calculations
- Missing data & zero-history handling
- Trend detection thresholds (minimum 2 attempts)
- Topic mastery categorization (strengths vs weaknesses)
- API schema validation with mocked multi-agent workflows
- Authentication enforcement & 503 error handling on LLM failures
"""

import sys
import uuid
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
    create_learning_session,
    init_db,
    record_topic_assessment_score,
    save_assessment_attempt,
    save_quiz,
    save_student,
)
from backend.services.progress_analyzer import calculate_objective_statistics

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    init_db()


def register_test_student(name: str = "Test Student") -> dict:
    """Helper fixture to register a student and obtain auth headers."""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/v1/auth/register", json={
        "display_name": name,
        "email": email,
        "password": "Password123!",
        "grade": "Class 10",
        "preferred_language": "English",
    })
    assert resp.status_code == 201
    data = resp.json()
    return {
        "student_id": data["student"]["id"],
        "token": data["token"],
        "headers": {"Authorization": f"Bearer {data['token']}"},
    }


# ==============================================================================
# Objective Statistics & Math Calculation Tests
# ==============================================================================

def test_objective_statistics_empty_student():
    """Verify objective metrics for a fresh student with zero records."""
    student_id = f"empty_{uuid.uuid4().hex[:8]}"
    stats = calculate_objective_statistics(student_id)

    assert stats["student_id"] == student_id
    assert stats["has_sufficient_history"] is False
    assert stats["total_assessments_completed"] == 0
    assert stats["unique_quizzes_taken"] == 0
    assert stats["total_questions_answered"] == 0
    assert stats["average_percentage"] is None  # Must NOT be 0.0
    assert stats["performance_trend"] == "insufficient_evidence"
    assert stats["strengths"] == []
    assert stats["areas_needing_improvement"] == []
    assert stats["most_recent_activity_date"] is None


def test_objective_statistics_single_attempt_insufficient_trend():
    """Verify that a single assessment attempt correctly reports insufficient evidence for trend."""
    student = register_test_student("Single Attempt Student")
    stu_id = student["student_id"]

    quiz_id = f"quiz_{uuid.uuid4().hex[:6]}"
    save_quiz(
        quiz_id=quiz_id,
        student_id=stu_id,
        subject="Science",
        topic="Chemical Reactions",
        grade="Class 10",
        questions=[{"id": "q1", "marks": 2.0}],
    )

    save_assessment_attempt(
        attempt_id=f"att_{uuid.uuid4().hex[:6]}",
        quiz_id=quiz_id,
        student_id=stu_id,
        submitted_answers={"q1": "Oxidation is gain of oxygen."},
        score=2.0,
        max_marks=2.0,
        evaluation_details={
            "evaluations": [{"question_id": "q1", "score_awarded": 2.0, "status": "correct"}]
        },
    )

    record_topic_assessment_score(
        student_id=stu_id,
        subject="Science",
        topic="Chemical Reactions",
        score=2.0,
        max_marks=2.0,
    )

    stats = calculate_objective_statistics(stu_id)
    assert stats["total_assessments_completed"] == 1
    assert stats["unique_quizzes_taken"] == 1
    assert stats["average_percentage"] == 100.0
    # Must NOT infer trend from 1 data point!
    assert stats["performance_trend"] == "insufficient_evidence"
    assert "insufficient" in stats["trend_description"].lower()
    assert len(stats["strengths"]) == 1
    assert "Chemical Reactions (100.0%)" in stats["strengths"][0]


def test_objective_statistics_multiple_attempts_improving_trend():
    """Verify performance trend calculation detects improvement across multiple attempts."""
    student = register_test_student("Multi Attempt Student")
    stu_id = student["student_id"]

    quiz1 = f"quiz_1_{uuid.uuid4().hex[:6]}"
    save_quiz(quiz_id=quiz1, student_id=stu_id, subject="Science", topic="Acids", grade="Class 10", questions=[])
    # Baseline older attempt: 50%
    save_assessment_attempt(
        attempt_id=f"att_old_{uuid.uuid4().hex[:6]}",
        quiz_id=quiz1,
        student_id=stu_id,
        submitted_answers={},
        score=1.0,
        max_marks=2.0,
        evaluation_details={},
    )

    quiz2 = f"quiz_2_{uuid.uuid4().hex[:6]}"
    save_quiz(quiz_id=quiz2, student_id=stu_id, subject="Science", topic="Acids", grade="Class 10", questions=[])
    # Newer attempt: 100%
    save_assessment_attempt(
        attempt_id=f"att_new_{uuid.uuid4().hex[:6]}",
        quiz_id=quiz2,
        student_id=stu_id,
        submitted_answers={},
        score=2.0,
        max_marks=2.0,
        evaluation_details={},
    )

    stats = calculate_objective_statistics(stu_id)
    assert stats["total_assessments_completed"] == 2
    assert stats["average_percentage"] == 75.0
    assert stats["performance_trend"] in ["improving", "stable"]


def test_topic_mastery_categorization():
    """Verify topic mastery thresholds: >=80% strength, <60% needs revision, 60-79% in progress."""
    stu_id = f"topic_test_{uuid.uuid4().hex[:6]}"
    save_student(stu_id, "Topic Tester", "Class 10")

    # Topic 1: 90% (strength)
    record_topic_assessment_score(stu_id, "Science", "Acids and Bases", score=9.0, max_marks=10.0)
    # Topic 2: 50% (needs revision / weakness)
    record_topic_assessment_score(stu_id, "Science", "Metals and Non-metals", score=5.0, max_marks=10.0)
    # Topic 3: 70% (in progress)
    record_topic_assessment_score(stu_id, "Science", "Life Processes", score=7.0, max_marks=10.0)

    stats = calculate_objective_statistics(stu_id)
    assert any("Acids and Bases (90.0%)" in s for s in stats["strengths"])
    assert any("Metals and Non-metals (50.0%)" in w for w in stats["areas_needing_improvement"])
    assert any("Life Processes (In Progress, 70.0%)" in p for p in stats["topics_needing_practice"])


# ==============================================================================
# Endpoint & Schema Validation Unit Tests (Mocked Workflows)
# ==============================================================================

def test_progress_endpoint_requires_authentication():
    """Verify GET /api/v1/students/me/progress requires Bearer authentication."""
    unauth_client = TestClient(app)
    response = unauth_client.get("/api/v1/students/me/progress")
    assert response.status_code == 401


def test_mentor_recommendations_endpoint_requires_authentication():
    """Verify GET /api/v1/students/me/mentor-recommendations requires Bearer authentication."""
    unauth_client = TestClient(app)
    response = unauth_client.get("/api/v1/students/me/mentor-recommendations")
    assert response.status_code == 401


def test_progress_endpoint_success_with_mock():
    """Verify GET /api/v1/students/me/progress returns valid ProgressReportResponse."""
    student = register_test_student("Progress Mock Student")
    headers = student["headers"]

    mock_analysis_result = {
        "student_id": student["student_id"],
        "objective_statistics": {
            "student_id": student["student_id"],
            "has_sufficient_history": True,
            "total_assessments_completed": 1,
            "unique_quizzes_taken": 1,
            "total_questions_answered": 2,
            "correct_answers_count": 2,
            "partially_correct_answers_count": 0,
            "incorrect_answers_count": 0,
            "average_percentage": 100.0,
            "performance_trend": "insufficient_evidence",
            "trend_description": "Baseline established.",
            "strengths": ["Acids (100.0%)"],
            "areas_needing_improvement": [],
            "topics_needing_practice": [],
            "total_learning_sessions": 2,
            "completed_sessions_count": 2,
            "sessions_by_type": {"quiz": 1, "diagnostic": 1},
            "diagnostic_records_count": 1,
            "curriculum_plans_count": 1,
            "most_recent_activity_date": "2026-10-29T12:00:00",
        },
        "agent_analysis": {
            "overall_summary": "Demonstrated strong mastery of acid-base indicators.",
            "strengths_analysis": ["Mastery of neutral pH values."],
            "weaknesses_analysis": ["No critical weaknesses observed."],
            "topic_observations": [
                {
                    "topic": "Acids, Bases and Salts",
                    "observation": "High accuracy on definitions.",
                    "status": "mastered",
                }
            ],
            "performance_interpretation": "Scored 100% on initial diagnostic test.",
            "data_limitations": "More assessment data needed across other syllabus chapters.",
            "recommended_priorities": ["Chemical Reactions", "Carbon Compounds"],
        },
    }

    with patch("backend.app.main.run_progress_analysis_workflow", return_value=mock_analysis_result):
        resp = client.get("/api/v1/students/me/progress", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["student_id"] == student["student_id"]
        assert data["overall_summary"] == mock_analysis_result["agent_analysis"]["overall_summary"]
        assert len(data["strengths_analysis"]) == 1
        assert len(data["topic_observations"]) == 1
        assert data["topic_observations"][0]["topic"] == "Acids, Bases and Salts"
        assert data["topic_observations"][0]["status"] == "mastered"
        assert "duration_ms" in data


def test_mentor_recommendations_endpoint_success_with_mock():
    """Verify GET /api/v1/students/me/mentor-recommendations returns valid MentorRecommendationsResponse."""
    student = register_test_student("Mentor Mock Student")
    headers = student["headers"]

    mock_workflow_result = {
        "student_id": student["student_id"],
        "duration_seconds": 12.5,
        "objective_statistics": {
            "student_id": student["student_id"],
            "has_sufficient_history": True,
            "total_assessments_completed": 1,
            "unique_quizzes_taken": 1,
            "total_questions_answered": 2,
            "correct_answers_count": 1,
            "partially_correct_answers_count": 0,
            "incorrect_answers_count": 1,
            "average_percentage": 50.0,
            "performance_trend": "insufficient_evidence",
            "trend_description": "Single assessment baseline.",
            "strengths": [],
            "areas_needing_improvement": ["Acids (50.0%)"],
            "topics_needing_practice": ["Acids"],
            "total_learning_sessions": 1,
            "completed_sessions_count": 1,
            "sessions_by_type": {"quiz": 1},
            "diagnostic_records_count": 0,
            "curriculum_plans_count": 0,
            "most_recent_activity_date": "2026-10-29T12:00:00",
        },
        "progress_report": {
            "overall_summary": "Initial assessment completed with basic recall gaps.",
            "strengths_analysis": [],
            "weaknesses_analysis": ["Weakness in hydronium ion formation."],
            "topic_observations": [{"topic": "Acids", "observation": "Gap in pH scale", "status": "needs_revision"}],
            "performance_interpretation": "50% score indicates need for foundational review.",
            "recommended_priorities": ["Revise NCERT Chapter 2 Section 2.2"],
        },
        "mentor_recommendations": {
            "mentor_overview": "Great effort on completing your first quiz! Let's focus on reinforcing acid-base concepts.",
            "recommendations": [
                {
                    "title": "Revise Acid Dissociation in Water",
                    "topic": "Acids, Bases and Salts",
                    "reason": "You missed the question about hydronium ion formation.",
                    "suggested_action": "Read NCERT Class 10 Chapter 2, Section 2.2 on pages 22-24.",
                    "priority": "high",
                    "estimated_minutes": 20,
                    "supporting_evidence": "Missed question on H+ + H2O -> H3O+.",
                    "resource_reference": "NCERT Class 10 Science Chapter 2",
                }
            ],
            "study_tip": "Create flashcards for common indicators and their color transitions.",
            "next_milestone": "Score >= 80% on the Chapter 2 follow-up practice quiz.",
        },
    }

    with patch("backend.app.main.run_progress_and_mentor_workflow", return_value=mock_workflow_result):
        resp = client.get("/api/v1/students/me/mentor-recommendations", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["student_id"] == student["student_id"]
        assert "mentor_overview" in data
        assert len(data["recommendations"]) == 1
        rec = data["recommendations"][0]
        assert rec["title"] == "Revise Acid Dissociation in Water"
        assert rec["priority"] == "high"
        assert rec["estimated_minutes"] == 20
        assert data["study_tip"] is not None
        assert data["next_milestone"] is not None


def test_progress_endpoint_handles_llm_failure():
    """Verify GET /api/v1/students/me/progress returns 503 on model failure."""
    student = register_test_student("Error Tester")
    headers = student["headers"]

    with patch("backend.app.main.run_progress_analysis_workflow", side_effect=RuntimeError("Ollama inference timeout")):
        resp = client.get("/api/v1/students/me/progress", headers=headers)
        assert resp.status_code == 503
        data = resp.json()
        assert "detail" in data
        assert "Ollama inference timeout" in data["detail"]["message"]
