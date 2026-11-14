"""Gyaan AI - SQLite Persistence Foundation.

Provides parameterized, transactional persistence for students,
student accounts & sessions, diagnostic assessment records,
personalized curriculum plans, quizzes, student assessment attempts,
learning history sessions, and topic-wise mastery tracking.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gyaan_ai.db")

DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DEFAULT_DB_PATH = (DEFAULT_DB_DIR / "gyaan_ai.db").resolve()
PHASE4_BACKUP_PATH = (DEFAULT_DB_DIR / "gyaan_ai.db.bak_phase4").resolve()


def get_db_path(custom_path: Optional[Path | str] = None) -> Path:
    """Resolve database path, ensuring parent directory exists.

    Supports GYAAN_DB_PATH and DATABASE_PATH environment overrides for test isolation.
    Enforces a strict fail-safe guard preventing test executions from writing to or
    connecting to the active project database (gyaan_ai.db) or Phase 4 backup.
    """
    if custom_path:
        target = Path(custom_path).resolve()
    else:
        env_path = os.environ.get("GYAAN_DB_PATH") or os.environ.get("DATABASE_PATH")
        if env_path:
            target = Path(env_path).resolve()
        else:
            target = DEFAULT_DB_PATH

    # Fail-safe configuration guard for tests
    is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("GYAAN_TEST_MODE") == "1"
    if is_testing:
        # Under test execution, prohibit connection to active project database or backup
        if target == DEFAULT_DB_PATH or target == PHASE4_BACKUP_PATH or target.name in ("gyaan_ai.db", "gyaan_ai.db.bak_phase4"):
            if os.environ.get("GYAAN_ALLOW_READONLY_PROD_INSPECTION") != "1":
                raise RuntimeError(
                    f"CRITICAL SECURITY GUARD: Test attempted to connect to the active project database ({target})! "
                    "Tests must execute against an isolated temporary database. Configure GYAAN_DB_PATH or use test fixtures."
                )

    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def get_db_connection(custom_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Open an SQLite connection with WAL mode and foreign key enforcement."""
    path = get_db_path(custom_path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(custom_path: Optional[Path | str] = None) -> None:
    """Initialize database tables with safe, non-destructive schema migrations."""
    conn = get_db_connection(custom_path)
    try:
        with conn:
            # 1. Create base tables if they do not exist
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS students (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    grade TEXT NOT NULL DEFAULT 'Class 10',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS diagnostic_records (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    assessment_input TEXT NOT NULL,
                    diagnostic_output TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS curriculum_plans (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    diagnostic_id TEXT NOT NULL,
                    plan_output TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY (diagnostic_id) REFERENCES diagnostic_records(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS quizzes (
                    id TEXT PRIMARY KEY,
                    student_id TEXT,
                    subject TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    grade TEXT NOT NULL DEFAULT 'Class 10',
                    questions TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS assessment_attempts (
                    id TEXT PRIMARY KEY,
                    quiz_id TEXT NOT NULL,
                    student_id TEXT,
                    submitted_answers TEXT NOT NULL,
                    score REAL NOT NULL,
                    max_marks REAL NOT NULL,
                    evaluation_details TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_diag_student ON diagnostic_records(student_id);
                CREATE INDEX IF NOT EXISTS idx_plan_student ON curriculum_plans(student_id);
                CREATE INDEX IF NOT EXISTS idx_plan_diag ON curriculum_plans(diagnostic_id);
                CREATE INDEX IF NOT EXISTS idx_quiz_student ON quizzes(student_id);
                CREATE INDEX IF NOT EXISTS idx_attempt_quiz ON assessment_attempts(quiz_id);
                CREATE INDEX IF NOT EXISTS idx_attempt_student ON assessment_attempts(student_id);
            """)

            # 2. Add Phase 5 student profile and authentication columns if missing
            cursor = conn.cursor()
            existing_cols = {col[1] for col in cursor.execute("PRAGMA table_info(students)").fetchall()}
            if "email" not in existing_cols:
                conn.execute("ALTER TABLE students ADD COLUMN email TEXT;")
            if "password_hash" not in existing_cols:
                conn.execute("ALTER TABLE students ADD COLUMN password_hash TEXT;")
            if "preferred_language" not in existing_cols:
                conn.execute("ALTER TABLE students ADD COLUMN preferred_language TEXT DEFAULT 'English';")
            if "updated_at" not in existing_cols:
                conn.execute("ALTER TABLE students ADD COLUMN updated_at TEXT;")
            if "account_status" not in existing_cols:
                conn.execute("ALTER TABLE students ADD COLUMN account_status TEXT DEFAULT 'active';")

            # Unique index on normalized email (allows NULL for legacy/unregistered students)
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_email ON students(email) WHERE email IS NOT NULL;")

            # 3. Create Phase 5 Authentication & Learning Tracking tables
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS student_sessions (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON student_sessions(token_hash);
                CREATE INDEX IF NOT EXISTS idx_sessions_student ON student_sessions(student_id);

                CREATE TABLE IF NOT EXISTS learning_sessions (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    details TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_learning_sessions_student ON learning_sessions(student_id);
                CREATE INDEX IF NOT EXISTS idx_learning_sessions_topic ON learning_sessions(subject, topic);

                CREATE TABLE IF NOT EXISTS student_topic_mastery (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    latest_score REAL NOT NULL,
                    max_marks REAL NOT NULL,
                    percentage REAL NOT NULL,
                    attempts_count INTEGER NOT NULL DEFAULT 1,
                    mastery_status TEXT NOT NULL,
                    last_assessed_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    UNIQUE(student_id, subject, topic)
                );
                CREATE INDEX IF NOT EXISTS idx_mastery_student ON student_topic_mastery(student_id);

                CREATE TABLE IF NOT EXISTS learning_journeys (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    chapter TEXT NOT NULL,
                    learning_goal TEXT,
                    current_step TEXT NOT NULL DEFAULT 'orchestrator',
                    status TEXT NOT NULL DEFAULT 'active',
                    loop_iteration INTEGER NOT NULL DEFAULT 1,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    mastery_score REAL DEFAULT 0.0,
                    mastery_achieved INTEGER DEFAULT 0,
                    journey_data TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_journeys_student ON learning_journeys(student_id);
                CREATE INDEX IF NOT EXISTS idx_journeys_subject_chapter ON learning_journeys(subject, chapter);

                -- 4. CBSE Class 10 Curriculum System Tables
                CREATE TABLE IF NOT EXISTS education_boards (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL UNIQUE,
                    country TEXT NOT NULL DEFAULT 'India',
                    official_portal TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS academic_sessions (
                    id TEXT PRIMARY KEY,
                    board_id TEXT NOT NULL,
                    session_code TEXT NOT NULL,
                    start_year INTEGER NOT NULL DEFAULT 2026,
                    end_year INTEGER NOT NULL DEFAULT 2027,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    curriculum_url TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (board_id) REFERENCES education_boards(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS curriculum_classes (
                    id TEXT PRIMARY KEY,
                    board_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    class_code TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (board_id) REFERENCES education_boards(id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS curriculum_subjects (
                    id TEXT PRIMARY KEY,
                    class_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    short_name TEXT,
                    category TEXT NOT NULL,
                    is_compulsory INTEGER NOT NULL DEFAULT 0,
                    description TEXT,
                    official_syllabus_url TEXT,
                    verification_status TEXT DEFAULT 'VERIFIED',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (class_id) REFERENCES curriculum_classes(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS student_enrolled_subjects (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    enrolled_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY (subject_id) REFERENCES curriculum_subjects(id) ON DELETE CASCADE,
                    UNIQUE(student_id, subject_id)
                );

                CREATE TABLE IF NOT EXISTS curriculum_units (
                    id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    unit_number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    section_tag TEXT,
                    description TEXT,
                    weightage_marks INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (subject_id) REFERENCES curriculum_subjects(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS curriculum_chapters (
                    id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    unit_id TEXT,
                    chapter_number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    slug TEXT,
                    section_tag TEXT,
                    description TEXT,
                    estimated_minutes INTEGER DEFAULT 360,
                    prerequisites TEXT,
                    is_prescribed INTEGER NOT NULL DEFAULT 1,
                    excluded_topics TEXT,
                    source_reference TEXT,
                    verification_status TEXT DEFAULT 'VERIFIED',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (subject_id) REFERENCES curriculum_subjects(id) ON DELETE CASCADE,
                    FOREIGN KEY (unit_id) REFERENCES curriculum_units(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS curriculum_topics (
                    id TEXT PRIMARY KEY,
                    chapter_id TEXT NOT NULL,
                    topic_number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    slug TEXT,
                    summary TEXT,
                    importance TEXT DEFAULT 'High',
                    difficulty_level TEXT DEFAULT 'Intermediate',
                    key_concepts TEXT,
                    definitions TEXT,
                    formulas TEXT,
                    common_misconceptions TEXT,
                    practice_questions TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (chapter_id) REFERENCES curriculum_chapters(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS curriculum_subtopics (
                    id TEXT PRIMARY KEY,
                    topic_id TEXT NOT NULL,
                    subtopic_number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    explanation TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (topic_id) REFERENCES curriculum_topics(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS curriculum_learning_objectives (
                    id TEXT PRIMARY KEY,
                    topic_id TEXT NOT NULL,
                    objective_code TEXT,
                    description TEXT NOT NULL,
                    bloom_level TEXT DEFAULT 'Understand',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (topic_id) REFERENCES curriculum_topics(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS curriculum_resources (
                    id TEXT PRIMARY KEY,
                    chapter_id TEXT,
                    topic_id TEXT,
                    title TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    url TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (chapter_id) REFERENCES curriculum_chapters(id) ON DELETE CASCADE,
                    FOREIGN KEY (topic_id) REFERENCES curriculum_topics(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS student_topic_progress (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    topic_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'not_started',
                    time_spent_seconds INTEGER NOT NULL DEFAULT 0,
                    last_studied_at TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY (topic_id) REFERENCES curriculum_topics(id) ON DELETE CASCADE,
                    UNIQUE(student_id, topic_id)
                );

                CREATE TABLE IF NOT EXISTS lesson_sessions (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    chapter_id TEXT NOT NULL,
                    topic_id TEXT,
                    subtopic_id TEXT,
                    lesson_mode TEXT NOT NULL DEFAULT 'conceptual',
                    messages TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'active',
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY (subject_id) REFERENCES curriculum_subjects(id) ON DELETE CASCADE,
                    FOREIGN KEY (chapter_id) REFERENCES curriculum_chapters(id) ON DELETE CASCADE,
                    FOREIGN KEY (topic_id) REFERENCES curriculum_topics(id) ON DELETE SET NULL,
                    FOREIGN KEY (subtopic_id) REFERENCES curriculum_subtopics(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS student_bookmarks (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    UNIQUE(student_id, entity_type, entity_id)
                );

                CREATE INDEX IF NOT EXISTS idx_curr_subj_class ON curriculum_subjects(class_id);
                CREATE INDEX IF NOT EXISTS idx_curr_units_subj ON curriculum_units(subject_id);
                CREATE INDEX IF NOT EXISTS idx_curr_chap_subj ON curriculum_chapters(subject_id);
                CREATE INDEX IF NOT EXISTS idx_curr_chap_unit ON curriculum_chapters(unit_id);
                CREATE INDEX IF NOT EXISTS idx_curr_top_chap ON curriculum_topics(chapter_id);
                CREATE INDEX IF NOT EXISTS idx_curr_subtop_top ON curriculum_subtopics(topic_id);
                CREATE INDEX IF NOT EXISTS idx_curr_obj_top ON curriculum_learning_objectives(topic_id);
                CREATE INDEX IF NOT EXISTS idx_curr_res_chap ON curriculum_resources(chapter_id);
                CREATE INDEX IF NOT EXISTS idx_curr_res_top ON curriculum_resources(topic_id);
                CREATE INDEX IF NOT EXISTS idx_stud_enrolled_stud ON student_enrolled_subjects(student_id);
                CREATE INDEX IF NOT EXISTS idx_stud_top_prog_stud ON student_topic_progress(student_id);
                CREATE INDEX IF NOT EXISTS idx_stud_top_prog_top ON student_topic_progress(topic_id);
                CREATE INDEX IF NOT EXISTS idx_lesson_sess_stud ON lesson_sessions(student_id);
                CREATE INDEX IF NOT EXISTS idx_lesson_sess_chap ON lesson_sessions(chapter_id);
                CREATE INDEX IF NOT EXISTS idx_stud_bookmarks_stud ON student_bookmarks(student_id);
            """)

            # Automatically seed CBSE Class 10 curriculum if needed
            seed_cbse_curriculum_if_needed(custom_path=custom_path, conn=conn)

        logger.info("Database initialized successfully at %s", get_db_path(custom_path))
    finally:
        conn.close()


# ==============================================================================
# Student Account and Authentication Persistence
# ==============================================================================

def create_student_account(
    student_id: str,
    email: str,
    password_hash: str,
    display_name: str,
    grade: str = "Class 10",
    preferred_language: str = "English",
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Register a new student account with unique email and hashed password."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    norm_email = email.strip().lower()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO students (
                    id, email, password_hash, display_name, grade, preferred_language, created_at, updated_at, account_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active');
                """,
                (student_id, norm_email, password_hash, display_name.strip(), grade.strip(), preferred_language.strip(), now, now),
            )
        return {
            "id": student_id,
            "email": norm_email,
            "display_name": display_name.strip(),
            "grade": grade.strip(),
            "preferred_language": preferred_language.strip(),
            "created_at": now,
            "updated_at": now,
            "account_status": "active",
        }
    except sqlite3.IntegrityError as exc:
        if "UNIQUE" in str(exc).upper() and "EMAIL" in str(exc).upper():
            raise ValueError(f"An account with email '{norm_email}' already exists.") from exc
        raise
    finally:
        conn.close()


def get_student_by_email(
    email: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve student account by email, including password_hash for credential validation."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, email, password_hash, display_name, grade, preferred_language,
                   created_at, updated_at, account_status
            FROM students WHERE email = ?;
            """,
            (email.strip().lower(),),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_student_by_id(
    student_id: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve safe student profile by ID (without exposing password hash)."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, email, display_name, grade, preferred_language,
                   created_at, updated_at, account_status
            FROM students WHERE id = ?;
            """,
            (student_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_student_profile(
    student_id: str,
    display_name: Optional[str] = None,
    grade: Optional[str] = None,
    preferred_language: Optional[str] = None,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Update permitted fields for an authenticated student profile."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    updates = []
    params = []

    if display_name is not None and display_name.strip():
        updates.append("display_name = ?")
        params.append(display_name.strip())
    if grade is not None and grade.strip():
        updates.append("grade = ?")
        params.append(grade.strip())
    if preferred_language is not None and preferred_language.strip():
        updates.append("preferred_language = ?")
        params.append(preferred_language.strip())

    if not updates:
        return get_student_by_id(student_id, custom_path=custom_path)

    updates.append("updated_at = ?")
    params.append(now)
    params.append(student_id)

    query = f"UPDATE students SET {', '.join(updates)} WHERE id = ?;"

    try:
        with conn:
            cursor = conn.execute(query, tuple(params))
            if cursor.rowcount == 0:
                return None
        return get_student_by_id(student_id, custom_path=custom_path)
    finally:
        conn.close()


def save_student(
    student_id: str,
    display_name: str,
    grade: str = "Class 10",
    custom_path: Optional[Path | str] = None,
) -> str:
    """Insert or update a minimal student profile without overwriting existing names with raw IDs."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO students (id, display_name, grade, created_at, account_status)
                VALUES (?, ?, ?, ?, 'active')
                ON CONFLICT(id) DO UPDATE SET
                    display_name = CASE
                        WHEN excluded.display_name = excluded.id AND students.display_name IS NOT NULL AND students.display_name != students.id
                        THEN students.display_name
                        ELSE excluded.display_name
                    END,
                    grade = excluded.grade;
                """,
                (student_id, display_name.strip(), grade.strip(), now),
            )
        return student_id
    finally:
        conn.close()


def get_student(
    student_id: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve student profile by id."""
    return get_student_by_id(student_id, custom_path=custom_path)


# ==============================================================================
# Session Token Persistence
# ==============================================================================

def create_session(
    session_id: str,
    student_id: str,
    token_hash: str,
    expires_at: str,
    custom_path: Optional[Path | str] = None,
) -> str:
    """Persist a hashed session token in SQLite."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO student_sessions (id, student_id, token_hash, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                (session_id, student_id, token_hash, now, expires_at),
            )
        return session_id
    finally:
        conn.close()


def get_session_by_token_hash(
    token_hash: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Lookup active session and student profile by token hash."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT s.id as session_id, s.student_id, s.token_hash, s.created_at as session_created_at,
                   s.expires_at, s.revoked_at,
                   u.id, u.email, u.display_name, u.grade, u.preferred_language,
                   u.created_at, u.updated_at, u.account_status
            FROM student_sessions s
            JOIN students u ON s.student_id = u.id
            WHERE s.token_hash = ? AND s.revoked_at IS NULL;
            """,
            (token_hash,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def revoke_session(
    token_hash: str,
    custom_path: Optional[Path | str] = None,
) -> bool:
    """Revoke a specific session token."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE student_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL;",
                (now, token_hash),
            )
            return cursor.rowcount > 0
    finally:
        conn.close()


def revoke_all_student_sessions(
    student_id: str,
    custom_path: Optional[Path | str] = None,
) -> int:
    """Revoke all active sessions for a student (e.g. on global signout or password change)."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE student_sessions SET revoked_at = ? WHERE student_id = ? AND revoked_at IS NULL;",
                (now, student_id),
            )
            return cursor.rowcount
    finally:
        conn.close()


# ==============================================================================
# Learning Session Tracking & Topic Mastery
# ==============================================================================

def create_learning_session(
    session_id: str,
    student_id: str,
    subject: str,
    topic: str,
    activity_type: str,
    status: str = "started",
    details: Optional[Dict[str, Any]] = None,
    custom_path: Optional[Path | str] = None,
) -> str:
    """Record learning session start."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    details_json = json.dumps(details) if details else None
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO learning_sessions (
                    id, student_id, subject, topic, activity_type, status, started_at, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (session_id, student_id, subject.strip(), topic.strip(), activity_type.strip(), status.strip(), now, details_json),
            )
        return session_id
    finally:
        conn.close()


def complete_learning_session(
    session_id: str,
    status: str = "completed",
    details: Optional[Dict[str, Any]] = None,
    custom_path: Optional[Path | str] = None,
) -> bool:
    """Mark a learning session as completed with updated metadata."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    details_json = json.dumps(details) if details else None
    try:
        with conn:
            cursor = conn.execute(
                """
                UPDATE learning_sessions
                SET status = ?, completed_at = ?, details = COALESCE(?, details)
                WHERE id = ?;
                """,
                (status.strip(), now, details_json, session_id),
            )
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_student_learning_sessions(
    student_id: str,
    limit: int = 50,
    custom_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve learning sessions for student ordered by most recent."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, student_id, subject, topic, activity_type, status, started_at, completed_at, details
            FROM learning_sessions
            WHERE student_id = ?
            ORDER BY started_at DESC
            LIMIT ?;
            """,
            (student_id, limit),
        )
        rows = cursor.fetchall()
        result = []
        for r in rows:
            item = dict(r)
            if item.get("details"):
                try:
                    item["details"] = json.loads(item["details"])
                except Exception:
                    pass
            result.append(item)
        return result
    finally:
        conn.close()


def record_topic_assessment_score(
    student_id: str,
    subject: str,
    topic: str,
    score: float,
    max_marks: float,
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Update topic-wise mastery record based on authentic assessment outcome."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    percentage = round((score / max_marks * 100.0) if max_marks > 0 else 0.0, 1)

    if percentage >= 85.0:
        mastery_status = "mastered"
    elif percentage >= 60.0:
        mastery_status = "in_progress"
    else:
        mastery_status = "needs_revision"

    record_id = f"mst_{student_id[:8]}_{abs(hash(subject + topic)) % 1000000}"

    try:
        with conn:
            conn.execute(
                """
                INSERT INTO student_topic_mastery (
                    id, student_id, subject, topic, latest_score, max_marks,
                    percentage, attempts_count, mastery_status, last_assessed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(student_id, subject, topic) DO UPDATE SET
                    latest_score = excluded.latest_score,
                    max_marks = excluded.max_marks,
                    percentage = excluded.percentage,
                    attempts_count = student_topic_mastery.attempts_count + 1,
                    mastery_status = excluded.mastery_status,
                    last_assessed_at = excluded.last_assessed_at,
                    updated_at = excluded.updated_at;
                """,
                (record_id, student_id, subject.strip(), topic.strip(), score, max_marks, percentage, mastery_status, now, now),
            )
        return {
            "student_id": student_id,
            "subject": subject,
            "topic": topic,
            "latest_score": score,
            "max_marks": max_marks,
            "percentage": percentage,
            "mastery_status": mastery_status,
            "last_assessed_at": now,
        }
    finally:
        conn.close()


def get_student_topic_mastery(
    student_id: str,
    subject: Optional[str] = None,
    custom_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve topic mastery records for a student."""
    conn = get_db_connection(custom_path)
    try:
        if subject:
            cursor = conn.execute(
                """
                SELECT id, student_id, subject, topic, latest_score, max_marks,
                       percentage, attempts_count, mastery_status, last_assessed_at, updated_at
                FROM student_topic_mastery
                WHERE student_id = ? AND subject = ?
                ORDER BY updated_at DESC;
                """,
                (student_id, subject.strip()),
            )
        else:
            cursor = conn.execute(
                """
                SELECT id, student_id, subject, topic, latest_score, max_marks,
                       percentage, attempts_count, mastery_status, last_assessed_at, updated_at
                FROM student_topic_mastery
                WHERE student_id = ?
                ORDER BY updated_at DESC;
                """,
                (student_id,),
            )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def get_student_curriculum_plans(
    student_id: str,
    limit: int = 10,
    custom_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve curriculum plans generated for a student."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT c.id as plan_id, c.student_id, c.diagnostic_id, c.plan_output, c.created_at,
                   d.subject, d.topic
            FROM curriculum_plans c
            JOIN diagnostic_records d ON c.diagnostic_id = d.id
            WHERE c.student_id = ?
            ORDER BY c.created_at DESC
            LIMIT ?;
            """,
            (student_id, limit),
        )
        rows = cursor.fetchall()
        result = []
        for r in rows:
            item = dict(r)
            try:
                item["plan_output"] = json.loads(item["plan_output"])
            except Exception:
                pass
            result.append(item)
        return result
    finally:
        conn.close()


def get_student_diagnostic_records(
    student_id: str,
    limit: int = 10,
    custom_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve diagnostic reports for a student."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, student_id, subject, topic, assessment_input, diagnostic_output, created_at
            FROM diagnostic_records
            WHERE student_id = ?
            ORDER BY created_at DESC
            LIMIT ?;
            """,
            (student_id, limit),
        )
        rows = cursor.fetchall()
        result = []
        for r in rows:
            item = dict(r)
            try:
                item["assessment_input"] = json.loads(item["assessment_input"])
            except Exception:
                pass
            try:
                item["diagnostic_output"] = json.loads(item["diagnostic_output"])
            except Exception:
                pass
            result.append(item)
        return result
    finally:
        conn.close()


def get_student_dashboard_data(
    student_id: str,
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Aggregate complete persistent learning data for the student dashboard."""
    student = get_student_by_id(student_id, custom_path=custom_path)
    if not student:
        raise ValueError(f"Student '{student_id}' does not exist.")

    sessions = get_student_learning_sessions(student_id, limit=10, custom_path=custom_path)
    diagnostics = get_student_diagnostic_records(student_id, limit=5, custom_path=custom_path)
    curricula = get_student_curriculum_plans(student_id, limit=5, custom_path=custom_path)
    assessments = get_student_assessment_history(student_id, custom_path=custom_path)
    mastery = get_student_topic_mastery(student_id, custom_path=custom_path)

    return {
        "profile": student,
        "recent_learning_sessions": sessions,
        "recent_diagnostics": diagnostics,
        "recent_curriculum_plans": curricula,
        "recent_assessments": assessments[:10],
        "topic_mastery": mastery,
        "stats": {
            "total_sessions": len(sessions),
            "total_quizzes_taken": len(assessments),
            "topics_mastered": sum(1 for m in mastery if m.get("mastery_status") == "mastered"),
            "topics_in_progress": sum(1 for m in mastery if m.get("mastery_status") == "in_progress"),
            "topics_needing_revision": sum(1 for m in mastery if m.get("mastery_status") == "needs_revision"),
        },
    }


# ==============================================================================
# Existing Diagnostic, Curriculum, Quiz, and Assessment Attempts Persistence
# ==============================================================================

def save_diagnostic_record(
    record_id: str,
    student_id: str,
    subject: str,
    topic: str,
    assessment_input: Any,
    diagnostic_output: Any,
    custom_path: Optional[Path | str] = None,
) -> str:
    """Save an evaluated student diagnostic report."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    input_json = (
        json.dumps(assessment_input)
        if not isinstance(assessment_input, str)
        else assessment_input
    )
    output_json = (
        json.dumps(diagnostic_output)
        if not isinstance(diagnostic_output, str)
        else diagnostic_output
    )

    try:
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO diagnostic_records (
                    id, student_id, subject, topic, assessment_input, diagnostic_output, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record_id,
                    student_id,
                    subject.strip(),
                    topic.strip(),
                    input_json,
                    output_json,
                    now,
                ),
            )
        return record_id
    finally:
        conn.close()


def get_diagnostic_record(
    record_id: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a diagnostic record by id."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, student_id, subject, topic, assessment_input, diagnostic_output, created_at
            FROM diagnostic_records WHERE id = ?;
            """,
            (record_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            res["assessment_input"] = json.loads(res["assessment_input"])
        except Exception:
            pass
        try:
            res["diagnostic_output"] = json.loads(res["diagnostic_output"])
        except Exception:
            pass
        return res
    finally:
        conn.close()


def save_curriculum_plan(
    plan_id: str,
    student_id: str,
    diagnostic_id: str,
    plan_output: Any,
    custom_path: Optional[Path | str] = None,
) -> str:
    """Save a personalized curriculum plan linked to its diagnostic record."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    output_json = (
        json.dumps(plan_output)
        if not isinstance(plan_output, str)
        else plan_output
    )

    try:
        with conn:
            conn.execute(
                """
                INSERT INTO curriculum_plans (
                    id, student_id, diagnostic_id, plan_output, created_at
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (plan_id, student_id, diagnostic_id, output_json, now),
            )
        return plan_id
    finally:
        conn.close()


def get_curriculum_plan(
    plan_id: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a curriculum plan by id."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, student_id, diagnostic_id, plan_output, created_at
            FROM curriculum_plans WHERE id = ?;
            """,
            (plan_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            res["plan_output"] = json.loads(res["plan_output"])
        except Exception:
            pass
        return res
    finally:
        conn.close()


def save_quiz(
    quiz_id: str,
    subject: str,
    topic: str,
    grade: str,
    questions: Any,
    student_id: Optional[str] = None,
    custom_path: Optional[Path | str] = None,
) -> str:
    """Save generated quiz including full question structures and rubrics."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    q_json = (
        json.dumps(questions)
        if not isinstance(questions, str)
        else questions
    )
    try:
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO quizzes (id, student_id, subject, topic, grade, questions, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (quiz_id, student_id, subject.strip(), topic.strip(), grade.strip(), q_json, now),
            )
        return quiz_id
    finally:
        conn.close()


def get_quiz(
    quiz_id: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve full quiz including question structures."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, student_id, subject, topic, grade, questions, created_at
            FROM quizzes WHERE id = ?;
            """,
            (quiz_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            res["questions"] = json.loads(res["questions"])
        except Exception:
            pass
        return res
    finally:
        conn.close()


def save_assessment_attempt(
    attempt_id: str,
    quiz_id: str,
    submitted_answers: Any,
    score: float,
    max_marks: float,
    evaluation_details: Any,
    student_id: Optional[str] = None,
    custom_path: Optional[Path | str] = None,
) -> str:
    """Save student quiz attempt, scores, and constructive feedback."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    ans_json = (
        json.dumps(submitted_answers)
        if not isinstance(submitted_answers, str)
        else submitted_answers
    )
    eval_json = (
        json.dumps(evaluation_details)
        if not isinstance(evaluation_details, str)
        else evaluation_details
    )
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO assessment_attempts (
                    id, quiz_id, student_id, submitted_answers, score, max_marks, evaluation_details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (attempt_id, quiz_id, student_id, ans_json, score, max_marks, eval_json, now),
            )
        return attempt_id
    finally:
        conn.close()


def get_assessment_attempt(
    attempt_id: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a single assessment attempt by id."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, quiz_id, student_id, submitted_answers, score, max_marks, evaluation_details, created_at
            FROM assessment_attempts WHERE id = ?;
            """,
            (attempt_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            res["submitted_answers"] = json.loads(res["submitted_answers"])
        except Exception:
            pass
        try:
            res["evaluation_details"] = json.loads(res["evaluation_details"])
        except Exception:
            pass
        return res
    finally:
        conn.close()


def get_student_assessment_history(
    student_id: str,
    custom_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve all assessment attempts for a given student."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT a.id as attempt_id, a.quiz_id, a.student_id, a.score, a.max_marks,
                   a.evaluation_details, a.created_at, q.subject, q.topic, q.grade
            FROM assessment_attempts a
            JOIN quizzes q ON a.quiz_id = q.id
            WHERE a.student_id = ?
            ORDER BY a.created_at DESC;
            """,
            (student_id,),
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            item = dict(r)
            try:
                item["evaluation_details"] = json.loads(item["evaluation_details"])
            except Exception:
                pass
            results.append(item)
        return results
    finally:
        conn.close()


# ==============================================================================
# Complete Chapter Learning Journey & Adaptive Loop Persistence
# ==============================================================================

def create_learning_journey(
    journey_id: str,
    student_id: str,
    subject: str,
    chapter: str,
    learning_goal: Optional[str] = None,
    max_retries: int = 3,
    initial_data: Optional[Dict[str, Any]] = None,
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Create and persist a new sequential Chapter Learning Journey record."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection(custom_path)
    journey_payload = json.dumps(initial_data or {})
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO learning_journeys (
                    id, student_id, subject, chapter, learning_goal,
                    current_step, status, loop_iteration, max_retries,
                    mastery_score, mastery_achieved, journey_data, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'orchestrator', 'active', 1, ?, 0.0, 0, ?, ?, ?);
                """,
                (
                    journey_id,
                    student_id,
                    subject,
                    chapter,
                    learning_goal,
                    max_retries,
                    journey_payload,
                    now,
                    now,
                ),
            )
        return {
            "id": journey_id,
            "student_id": student_id,
            "subject": subject,
            "chapter": chapter,
            "learning_goal": learning_goal,
            "current_step": "orchestrator",
            "status": "active",
            "loop_iteration": 1,
            "max_retries": max_retries,
            "mastery_score": 0.0,
            "mastery_achieved": False,
            "journey_data": initial_data or {},
            "created_at": now,
            "updated_at": now,
        }
    finally:
        conn.close()


def get_learning_journey(
    journey_id: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a single chapter learning journey by ID."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, student_id, subject, chapter, learning_goal,
                   current_step, status, loop_iteration, max_retries,
                   mastery_score, mastery_achieved, journey_data, created_at, updated_at
            FROM learning_journeys WHERE id = ?;
            """,
            (journey_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item["journey_data"] = json.loads(item["journey_data"]) if item["journey_data"] else {}
        except Exception:
            item["journey_data"] = {}
        item["mastery_achieved"] = bool(item["mastery_achieved"])
        return item
    finally:
        conn.close()


def get_active_learning_journey_for_student(
    student_id: str,
    subject: Optional[str] = None,
    chapter: Optional[str] = None,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve an active learning journey for the given student."""
    conn = get_db_connection(custom_path)
    try:
        query = "SELECT * FROM learning_journeys WHERE student_id = ? AND status IN ('active', 'needs_student_input')"
        params = [student_id]
        if subject:
            query += " AND subject = ?"
            params.append(subject)
        if chapter:
            query += " AND chapter = ?"
            params.append(chapter)
        query += " ORDER BY updated_at DESC LIMIT 1;"

        cursor = conn.execute(query, tuple(params))
        row = cursor.fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item["journey_data"] = json.loads(item["journey_data"]) if item["journey_data"] else {}
        except Exception:
            item["journey_data"] = {}
        item["mastery_achieved"] = bool(item["mastery_achieved"])
        return item
    finally:
        conn.close()


def update_learning_journey_step(
    journey_id: str,
    current_step: str,
    status: str,
    step_key: Optional[str] = None,
    step_data: Optional[Any] = None,
    mastery_score: Optional[float] = None,
    mastery_achieved: Optional[bool] = None,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Update current step, execution status, and append step output to journey_data."""
    current = get_learning_journey(journey_id, custom_path=custom_path)
    if not current:
        return None

    now = datetime.now(timezone.utc).isoformat()
    journey_data = current.get("journey_data", {})
    if step_key and step_data is not None:
        journey_data[step_key] = step_data

    conn = get_db_connection(custom_path)
    try:
        with conn:
            updates = ["current_step = ?", "status = ?", "journey_data = ?", "updated_at = ?"]
            params = [current_step, status, json.dumps(journey_data), now]

            if mastery_score is not None:
                updates.append("mastery_score = ?")
                params.append(mastery_score)

            if mastery_achieved is not None:
                updates.append("mastery_achieved = ?")
                params.append(1 if mastery_achieved else 0)

            params.append(journey_id)
            sql = f"UPDATE learning_journeys SET {', '.join(updates)} WHERE id = ?;"
            conn.execute(sql, tuple(params))

        return get_learning_journey(journey_id, custom_path=custom_path)
    finally:
        conn.close()


def increment_journey_iteration(
    journey_id: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Increment the adaptive loop iteration counter when student repeats remediation."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection(custom_path)
    try:
        with conn:
            conn.execute(
                """
                UPDATE learning_journeys
                SET loop_iteration = loop_iteration + 1, updated_at = ?
                WHERE id = ?;
                """,
                (now, journey_id),
            )
        return get_learning_journey(journey_id, custom_path=custom_path)
    finally:
        conn.close()


def list_student_learning_journeys(
    student_id: str,
    custom_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve all chapter learning journeys for a student."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, student_id, subject, chapter, learning_goal,
                   current_step, status, loop_iteration, max_retries,
                   mastery_score, mastery_achieved, created_at, updated_at
            FROM learning_journeys
            WHERE student_id = ?
            ORDER BY created_at DESC;
            """,
            (student_id,),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()



# ==============================================================================
# CBSE CLASS 10 CURRICULUM SEEDING & CATALOGUE FOUNDATION
# ==============================================================================

def seed_cbse_curriculum_if_needed(
    custom_path: Optional[Path | str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Idempotently seed verified CBSE Class 10 Curriculum for Academic Session 2026-2027."""
    from backend.curriculum import cbse_class10_data as data

    should_close = False
    if conn is None:
        conn = get_db_connection(custom_path)
        should_close = True

    now = datetime.now(timezone.utc).isoformat()
    try:
        cursor = conn.cursor()
        subj_count = cursor.execute("SELECT count(*) FROM curriculum_subjects;").fetchone()[0]
        chap_count = cursor.execute("SELECT count(*) FROM curriculum_chapters;").fetchone()[0]

        if subj_count >= 17 and chap_count >= 100:
            logger.info("CBSE Curriculum already fully seeded (%d subjects, %d chapters).", subj_count, chap_count)
            _auto_enroll_existing_students(conn, now)
            return

        logger.info("Seeding CBSE Class 10 Curriculum (Session 2026-2027)...")

        # 1. Education Board
        b = data.BOARD_INFO
        conn.execute(
            """
            INSERT OR REPLACE INTO education_boards (id, name, code, country, official_portal, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (b["id"], b["name"], b["code"], b.get("country", "India"), b.get("official_website"), now),
        )

        # 2. Academic Session
        s = data.ACADEMIC_SESSION
        conn.execute(
            """
            INSERT OR REPLACE INTO academic_sessions (id, board_id, session_code, start_year, end_year, is_active, curriculum_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (s["id"], s["board_id"], s["session_code"], s.get("start_year", 2026), s.get("end_year", 2027), 1 if s.get("is_active", True) else 0, s.get("curriculum_url"), now),
        )

        # 3. Class
        cl = data.CLASS_INFO
        conn.execute(
            """
            INSERT OR REPLACE INTO curriculum_classes (id, board_id, session_id, class_code, class_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (cl["id"], cl["board_id"], cl["session_id"], cl["class_code"], cl["class_name"], now),
        )

        # 4. Subjects
        for subj in data.SUBJECTS:
            conn.execute(
                """
                INSERT OR REPLACE INTO curriculum_subjects (
                    id, class_id, code, name, short_name, category, is_compulsory, description, official_syllabus_url, verification_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    subj["id"],
                    cl["id"],
                    subj["code"],
                    subj["name"],
                    subj.get("short_name", subj["name"]),
                    subj["category"],
                    1 if subj.get("is_compulsory") else 0,
                    subj.get("description", ""),
                    subj.get("official_syllabus_url", ""),
                    subj.get("verification_status", "VERIFIED"),
                    now,
                ),
            )

        # 5. Units
        for u in data.UNITS:
            conn.execute(
                """
                INSERT OR REPLACE INTO curriculum_units (
                    id, subject_id, unit_number, title, section_tag, description, weightage_marks, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    u["id"],
                    u["subject_id"],
                    u["unit_number"],
                    u["title"],
                    u.get("section_tag", ""),
                    u.get("description", ""),
                    u.get("weightage_marks", 0),
                    now,
                ),
            )

        # 6. Chapters
        for ch in data.CHAPTERS:
            prereqs = ch.get("prerequisites", [])
            prereqs_str = json.dumps(prereqs) if isinstance(prereqs, list) else str(prereqs)
            conn.execute(
                """
                INSERT OR REPLACE INTO curriculum_chapters (
                    id, subject_id, unit_id, chapter_number, title, slug, section_tag, description, estimated_minutes, prerequisites, is_prescribed, excluded_topics, source_reference, verification_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    ch["id"],
                    ch["subject_id"],
                    ch.get("unit_id"),
                    ch["chapter_number"],
                    ch["title"],
                    ch.get("slug", ""),
                    ch.get("section_tag", ""),
                    ch.get("description", ""),
                    ch.get("estimated_minutes", 360),
                    prereqs_str,
                    1 if ch.get("is_prescribed", True) else 0,
                    ch.get("excluded_topics", ""),
                    ch.get("source_reference", ""),
                    ch.get("verification_status", "VERIFIED"),
                    now,
                ),
            )

        # 7. Topics
        for top in data.TOPICS:
            kc = json.dumps(top.get("key_concepts", [])) if not isinstance(top.get("key_concepts"), str) else top.get("key_concepts")
            defs = json.dumps(top.get("definitions", {})) if not isinstance(top.get("definitions"), str) else top.get("definitions")
            forms = json.dumps(top.get("formulas", [])) if not isinstance(top.get("formulas"), str) else top.get("formulas")
            miscon = json.dumps(top.get("common_misconceptions", [])) if not isinstance(top.get("common_misconceptions"), str) else top.get("common_misconceptions")
            pq = json.dumps(top.get("practice_questions", [])) if not isinstance(top.get("practice_questions"), str) else top.get("practice_questions")

            conn.execute(
                """
                INSERT OR REPLACE INTO curriculum_topics (
                    id, chapter_id, topic_number, title, slug, summary, importance, difficulty_level, key_concepts, definitions, formulas, common_misconceptions, practice_questions, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    top["id"],
                    top["chapter_id"],
                    top["topic_number"],
                    top["title"],
                    top.get("slug", ""),
                    top.get("summary", ""),
                    top.get("importance", "High"),
                    top.get("difficulty_level", "Intermediate"),
                    kc,
                    defs,
                    forms,
                    miscon,
                    pq,
                    now,
                ),
            )

        # 8. Subtopics
        for sub in data.SUBTOPICS:
            conn.execute(
                """
                INSERT OR REPLACE INTO curriculum_subtopics (
                    id, topic_id, subtopic_number, title, explanation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    sub["id"],
                    sub["topic_id"],
                    sub["subtopic_number"],
                    sub["title"],
                    sub.get("explanation", ""),
                    now,
                ),
            )

        # 9. Learning Objectives
        for obj in data.LEARNING_OBJECTIVES:
            conn.execute(
                """
                INSERT OR REPLACE INTO curriculum_learning_objectives (
                    id, topic_id, objective_code, description, bloom_level, created_at
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    obj["id"],
                    obj["topic_id"],
                    obj.get("objective_code", ""),
                    obj.get("description", ""),
                    obj.get("bloom_level", "Understand"),
                    now,
                ),
            )

        # 10. Resources
        for res in data.RESOURCES:
            conn.execute(
                """
                INSERT OR REPLACE INTO curriculum_resources (
                    id, chapter_id, topic_id, title, resource_type, url, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    res["id"],
                    res.get("chapter_id"),
                    res.get("topic_id"),
                    res["title"],
                    res["resource_type"],
                    res.get("url", ""),
                    res.get("notes", ""),
                    now,
                ),
            )

        # 11. Auto-enroll existing students
        _auto_enroll_existing_students(conn, now)

        logger.info("CBSE Class 10 Curriculum seeded successfully!")
    finally:
        if should_close:
            conn.commit()
            conn.close()


def _auto_enroll_existing_students(conn: sqlite3.Connection, now: str) -> None:
    """Ensure all existing students are enrolled in core subjects."""
    cursor = conn.cursor()
    students = cursor.execute("SELECT id FROM students;").fetchall()
    default_subject_ids = [
        "subj_science_086",
        "subj_math_std_041",
        "subj_social_science_087",
        "subj_english_lit_184",
        "subj_hindi_a_002",
    ]
    for s in students:
        s_id = s[0]
        for subj_id in default_subject_ids:
            enroll_id = f"enr_{s_id}_{subj_id}"
            conn.execute(
                """
                INSERT OR IGNORE INTO student_enrolled_subjects (id, student_id, subject_id, enrolled_at, is_active)
                VALUES (?, ?, ?, ?, 1);
                """,
                (enroll_id, s_id, subj_id, now),
            )


# ==============================================================================
# CURRICULUM QUERY & HIERARCHY FUNCTIONS
# ==============================================================================

def get_education_boards(custom_path: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """Retrieve all education boards."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute("SELECT id, name, code, country, official_portal, created_at FROM education_boards ORDER BY code;")
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def get_curriculum_subjects(
    category: Optional[str] = None,
    is_compulsory: Optional[bool] = None,
    custom_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve all curriculum subjects for Class 10 with unit and chapter statistics."""
    conn = get_db_connection(custom_path)
    try:
        query = """
            SELECT s.id, s.class_id, s.code, s.name, s.short_name, s.category,
                   s.is_compulsory, s.description, s.official_syllabus_url,
                   s.verification_status, s.created_at,
                   COUNT(DISTINCT u.id) as unit_count,
                   COUNT(DISTINCT c.id) as chapter_count
            FROM curriculum_subjects s
            LEFT JOIN curriculum_units u ON u.subject_id = s.id
            LEFT JOIN curriculum_chapters c ON c.subject_id = s.id
            WHERE 1=1
        """
        params: List[Any] = []
        if category:
            query += " AND s.category = ?"
            params.append(category)
        if is_compulsory is not None:
            query += " AND s.is_compulsory = ?"
            params.append(1 if is_compulsory else 0)

        query += " GROUP BY s.id ORDER BY s.is_compulsory DESC, s.name ASC;"
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["is_compulsory"] = bool(d["is_compulsory"])
            result.append(d)
        return result
    finally:
        conn.close()


def get_curriculum_subject(subject_id: str, custom_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve details for a single subject by ID."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, class_id, code, name, short_name, category, is_compulsory,
                   description, official_syllabus_url, verification_status, created_at
            FROM curriculum_subjects
            WHERE id = ?;
            """,
            (subject_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["is_compulsory"] = bool(d["is_compulsory"])
        return d
    finally:
        conn.close()


def get_subject_hierarchy(subject_id: str, custom_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve complete subject hierarchy: units, chapters, and topics."""
    subj = get_curriculum_subject(subject_id, custom_path=custom_path)
    if not subj:
        return None

    conn = get_db_connection(custom_path)
    try:
        # Fetch units
        cursor = conn.execute(
            """
            SELECT id, subject_id, unit_number, title, section_tag, description, weightage_marks, created_at
            FROM curriculum_units
            WHERE subject_id = ?
            ORDER BY unit_number ASC;
            """,
            (subject_id,),
        )
        units = [dict(r) for r in cursor.fetchall()]

        # Fetch chapters
        cursor = conn.execute(
            """
            SELECT id, subject_id, unit_id, chapter_number, title, slug, section_tag,
                   description, estimated_minutes, prerequisites, is_prescribed,
                   excluded_topics, source_reference, verification_status, created_at
            FROM curriculum_chapters
            WHERE subject_id = ?
            ORDER BY chapter_number ASC;
            """,
            (subject_id,),
        )
        all_chapters = [dict(r) for r in cursor.fetchall()]

        # Fetch all topics for subject
        cursor = conn.execute(
            """
            SELECT t.id, t.chapter_id, t.topic_number, t.title, t.slug, t.summary,
                   t.importance, t.difficulty_level, t.created_at
            FROM curriculum_topics t
            JOIN curriculum_chapters c ON c.id = t.chapter_id
            WHERE c.subject_id = ?
            ORDER BY t.topic_number ASC;
            """,
            (subject_id,),
        )
        all_topics = [dict(r) for r in cursor.fetchall()]

        # Map topics to chapters
        topics_by_chapter: Dict[str, List[Dict[str, Any]]] = {}
        for top in all_topics:
            topics_by_chapter.setdefault(top["chapter_id"], []).append(top)

        for chap in all_chapters:
            chap["topics"] = topics_by_chapter.get(chap["id"], [])
            chap["topic_count"] = len(chap["topics"])

        # Map chapters to units
        chapters_by_unit: Dict[str, List[Dict[str, Any]]] = {}
        orphan_chapters: List[Dict[str, Any]] = []
        for chap in all_chapters:
            u_id = chap.get("unit_id")
            if u_id:
                chapters_by_unit.setdefault(u_id, []).append(chap)
            else:
                orphan_chapters.append(chap)

        for u in units:
            u["chapters"] = chapters_by_unit.get(u["id"], [])

        subj["units"] = units
        if orphan_chapters:
            subj["unassigned_chapters"] = orphan_chapters
        subj["total_chapters"] = len(all_chapters)
        subj["total_topics"] = len(all_topics)
        return subj
    finally:
        conn.close()


def get_chapters_by_subject(
    subject_id: str,
    unit_id: Optional[str] = None,
    custom_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve all chapters for a given subject."""
    conn = get_db_connection(custom_path)
    try:
        query = """
            SELECT c.id, c.subject_id, c.unit_id, c.chapter_number, c.title, c.slug,
                   c.section_tag, c.description, c.estimated_minutes, c.prerequisites,
                   c.is_prescribed, c.excluded_topics, c.source_reference,
                   c.verification_status, c.created_at,
                   u.title as unit_title,
                   COUNT(DISTINCT t.id) as topic_count
            FROM curriculum_chapters c
            LEFT JOIN curriculum_units u ON u.id = c.unit_id
            LEFT JOIN curriculum_topics t ON t.chapter_id = c.id
            WHERE c.subject_id = ?
        """
        params: List[Any] = [subject_id]
        if unit_id:
            query += " AND c.unit_id = ?"
            params.append(unit_id)

        query += " GROUP BY c.id ORDER BY c.chapter_number ASC;"
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("prerequisites"):
                try:
                    d["prerequisites"] = json.loads(d["prerequisites"])
                except Exception:
                    pass
            d["is_prescribed"] = bool(d["is_prescribed"])
            result.append(d)
        return result
    finally:
        conn.close()


def get_chapter_details(chapter_id: str, custom_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve full chapter details including topics, subtopics, objectives, and resources."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT c.id, c.subject_id, c.unit_id, c.chapter_number, c.title, c.slug,
                   c.section_tag, c.description, c.estimated_minutes, c.prerequisites,
                   c.is_prescribed, c.excluded_topics, c.source_reference,
                   c.verification_status, c.created_at,
                   s.name as subject_name, s.code as subject_code,
                   u.title as unit_title
            FROM curriculum_chapters c
            JOIN curriculum_subjects s ON s.id = c.subject_id
            LEFT JOIN curriculum_units u ON u.id = c.unit_id
            WHERE c.id = ?;
            """,
            (chapter_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        chap = dict(row)
        if chap.get("prerequisites"):
            try:
                chap["prerequisites"] = json.loads(chap["prerequisites"])
            except Exception:
                pass

        # Topics
        cursor = conn.execute(
            """
            SELECT id, chapter_id, topic_number, title, slug, summary,
                   importance, difficulty_level, key_concepts, definitions,
                   formulas, common_misconceptions, practice_questions, created_at
            FROM curriculum_topics
            WHERE chapter_id = ?
            ORDER BY topic_number ASC;
            """,
            (chapter_id,),
        )
        topics = []
        for tr in cursor.fetchall():
            td = dict(tr)
            for jf in ["key_concepts", "definitions", "formulas", "common_misconceptions", "practice_questions"]:
                if td.get(jf) and isinstance(td[jf], str):
                    try:
                        td[jf] = json.loads(td[jf])
                    except Exception:
                        pass
            topics.append(td)

        # Resources
        cursor = conn.execute(
            """
            SELECT id, chapter_id, topic_id, title, resource_type, url, notes, created_at
            FROM curriculum_resources
            WHERE chapter_id = ?
            ORDER BY created_at ASC;
            """,
            (chapter_id,),
        )
        resources = [dict(rr) for rr in cursor.fetchall()]

        chap["topics"] = topics
        chap["resources"] = resources
        return chap
    finally:
        conn.close()


def get_topics_by_chapter(chapter_id: str, custom_path: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """Retrieve topics for a given chapter."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, chapter_id, topic_number, title, slug, summary,
                   importance, difficulty_level, key_concepts, definitions,
                   formulas, common_misconceptions, practice_questions, created_at
            FROM curriculum_topics
            WHERE chapter_id = ?
            ORDER BY topic_number ASC;
            """,
            (chapter_id,),
        )
        result = []
        for r in cursor.fetchall():
            td = dict(r)
            for jf in ["key_concepts", "definitions", "formulas", "common_misconceptions", "practice_questions"]:
                if td.get(jf) and isinstance(td[jf], str):
                    try:
                        td[jf] = json.loads(td[jf])
                    except Exception:
                        pass
            result.append(td)
        return result
    finally:
        conn.close()


def get_topic_details(topic_id: str, custom_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve comprehensive topic details including subtopics, learning objectives, and resources."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT t.id, t.chapter_id, t.topic_number, t.title, t.slug, t.summary,
                   t.importance, t.difficulty_level, t.key_concepts, t.definitions,
                   t.formulas, t.common_misconceptions, t.practice_questions, t.created_at,
                   c.title as chapter_title, c.chapter_number, c.subject_id,
                   s.name as subject_name, s.code as subject_code
            FROM curriculum_topics t
            JOIN curriculum_chapters c ON c.id = t.chapter_id
            JOIN curriculum_subjects s ON s.id = c.subject_id
            WHERE t.id = ?;
            """,
            (topic_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        top = dict(row)
        for jf in ["key_concepts", "definitions", "formulas", "common_misconceptions", "practice_questions"]:
            if top.get(jf) and isinstance(top[jf], str):
                try:
                    top[jf] = json.loads(top[jf])
                except Exception:
                    pass

        # Subtopics
        cursor = conn.execute(
            """
            SELECT id, topic_id, subtopic_number, title, explanation, created_at
            FROM curriculum_subtopics
            WHERE topic_id = ?
            ORDER BY subtopic_number ASC;
            """,
            (topic_id,),
        )
        top["subtopics"] = [dict(sr) for sr in cursor.fetchall()]

        # Learning Objectives
        cursor = conn.execute(
            """
            SELECT id, topic_id, objective_code, description, bloom_level, created_at
            FROM curriculum_learning_objectives
            WHERE topic_id = ?
            ORDER BY id ASC;
            """,
            (topic_id,),
        )
        top["learning_objectives"] = [dict(lor) for lor in cursor.fetchall()]

        # Resources
        cursor = conn.execute(
            """
            SELECT id, chapter_id, topic_id, title, resource_type, url, notes, created_at
            FROM curriculum_resources
            WHERE topic_id = ? OR (chapter_id = ? AND topic_id IS NULL)
            ORDER BY created_at ASC;
            """,
            (topic_id, top["chapter_id"]),
        )
        top["resources"] = [dict(rr) for rr in cursor.fetchall()]

        return top
    finally:
        conn.close()


def search_curriculum(
    query: str,
    subject_id: Optional[str] = None,
    limit: int = 20,
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Search curriculum chapters and topics matching keyword queries."""
    conn = get_db_connection(custom_path)
    try:
        norm_q = f"%{query.strip().lower()}%"

        # Search chapters
        chap_sql = """
            SELECT c.id, c.subject_id, c.chapter_number, c.title, c.description, c.section_tag,
                   s.name as subject_name, s.code as subject_code
            FROM curriculum_chapters c
            JOIN curriculum_subjects s ON s.id = c.subject_id
            WHERE (LOWER(c.title) LIKE ? OR LOWER(c.description) LIKE ? OR LOWER(c.section_tag) LIKE ?)
        """
        chap_params: List[Any] = [norm_q, norm_q, norm_q]
        if subject_id:
            chap_sql += " AND c.subject_id = ?"
            chap_params.append(subject_id)
        chap_sql += " LIMIT ?;"
        chap_params.append(limit)

        c_rows = conn.execute(chap_sql, tuple(chap_params)).fetchall()

        # Search topics
        top_sql = """
            SELECT t.id, t.chapter_id, t.topic_number, t.title, t.summary, t.importance,
                   c.title as chapter_title, c.chapter_number, c.subject_id,
                   s.name as subject_name, s.code as subject_code
            FROM curriculum_topics t
            JOIN curriculum_chapters c ON c.id = t.chapter_id
            JOIN curriculum_subjects s ON s.id = c.subject_id
            WHERE (LOWER(t.title) LIKE ? OR LOWER(t.summary) LIKE ? OR LOWER(t.key_concepts) LIKE ?)
        """
        top_params: List[Any] = [norm_q, norm_q, norm_q]
        if subject_id:
            top_sql += " AND c.subject_id = ?"
            top_params.append(subject_id)
        top_sql += " LIMIT ?;"
        top_params.append(limit)

        t_rows = conn.execute(top_sql, tuple(top_params)).fetchall()

        return {
            "query": query,
            "chapters": [dict(r) for r in c_rows],
            "topics": [dict(r) for r in t_rows],
            "total_matches": len(c_rows) + len(t_rows),
        }
    finally:
        conn.close()


# ==============================================================================
# STUDENT SUBJECT ENROLLMENT & PROGRESS PERSISTENCE
# ==============================================================================

def enroll_student_subjects(
    student_id: str,
    subject_ids: List[str],
    custom_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Enroll a student in selected curriculum subjects."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            # Verify student exists
            student = conn.execute("SELECT id FROM students WHERE id = ?;", (student_id,)).fetchone()
            if not student:
                raise ValueError(f"Student '{student_id}' does not exist.")

            # Deactivate unselected subjects and insert/activate selected
            conn.execute("UPDATE student_enrolled_subjects SET is_active = 0 WHERE student_id = ?;", (student_id,))

            for sid in subject_ids:
                enroll_id = f"enr_{student_id}_{sid}"
                conn.execute(
                    """
                    INSERT INTO student_enrolled_subjects (id, student_id, subject_id, enrolled_at, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(student_id, subject_id) DO UPDATE SET is_active = 1, enrolled_at = ?;
                    """,
                    (enroll_id, student_id, sid, now, now),
                )

        return get_student_enrolled_subjects(student_id, custom_path=custom_path)
    finally:
        conn.close()


def get_student_enrolled_subjects(
    student_id: str,
    custom_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve all active subjects a student is enrolled in with progress stats."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT e.id as enrollment_id, e.enrolled_at,
                   s.id, s.class_id, s.code, s.name, s.short_name, s.category,
                   s.is_compulsory, s.description, s.official_syllabus_url,
                   COUNT(DISTINCT c.id) as chapter_count,
                   COUNT(DISTINCT t.id) as total_topics
            FROM student_enrolled_subjects e
            JOIN curriculum_subjects s ON s.id = e.subject_id
            LEFT JOIN curriculum_chapters c ON c.subject_id = s.id
            LEFT JOIN curriculum_topics t ON t.chapter_id = c.id
            WHERE e.student_id = ? AND e.is_active = 1
            GROUP BY s.id
            ORDER BY s.is_compulsory DESC, s.name ASC;
            """,
            (student_id,),
        )
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["is_compulsory"] = bool(d["is_compulsory"])

            # Compute completed topics
            prog = conn.execute(
                """
                SELECT COUNT(p.id)
                FROM student_topic_progress p
                JOIN curriculum_topics t ON t.id = p.topic_id
                JOIN curriculum_chapters c ON c.id = t.chapter_id
                WHERE p.student_id = ? AND c.subject_id = ? AND p.status IN ('completed', 'mastered');
                """,
                (student_id, d["id"]),
            ).fetchone()[0]

            d["completed_topics"] = prog
            tot = d["total_topics"]
            d["progress_percentage"] = round((prog / tot * 100), 1) if tot > 0 else 0.0
            result.append(d)
        return result
    finally:
        conn.close()


def update_student_topic_progress(
    student_id: str,
    topic_id: str,
    status: str,
    time_spent_seconds: int = 0,
    notes: Optional[str] = None,
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Record or update student progress on a curriculum topic."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    prog_id = f"prog_{student_id}_{topic_id}"
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO student_topic_progress (
                    id, student_id, topic_id, status, time_spent_seconds, last_studied_at, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id, topic_id) DO UPDATE SET
                    status = excluded.status,
                    time_spent_seconds = student_topic_progress.time_spent_seconds + excluded.time_spent_seconds,
                    last_studied_at = excluded.last_studied_at,
                    notes = COALESCE(excluded.notes, student_topic_progress.notes),
                    updated_at = excluded.updated_at;
                """,
                (prog_id, student_id, topic_id, status, time_spent_seconds, now, notes, now, now),
            )
        return get_student_topic_progress(student_id, topic_id, custom_path=custom_path) or {}
    finally:
        conn.close()


def get_student_topic_progress(
    student_id: str,
    topic_id: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve student progress on a specific topic."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, student_id, topic_id, status, time_spent_seconds, last_studied_at, notes, created_at, updated_at
            FROM student_topic_progress
            WHERE student_id = ? AND topic_id = ?;
            """,
            (student_id, topic_id),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_student_subject_progress(
    student_id: str,
    subject_id: str,
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Calculate aggregated topic progress and chapter completion for a subject."""
    conn = get_db_connection(custom_path)
    try:
        # Total topics in subject
        tot_topics = conn.execute(
            """
            SELECT COUNT(t.id)
            FROM curriculum_topics t
            JOIN curriculum_chapters c ON c.id = t.chapter_id
            WHERE c.subject_id = ?;
            """,
            (subject_id,),
        ).fetchone()[0]

        # Topics by status
        cursor = conn.execute(
            """
            SELECT p.status, COUNT(p.id) as cnt, SUM(p.time_spent_seconds) as total_time
            FROM student_topic_progress p
            JOIN curriculum_topics t ON t.id = p.topic_id
            JOIN curriculum_chapters c ON c.id = t.chapter_id
            WHERE p.student_id = ? AND c.subject_id = ?
            GROUP BY p.status;
            """,
            (student_id, subject_id),
        )
        status_map: Dict[str, int] = {}
        total_time = 0
        for r in cursor.fetchall():
            status_map[r["status"]] = r["cnt"]
            if r["total_time"]:
                total_time += r["total_time"]

        completed = status_map.get("completed", 0) + status_map.get("mastered", 0)
        percentage = round((completed / tot_topics * 100), 1) if tot_topics > 0 else 0.0

        return {
            "student_id": student_id,
            "subject_id": subject_id,
            "total_topics": tot_topics,
            "completed_topics": completed,
            "in_progress_topics": status_map.get("in_progress", 0),
            "mastered_topics": status_map.get("mastered", 0),
            "progress_percentage": percentage,
            "total_study_time_seconds": total_time,
        }
    finally:
        conn.close()


# ==============================================================================
# LESSON SESSIONS & BOOKMARKS PERSISTENCE
# ==============================================================================

def create_or_get_lesson_session(
    student_id: str,
    subject_id: str,
    chapter_id: str,
    topic_id: Optional[str] = None,
    subtopic_id: Optional[str] = None,
    lesson_mode: str = "conceptual",
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Create or resume an active interactive lesson session for a student."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            # Check for existing active lesson
            cursor = conn.execute(
                """
                SELECT id, student_id, subject_id, chapter_id, topic_id, subtopic_id,
                       lesson_mode, messages, status, started_at, updated_at
                FROM lesson_sessions
                WHERE student_id = ? AND chapter_id = ? AND status = 'active'
                ORDER BY updated_at DESC LIMIT 1;
                """,
                (student_id, chapter_id),
            )
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["messages"] = json.loads(d["messages"]) if d.get("messages") else []
                return d

            import uuid
            sess_id = f"ls_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO lesson_sessions (
                    id, student_id, subject_id, chapter_id, topic_id, subtopic_id, lesson_mode, messages, status, started_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', 'active', ?, ?);
                """,
                (sess_id, student_id, subject_id, chapter_id, topic_id, subtopic_id, lesson_mode, now, now),
            )
        return {
            "id": sess_id,
            "student_id": student_id,
            "subject_id": subject_id,
            "chapter_id": chapter_id,
            "topic_id": topic_id,
            "subtopic_id": subtopic_id,
            "lesson_mode": lesson_mode,
            "messages": [],
            "status": "active",
            "started_at": now,
            "updated_at": now,
        }
    finally:
        conn.close()


def append_lesson_session_message(
    session_id: str,
    role: str,
    content: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Append a dialogue turn to a lesson session."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            cursor = conn.execute("SELECT messages FROM lesson_sessions WHERE id = ?;", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            msgs = json.loads(row[0]) if row[0] else []
            msgs.append({"role": role, "content": content, "timestamp": now})
            conn.execute(
                """
                UPDATE lesson_sessions
                SET messages = ?, updated_at = ?
                WHERE id = ?;
                """,
                (json.dumps(msgs), now, session_id),
            )
        return get_lesson_session(session_id, custom_path=custom_path)
    finally:
        conn.close()


def get_lesson_session(session_id: str, custom_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a lesson session by ID."""
    conn = get_db_connection(custom_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, student_id, subject_id, chapter_id, topic_id, subtopic_id,
                   lesson_mode, messages, status, started_at, updated_at, completed_at
            FROM lesson_sessions
            WHERE id = ?;
            """,
            (session_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["messages"] = json.loads(d["messages"]) if d.get("messages") else []
        return d
    finally:
        conn.close()


def get_active_lesson_session(
    student_id: str,
    chapter_id: Optional[str] = None,
    custom_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve active lesson session for student."""
    conn = get_db_connection(custom_path)
    try:
        query = """
            SELECT id, student_id, subject_id, chapter_id, topic_id, subtopic_id,
                   lesson_mode, messages, status, started_at, updated_at
            FROM lesson_sessions
            WHERE student_id = ? AND status = 'active'
        """
        params: List[Any] = [student_id]
        if chapter_id:
            query += " AND chapter_id = ?"
            params.append(chapter_id)
        query += " ORDER BY updated_at DESC LIMIT 1;"

        cursor = conn.execute(query, tuple(params))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["messages"] = json.loads(d["messages"]) if d.get("messages") else []
        return d
    finally:
        conn.close()


def complete_lesson_session(session_id: str, custom_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Mark a lesson session as completed."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute(
                """
                UPDATE lesson_sessions
                SET status = 'completed', completed_at = ?, updated_at = ?
                WHERE id = ?;
                """,
                (now, now, session_id),
            )
        return get_lesson_session(session_id, custom_path=custom_path)
    finally:
        conn.close()


def toggle_student_bookmark(
    student_id: str,
    entity_type: str,
    entity_id: str,
    note: Optional[str] = None,
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Toggle a bookmark (chapter, topic, resource, question) for a student."""
    conn = get_db_connection(custom_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            cursor = conn.execute(
                "SELECT id FROM student_bookmarks WHERE student_id = ? AND entity_type = ? AND entity_id = ?;",
                (student_id, entity_type, entity_id),
            )
            row = cursor.fetchone()
            if row:
                conn.execute("DELETE FROM student_bookmarks WHERE id = ?;", (row[0],))
                return {"action": "removed", "entity_type": entity_type, "entity_id": entity_id}
            else:
                bm_id = f"bm_{student_id}_{entity_type}_{entity_id}"
                conn.execute(
                    """
                    INSERT INTO student_bookmarks (id, student_id, entity_type, entity_id, note, created_at)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (bm_id, student_id, entity_type, entity_id, note, now),
                )
                return {"action": "created", "id": bm_id, "entity_type": entity_type, "entity_id": entity_id, "note": note}
    finally:
        conn.close()


def get_student_bookmarks(
    student_id: str,
    entity_type: Optional[str] = None,
    custom_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve bookmarks for a student."""
    conn = get_db_connection(custom_path)
    try:
        query = "SELECT id, student_id, entity_type, entity_id, note, created_at FROM student_bookmarks WHERE student_id = ?"
        params: List[Any] = [student_id]
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        query += " ORDER BY created_at DESC;"

        cursor = conn.execute(query, tuple(params))
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()
