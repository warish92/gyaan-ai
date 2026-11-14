"""Unit tests for Gyaan AI SQLite database persistence layer."""

import tempfile
from pathlib import Path
import pytest

from backend.db.database import (
    init_db,
    save_student,
    get_student,
    save_diagnostic_record,
    get_diagnostic_record,
    save_curriculum_plan,
    get_curriculum_plan,
    save_quiz,
    get_quiz,
    save_assessment_attempt,
    get_assessment_attempt,
    get_student_assessment_history,
    get_db_connection,
)


@pytest.fixture
def temp_db():
    """Create a clean isolated temporary SQLite database for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_gyaan.db"
        init_db(db_path)
        yield db_path


def test_init_db_creates_tables(temp_db):
    """Verify that init_db creates all required tables including Phase 4 quiz tables."""
    conn = get_db_connection(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row["name"] for row in cursor.fetchall()]
    conn.close()

    assert "students" in tables
    assert "diagnostic_records" in tables
    assert "curriculum_plans" in tables
    assert "quizzes" in tables
    assert "assessment_attempts" in tables


def test_student_crud(temp_db):
    """Verify student insert, update, and retrieval."""
    save_student("s100", "Ananya Sharma", "Class 10", temp_db)
    student = get_student("s100", temp_db)

    assert student is not None
    assert student["id"] == "s100"
    assert student["display_name"] == "Ananya Sharma"
    assert student["grade"] == "Class 10"

    # Test upsert updates display_name
    save_student("s100", "Ananya S.", "Class 10", temp_db)
    updated = get_student("s100", temp_db)
    assert updated["display_name"] == "Ananya S."


def test_diagnostic_record_persistence(temp_db):
    """Verify diagnostic record creation with JSON serialization and retrieval."""
    save_student("s101", "Rohan", "Class 10", temp_db)

    assessment_input = [
        {"question": "What is pH?", "student_answer": "It is acid strength"}
    ]
    diagnostic_output = {
        "gaps": ["Logarithmic definition of pH"],
        "misconceptions": ["Assumed pH only measures acids"],
    }

    record_id = save_diagnostic_record(
        record_id="diag_001",
        student_id="s101",
        subject="Science",
        topic="Acids and Bases",
        assessment_input=assessment_input,
        diagnostic_output=diagnostic_output,
        custom_path=temp_db,
    )

    retrieved = get_diagnostic_record("diag_001", temp_db)
    assert retrieved is not None
    assert retrieved["id"] == "diag_001"
    assert retrieved["subject"] == "Science"
    assert retrieved["topic"] == "Acids and Bases"
    assert retrieved["assessment_input"] == assessment_input
    assert retrieved["diagnostic_output"] == diagnostic_output


def test_curriculum_plan_foreign_key_relationship(temp_db):
    """Verify curriculum plan links correctly to diagnostic record and student."""
    save_student("s102", "Pooja", "Class 10", temp_db)

    save_diagnostic_record(
        record_id="diag_002",
        student_id="s102",
        subject="Chemistry",
        topic="Chemical Reactions",
        assessment_input=[{"q": "balance equation"}],
        diagnostic_output={"understanding": ["conservation of mass"]},
        custom_path=temp_db,
    )

    plan_data = {
        "learning_goal": "Master chemical equation balancing",
        "steps": ["Step 1: Count atoms", "Step 2: Add coefficients"],
    }

    plan_id = save_curriculum_plan(
        plan_id="plan_002",
        student_id="s102",
        diagnostic_id="diag_002",
        plan_output=plan_data,
        custom_path=temp_db,
    )

    retrieved_plan = get_curriculum_plan("plan_002", temp_db)
    assert retrieved_plan is not None
    assert retrieved_plan["id"] == "plan_002"
    assert retrieved_plan["student_id"] == "s102"
    assert retrieved_plan["diagnostic_id"] == "diag_002"
    assert retrieved_plan["plan_output"] == plan_data


def test_quiz_and_assessment_attempt_persistence(temp_db):
    """Verify saving and retrieving quizzes and student attempts with scoring."""
    save_student("s103", "Kavya", "Class 10", temp_db)

    questions_data = [
        {
            "id": "q1",
            "type": "mcq",
            "question": "Which gas is evolved when acid reacts with metal?",
            "options": ["A) Oxygen", "B) Hydrogen", "C) Nitrogen", "D) Chlorine"],
            "correct_answer": "B) Hydrogen",
            "explanation": "Acid + Metal -> Salt + Hydrogen gas",
            "marks": 1.0,
        }
    ]

    # Save quiz
    save_quiz(
        quiz_id="quiz_101",
        student_id="s103",
        subject="Science",
        topic="Acids and Bases",
        grade="Class 10",
        questions=questions_data,
        custom_path=temp_db,
    )

    retrieved_quiz = get_quiz("quiz_101", temp_db)
    assert retrieved_quiz is not None
    assert retrieved_quiz["id"] == "quiz_101"
    assert retrieved_quiz["topic"] == "Acids and Bases"
    assert len(retrieved_quiz["questions"]) == 1
    assert retrieved_quiz["questions"][0]["correct_answer"] == "B) Hydrogen"

    # Save attempt
    eval_details = {
        "total_score": 1.0,
        "max_marks": 1.0,
        "percentage": 100.0,
        "evaluations": [
            {
                "question_id": "q1",
                "score_awarded": 1.0,
                "max_marks": 1.0,
                "status": "correct",
                "feedback": "Correct identification of hydrogen gas.",
            }
        ],
    }

    save_assessment_attempt(
        attempt_id="att_101",
        quiz_id="quiz_101",
        student_id="s103",
        submitted_answers={"q1": "B) Hydrogen"},
        score=1.0,
        max_marks=1.0,
        evaluation_details=eval_details,
        custom_path=temp_db,
    )

    retrieved_att = get_assessment_attempt("att_101", temp_db)
    assert retrieved_att is not None
    assert retrieved_att["score"] == 1.0
    assert retrieved_att["evaluation_details"]["percentage"] == 100.0

    # Retrieve history
    history = get_student_assessment_history("s103", temp_db)
    assert len(history) == 1
    assert history[0]["attempt_id"] == "att_101"
    assert history[0]["topic"] == "Acids and Bases"
