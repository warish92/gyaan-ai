"""Gyaan AI - Comprehensive CBSE Class 10 Curriculum System Tests.

Validates:
1. Official Board and Session metadata (CBSE, Academic Session 2026-2027, Class 10).
2. Complete subject catalogue: All 17 subjects (Core, Alternatives, Electives, Skills).
3. Science chapter coverage: 13 prescribed chapters with Physics/Chem/Bio section tags.
4. Mathematics chapter coverage: 14 prescribed chapters for Standard (041) and Basic (241).
5. Social Science structure: 4 distinct units (History, Geography, Political Science, Economics).
6. Language structures: English (184) and Hindi (002) Literature, Supplementary, Grammar, Writing.
7. Skill subjects: Information Technology (402) and Artificial Intelligence (417).
8. Full subject hierarchy retrieval with nested units, chapters, and topics.
9. Topic pedagogical components: Key concepts, definitions, formulas, misconceptions, practice.
10. Learning objectives mapped to Bloom's taxonomy levels.
11. Real-time curriculum search.
12. Student subject enrollment and retrieval.
13. Topic progress tracking (status, time spent, notes).
14. Subject progress aggregation and percentage completion.
15. Interactive lesson sessions lifecycle (create, append message, complete).
16. Student bookmarks toggle and listing.
17. AI Teacher Studio curriculum context passing.
"""

import json
import pytest
import uuid
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.curriculum import cbse_class10_data as cdata
from backend.db.database import (
    init_db,
    get_education_boards,
    get_curriculum_subjects,
    get_curriculum_subject,
    get_subject_hierarchy,
    get_chapters_by_subject,
    get_chapter_details,
    get_topics_by_chapter,
    get_topic_details,
    search_curriculum,
    enroll_student_subjects,
    get_student_enrolled_subjects,
    update_student_topic_progress,
    get_student_topic_progress,
    get_student_subject_progress,
    create_or_get_lesson_session,
    append_lesson_session_message,
    get_lesson_session,
    complete_lesson_session,
    toggle_student_bookmark,
    get_student_bookmarks,
    create_student_account,
)
from backend.agents.crew import create_teacher_task, build_teacher_crew
from backend.agents.teacher import create_teacher_agent


@pytest.fixture(scope="module")
def client():
    init_db()
    return TestClient(app)


# ==============================================================================
# 1. BOARD, SESSION, AND CLASS METADATA
# ==============================================================================

def test_cbse_board_and_session_metadata():
    """Verify official CBSE, Academic Session 2026-2027, and Class 10 metadata."""
    assert cdata.BOARD_INFO["code"] == "CBSE"
    assert "Central Board of Secondary Education" in cdata.BOARD_INFO["name"]
    assert cdata.ACADEMIC_SESSION["session_code"] == "2026-2027"
    assert cdata.ACADEMIC_SESSION["is_active"] is True
    assert cdata.CLASS_INFO["class_code"] == "Class 10"

    boards = get_education_boards()
    assert len(boards) >= 1
    assert boards[0]["code"] == "CBSE"


# ==============================================================================
# 2. COMPLETE SUBJECT CATALOGUE (17 PRESCRIBED SUBJECTS)
# ==============================================================================

def test_complete_subject_catalogue():
    """Verify all 17 prescribed CBSE subjects exist in the catalogue."""
    subjects = get_curriculum_subjects()
    assert len(subjects) == 17

    codes = {s["code"] for s in subjects}
    expected_codes = {
        "041", "241", "086", "087", "184", "101", "002", "085",
        "122", "165", "064", "049", "154", "254", "402", "417", "405",
    }
    for code in expected_codes:
        assert code in codes, f"Expected CBSE subject code '{code}' not found."


# ==============================================================================
# 3. SCIENCE (086) - 13 PRESCRIBED CHAPTERS & DOMAINS
# ==============================================================================

