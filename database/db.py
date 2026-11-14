"""Gyaan AI - Central Database Module.

Exposes SQLite database connection, table initialization, and persistence operations.
"""

from backend.db.database import (
    DEFAULT_DB_PATH,
    get_db_connection,
    get_db_path,
    init_db,
    # Student & Session
    create_student_account,
    get_student_by_email,
    get_student_by_id,
    save_student,
    update_student_profile,
    create_student_session,
    get_active_session_by_token,
    revoke_session,
    # Learning Sessions
    create_learning_session,
    get_student_learning_history,
    # Topic Mastery
    record_topic_assessment_score,
    get_student_topic_mastery,
    # Diagnostic & Curriculum
    save_diagnostic_record,
    get_diagnostic_record,
    get_student_diagnostic_records,
    save_curriculum_plan,
    get_curriculum_plan,
    get_student_curriculum_plans,
    # Quizzes & Assessments
    save_quiz,
    get_quiz,
    save_assessment_attempt,
    get_assessment_attempt,
    get_student_assessment_history,
    # Chapter Learning Journeys
    create_learning_journey,
    get_learning_journey,
    get_active_learning_journey_for_student,
    update_learning_journey_step,
    increment_journey_iteration,
    list_student_learning_journeys,
)

__all__ = [
    "DEFAULT_DB_PATH",
    "get_db_connection",
    "get_db_path",
    "init_db",
    "create_student_account",
    "get_student_by_email",
    "get_student_by_id",
    "save_student",
    "update_student_profile",
    "create_student_session",
    "get_active_session_by_token",
    "revoke_session",
    "create_learning_session",
    "get_student_learning_history",
    "record_topic_assessment_score",
    "get_student_topic_mastery",
    "save_diagnostic_record",
    "get_diagnostic_record",
    "get_student_diagnostic_records",
    "save_curriculum_plan",
    "get_curriculum_plan",
    "get_student_curriculum_plans",
    "save_quiz",
    "get_quiz",
    "save_assessment_attempt",
    "get_assessment_attempt",
    "get_student_assessment_history",
    "create_learning_journey",
    "get_learning_journey",
    "get_active_learning_journey_for_student",
    "update_learning_journey_step",
    "increment_journey_iteration",
    "list_student_learning_journeys",
]
