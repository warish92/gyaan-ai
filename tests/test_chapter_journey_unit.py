"""Unit tests for Gyaan AI Canonical 8-Agent Sequential Chapter Learning Journey.

Tests:
1. build_chapter_learning_journey_crew builds all 8 agents and 8 tasks.
2. Crew configured with Process.sequential.
3. Explicit task context chaining across all downstream tasks.
4. Database helper lifecycle for learning_journeys table.
5. Orchestrator WORKFLOW_REGISTRY registers chapter_learning_journey.
"""

import pytest
from crewai import Process

from backend.agents.chapter_journey import build_chapter_learning_journey_crew
from backend.agents.orchestrator import WORKFLOW_REGISTRY
from backend.db.database import (
    create_learning_journey,
    get_learning_journey,
    get_active_learning_journey_for_student,
    update_learning_journey_step,
    increment_journey_iteration,
    list_student_learning_journeys,
    init_db,
)


def test_workflow_registry_includes_chapter_learning_journey():
    """Ensure chapter_learning_journey is registered in the central orchestrator."""
    assert "chapter_learning_journey" in WORKFLOW_REGISTRY
    entry = WORKFLOW_REGISTRY["chapter_learning_journey"]
    assert entry.requires_auth is False
    assert len(entry.agents) == 8
    assert "chapter_learning_journey" in entry.description.lower() or "sequential" in entry.description.lower()


def test_build_chapter_learning_journey_crew_structure():
    """Ensure build_chapter_learning_journey_crew constructs genuine 8 agents and 9 sequential tasks."""
    crew, tasks, agents_map = build_chapter_learning_journey_crew(
        subject="Science",
        chapter="Chemical Reactions and Equations",
        student_goal="Master balancing equations",
        grade="Class 10",
        language="English",
    )

    assert len(tasks) == 9
    assert len(agents_map) == 8
    assert crew.process == Process.sequential

    expected_agent_keys = [
        "orchestrator", "curriculum", "diagnostic", "resource",
        "teacher", "assessment", "progress", "mentor"
    ]
    for key in expected_agent_keys:
        assert key in agents_map

    # Verify context chaining:
    # Task 0 (Orchestrator Scope) has no upstream context
    # Task 1 (Curriculum) depends on Task 0
    assert tasks[1].context is not None
    assert tasks[0] in tasks[1].context

    # Task 2 (Diagnostic) depends on Task 1
    assert tasks[2].context is not None
    assert tasks[1] in tasks[2].context

    # Task 3 (Resource) depends on Task 1
    assert tasks[3].context is not None
    assert tasks[1] in tasks[3].context

    # Task 4 (Teacher) depends on Tasks 1, 2, 3
    assert tasks[4].context is not None
    assert tasks[2] in tasks[4].context
    assert tasks[1] in tasks[4].context
    assert tasks[3] in tasks[4].context

    # Task 5 (Assessment) depends on Tasks 1, 4
    assert tasks[5].context is not None
    assert tasks[1] in tasks[5].context
    assert tasks[4] in tasks[5].context

    # Task 6 (Progress) depends on Task 5
    assert tasks[6].context is not None
    assert tasks[5] in tasks[6].context

    # Task 7 (Mentor) depends on Tasks 0, 1, 5, 6
    assert tasks[7].context is not None
    assert tasks[0] in tasks[7].context
    assert tasks[1] in tasks[7].context
    assert tasks[5] in tasks[7].context
    assert tasks[6] in tasks[7].context

    # Task 8 (Orchestrator Final Synthesis) depends on Tasks 1, 4, 5, 6, 7
    assert tasks[8].context is not None
    assert tasks[1] in tasks[8].context
    assert tasks[4] in tasks[8].context
    assert tasks[5] in tasks[8].context
    assert tasks[6] in tasks[8].context
    assert tasks[7] in tasks[8].context


def test_learning_journey_database_crud(tmp_path):
    """Test full CRUD lifecycle for learning_journeys table in isolated SQLite database."""
    from backend.db.database import create_student_account

    test_db = tmp_path / "test_journey.db"
    init_db(test_db)

    jid = "jrn_test_unit_01"
    sid = "stu_test_unit_01"

    # Create parent student first to satisfy FOREIGN KEY
    create_student_account(
        student_id=sid,
        email="test_journey_crud@example.com",
        password_hash="fake_hash_123",
        display_name="Unit Test Student",
        grade="Class 10",
        preferred_language="English",
        custom_path=test_db,
    )

    # 1. Create journey
    created = create_learning_journey(
        journey_id=jid,
        student_id=sid,
        subject="Science",
        chapter="Acids, Bases and Salts",
        learning_goal="Understand pH scale",
        max_retries=3,
        initial_data={"orchestrator": "Initialized"},
        custom_path=test_db,
    )
    assert created["id"] == jid

    # 2. Retrieve journey
    rec = get_learning_journey(jid, custom_path=test_db)
    assert rec is not None
    assert rec["id"] == jid
    assert rec["student_id"] == sid
    assert rec["subject"] == "Science"
    assert rec["current_step"] == "orchestrator"
    assert rec["status"] == "active"
    assert rec["loop_iteration"] == 1
    assert rec["mastery_achieved"] is False

    # 3. Retrieve active journey for student
    active_rec = get_active_learning_journey_for_student(sid, custom_path=test_db)
    assert active_rec is not None
    assert active_rec["id"] == jid

    # 4. Increment iteration
    incremented = increment_journey_iteration(jid, custom_path=test_db)
    assert incremented["loop_iteration"] == 2
    rec2 = get_learning_journey(jid, custom_path=test_db)
    assert rec2["loop_iteration"] == 2

    # 5. Update step and complete
    updated = update_learning_journey_step(
        journey_id=jid,
        current_step="completed",
        status="completed",
        step_key="final_outputs",
        step_data={"mentor": "Great work on pH scale"},
        mastery_score=85.0,
        mastery_achieved=True,
        custom_path=test_db,
    )
    assert updated is not None
    assert updated["current_step"] == "completed"

    rec3 = get_learning_journey(jid, custom_path=test_db)
    assert rec3["current_step"] == "completed"
    assert rec3["status"] == "completed"
    assert rec3["mastery_score"] == 85.0
    assert bool(rec3["mastery_achieved"]) is True
    assert rec3["journey_data"]["final_outputs"]["mentor"] == "Great work on pH scale"

    # 6. List student journeys
    all_journeys = list_student_learning_journeys(sid, custom_path=test_db)
    assert len(all_journeys) == 1
    assert all_journeys[0]["id"] == jid