def test_science_chapters_and_sections():
    """Verify Science has exactly 13 prescribed chapters with Physics, Chemistry, Biology tags."""
    chapters = get_chapters_by_subject("subj_science_086")
    assert len(chapters) == 13

    tags = {c["section_tag"] for c in chapters}
    assert "Chemistry" in tags
    assert "Biology" in tags
    assert "Physics" in tags

    titles = [c["title"] for c in chapters]
    assert "Chemical Reactions and Equations" in titles
    assert "Acids, Bases and Salts" in titles
    assert "Life Processes" in titles
    assert "Electricity" in titles
    assert "Our Environment" in titles


# ==============================================================================
# 4. MATHEMATICS STANDARD (041) & BASIC (241)
# ==============================================================================

def test_mathematics_chapters():
    """Verify 14 chapters for Mathematics Standard (041) and Basic (241)."""
    std_chapters = get_chapters_by_subject("subj_math_std_041")
    assert len(std_chapters) == 14

    basic_chapters = get_chapters_by_subject("subj_math_basic_241")
    assert len(basic_chapters) == 14

    std_titles = [c["title"] for c in std_chapters]
    assert "Real Numbers" in std_titles
    assert "Polynomials" in std_titles
    assert "Quadratic Equations" in std_titles
    assert "Triangles" in std_titles
    assert "Introduction to Trigonometry" in std_titles
    assert "Statistics" in std_titles
    assert "Probability" in std_titles


# ==============================================================================
# 5. SOCIAL SCIENCE (087) - 4 DISTINCT UNITS
# ==============================================================================

def test_social_science_structure():
    """Verify Social Science contains History, Geography, Political Science, and Economics."""
    hierarchy = get_subject_hierarchy("subj_social_science_087")
    assert hierarchy is not None
    assert len(hierarchy["units"]) == 4

    unit_tags = {u["section_tag"] for u in hierarchy["units"]}
    assert "History" in unit_tags
    assert "Geography" in unit_tags
    assert "Political Science" in unit_tags
    assert "Economics" in unit_tags

    chapters = get_chapters_by_subject("subj_social_science_087")
    assert len(chapters) >= 20
    titles = [c["title"] for c in chapters]
    assert "The Rise of Nationalism in Europe" in titles
    assert "Nationalism in India" in titles
    assert "Resources and Development" in titles
    assert "Power Sharing" in titles
    assert "Development" in titles


# ==============================================================================
# 6. LANGUAGE STRUCTURES (ENGLISH 184 & HINDI 002)
# ==============================================================================

def test_language_curriculum_structures():
    """Verify English and Hindi maintain dedicated Literature, Grammar, and Writing structures."""
    eng_hierarchy = get_subject_hierarchy("subj_english_lit_184")
    assert eng_hierarchy is not None
    eng_units = {u["section_tag"] for u in eng_hierarchy["units"]}
    assert any("Literature" in tag or "First Flight" in tag for tag in eng_units)
    assert any("Writing" in tag or "Grammar" in tag for tag in eng_units)

    hin_hierarchy = get_subject_hierarchy("subj_hindi_a_002")
    assert hin_hierarchy is not None
    hin_units = {u["section_tag"] for u in hin_hierarchy["units"]}
    assert any("Literature" in tag for tag in hin_units)
    assert any("Grammar" in tag for tag in hin_units)


# ==============================================================================
# 7. SKILL & ELECTIVE SUBJECTS (IT 402 & AI 417)
# ==============================================================================

def test_skill_subjects():
    """Verify IT (402) and AI (417) are present with verified chapters."""
    ai_chaps = get_chapters_by_subject("subj_ai_417")
    assert len(ai_chaps) >= 5
    ai_titles = [c["title"] for c in ai_chaps]
    assert any("AI Project Cycle" in t for t in ai_titles)
    assert any("Computer Vision" in t for t in ai_titles)
    assert any("Natural Language Processing" in t for t in ai_titles)

    it_chaps = get_chapters_by_subject("subj_it_402")
    assert len(it_chaps) >= 4
    it_titles = [c["title"] for c in it_chaps]
    assert any("Digital Documentation" in t for t in it_titles)
    assert any("DBMS" in t or "Database" in t for t in it_titles)


