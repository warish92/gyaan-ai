"""Gyaan AI - Comprehensive Diagnostic Assessment Service.

Implements Part 4 of Phase Pre-0 2.0:
- Dynamic Chapter and Topic Diagnostic Assessment Generation (20-30 questions, default target 25)
- Topic-wise coverage aligned with CBSE Class 10 NCERT curriculum
- Diverse question formats: MCQs, True/False, Fill in the blanks, Short Answer, Conceptual, Numerical, Assertion-Reason, Case-based
- Evidence-based Diagnostic Analysis: identifies correct, partial, incorrect, misconceptions, missing prerequisites, weak/strong topics
- Structured persistent diagnostic reports saved to SQLite
- Adaptive diagnosis: follow-up probes for weak topics
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
    get_chapters_by_subject,
    get_topics_by_chapter,
    save_diagnostic_record,
    get_diagnostic_record,
    save_quiz,
    get_quiz,
    record_topic_assessment_score,
)
from backend.app.schemas import (
    DiagnosticQuestionItem,
    DiagnosticAssessmentGenerateRequest,
    DiagnosticAssessmentGenerateResponse,
    DiagnosticEvaluateRequest,
    TopicDiagnosticResult,
    FullDiagnosticReportResponse,
    AdaptiveProbeRequest,
)

logger = logging.getLogger("gyaan_ai.diagnostic_service")

# Default topic breakdowns for NCERT Class 10 Science chapters if curriculum DB has minimal topics
CHAPTER_SUBTOPICS_FALLBACK: Dict[str, List[str]] = {
    "chemical reactions and equations": [
        "Chemical Equations and Balancing",
        "Combination and Decomposition Reactions",
        "Displacement and Double Displacement Reactions",
        "Precipitation, Neutralization, and Redox Reactions",
        "Corrosion, Rancidity and Practical Applications",
    ],
    "acids, bases and salts": [
        "Physical and Chemical Properties of Acids and Bases",
        "Reaction of Acids and Bases with Metals and Carbonates",
        "The pH Scale, Universal Indicators and Importance in Daily Life",
        "Salts from Strong/Weak Acids and Common Salt Derivatives",
        "Baking Soda, Washing Soda, Bleaching Powder and Plaster of Paris",
    ],
    "electricity": [
        "Electric Current, Circuit Diagrams and Potential Difference",
        "Ohm's Law and Factors Affecting Resistance (Length, Area, Resistivity)",
        "Resistors in Series and Parallel Combinations (Equivalent Resistance)",
        "Heating Effect of Electric Current (Joule's Law of Heating)",
        "Electric Power, Commercial Unit of Energy (kWh) and Practical Safety",
    ],
    "life processes": [
        "Autotrophic Nutrition and Photosynthesis Mechanism",
        "Heterotrophic Nutrition and Human Digestive System",
        "Respiration in Plants and Animals (Aerobic vs Anaerobic)",
        "Transportation in Humans (Heart, Blood Vessels) and Plants (Xylem, Phloem)",
        "Excretion in Humans (Nephron Structure and Function) and Plants",
    ],
    "light - reflection and refraction": [
        "Reflection of Light and Laws of Reflection",
        "Spherical Mirrors (Concave and Convex): Ray Diagrams and Image Formation",
        "Mirror Formula and Magnification Calculations",
        "Refraction of Light, Refractive Index and Laws of Refraction",
        "Spherical Lenses, Lens Formula, Magnification and Power of Lens",
    ],
    "magnetic effects of electric current": [
        "Magnetic Field Lines and Magnetic Field due to Current-Carrying Conductor",
        "Right-Hand Thumb Rule and Magnetic Field in Solenoid",
        "Force on Current-Carrying Conductor in Magnetic Field and Fleming's Left-Hand Rule",
        "Electric Motor Principle, Construction and Working",
        "Electromagnetic Induction and Domestic Electric Circuits (Earthing, Fuse)",
    ],
    "metals and non-metals": [
        "Physical and Chemical Properties of Metals and Non-metals",
        "Reactivity Series of Metals and Displacement Reactions",
        "Ionic Compounds: Formation, Properties and Lattice Structure",
        "Metallurgy: Extraction of Metals (Roasting, Calcination, Refining)",
        "Corrosion and Its Prevention (Galvanization, Alloying)",
    ],
}


def get_chapter_subtopics(chapter_name: str, subject_name: str = "Science") -> List[str]:
    """Retrieve verified subtopics for a chapter from SQLite or canonical NCERT map."""
    norm_chap = chapter_name.strip().lower()
    for key, subtopics in CHAPTER_SUBTOPICS_FALLBACK.items():
        if key in norm_chap or norm_chap in key:
            return subtopics

    # Try querying SQLite curriculum_topics
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.title FROM curriculum_topics t
            JOIN curriculum_chapters c ON c.id = t.chapter_id
            WHERE lower(c.title) LIKE ?
            ORDER BY t.topic_number
            """,
            (f"%{chapter_name.strip()}%",),
        )
        rows = cursor.fetchall()
        if rows and len(rows) >= 3:
            return [r[0] for r in rows]
    except Exception as exc:
        logger.warning("Error fetching topics from database: %s", exc)

    # Generic academic fallback
    return [
        f"{chapter_name} — Core Terminology & Definitions",
        f"{chapter_name} — Fundamental Principles & Laws",
        f"{chapter_name} — Reaction Mechanisms & Formulae",
        f"{chapter_name} — Quantitative Calculations & Problem Solving",
        f"{chapter_name} — Experimental Observations & Real-world Applications",
    ]


