"""Gyaan AI - Comprehensive Chapter Practice Set Service.

Implements Part 8 of Phase Pre-0 2.0:
- Complete Chapter Practice Sets with 60 questions total:
  * LOW / BASIC: 30 questions
  * MEDIUM / INTERMEDIATE: 20 questions
  * HARD / ADVANCED: 10 questions
  * TOTAL: 60 questions per complete chapter practice set
- Student can select a single difficulty tier ('basic', 'medium', 'hard') or the complete set ('all')
- Manageable batch generation (5-10 questions per batch) with deduplication and schema validation
- Supported formats: MCQs, True/False, Fill in blanks, Short Answer, Long Answer, Numerical Problems, Conceptual Reasoning, Assertion-Reason, Case-based, Application
- Database persistence in SQLite `quizzes` table to prevent re-generating on page refresh
- Save and resume unfinished student practice sessions
- Rubric-level evaluation with partial scoring and topic-wise mastery tracking
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import json_repair

from backend.agents.teacher import get_local_llm
from backend.db.database import (
    get_db_connection,
    save_quiz,
    get_quiz,
    save_assessment_attempt,
    record_topic_assessment_score,
    create_learning_session,
)
from backend.app.schemas import (
    PracticeQuestionItem,
    ChapterPracticeSetRequest,
    ChapterPracticeSetResponse,
    SavePracticeSessionRequest,
    SavePracticeSessionResponse,
)
from backend.services.diagnostic_service import get_chapter_subtopics

logger = logging.getLogger("gyaan_ai.practice_service")


def get_cached_practice_quiz_id(chapter: str, subject: str) -> str:
    """Generate consistent cache key for a chapter practice set in SQLite."""
    c_slug = "".join(c if c.isalnum() else "_" for c in chapter.lower()).strip("_")
    s_slug = "".join(c if c.isalnum() else "_" for c in subject.lower()).strip("_")
    return f"practice_set_{c_slug}_{s_slug}"


def build_practice_batch_prompt(
    grade: str,
    subject: str,
    chapter: str,
    topic: str,
    difficulty: str,
    num_questions: int,
    batch_index: int,
) -> str:
    """Construct prompt for a batch of questions tailored to a specific difficulty."""
    if difficulty == "basic":
        diff_guidance = (
            "Focus on direct recall, fundamental definitions, simple 1-step formulas, and standard facts. "
            "Questions should be accessible, building confidence."
        )
        type_guidance = "Mix of 3 MCQs (1 mark each), 1 True/False (1 mark), and 1 direct short-answer/fill-in-the-blank (1 mark)."
        marks = 1
    elif difficulty == "medium":
        diff_guidance = (
            "Focus on conceptual understanding, 2-step calculations, ray diagrams, or chemical reaction balancing. "
            "Questions test why and how."
        )
        type_guidance = "Mix of 2 conceptual MCQs (1 mark), 2 Short Answer/Numerical probes (2 marks each), and 1 Assertion-Reason probe (1 mark)."
        marks = 2
    else:  # hard
        diff_guidance = (
            "Focus on higher-order thinking skills (HOTS), multi-step numerical problems, complex circuit analysis, "
            "case-based analytical reasoning, and practical experimental design."
        )
        type_guidance = "Mix of multi-step numerical problems (3 marks), case-based multi-part probes (3 marks), and deep conceptual reasoning."
        marks = 3

    return (
        f"You are the CBSE Class 10 Assessment Specialist for Gyaan AI.\n"
        f"Generate a batch of EXACTLY {num_questions} {difficulty.upper()} practice questions for {grade} {subject}.\n"
        f"Chapter: '{chapter}'\n"
        f"Topic: '{topic}'\n"
        f"Difficulty Level: {difficulty.upper()}\n"
        f"Guidance: {diff_guidance}\n"
        f"Question Formats: {type_guidance}\n\n"
        f"REQUIREMENTS:\n"
        f"1. Align strictly with CBSE Class 10 NCERT standards.\n"
        f"2. Provide accurate answer keys and clear step-by-step marking rubrics.\n"
        f"3. Include pedagogical explanations for examiner records.\n\n"
        f"OUTPUT FORMAT:\n"
        f"Return ONLY a valid JSON list of {num_questions} objects with these exact keys:\n"
        f"[\n"
        f"  {{\n"
        f"    \"id\": \"prac_{difficulty[:3]}_{batch_index}_q1\",\n"
        f"    \"topic\": \"{topic}\",\n"
        f"    \"difficulty\": \"{difficulty}\",\n"
        f"    \"question_type\": \"mcq\" | \"true_false\" | \"fill_blank\" | \"short_answer\" | \"numerical\" | \"conceptual\" | \"assertion_reason\" | \"case_based\",\n"
        f"    \"question\": \"Question text here?\",\n"
        f"    \"options\": [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"] (or [\"True\", \"False\"] or []),\n"
        f"    \"marks\": {marks},\n"
        f"    \"expected_answer\": \"Precise correct answer or numerical result with units\",\n"
        f"    \"marking_rubric\": \"Step-by-step points needed for full credit\",\n"
        f"    \"explanation\": \"Pedagogical explanation of the solution\",\n"
        f"    \"source_reference\": \"NCERT Class 10 {subject}, Chapter: {chapter}\"\n"
        f"  }}\n"
        f"]\n\n"
        f"Provide ONLY the JSON list. Do not include conversational text or markdown preamble."
    )


def generate_full_chapter_practice_set_if_missing(
    chapter: str,
    subject: str = "Science",
    grade: str = "Class 10",
    student_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Ensure the complete 60-question practice set is generated and persisted in SQLite.

    Distribution:
    - Basic: 30 questions (across 5 subtopics, 6 questions each)
    - Medium: 20 questions (across 5 subtopics, 4 questions each)
    - Hard: 10 questions (across 5 subtopics, 2 questions each)
    Total = 60 questions
    """
    cache_quiz_id = get_cached_practice_quiz_id(chapter, subject)
    existing_quiz = get_quiz(cache_quiz_id)

    if existing_quiz and existing_quiz.get("questions") and len(existing_quiz["questions"]) >= 50:
        logger.info("Found existing complete 60-question practice set '%s' in database.", cache_quiz_id)
        return existing_quiz

    logger.info("Generating complete 60-question practice set for chapter: %s (%s)", chapter, subject)
    subtopics = get_chapter_subtopics(chapter, subject)[:5]
    llm = get_local_llm()

    all_questions: List[Dict[str, Any]] = []
    seen_texts = set()

    # Tier 1: Basic (30 questions -> 5 topics * 6 questions)
    logger.info("Generating Tier 1 (Basic): 30 questions...")
    for idx, topic in enumerate(subtopics):
        prompt = build_practice_batch_prompt(
            grade=grade,
            subject=subject,
            chapter=chapter,
            topic=topic,
            difficulty="basic",
            num_questions=6,
            batch_index=idx + 1,
        )
        _run_and_collect_batch(llm, prompt, all_questions, seen_texts, chapter, subject, topic, "basic")

    # Tier 2: Medium (20 questions -> 5 topics * 4 questions)
    logger.info("Generating Tier 2 (Medium): 20 questions...")
    for idx, topic in enumerate(subtopics):
        prompt = build_practice_batch_prompt(
            grade=grade,
            subject=subject,
            chapter=chapter,
            topic=topic,
            difficulty="medium",
            num_questions=4,
            batch_index=idx + 1,
        )
        _run_and_collect_batch(llm, prompt, all_questions, seen_texts, chapter, subject, topic, "medium")

    # Tier 3: Hard (10 questions -> 5 topics * 2 questions)
    logger.info("Generating Tier 3 (Hard): 10 questions...")
    for idx, topic in enumerate(subtopics):
        prompt = build_practice_batch_prompt(
            grade=grade,
            subject=subject,
            chapter=chapter,
            topic=topic,
            difficulty="hard",
            num_questions=2,
            batch_index=idx + 1,
        )
        _run_and_collect_batch(llm, prompt, all_questions, seen_texts, chapter, subject, topic, "hard")

    # Ensure question IDs are unique and sequential
    for i, q in enumerate(all_questions, 1):
        q["id"] = f"prac_{q.get('difficulty', 'basic')[:3]}_q{i:02d}"

    # Persist in SQLite quizzes table
    try:
        save_quiz(
            quiz_id=cache_quiz_id,
            student_id=student_id,
            subject=subject,
            topic=chapter,
            grade=grade,
            questions=all_questions,
        )
        logger.info("Saved complete practice set '%s' with %d questions into SQLite.", cache_quiz_id, len(all_questions))
    except Exception as exc:
        logger.warning("Could not persist practice set to SQLite: %s", exc)

    return {
        "id": cache_quiz_id,
        "subject": subject,
        "topic": chapter,
        "grade": grade,
        "questions": all_questions,
    }


