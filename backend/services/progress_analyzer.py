"""Gyaan AI - Objective Progress Analytics Service.

Calculates deterministic, verified statistical metrics from SQLite learning history
before passing evidence to the Progress Agent. Zero LLM hallucinations for raw math.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.db.database import (
    get_student_assessment_history,
    get_student_curriculum_plans,
    get_student_diagnostic_records,
    get_student_learning_sessions,
    get_student_topic_mastery,
)

logger = logging.getLogger("gyaan_ai.progress_analyzer")


def calculate_objective_statistics(
    student_id: str,
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Calculate objective, evidence-based learning metrics for a student.

    Args:
        student_id: Target student identifier.
        custom_path: Optional SQLite database path.

    Returns:
        Dict[str, Any]: Comprehensive deterministic metrics summary.
    """
    attempts = get_student_assessment_history(student_id, custom_path=custom_path)
    sessions = get_student_learning_sessions(student_id, limit=100, custom_path=custom_path)
    mastery = get_student_topic_mastery(student_id, custom_path=custom_path)
    diagnostics = get_student_diagnostic_records(student_id, limit=50, custom_path=custom_path)
    curricula = get_student_curriculum_plans(student_id, limit=50, custom_path=custom_path)

    # 1. Assessment and Quiz Metrics
    total_assessments_completed = len(attempts)
    unique_quizzes_taken = len({a["quiz_id"] for a in attempts if a.get("quiz_id")})

    total_questions_answered = 0
    correct_count = 0
    partially_correct_count = 0
    incorrect_count = 0

    percentages: List[float] = []
    recent_assessment_scores: List[Dict[str, Any]] = []

    for att in attempts:
        max_marks = float(att.get("max_marks", 0.0))
        score = float(att.get("score", 0.0))

        if max_marks > 0:
            pct = round((score / max_marks) * 100.0, 1)
            percentages.append(pct)
            recent_assessment_scores.append({
                "attempt_id": att.get("attempt_id"),
                "quiz_id": att.get("quiz_id"),
                "subject": att.get("subject"),
                "topic": att.get("topic"),
                "score": score,
                "max_marks": max_marks,
                "percentage": pct,
                "created_at": att.get("created_at"),
            })

        # Parse per-question breakdown if available in evaluation_details
        eval_details = att.get("evaluation_details")
        if isinstance(eval_details, dict):
            for q_eval in eval_details.get("evaluations", []):
                if isinstance(q_eval, dict):
                    total_questions_answered += 1
                    status = str(q_eval.get("status", "")).lower()
                    if status == "correct":
                        correct_count += 1
                    elif status == "partially_correct":
                        partially_correct_count += 1
                    else:
                        incorrect_count += 1

    # 2. Average percentage calculation (handling missing values cleanly)
    if percentages:
        average_percentage = round(sum(percentages) / len(percentages), 1)
    else:
        average_percentage = None

    # 3. Performance Trend Analysis (Strictly requires >= 2 attempts to detect a trend)
    if len(percentages) >= 2:
        # Attempts are returned ordered by created_at DESC:
        # percentages[0] is latest, percentages[-1] is oldest
        recent_pct = percentages[0]
        older_pct = percentages[-1]
        diff = recent_pct - older_pct

        if diff >= 5.0:
            performance_trend = "improving"
            trend_description = f"Performance has improved by +{round(diff, 1)}% from earliest ({older_pct}%) to latest ({recent_pct}%)."
        elif diff <= -5.0:
            performance_trend = "declining"
            trend_description = f"Performance dropped by {round(diff, 1)}% from earliest ({older_pct}%) to latest ({recent_pct}%)."
        else:
            performance_trend = "stable"
            trend_description = f"Performance remains consistent across attempts (latest: {recent_pct}%, baseline: {older_pct}%)."
    else:
        performance_trend = "insufficient_evidence"
        trend_description = (
            "Insufficient assessment evidence (minimum 2 completed assessments required to establish a performance trend)."
        )

    # 4. Topic-Level Strengths & Weaknesses
    strengths: List[str] = []
    areas_needing_improvement: List[str] = []
    topics_needing_practice: List[str] = []

    for m in mastery:
        topic = m.get("topic", "Unknown")
        status = m.get("mastery_status", "")
        pct = float(m.get("percentage", 0.0))

        if status == "mastered" or pct >= 80.0:
            strengths.append(f"{topic} ({pct}%)")
        elif status == "needs_revision" or pct < 60.0:
            areas_needing_improvement.append(f"{topic} ({pct}%)")
            topics_needing_practice.append(topic)
        else:
            # 60 <= pct < 80 (in_progress)
            topics_needing_practice.append(f"{topic} (In Progress, {pct}%)")

    # 5. Learning Sessions Breakdown
    total_learning_sessions = len(sessions)
    completed_sessions_count = sum(1 for s in sessions if s.get("status") == "completed")
    sessions_by_type: Dict[str, int] = {}
    for s in sessions:
        act_type = s.get("activity_type", "other")
        sessions_by_type[act_type] = sessions_by_type.get(act_type, 0) + 1

    # 6. Most Recent Activity Timestamp
    all_timestamps: List[str] = []
    for a in attempts:
        if a.get("created_at"):
            all_timestamps.append(a["created_at"])
    for s in sessions:
        if s.get("started_at"):
            all_timestamps.append(s["started_at"])
    for d in diagnostics:
        if d.get("created_at"):
            all_timestamps.append(d["created_at"])

    most_recent_activity_date = max(all_timestamps) if all_timestamps else None

    has_sufficient_history = (total_assessments_completed >= 1 or total_learning_sessions >= 2)

    return {
        "student_id": student_id,
        "has_sufficient_history": has_sufficient_history,
        "total_assessments_completed": total_assessments_completed,
        "unique_quizzes_taken": unique_quizzes_taken,
        "total_questions_answered": total_questions_answered,
        "correct_answers_count": correct_count,
        "partially_correct_answers_count": partially_correct_count,
        "incorrect_answers_count": incorrect_count,
        "average_percentage": average_percentage,
        "performance_trend": performance_trend,
        "trend_description": trend_description,
        "recent_assessment_scores": recent_assessment_scores[:5],
        "strengths": strengths,
        "areas_needing_improvement": areas_needing_improvement,
        "topics_needing_practice": topics_needing_practice,
        "total_learning_sessions": total_learning_sessions,
        "completed_sessions_count": completed_sessions_count,
        "sessions_by_type": sessions_by_type,
        "diagnostic_records_count": len(diagnostics),
        "curriculum_plans_count": len(curricula),
        "most_recent_activity_date": most_recent_activity_date,
    }