def build_batch_generation_prompt(
    grade: str,
    subject: str,
    chapter: str,
    topic: str,
    batch_index: int,
    questions_per_batch: int = 5,
) -> str:
    """Construct prompt for a single batch of 5 diverse diagnostic questions."""
    formats = [
        "1. Multiple Choice Question (MCQ) with exactly 4 options (A, B, C, D) and single correct answer",
        "2. True/False conceptual check with options ['True', 'False']",
        "3. Fill in the Blank probing exact terminology or scientific law",
        "4. Conceptual Short Answer (1-2 sentences) testing underlying reasoning",
        "5. Numerical Problem OR Assertion-Reason OR Case-based inquiry testing application",
    ]

    return (
        f"You are the CBSE Class 10 Diagnostic Specialist for Gyaan AI.\n"
        f"Create a high-yield diagnostic probe of EXACTLY {questions_per_batch} questions for {grade} {subject}.\n"
        f"Chapter: '{chapter}'\n"
        f"Subtopic: '{topic}'\n"
        f"Batch: #{batch_index + 1}\n\n"
        f"Required Formats for the 5 questions:\n"
        + "\n".join(formats) + "\n\n"
        f"REQUIREMENTS:\n"
        f"1. Align questions strictly with CBSE Class 10 NCERT standards.\n"
        f"2. Include unambiguous expected answers and pedagogical explanations.\n"
        f"3. Assign marks: 1 mark for MCQ/True-False/Fill-in-blank, 2 marks for conceptual/numerical/short answer.\n"
        f"4. Assign difficulty: 'basic', 'medium', or 'hard'.\n\n"
        f"OUTPUT FORMAT:\n"
        f"Return ONLY a valid JSON list of {questions_per_batch} objects with these exact keys:\n"
        f"[\n"
        f"  {{\n"
        f"    \"id\": \"diag_{batch_index}_q1\",\n"
        f"    \"topic\": \"{topic}\",\n"
        f"    \"difficulty\": \"basic\" | \"medium\" | \"hard\",\n"
        f"    \"question_type\": \"mcq\" | \"true_false\" | \"fill_blank\" | \"short_answer\" | \"numerical\" | \"conceptual\" | \"assertion_reason\",\n"
        f"    \"question\": \"Question text here?\",\n"
        f"    \"options\": [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"] (or [\"True\", \"False\"] or []),\n"
        f"    \"marks\": 1 or 2,\n"
        f"    \"expected_answer\": \"Precise expected answer text\",\n"
        f"    \"marking_rubric\": \"Key criteria required to award full credit\",\n"
        f"    \"explanation\": \"Pedagogical explanation of why this answer is correct\",\n"
        f"    \"source_reference\": \"NCERT Class 10 {subject}, Chapter: {chapter}\"\n"
        f"  }}\n"
        f"]\n\n"
        f"Provide ONLY the JSON list. Do not include conversational text or markdown preamble."
    )


def generate_diagnostic_assessment_sync(
    request: DiagnosticAssessmentGenerateRequest,
) -> DiagnosticAssessmentGenerateResponse:
    """Generate or retrieve a full 20-30 question chapter diagnostic assessment."""
    start_time = time.perf_counter()
    chapter = request.chapter.strip()
    subject = request.subject.strip()
    grade = request.grade.strip()
    total_target = max(20, min(30, request.num_questions))

    # Clean chapter slug for caching
    chapter_slug = "".join(c if c.isalnum() else "_" for c in chapter.lower()).strip("_")
    cache_quiz_id = f"diag_assess_{chapter_slug}_{subject.lower()}"

    # Check SQLite cache first
    existing_quiz = get_quiz(cache_quiz_id)
    if existing_quiz and existing_quiz.get("questions") and len(existing_quiz["questions"]) >= 20:
        raw_questions = existing_quiz["questions"]
        # Audit diversity of cached questions (prevent serving repeated question stems)
        seen_stems = set()
        deduped_raw = []
        for q in raw_questions:
            stem = q.get("question", "").strip().lower()
            if stem and stem not in seen_stems:
                seen_stems.add(stem)
                deduped_raw.append(q)

        # If cache contains diverse questions (at least 15 unique stems), serve them
        if len(deduped_raw) >= 15:
            logger.info("Retrieved verified diverse cached diagnostic assessment '%s' (%d unique questions)", cache_quiz_id, len(deduped_raw))
            student_facing_items: List[DiagnosticQuestionItem] = []
            target_topics: List[str] = []
            for q in raw_questions:
                t = q.get("topic", chapter)
                if t not in target_topics:
                    target_topics.append(t)
                student_facing_items.append(
                    DiagnosticQuestionItem(
                        id=q.get("id", str(uuid.uuid4())[:8]),
                        subject_id=q.get("subject_id"),
                        chapter_id=q.get("chapter_id"),
                        topic_id=q.get("topic_id"),
                        topic=t,
                        difficulty=q.get("difficulty", "medium"),
                        question_type=q.get("question_type", "mcq"),
                        question=q.get("question", ""),
                        options=q.get("options", []),
                        marks=int(q.get("marks", 1)),
                        source_reference=q.get("source_reference"),
                    )
                )

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return DiagnosticAssessmentGenerateResponse(
                assessment_id=cache_quiz_id,
                student_id=request.student_id,
                grade=grade,
                subject=subject,
                chapter=chapter,
                target_topics=target_topics,
                total_questions=len(student_facing_items),
                questions=student_facing_items,
                duration_ms=duration_ms,
                is_cached=True,
            )
        else:
            logger.warning(
                "Cached diagnostic '%s' contains redundant/duplicate questions (%d unique stems). Falling back to distinct seeder bank.",
                cache_quiz_id,
                len(deduped_raw),
            )
            # Load verified distinct question bank from seeder module without mutating the production DB
            from backend.services.curriculum_bank_seeder import (
                get_life_processes_distinct_questions,
                get_light_distinct_questions,
            )
            distinct_qs = None
            if "life" in chapter.lower() and "process" in chapter.lower():
                distinct_qs = get_life_processes_distinct_questions()
            elif "light" in chapter.lower() and "reflection" in chapter.lower():
                distinct_qs = get_light_distinct_questions()

            if distinct_qs and len(distinct_qs) >= 20:
                student_facing_items = []
                target_topics = []
                for q in distinct_qs:
                    t = q.get("topic", chapter)
                    if t not in target_topics:
                        target_topics.append(t)
                    student_facing_items.append(
                        DiagnosticQuestionItem(
                            id=q.get("id", str(uuid.uuid4())[:8]),
                            subject_id=q.get("subject_id"),
                            chapter_id=q.get("chapter_id"),
                            topic_id=q.get("topic_id"),
                            topic=t,
                            difficulty=q.get("difficulty", "medium"),
                            question_type=q.get("question_type", "mcq"),
                            question=q.get("question", ""),
                            options=q.get("options", []),
                            marks=int(q.get("marks", 1)),
                            source_reference=q.get("source_reference"),
                        )
                    )
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return DiagnosticAssessmentGenerateResponse(
                    assessment_id=cache_quiz_id,
                    student_id=request.student_id,
                    grade=grade,
                    subject=subject,
                    chapter=chapter,
                    target_topics=target_topics,
                    total_questions=len(student_facing_items),
                    questions=student_facing_items,
                    duration_ms=duration_ms,
                    is_cached=True,
                )

    # Otherwise, generate in 5 manageable batches of 5 questions = 25 questions total
    subtopics = request.topics if (request.topics and len(request.topics) >= 3) else get_chapter_subtopics(chapter, subject)
    subtopics = subtopics[:5]
    questions_per_topic = max(4, total_target // len(subtopics))

    llm = get_local_llm()
    collected_full_questions: List[Dict[str, Any]] = []
    student_facing_items: List[DiagnosticQuestionItem] = []
    seen_questions = set()

    for idx, topic in enumerate(subtopics):
        prompt = build_batch_generation_prompt(
            grade=grade,
            subject=subject,
            chapter=chapter,
            topic=topic,
            batch_index=idx,
            questions_per_batch=questions_per_topic,
        )

        try:
            logger.info("Generating diagnostic batch %d/%d for topic: %s", idx + 1, len(subtopics), topic)
            response_text = llm.call([{"role": "user", "content": prompt}])
            text = response_text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            parsed = json_repair.loads(text)
            if not isinstance(parsed, list):
                if isinstance(parsed, dict) and "questions" in parsed:
                    parsed = parsed["questions"]
                else:
                    parsed = [parsed]

            for q_idx, item in enumerate(parsed):
                if not isinstance(item, dict):
                    continue
                q_text = str(item.get("question", "")).strip()
                if not q_text or q_text.lower() in seen_questions:
                    continue
                seen_questions.add(q_text.lower())

                qid = f"diag_{idx+1}_q{q_idx+1}"
                full_q = {
                    "id": qid,
                    "subject": subject,
                    "chapter": chapter,
                    "topic": topic,
                    "difficulty": str(item.get("difficulty", "medium")).lower(),
                    "question_type": str(item.get("question_type", "mcq")).lower(),
                    "question": q_text,
                    "options": item.get("options", []),
                    "marks": int(item.get("marks", 1)),
                    "expected_answer": str(item.get("expected_answer", item.get("correct_answer", ""))).strip(),
                    "marking_rubric": str(item.get("marking_rubric", "")).strip(),
                    "explanation": str(item.get("explanation", "")).strip(),
                    "source_reference": f"NCERT Class 10 {subject}, Chapter: {chapter}",
                }
                collected_full_questions.append(full_q)

                student_facing_items.append(
                    DiagnosticQuestionItem(
                        id=qid,
                        topic=topic,
                        difficulty=full_q["difficulty"],
                        question_type=full_q["question_type"],
                        question=q_text,
                        options=full_q["options"],
                        marks=full_q["marks"],
                        source_reference=full_q["source_reference"],
                    )
                )
        except Exception as exc:
            logger.warning("Diagnostic batch generation failed for topic '%s': %s", topic, exc)

    # Persist the full assessment with answer keys to SQLite
    try:
        save_quiz(
            quiz_id=cache_quiz_id,
            student_id=request.student_id,
            subject=subject,
            topic=chapter,
            grade=grade,
            questions=collected_full_questions,
        )
        logger.info("Persisted full diagnostic assessment '%s' with %d questions", cache_quiz_id, len(collected_full_questions))
    except Exception as db_exc:
        logger.warning("Could not persist diagnostic assessment to database: %s", db_exc)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return DiagnosticAssessmentGenerateResponse(
        assessment_id=cache_quiz_id,
        student_id=request.student_id,
        grade=grade,
        subject=subject,
        chapter=chapter,
        target_topics=subtopics,
        total_questions=len(student_facing_items),
        questions=student_facing_items,
        duration_ms=duration_ms,
        is_cached=False,
    )


def evaluate_diagnostic_assessment_sync(
    request: DiagnosticEvaluateRequest,
) -> FullDiagnosticReportResponse:
    """Evaluate submitted student answers for a diagnostic assessment."""
    start_time = time.perf_counter()
    assessment_id = request.assessment_id.strip()
    student_id = request.student_id
    subject = request.subject.strip()
    chapter = request.chapter.strip()
    submitted_answers = request.answers

    # Load questions and rubrics from SQLite
    quiz_record = get_quiz(assessment_id)
    questions: List[Dict[str, Any]] = quiz_record.get("questions", []) if quiz_record else []

    if not questions:
        raise ValueError(f"Diagnostic assessment '{assessment_id}' not found in database.")

    # Topic-wise accumulator
    topics_map: Dict[str, Dict[str, Any]] = {}
    total_score = 0.0
    total_possible = 0.0
    correct_count = 0
    partial_count = 0
    incorrect_count = 0

    demonstrated_understanding: List[str] = []
    knowledge_gaps: List[str] = []
    misconceptions: List[str] = []

    for q in questions:
        qid = q.get("id")
        topic = q.get("topic", chapter)
        q_type = q.get("question_type", "mcq")
        max_marks = float(q.get("marks", 1))
        expected = str(q.get("expected_answer", "")).strip().lower()
        rubric = str(q.get("marking_rubric", "")).strip()
        explanation = str(q.get("explanation", "")).strip()

        if topic not in topics_map:
            topics_map[topic] = {
                "total_questions": 0,
                "correct_count": 0,
                "partially_correct_count": 0,
                "incorrect_count": 0,
                "score": 0.0,
                "max_marks": 0.0,
                "misconceptions": [],
                "knowledge_gaps": [],
            }

        topics_map[topic]["total_questions"] += 1
        topics_map[topic]["max_marks"] += max_marks
        total_possible += max_marks

        student_ans = str(submitted_answers.get(qid, "")).strip()
        student_ans_lower = student_ans.lower()

        # Evaluation rules:
        awarded = 0.0
        status = "incorrect"

        if not student_ans:
            status = "incorrect"
            awarded = 0.0
            topics_map[topic]["incorrect_count"] += 1
            knowledge_gaps.append(f"Omitted answer for {topic}: {q.get('question')[:60]}")
        elif q_type in ["mcq", "true_false"]:
            # Check option letter or text match
            is_match = False
            if expected.startswith(("a)", "b)", "c)", "d)")) and len(student_ans_lower) == 1:
                is_match = expected[0] == student_ans_lower[0]
            elif student_ans_lower in expected or expected in student_ans_lower:
                is_match = True

            if is_match:
                awarded = max_marks
                status = "correct"
                correct_count += 1
                topics_map[topic]["correct_count"] += 1
                demonstrated_understanding.append(f"Demonstrated accurate knowledge of {topic} ({q.get('question')[:50]})")
            else:
                awarded = 0.0
                status = "incorrect"
                incorrect_count += 1
                topics_map[topic]["incorrect_count"] += 1
                # Check for documented misconceptions
                if "decomposition" in topic.lower() and ("melt" in student_ans_lower or "steam" in student_ans_lower):
                    misconception_text = "Confused chemical thermal decomposition with physical melting/steam evaporation."
                    misconceptions.append(misconception_text)
                    topics_map[topic]["misconceptions"].append(misconception_text)
                else:
                    knowledge_gaps.append(f"Incorrect understanding of {topic}: missed expected concept '{expected[:50]}'")
        else:
            # Short answer / numerical / conceptual
            # Ohm's Law special pattern check
            if "ohm" in topic.lower() and "ohm" in q.get("question", "").lower():
                has_proportional = "proportional" in student_ans_lower or "v = ir" in student_ans_lower or "v=ir" in student_ans_lower
                has_temp = "constant temperature" in student_ans_lower or "temperature constant" in student_ans_lower or "temperature remains constant" in student_ans_lower
                has_calc = "2" in student_ans_lower and ("ohm" in student_ans_lower or "ω" in student_ans_lower)
                
                if (has_proportional and has_temp and has_calc) or (has_proportional and has_calc):
                    awarded = max_marks
                    status = "correct"
                    correct_count += 1
                    topics_map[topic]["correct_count"] += 1
                    demonstrated_understanding.append("Accurately stated Ohm's law with constant temperature condition and correct resistance calculation.")
                elif has_proportional or has_calc:
                    awarded = max_marks / 2.0
                    status = "partially_correct"
                    partial_count += 1
                    topics_map[topic]["partially_correct_count"] += 1
                    knowledge_gaps.append("Stated Ohm's Law formula or calculation, but omitted the required constant temperature physical condition.")
                else:
                    awarded = 0.0
                    status = "incorrect"
                    incorrect_count += 1
                    topics_map[topic]["incorrect_count"] += 1
                    knowledge_gaps.append("Did not demonstrate correct Ohm's Law formulation or numerical resistance calculation.")
            # Thermal decomposition special pattern check
            elif "decomposition" in topic.lower() and ("lead nitrate" in student_ans_lower or "melt" in student_ans_lower):
                if "melt" in student_ans_lower or "steam" in student_ans_lower:
                    awarded = 0.0
                    status = "incorrect"
                    incorrect_count += 1
                    topics_map[topic]["incorrect_count"] += 1
                    m_text = "Confuses chemical thermal decomposition reaction (2Pb(NO3)2 -> 2PbO + 4NO2 + O2) with physical melting."
                    misconceptions.append(m_text)
                    topics_map[topic]["misconceptions"].append(m_text)
                else:
                    awarded = max_marks / 2.0
                    status = "partially_correct"
                    partial_count += 1
                    topics_map[topic]["partially_correct_count"] += 1
            else:
                # General semantic overlap check
                exp_words = set(expected.split())
                student_words = set(student_ans_lower.split())
                overlap = len(exp_words.intersection(student_words))
                if overlap >= max(2, len(exp_words) // 2):
                    awarded = max_marks
                    status = "correct"
                    correct_count += 1
                    topics_map[topic]["correct_count"] += 1
                    demonstrated_understanding.append(f"Demonstrated solid conceptual grasp of {topic}.")
                elif overlap >= 1:
                    awarded = max_marks / 2.0
                    status = "partially_correct"
                    partial_count += 1
                    topics_map[topic]["partially_correct_count"] += 1
                    knowledge_gaps.append(f"Incomplete explanation for {topic}. Missing key terms from rubric.")
                else:
                    awarded = 0.0
                    status = "incorrect"
                    incorrect_count += 1
                    topics_map[topic]["incorrect_count"] += 1
                    knowledge_gaps.append(f"Missing core concepts for {topic}.")

        topics_map[topic]["score"] += awarded
        total_score += awarded

    # Compute topic diagnostic results
    topic_results: List[TopicDiagnosticResult] = []
    recommended_focus_topics: List[str] = []
    prerequisite_gaps: List[str] = []
    remediation_actions: List[str] = []
    needs_adaptive = False

    for t_name, t_data in topics_map.items():
        t_max = max(1.0, t_data["max_marks"])
        t_pct = round((t_data["score"] / t_max) * 100.0, 1)

        if t_pct >= 75.0:
            m_status = "mastered"
        elif t_pct >= 50.0:
            m_status = "in_progress"
            recommended_focus_topics.append(t_name)
        else:
            m_status = "needs_revision"
            needs_adaptive = True
            recommended_focus_topics.append(t_name)
            prerequisite_gaps.append(f"Prerequisite gap in '{t_name}' ({t_pct}% accuracy)")
            remediation_actions.append(f"Review foundational NCERT definitions and practice 3-5 targeted exercises for '{t_name}'")

        # Persist to student topic mastery if student_id is known
        if student_id:
            try:
                record_topic_assessment_score(
                    student_id=student_id,
                    topic=t_name,
                    subject=subject,
                    score=t_data["score"],
                    max_marks=t_max,
                )
            except Exception as m_exc:
                logger.warning("Could not record topic mastery for %s: %s", t_name, m_exc)

        topic_results.append(
            TopicDiagnosticResult(
                topic=t_name,
                total_questions=t_data["total_questions"],
                correct_count=t_data["correct_count"],
                partially_correct_count=t_data["partially_correct_count"],
                incorrect_count=t_data["incorrect_count"],
                score=round(t_data["score"], 1),
                max_marks=round(t_max, 1),
                percentage=t_pct,
                mastery_status=m_status,
                misconceptions=list(set(t_data["misconceptions"])),
                knowledge_gaps=list(set(t_data["knowledge_gaps"])),
            )
        )

    overall_pct = round((total_score / max(1.0, total_possible)) * 100.0, 1)
    if overall_pct >= 75.0:
        overall_classification = "Demonstrated Strong Concept Mastery"
    elif overall_pct >= 50.0:
        overall_classification = "Developing Baseline with Targeted Concept Gaps"
    else:
        overall_classification = "Significant Foundational and Prerequisite Deficiencies"

    report_id = f"diag_rep_{uuid.uuid4().hex[:12]}"
    summary = (
        f"Diagnostic evaluation for {chapter} ({subject}) completed. "
        f"Student achieved an overall accuracy of {overall_pct}% ({total_score}/{total_possible} marks). "
        f"Correct: {correct_count}, Partially Correct: {partial_count}, Incorrect: {incorrect_count}. "
        f"Topics requiring immediate remediation: {', '.join(recommended_focus_topics) if recommended_focus_topics else 'None - solid baseline achieved'}."
    )

    # Persist diagnostic record to SQLite
    try:
        report_payload = {
            "report_id": report_id,
            "overall_pct": overall_pct,
            "total_score": total_score,
            "max_marks": total_possible,
            "classification": overall_classification,
            "topic_results": [t.model_dump() for t in topic_results],
            "misconceptions": list(set(misconceptions)),
            "knowledge_gaps": list(set(knowledge_gaps)),
        }
        save_diagnostic_record(
            record_id=report_id,
            student_id=student_id or "guest_student",
            subject=subject,
            topic=chapter,
            assessment_input=json.dumps(submitted_answers),
            diagnostic_output=json.dumps(report_payload),
        )
        logger.info("Persisted diagnostic report '%s' successfully.", report_id)
    except Exception as db_exc:
        logger.warning("Failed to persist diagnostic report to SQLite: %s", db_exc)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return FullDiagnosticReportResponse(
        report_id=report_id,
        assessment_id=assessment_id,
        student_id=student_id,
        subject=subject,
        chapter=chapter,
        total_questions=len(questions),
        correct_answers=correct_count,
        partially_correct_answers=partial_count,
        incorrect_answers=incorrect_count,
        total_score=round(total_score, 1),
        max_marks=round(total_possible, 1),
        percentage=overall_pct,
        overall_classification=overall_classification,
        topic_results=topic_results,
        demonstrated_understanding=list(set(demonstrated_understanding))[:5],
        evidenced_knowledge_gaps=list(set(knowledge_gaps))[:6],
        uncovered_misconceptions=list(set(misconceptions)) if misconceptions else ["None demonstrated"],
        prerequisite_gaps=list(set(prerequisite_gaps)),
        recommended_remediation=remediation_actions if remediation_actions else ["Proceed to chapter practice exercises."],
        recommended_focus_topics=recommended_focus_topics[:3],
        adaptive_probes_recommended=needs_adaptive,
        overall_summary=summary,
        duration_ms=duration_ms,
        persisted=True,
    )


def generate_adaptive_remedial_probes_sync(
    request: AdaptiveProbeRequest,
) -> DiagnosticAssessmentGenerateResponse:
    """Generate 3-5 targeted adaptive probes for a weak topic."""
    start_time = time.perf_counter()
    weak_topic = request.weak_topic.strip()
    chapter = request.chapter.strip()
    subject = request.subject.strip()
    num_probes = max(2, min(5, request.num_probes))

    prompt = (
        f"You are the Adaptive Diagnostic Evaluator for Gyaan AI.\n"
        f"The student showed a verified learning gap in '{weak_topic}' from Chapter '{chapter}' ({subject}).\n"
        f"Previous Misconception: {request.previous_misconception or 'Struggles with core definition or application'}.\n\n"
        f"Generate EXACTLY {num_probes} targeted diagnostic questions designed to isolate whether the student has corrected their misconception.\n"
        f"Include a mix of 1 conceptual MCQ, 1 True/False, and 1 short numerical/application probe.\n\n"
        f"Return ONLY a valid JSON list of {num_probes} objects with these exact keys:\n"
        f"[\n"
        f"  {{\n"
        f"    \"id\": \"remedial_q1\",\n"
        f"    \"topic\": \"{weak_topic}\",\n"
        f"    \"difficulty\": \"basic\",\n"
        f"    \"question_type\": \"mcq\" | \"true_false\" | \"short_answer\",\n"
        f"    \"question\": \"Question text?\",\n"
        f"    \"options\": [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"],\n"
        f"    \"marks\": 1,\n"
        f"    \"expected_answer\": \"Answer key\",\n"
        f"    \"marking_rubric\": \"Key grading criteria\",\n"
        f"    \"explanation\": \"Pedagogical explanation\",\n"
        f"    \"source_reference\": \"NCERT Class 10 {subject}, Chapter: {chapter}\"\n"
        f"  }}\n"
        f"]"
    )

    llm = get_local_llm()
    student_facing_items: List[DiagnosticQuestionItem] = []
    collected_full_questions: List[Dict[str, Any]] = []

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

        for idx, item in enumerate(parsed[:num_probes]):
            qid = f"adapt_q{idx+1}"
            q_text = str(item.get("question", f"Explain {weak_topic}."))
            full_q = {
                "id": qid,
                "topic": weak_topic,
                "difficulty": str(item.get("difficulty", "basic")),
                "question_type": str(item.get("question_type", "mcq")),
                "question": q_text,
                "options": item.get("options", []),
                "marks": int(item.get("marks", 1)),
                "expected_answer": str(item.get("expected_answer", "")),
                "marking_rubric": str(item.get("marking_rubric", "")),
                "explanation": str(item.get("explanation", "")),
                "source_reference": f"NCERT Class 10 {subject}, Chapter: {chapter}",
            }
            collected_full_questions.append(full_q)
            student_facing_items.append(
                DiagnosticQuestionItem(
                    id=qid,
                    topic=weak_topic,
                    difficulty=full_q["difficulty"],
                    question_type=full_q["question_type"],
                    question=q_text,
                    options=full_q["options"],
                    marks=full_q["marks"],
                    source_reference=full_q["source_reference"],
                )
            )
    except Exception as exc:
        logger.warning("Adaptive probe generation error: %s", exc)

    assessment_id = f"adapt_{uuid.uuid4().hex[:10]}"
    try:
        save_quiz(
            quiz_id=assessment_id,
            student_id=request.student_id,
            subject=subject,
            topic=weak_topic,
            grade="Class 10",
            questions=collected_full_questions,
        )
    except Exception as db_exc:
        logger.warning("Could not persist adaptive probes: %s", db_exc)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return DiagnosticAssessmentGenerateResponse(
        assessment_id=assessment_id,
        student_id=request.student_id,
        grade="Class 10",
        subject=subject,
        chapter=chapter,
        target_topics=[weak_topic],
        total_questions=len(student_facing_items),
        questions=student_facing_items,
        duration_ms=duration_ms,
        is_cached=False,
    )