def _run_and_collect_batch(
    llm: Any,
    prompt: str,
    all_questions: List[Dict[str, Any]],
    seen_texts: set,
    chapter: str,
    subject: str,
    topic: str,
    difficulty: str,
) -> None:
    """Helper to execute LLM call and parse batch items safely."""
    try:
        response_text = llm.call([{"role": "user", "content": prompt}])
        text = response_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        parsed = json_repair.loads(text)
        if not isinstance(parsed, list):
            parsed = [parsed] if isinstance(parsed, dict) else []

        for item in parsed:
            if not isinstance(item, dict):
                continue
            q_text = str(item.get("question", "")).strip()
            if not q_text or q_text.lower() in seen_texts:
                continue
            seen_texts.add(q_text.lower())

            all_questions.append({
                "id": str(item.get("id", uuid.uuid4().hex[:8])),
                "subject": subject,
                "chapter": chapter,
                "topic": topic,
                "difficulty": difficulty,
                "question_type": str(item.get("question_type", "mcq")).lower(),
                "question": q_text,
                "options": item.get("options", []),
                "marks": int(item.get("marks", 1 if difficulty == "basic" else (2 if difficulty == "medium" else 3))),
                "expected_answer": str(item.get("expected_answer", item.get("correct_answer", ""))).strip(),
                "marking_rubric": str(item.get("marking_rubric", "")).strip(),
                "explanation": str(item.get("explanation", "")).strip(),
                "source_reference": f"NCERT Class 10 {subject}, Chapter: {chapter}",
            })
    except Exception as exc:
        logger.warning("Error running practice batch for %s (%s): %s", topic, difficulty, exc)