def get_comprehensive_progress_dashboard_sync(
    student_id: str,
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Compile comprehensive multi-tier progress dashboard metrics from verified SQLite data."""
    import time
    start_time = time.perf_counter()

    from backend.db.database import (
        get_student_by_id,
        get_chapters_by_subject,
        get_db_connection,
    )

    student = get_student_by_id(student_id, custom_path=custom_path) or {
        "id": student_id,
        "display_name": "Student",
        "grade": "Class 10",
    }
    student_name = student.get("display_name", "Student")
    grade = student.get("grade", "Class 10")

    stats = calculate_objective_statistics(student_id, custom_path=custom_path)
    mastery_records = get_student_topic_mastery(student_id, custom_path=custom_path)
    attempts = get_student_assessment_history(student_id, custom_path=custom_path)

    # 1. Subject-level breakdown
    subject_map: Dict[str, Dict[str, Any]] = {}
    for att in attempts:
        subj = att.get("subject", "Science")
        if subj not in subject_map:
            subject_map[subj] = {
                "quizzes_taken": 0,
                "scores": [],
                "topics_mastered": 0,
                "topics_in_progress": 0,
                "topics_needing_revision": 0,
            }
        subject_map[subj]["quizzes_taken"] += 1
        max_m = float(att.get("max_marks", 1))
        sc = float(att.get("score", 0))
        if max_m > 0:
            subject_map[subj]["scores"].append((sc / max_m) * 100.0)

    for m in mastery_records:
        subj = m.get("subject", "Science")
        if subj not in subject_map:
            subject_map[subj] = {
                "quizzes_taken": 0,
                "scores": [],
                "topics_mastered": 0,
                "topics_in_progress": 0,
                "topics_needing_revision": 0,
            }
        status = m.get("mastery_status", "")
        if status == "mastered":
            subject_map[subj]["topics_mastered"] += 1
        elif status == "needs_revision":
            subject_map[subj]["topics_needing_revision"] += 1
        else:
            subject_map[subj]["topics_in_progress"] += 1

    subject_progress_items = []
    for s_name, s_data in subject_map.items():
        avg = round(sum(s_data["scores"]) / len(s_data["scores"]), 1) if s_data["scores"] else None
        subject_progress_items.append({
            "subject": s_name,
            "quizzes_taken": s_data["quizzes_taken"],
            "average_score": avg,
            "topics_mastered": s_data["topics_mastered"],
            "topics_in_progress": s_data["topics_in_progress"],
            "topics_needing_revision": s_data["topics_needing_revision"],
        })

    # Default Science subject item if none found
    if not subject_progress_items:
        subject_progress_items.append({
            "subject": "Science",
            "quizzes_taken": 0,
            "average_score": None,
            "topics_mastered": 0,
            "topics_in_progress": 0,
            "topics_needing_revision": 0,
        })

    # 2. Chapter-level completion for Class 10 Science
    science_chapters = get_chapters_by_subject("subj_science_086", custom_path=custom_path)
    attempted_topics = {att.get("topic", "").lower(): float(att.get("score", 0)) / max(1.0, float(att.get("max_marks", 1))) for att in attempts}

    chapter_completion_items = []
    for chap in science_chapters[:13]:
        chap_id = chap.get("id")
        chap_title = chap.get("title", "")
        # Check if attempted
        matched_score = None
        for t_name, sc_ratio in attempted_topics.items():
            if t_name in chap_title.lower() or chap_title.lower() in t_name:
                matched_score = sc_ratio
                break

        if matched_score is not None:
            pct = round(matched_score * 100.0, 1)
            c_status = "completed" if pct >= 70.0 else "in_progress"
            obj_done = 3 if pct >= 70.0 else 1
        else:
            pct = 0.0
            c_status = "not_started"
            obj_done = 0

        chapter_completion_items.append({
            "chapter_id": chap_id,
            "title": chap_title,
            "subject": "Science",
            "status": c_status,
            "mastery_percentage": pct,
            "objectives_completed": obj_done,
            "total_objectives": 4,
        })

    # 3. Topic observations
    topic_obs = []
    for m in mastery_records:
        topic_obs.append({
            "topic": m.get("topic", "Unknown"),
            "observation": f"Scored {m.get('score')}/{m.get('max_marks')} ({m.get('percentage')}%) across attempts.",
            "status": m.get("mastery_status", "in_progress"),
        })

    # 4. Empty state guide
    empty_guide = None
    if stats["total_assessments_completed"] == 0:
        empty_guide = (
            "Welcome to Gyaan AI! You haven't completed any diagnostic assessments or practice quizzes yet. "
            "To build your personalized learning analytics, take a 25-question Diagnostic Assessment in the Diagnostic workspace "
            "or start with a Basic Practice Set in Practice & Assessments."
        )

    # 5. Recommended priorities
    priorities = []
    if stats["areas_needing_improvement"]:
        priorities.append(f"Target revision for {stats['areas_needing_improvement'][0]}")
    if stats["topics_needing_practice"]:
        priorities.append(f"Complete practice set for {stats['topics_needing_practice'][0]}")
    if not priorities:
        priorities.append("Take chapter-level diagnostic assessment to identify your learning baseline.")
        priorities.append("Review NCERT Class 10 textbook concepts with AI Teacher.")

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return {
        "student_id": student_id,
        "student_name": student_name,
        "grade": grade,
        "has_sufficient_history": stats["has_sufficient_history"],
        "overall_accuracy": stats["average_percentage"],
        "total_assessments": stats["total_assessments_completed"],
        "total_questions_answered": stats["total_questions_answered"],
        "performance_trend": stats["performance_trend"],
        "trend_description": stats["trend_description"],
        "subject_progress": subject_progress_items,
        "chapter_completion": chapter_completion_items,
        "topic_mastery": topic_obs,
        "strengths": stats["strengths"],
        "weaknesses": stats["areas_needing_improvement"],
        "recent_attempts": attempts[:10],
        "recommended_priorities": priorities,
        "empty_state_guide": empty_guide,
        "duration_ms": duration_ms,
    }
