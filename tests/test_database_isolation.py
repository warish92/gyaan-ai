"""
Test verifying database isolation and fail-safe guard under tests/conftest.py.
"""
import os
import sqlite3
import pytest
from pathlib import Path

from backend.db.database import (
    DEFAULT_DB_PATH,
    PHASE4_BACKUP_PATH,
    get_db_path,
    get_db_connection,
    save_student,
    get_student_by_id,
)

def test_db_isolation_path_is_temporary():
    """Verify that get_db_path() resolves to a temporary database, NOT the active project database."""
    current_path = get_db_path()
    assert current_path != DEFAULT_DB_PATH, f"Test database must NOT be {DEFAULT_DB_PATH}"
    assert current_path != PHASE4_BACKUP_PATH, f"Test database must NOT be {PHASE4_BACKUP_PATH}"
    assert "isolated_test_gyaan_ai.db" in str(current_path) or "test" in str(current_path).lower()
    print(f"\n[PASS] Isolated test database path verified: {current_path}")

def test_db_isolation_write_does_not_modify_active_db():
    """Verify writing a student record writes to the temporary test DB and leaves active DB untouched."""
    active_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    active_cur = active_conn.cursor()
    active_students_before = active_cur.execute("SELECT count(*) FROM students").fetchone()[0]
    active_conn.close()

    # Insert record into test DB
    test_id = "test_isolated_student_9999"
    save_student(test_id, "Isolated Student", "Class 10")

    # Verify record exists in test DB
    rec = get_student_by_id(test_id)
    assert rec is not None
    assert rec["id"] == test_id

    # Verify active DB record count is UNCHANGED
    active_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    active_cur = active_conn.cursor()
    active_students_after = active_cur.execute("SELECT count(*) FROM students").fetchone()[0]
    active_conn.close()

    assert active_students_after == active_students_before, (
        f"CRITICAL VIOLATION: Active DB students changed from {active_students_before} to {active_students_after}!"
    )
    print(f"\n[PASS] Active DB remained unchanged at {active_students_after} students.")

def test_fail_safe_guard_triggers_if_directed_at_active_db():
    """Verify that attempting to connect to active DB under test mode raises RuntimeError."""
    with pytest.raises(RuntimeError) as exc_info:
        get_db_path(custom_path=DEFAULT_DB_PATH)
    assert "CRITICAL SECURITY GUARD" in str(exc_info.value)
    print(f"\n[PASS] Fail-safe guard correctly raised: {exc_info.value}")