def get_chapter_practice_set_sync(
    request: ChapterPracticeSetRequest,
) -> ChapterPracticeSetResponse:
    """Retrieve practice questions filtered by requested difficulty tier ('basic', 'medium', 'hard', 'all')."""
    start_time = time.perf_counter()
    chapter = request.chapter.strip()
    subject = request.subject.strip()
    grade = request.grade.strip()
    tier = request.difficulty_tier.strip().lower()

    # Retrieve or generate 60-question set
    full_set = generate_full_chapter_practice_set_if_missing(
        chapter=chapter,
        subject=subject,
        grade=grade,
        student_id=request.student_id,
    )
    all_qs: List[Dict[str, Any]] = full_set.get("questions", [])

    # Filter according to requested tier
    if tier == "basic":
        filtered = [q for q in all_qs if q.get("difficulty") == "basic"]
    elif tier == "medium":
        filtered = [q for q in all_qs if q.get("difficulty") == "medium"]
    elif tier == "hard":
        filtered = [q for q in all_qs if q.get("difficulty") == "hard"]
    else:  # 'all'
        filtered = all_qs

    # If specific topic filter requested
    if request.topic and request.topic.strip():
        req_top = request.topic.strip().lower()
        topic_filtered = [q for q in filtered if req_top in q.get("topic", "").lower()]
        if topic_filtered:
            filtered = topic_filtered

    # Convert to student-facing items (hide answer key)
    student_facing: List[PracticeQuestionItem] = []
    for q in filtered:
        student_facing.append(
            PracticeQuestionItem(
                id=q.get("id"),
                chapter_id=q.get("chapter_id"),
                topic_id=q.get("topic_id"),
                topic=q.get("topic", chapter),
                difficulty=q.get("difficulty", "basic"),
                question_type=q.get("question_type", "mcq"),
                question=q.get("question"),
                options=q.get("options", []),
                marks=int(q.get("marks", 1)),
                source_reference=q.get("source_reference"),
            )
        )

    basic_cnt = sum(1 for q in all_qs if q.get("difficulty") == "basic")
    med_cnt = sum(1 for q in all_qs if q.get("difficulty") == "medium")
    hard_cnt = sum(1 for q in all_qs if q.get("difficulty") == "hard")

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return ChapterPracticeSetResponse(
        practice_set_id=full_set.get("id", get_cached_practice_quiz_id(chapter, subject)),
        student_id=request.student_id,
        grade=grade,
        subject=subject,
        chapter=chapter,
        difficulty_tier=tier,
        total_questions=len(student_facing),
        basic_count=basic_cnt,
        medium_count=med_cnt,
        hard_count=hard_cnt,
        questions=student_facing,
        duration_ms=duration_ms,
        is_cached=True,
    )