# ==============================================================================
# 8. HIERARCHY RETRIEVAL
# ==============================================================================

def test_subject_hierarchy_retrieval():
    """Verify get_subject_hierarchy returns complete nested tree."""
    hierarchy = get_subject_hierarchy("subj_science_086")
    assert hierarchy is not None
    assert hierarchy["id"] == "subj_science_086"
    assert hierarchy["total_chapters"] == 13
    assert hierarchy["total_topics"] >= 20

    first_unit = hierarchy["units"][0]
    assert "chapters" in first_unit
    assert len(first_unit["chapters"]) > 0

    first_chap = first_unit["chapters"][0]
    assert "topics" in first_chap
    assert len(first_chap["topics"]) > 0


# ==============================================================================
# 9. TOPIC PEDAGOGICAL COMPONENTS
# ==============================================================================

def test_topic_details_components():
    """Verify topic details include key concepts, definitions, formulas, misconceptions, practice."""
    topic = get_topic_details("top_sci_1_1")
    assert topic is not None
    assert topic["title"] == "Chemical Equations and Balancing"
    assert len(topic["key_concepts"]) > 0
    assert len(topic["definitions"]) > 0
    assert len(topic["formulas"]) > 0
    assert len(topic["common_misconceptions"]) > 0
    assert len(topic["practice_questions"]) > 0
    assert len(topic["subtopics"]) >= 2
    assert len(topic["learning_objectives"]) >= 2


# ==============================================================================
# 10. BLOOM'S TAXONOMY OBJECTIVES
# ==============================================================================

def test_blooms_taxonomy_objectives():
    """Verify learning objectives specify recognized Bloom's taxonomy cognitive levels."""
    topic = get_topic_details("top_sci_1_1")
    assert topic is not None
    valid_levels = {"Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"}
    for obj in topic["learning_objectives"]:
        assert obj["bloom_level"] in valid_levels


# ==============================================================================
# 11. REAL-TIME CURRICULUM SEARCH
# ==============================================================================

def test_curriculum_search():
    """Verify search returns matching chapters and topics."""
    res = search_curriculum("reactions")
    assert res["total_matches"] > 0
    assert len(res["chapters"]) > 0 or len(res["topics"]) > 0

    res_math = search_curriculum("quadratic", subject_id="subj_math_std_041")
    assert res_math["total_matches"] > 0


# ==============================================================================
# 12. STUDENT ENROLLMENT & TRACKING
# ==============================================================================

def test_student_enrollment_and_progress(client):
    """Verify student subject enrollment and topic progress recording."""
    test_student_id = f"stu_test_curriculum_{uuid.uuid4().hex[:8]}"
    test_email = f"curriculum_tester_{uuid.uuid4().hex[:8]}@gyaan.ai"
    create_student_account(
        student_id=test_student_id,
        email=test_email,
        password_hash="testhash12345",
        display_name="Curriculum Tester",
    )

    # Enroll in 3 subjects
    enrolled = enroll_student_subjects(test_student_id, ["subj_science_086", "subj_math_std_041", "subj_social_science_087"])
    assert len(enrolled) == 3

    # Update topic progress
    prog = update_student_topic_progress(
        student_id=test_student_id,
        topic_id="top_sci_1_1",
        status="completed",
        time_spent_seconds=600,
        notes="Understood hit-and-trial balancing.",
    )
    assert prog["status"] == "completed"
    assert prog["time_spent_seconds"] >= 600

    # Retrieve subject progress
    subj_prog = get_student_subject_progress(test_student_id, "subj_science_086")
    assert subj_prog["completed_topics"] >= 1
    assert subj_prog["progress_percentage"] > 0.0


# ==============================================================================
# 13. INTERACTIVE LESSON SESSIONS
# ==============================================================================

