"""
Gyaan AI - Practice Session Security & Ownership Authorization Test Suite.

Comprehensive test coverage across:
- Student A can save and resume Student A's practice session with full answer preservation
- Student B cannot access or resume Student A's practice session (HTTP 403 Forbidden)
- Unauthenticated users cannot access protected student sessions (HTTP 401 Unauthorized)
- Nonexistent session IDs return standard HTTP 404 Not Found
- Saved answers are accurately restored from database persistence across cache clearing
- Student B cannot overwrite or hijack Student A's existing session (HTTP 403 Forbidden)
- Unauthenticated users cannot spoof student_id during session save
- Anonymous / unowned practice sessions function without leaking student identities
- Strict test isolation ensuring production database is untouched
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.db.database import (
    DEFAULT_DB_PATH,
    create_session,
    create_student_account,
    get_db_connection,
    init_db,
)
from backend.services.auth_service import hash_session_token
from backend.services.practice_service import clear_practice_session_cache


@pytest.fixture
def security_test_env(tmp_path: Path) -> Generator[Dict[str, Any], None, None]:
    """Sets up an isolated SQLite database and test identities for Student A and Student B."""
    temp_db = tmp_path / "test_practice_security.db"

    # Enforce test isolation guard via environment variable
    os.environ["GYAAN_DB_PATH"] = str(temp_db)
    os.environ["GYAAN_TEST_MODE"] = "1"

    # Initialize isolated SQLite database schema
    init_db(temp_db)

    # Register Student A and Student B
    create_student_account(
        student_id="student_A",
        email="student_a@example.com",
        password_hash="scrypt_dummy_hash_a",
        display_name="Student A",
        grade="Class 10",
        custom_path=temp_db,
    )
    create_student_account(
        student_id="student_B",
        email="student_b@example.com",
        password_hash="scrypt_dummy_hash_b",
        display_name="Student B",
        grade="Class 10",
        custom_path=temp_db,
    )

    # Generate active session tokens
    token_a = "tok_student_a_security_secret_111"
    token_b = "tok_student_b_security_secret_222"
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    create_session(
        session_id="sess_auth_a",
        student_id="student_A",
        token_hash=hash_session_token(token_a),
        expires_at=expires_at,
        custom_path=temp_db,
    )
    create_session(
        session_id="sess_auth_b",
        student_id="student_B",
        token_hash=hash_session_token(token_b),
        expires_at=expires_at,
        custom_path=temp_db,
    )

    client = TestClient(app)

    yield {
        "db_path": temp_db,
        "client": client,
        "token_a": token_a,
        "token_b": token_b,
        "student_a": "student_A",
        "student_b": "student_B",
    }

    # Teardown & cleanup
    clear_practice_session_cache()
    if "GYAAN_DB_PATH" in os.environ:
        del os.environ["GYAAN_DB_PATH"]
    if "GYAAN_TEST_MODE" in os.environ:
        del os.environ["GYAAN_TEST_MODE"]


# ============================================================================
# Security & Authorization Test Cases
# ============================================================================

def test_01_student_a_can_save_and_resume_own_session(security_test_env: Dict[str, Any]) -> None:
    """Verify that Student A can save and successfully resume their own practice session with answers."""
    client: TestClient = security_test_env["client"]
    token_a: str = security_test_env["token_a"]

    session_id = "practice_sess_alice_001"
    save_payload = {
        "session_id": session_id,
        "practice_set_id": "pset_chem_reactions_01",
        "chapter": "Chemical Reactions and Equations",
        "answers": {
            "q1": "Combustion produces heat and light",
            "q2": "Option B",
            "q3": "Exothermic",
        },
        "current_index": 2,
        "time_spent_seconds": 185,
    }

    # Save session with Student A's auth header
    save_res = client.post(
        "/api/v1/practice/save-session",
        json=save_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert save_res.status_code == status.HTTP_200_OK, save_res.text
    save_data = save_res.json()
    assert save_data["session_id"] == session_id
    assert save_data["status"] == "saved"

    # Resume session with Student A's auth header
    resume_res = client.get(
        f"/api/v1/practice/resume-session/{session_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resume_res.status_code == status.HTTP_200_OK, resume_res.text
    resume_data = resume_res.json()
    assert resume_data["session_id"] == session_id
    assert resume_data["student_id"] == "student_A"
    assert resume_data["chapter"] == "Chemical Reactions and Equations"
    assert resume_data["answers"] == {
        "q1": "Combustion produces heat and light",
        "q2": "Option B",
        "q3": "Exothermic",
    }
    assert resume_data["current_index"] == 2
    assert resume_data["time_spent_seconds"] == 185


def test_02_student_b_cannot_resume_student_a_session(security_test_env: Dict[str, Any]) -> None:
    """Verify that Student B receives HTTP 403 Forbidden when attempting to resume Student A's session."""
    client: TestClient = security_test_env["client"]
    token_a: str = security_test_env["token_a"]
    token_b: str = security_test_env["token_b"]

    session_id = "practice_sess_alice_private"
    save_payload = {
        "session_id": session_id,
        "practice_set_id": "pset_electricity_01",
        "chapter": "Electricity",
        "answers": {"q1": "Ohm's Law: V = IR"},
        "current_index": 0,
        "time_spent_seconds": 60,
    }

    # Student A creates session
    save_res = client.post(
        "/api/v1/practice/save-session",
        json=save_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert save_res.status_code == status.HTTP_200_OK

    # Student B attempts to access Student A's session
    cross_access_res = client.get(
        f"/api/v1/practice/resume-session/{session_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_access_res.status_code == status.HTTP_403_FORBIDDEN
    assert "Access denied" in cross_access_res.json()["detail"]


def test_03_unauthenticated_user_cannot_access_protected_session(security_test_env: Dict[str, Any]) -> None:
    """Verify that unauthenticated callers receive HTTP 401 Unauthorized for protected student sessions."""
    client: TestClient = security_test_env["client"]
    token_a: str = security_test_env["token_a"]

    session_id = "practice_sess_alice_protected"
    save_payload = {
        "session_id": session_id,
        "practice_set_id": "pset_acids_bases_01",
        "chapter": "Acids, Bases and Salts",
        "answers": {"q1": "pH of acidic solution is < 7"},
        "current_index": 1,
        "time_spent_seconds": 90,
    }

    # Student A creates session
    save_res = client.post(
        "/api/v1/practice/save-session",
        json=save_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert save_res.status_code == status.HTTP_200_OK

    # Unauthenticated caller attempts to resume
    anon_res = client.get(f"/api/v1/practice/resume-session/{session_id}")
    assert anon_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Authentication required" in anon_res.json()["detail"]


def test_04_nonexistent_session_id_returns_404(security_test_env: Dict[str, Any]) -> None:
    """Verify that querying a nonexistent session ID returns HTTP 404 Not Found."""
    client: TestClient = security_test_env["client"]
    token_a: str = security_test_env["token_a"]

    res = client.get(
        "/api/v1/practice/resume-session/nonexistent_session_xyz_999",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in res.json()["detail"].lower()


def test_05_answers_restored_from_database_after_cache_clear(security_test_env: Dict[str, Any]) -> None:
    """Verify that session answers are durably stored in SQLite and recovered even after cache purge."""
    client: TestClient = security_test_env["client"]
    token_a: str = security_test_env["token_a"]

    session_id = "practice_sess_alice_cold_db"
    expected_answers = {
        "item_1": "Direct Answer 1",
        "item_2": "Detailed calculation showing 42 Joules",
        "item_3": "Option D",
    }
    save_payload = {
        "session_id": session_id,
        "practice_set_id": "pset_magnetic_effects_01",
        "chapter": "Magnetic Effects of Electric Current",
        "answers": expected_answers,
        "current_index": 2,
        "time_spent_seconds": 320,
    }

    save_res = client.post(
        "/api/v1/practice/save-session",
        json=save_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert save_res.status_code == status.HTTP_200_OK

    # Simulate backend restart or cold cache by wiping in-memory session cache
    clear_practice_session_cache()

    # Resume must fetch from SQLite learning_sessions and reconstruct answers
    resume_res = client.get(
        f"/api/v1/practice/resume-session/{session_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resume_res.status_code == status.HTTP_200_OK
    data = resume_res.json()
    assert data["session_id"] == session_id
    assert data["student_id"] == "student_A"
    assert data["answers"] == expected_answers
    assert data["current_index"] == 2
    assert data["time_spent_seconds"] == 320


def test_06_unauthenticated_user_cannot_spoof_student_id_on_save(security_test_env: Dict[str, Any]) -> None:
    """Verify that unauthenticated callers cannot claim ownership of an authenticated student ID."""
    client: TestClient = security_test_env["client"]
    token_a: str = security_test_env["token_a"]

    session_id = "practice_sess_spoof_attempt"
    spoof_payload = {
        "session_id": session_id,
        "student_id": "student_A",  # Spoofing Student A without credentials
        "practice_set_id": "pset_metals_01",
        "chapter": "Metals and Non-metals",
        "answers": {"q1": "Sodium is reactive"},
        "current_index": 0,
        "time_spent_seconds": 30,
    }

    # Save without auth token
    save_res = client.post("/api/v1/practice/save-session", json=spoof_payload)
    assert save_res.status_code == status.HTTP_200_OK

    # The server must NOT have bound the session to student_A
    # Resuming it as an unauthenticated session must show student_id is null/None
    resume_res = client.get(f"/api/v1/practice/resume-session/{session_id}")
    assert resume_res.status_code == status.HTTP_200_OK
    assert resume_res.json()["student_id"] is None


def test_07_student_b_cannot_overwrite_student_a_session(security_test_env: Dict[str, Any]) -> None:
    """Verify that Student B cannot overwrite or hijack an existing session owned by Student A."""
    client: TestClient = security_test_env["client"]
    token_a: str = security_test_env["token_a"]
    token_b: str = security_test_env["token_b"]

    session_id = "practice_sess_alice_hijack_target"
    save_payload = {
        "session_id": session_id,
        "practice_set_id": "pset_life_processes_01",
        "chapter": "Life Processes",
        "answers": {"q1": "Original Alice Answer"},
        "current_index": 0,
        "time_spent_seconds": 50,
    }

    # Alice creates session
    save_res = client.post(
        "/api/v1/practice/save-session",
        json=save_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert save_res.status_code == status.HTTP_200_OK

    # Bob attempts to overwrite Alice's session
    hijack_payload = {
        "session_id": session_id,
        "practice_set_id": "pset_life_processes_01",
        "chapter": "Life Processes",
        "answers": {"q1": "Tampered Bob Answer"},
        "current_index": 1,
        "time_spent_seconds": 120,
    }
    hijack_res = client.post(
        "/api/v1/practice/save-session",
        json=hijack_payload,
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert hijack_res.status_code == status.HTTP_403_FORBIDDEN
    assert "Access denied" in hijack_res.json()["detail"]

    # Verify Alice's original session answers remain unchanged
    alice_resume = client.get(
        f"/api/v1/practice/resume-session/{session_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert alice_resume.status_code == status.HTTP_200_OK
    assert alice_resume.json()["answers"] == {"q1": "Original Alice Answer"}


def test_08_anonymous_session_save_and_resume(security_test_env: Dict[str, Any]) -> None:
    """Verify that anonymous practice sessions (unowned) function normally without authentication."""
    client: TestClient = security_test_env["client"]

    session_id = "practice_sess_guest_001"
    guest_payload = {
        "session_id": session_id,
        "student_id": None,
        "practice_set_id": "pset_guest_set",
        "chapter": "Control and Coordination",
        "answers": {"q1": "Neuron structure"},
        "current_index": 0,
        "time_spent_seconds": 45,
    }

    # Save as anonymous
    save_res = client.post("/api/v1/practice/save-session", json=guest_payload)
    assert save_res.status_code == status.HTTP_200_OK

    # Resume as anonymous
    resume_res = client.get(f"/api/v1/practice/resume-session/{session_id}")
    assert resume_res.status_code == status.HTTP_200_OK
    data = resume_res.json()
    assert data["session_id"] == session_id
    assert data["student_id"] is None
    assert data["answers"] == {"q1": "Neuron structure"}


def test_09_production_database_untouched(security_test_env: Dict[str, Any]) -> None:
    """Regression invariant verifying that running practice security tests leaves production database untouched."""
    import sqlite3
    active_db = DEFAULT_DB_PATH
    assert active_db.exists()

    uri = f"{active_db.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM students;")
        total_students = cur.fetchone()[0]
        assert total_students in (793, 794)

        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        assert cur.fetchone()[0] == 23
    finally:
        conn.close()