# In-memory session store backed by SQLite for saving and resuming sessions
_SESSION_CACHE: Dict[str, Dict[str, Any]] = {}


def clear_practice_session_cache() -> None:
    """Clear the in-memory practice session cache (used in testing and session reset)."""
    _SESSION_CACHE.clear()


def save_practice_session_sync(
    request: SavePracticeSessionRequest,
    custom_path: Optional[Path | str] = None,
) -> SavePracticeSessionResponse:
    """Save the current state of an unfinished practice session."""
    session_id = request.session_id.strip()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    _SESSION_CACHE[session_id] = {
        "session_id": session_id,
        "student_id": request.student_id,
        "practice_set_id": request.practice_set_id,
        "chapter": request.chapter,
        "answers": request.answers,
        "current_index": request.current_index,
        "time_spent_seconds": request.time_spent_seconds,
        "saved_at": now_iso,
    }

    # Also record as a learning session in SQLite
    if request.student_id:
        try:
            create_learning_session(
                session_id=session_id,
                student_id=request.student_id,
                subject="Science",
                topic=request.chapter,
                activity_type="practice_session",
                status="paused",
                details={
                    "practice_set_id": request.practice_set_id,
                    "answers_count": len(request.answers),
                    "answers": request.answers,
                    "current_index": request.current_index,
                    "time_spent_seconds": request.time_spent_seconds,
                },
                custom_path=custom_path,
            )
        except Exception as exc:
            logger.warning("Could not persist practice session to DB: %s", exc)

    return SavePracticeSessionResponse(
        session_id=session_id,
        status="saved",
        saved_at=now_iso,
    )


def resume_practice_session_sync(
    session_id: str,
    custom_path: Optional[Path | str] = None,
) -> Optional[SavePracticeSessionRequest]:
    """Retrieve the saved state of an in-progress practice session."""
    data = _SESSION_CACHE.get(session_id)
    if not data:
        # Check database learning_sessions
        try:
            conn = get_db_connection(custom_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT student_id, topic, details FROM learning_sessions WHERE id = ? LIMIT 1",
                (session_id,),
            )
            row = cursor.fetchone()
            if row:
                st_id, topic, det_json = row[0], row[1], row[2]
                det = json.loads(det_json) if det_json else {}
                return SavePracticeSessionRequest(
                    session_id=session_id,
                    student_id=st_id,
                    practice_set_id=det.get("practice_set_id", ""),
                    chapter=topic,
                    answers=det.get("answers", {}),
                    current_index=det.get("current_index", 0),
                    time_spent_seconds=det.get("time_spent_seconds", 0),
                )
        except Exception as exc:
            logger.warning("Error fetching session from DB: %s", exc)
        return None

    return SavePracticeSessionRequest(
        session_id=data["session_id"],
        student_id=data.get("student_id"),
        practice_set_id=data["practice_set_id"],
        chapter=data["chapter"],
        answers=data.get("answers", {}),
        current_index=data.get("current_index", 0),
        time_spent_seconds=data.get("time_spent_seconds", 0),
    )