def test_lesson_sessions():
    """Verify interactive lesson sessions create, append, and complete correctly."""
    test_student_id = "stu_test_curriculum_01"
    try:
        create_student_account(
            student_id=test_student_id,
            email="test_curriculum_01@gyaan.ai",
            password_hash="testhash12345",
            display_name="Curriculum Tester 01",
        )
    except Exception:
        pass
    sess = create_or_get_lesson_session(
        student_id=test_student_id,
        subject_id="subj_science_086",
        chapter_id="chap_sci_1",
        topic_id="top_sci_1_1",
        lesson_mode="conceptual",
    )
    assert sess["status"] == "active"
    sess_id = sess["id"]

    # Append student message
    updated = append_lesson_session_message(sess_id, role="student", content="Why do we balance chemical equations?")
    assert len(updated["messages"]) == 1

    # Append teacher message
    updated2 = append_lesson_session_message(sess_id, role="teacher", content="To satisfy the Law of Conservation of Mass.")
    assert len(updated2["messages"]) == 2

    # Complete session
    completed = complete_lesson_session(sess_id)
    assert completed["status"] == "completed"


# ==============================================================================
# 14. STUDENT BOOKMARKS
# ==============================================================================

def test_student_bookmarks():
    """Verify bookmark toggling and retrieval."""
    test_student_id = "stu_test_curriculum_01"
    try:
        create_student_account(
            student_id=test_student_id,
            email="test_curriculum_01@gyaan.ai",
            password_hash="testhash12345",
            display_name="Curriculum Tester 01",
        )
    except Exception:
        pass

    # Create bookmark
    res1 = toggle_student_bookmark(test_student_id, entity_type="topic", entity_id="top_sci_1_1", note="Revise before pre-boards")
    assert res1["action"] == "created"

    bookmarks = get_student_bookmarks(test_student_id)
    assert len(bookmarks) >= 1
    assert any(b["entity_id"] == "top_sci_1_1" for b in bookmarks)

    # Toggle to remove
    res2 = toggle_student_bookmark(test_student_id, entity_type="topic", entity_id="top_sci_1_1")
    assert res2["action"] == "removed"


# ==============================================================================
# 15. TEACHER AGENT CURRICULUM INTEGRATION
# ==============================================================================

def test_teacher_agent_curriculum_context():
    """Verify Teacher Agent Task and Crew accept and inject curriculum parameters."""
    teacher = create_teacher_agent()
    task = create_teacher_task(
        agent=teacher,
        student_question="How does temperature affect rate of reaction?",
        grade="Class 10",
        subject="Science",
        chapter="Chemical Reactions and Equations",
        topic="Types of Chemical Reactions",
        lesson_mode="conceptual",
    )

    assert "Chapter: 'Chemical Reactions and Equations'" in task.description
    assert "Topic: 'Types of Chemical Reactions'" in task.description
    assert "CONCEPTUAL" in task.description

    crew = build_teacher_crew(
        student_question="How does temperature affect rate of reaction?",
        grade="Class 10",
        subject="Science",
        chapter="Chemical Reactions and Equations",
        topic="Types of Chemical Reactions",
        lesson_mode="conceptual",
    )
    assert len(crew.agents) == 1
    assert len(crew.tasks) == 1


# ==============================================================================
# 16. FASTAPI API ENDPOINTS INTEGRATION
# ==============================================================================

def test_api_curriculum_endpoints(client):
    """Verify REST API responses for curriculum catalog, subjects, and search."""
    r_cat = client.get("/api/v1/curriculum/catalog")
    assert r_cat.status_code == 200
    data_cat = r_cat.json()
    assert data_cat["board"]["code"] == "CBSE"
    assert data_cat["total_subjects"] == 17

    r_subjs = client.get("/api/v1/curriculum/subjects")
    assert r_subjs.status_code == 200
    assert len(r_subjs.json()) == 17

    r_search = client.get("/api/v1/curriculum/search?q=photosynthesis")
    assert r_search.status_code == 200
    assert "total_matches" in r_search.json()
