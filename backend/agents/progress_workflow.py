"""Gyaan AI - Progress & Mentoring Multi-Agent Workflow Module.

Orchestrates canonical CrewAI agents:
- Progress Agent (Phase 6): Evaluates verified SQLite history & objective statistics
- Mentor Agent (Phase 6): Translates progress output into actionable recommendations via Task Context
"""

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from crewai import Crew, Process, Task
import json_repair

from backend.agents.mentor import create_mentor_agent, create_mentor_recommendation_task
from backend.agents.progress import create_progress_agent, create_progress_analysis_task
from backend.db.database import (
    create_learning_session,
    get_student_assessment_history,
    get_student_by_id,
)
from backend.services.progress_analyzer import calculate_objective_statistics
from backend.services.resource_retriever import retrieve_local_resources

logger = logging.getLogger("gyaan_ai.progress_workflow")


def clean_json_payload(raw_text: str) -> Any:
    """Extract and parse clean JSON payload from raw LLM completion."""
    text = raw_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json_repair.loads(text)
    except Exception as exc:
        logger.warning("json_repair fallback failed: %s", exc)
        import json
        return json.loads(text)


def build_progress_mentor_crew(
    student_profile: Dict[str, Any],
    objective_stats: Dict[str, Any],
    recent_history: Optional[List[Dict[str, Any]]] = None,
    verified_resources: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Crew, Task, Task]:
    """Construct a sequential 2-agent Crew executing Progress Analysis followed by Mentoring Recommendations.

    Task Context passing:
    progress_task output is injected directly into mentor_task context.
    """
    progress_agent = create_progress_agent()
    mentor_agent = create_mentor_agent()

    progress_task = create_progress_analysis_task(
        agent=progress_agent,
        student_profile=student_profile,
        objective_stats=objective_stats,
        recent_history=recent_history,
    )

    mentor_task = create_mentor_recommendation_task(
        agent=mentor_agent,
        progress_task=progress_task,
        student_profile=student_profile,
        verified_resources=verified_resources,
    )

    crew_kwargs = {
        "agents": [progress_agent, mentor_agent],
        "tasks": [progress_task, mentor_task],
        "process": Process.sequential,
        "verbose": True,
    }
    try:
        from backend.observability import attach_crewai_callbacks
        attach_crewai_callbacks(crew_kwargs, agent_name="ProgressMentorWorkflow")
    except Exception:
        pass
    crew = Crew(**crew_kwargs)

    return crew, progress_task, mentor_task


def run_progress_analysis_workflow(
    student_id: str,
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Execute standalone Progress Agent analysis for a student."""
    student = get_student_by_id(student_id, custom_path=custom_path)
    if not student:
        raise ValueError(f"Student '{student_id}' does not exist.")

    objective_stats = calculate_objective_statistics(student_id, custom_path=custom_path)
    recent_history = get_student_assessment_history(student_id, custom_path=custom_path)

    # Fast-path onboarding for students with zero completed assessments
    if not recent_history or objective_stats.get("total_assessments_completed", 0) == 0:
        logger.info("Student %s has 0 assessment attempts; returning initial baseline progress report.", student_id)
        return {
            "student_id": student_id,
            "objective_statistics": objective_stats,
            "agent_analysis": {
                "overall_summary": f"Welcome to Gyaan AI, {student.get('display_name', 'Student')}! You have not completed any quizzes or diagnostics yet.",
                "strengths_analysis": [],
                "weaknesses_analysis": [],
                "topic_observations": [],
                "performance_interpretation": "No assessment baseline recorded yet.",
                "recommended_priorities": ["Complete your first diagnostic assessment in Practice & Assessments"],
            },
        }

    progress_agent = create_progress_agent()
    progress_task = create_progress_analysis_task(
        agent=progress_agent,
        student_profile=student,
        objective_stats=objective_stats,
        recent_history=recent_history,
    )

    crew_kwargs = {
        "agents": [progress_agent],
        "tasks": [progress_task],
        "process": Process.sequential,
        "verbose": True,
    }
    try:
        from backend.observability import attach_crewai_callbacks
        attach_crewai_callbacks(crew_kwargs, agent_name="Progress Agent")
    except Exception:
        pass
    crew = Crew(**crew_kwargs)

    active_tok = None
    try:
        from backend.observability import set_gyaan_workflow_active
        active_tok = set_gyaan_workflow_active(True)
    except Exception:
        pass

    try:
        logger.info("Executing Progress Agent workflow for student %s", student_id)
        result = crew.kickoff()
    finally:
        if active_tok is not None:
            try:
                from backend.observability import reset_gyaan_workflow_active
                reset_gyaan_workflow_active(active_tok)
            except Exception:
                pass
    raw_output = str(result.raw if hasattr(result, "raw") else result).strip()

    parsed_analysis = clean_json_payload(raw_output)
    if not isinstance(parsed_analysis, dict):
        raise ValueError(f"Expected dict progress report, got: {type(parsed_analysis)}")

    return {
        "student_id": student_id,
        "objective_statistics": objective_stats,
        "agent_analysis": parsed_analysis,
    }


def run_progress_and_mentor_workflow(
    student_id: str,
    custom_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Execute full sequential workflow: Progress Agent -> Mentor Agent (with task context)."""
    student = get_student_by_id(student_id, custom_path=custom_path)
    if not student:
        raise ValueError(f"Student '{student_id}' does not exist.")

    objective_stats = calculate_objective_statistics(student_id, custom_path=custom_path)
    recent_history = get_student_assessment_history(student_id, custom_path=custom_path)

    # Fast-path onboarding for students with zero completed assessments
    if not recent_history or objective_stats.get("total_assessments_completed", 0) == 0:
        logger.info("Student %s has 0 assessment attempts; returning immediate onboarding mentoring guidance.", student_id)
        return {
            "student_id": student_id,
            "duration_seconds": 0.05,
            "objective_statistics": objective_stats,
            "progress_report": {
                "overall_summary": f"Welcome to Gyaan AI, {student.get('display_name', 'Student')}! You have not completed any quizzes or diagnostics yet.",
                "strengths_analysis": [],
                "weaknesses_analysis": [],
                "topic_observations": [],
                "performance_interpretation": "No assessment baseline recorded yet.",
                "recommended_priorities": ["Complete your first diagnostic assessment in Practice & Assessments"],
            },
            "mentor_recommendations": {
                "mentor_overview": (
                    f"Welcome to AI Mentoring, {student.get('display_name', 'Student')}! "
                    "You haven't completed any quizzes or diagnostic assessments yet. "
                    "Take a 5-question quick quiz or a diagnostic test in Practice & Assessments so I can analyze your strengths and provide personalized study recommendations."
                ),
                "recommendations": [
                    {
                        "title": "Complete Diagnostic Assessment",
                        "topic": "Class 10 Curriculum",
                        "reason": "You haven't completed any assessments yet. A baseline diagnostic helps calibrate your personalized learning curve.",
                        "suggested_action": "Take the 25-question Chapter Diagnostic in Science or Mathematics to establish your strengths and growth areas.",
                        "priority": "high",
                        "estimated_minutes": 15,
                        "supporting_evidence": "No assessment records found in student profile.",
                        "resource_reference": "CBSE Class 10 Diagnostic Suite",
                    }
                ],
                "study_tip": "Start by taking a 5-question quick quiz in Practice & Assessments to calibrate your baseline.",
                "next_milestone": "Complete your first Class 10 assessment to unlock personalized recommendations.",
            },
        }

    # Determine topic context for resources (from recent attempts or weaknesses)
    query_topic = "Acids, Bases and Salts"
    if objective_stats.get("areas_needing_improvement"):
        first_weakness = objective_stats["areas_needing_improvement"][0]
        query_topic = first_weakness.split("(")[0].strip()
    elif recent_history:
        query_topic = recent_history[0].get("topic", query_topic)

    retrieved = retrieve_local_resources(
        subject="Science",
        topic=query_topic,
        grade=student.get("grade", "Class 10"),
    )
    verified_resources = retrieved.get("sources", [])

    crew, progress_task, mentor_task = build_progress_mentor_crew(
        student_profile=student,
        objective_stats=objective_stats,
        recent_history=recent_history,
        verified_resources=verified_resources,
    )

    logger.info("Kickoff sequential Progress -> Mentor workflow for student %s", student_id)
    start_time = time.perf_counter()
    active_tok = None
    try:
        from backend.observability import set_gyaan_workflow_active
        active_tok = set_gyaan_workflow_active(True)
    except Exception:
        pass

    try:
        result = crew.kickoff()
    finally:
        if active_tok is not None:
            try:
                from backend.observability import reset_gyaan_workflow_active
                reset_gyaan_workflow_active(active_tok)
            except Exception:
                pass
    elapsed = round(time.perf_counter() - start_time, 2)

    progress_raw = (
        progress_task.output.raw
        if (progress_task.output and progress_task.output.raw)
        else ""
    )
    mentor_raw = (
        mentor_task.output.raw
        if (mentor_task.output and mentor_task.output.raw)
        else str(result.raw if hasattr(result, "raw") else result)
    )

    parsed_progress = clean_json_payload(progress_raw)
    parsed_mentor = clean_json_payload(mentor_raw)

    if not isinstance(parsed_progress, dict):
        parsed_progress = {"overall_summary": str(progress_raw)}
    if not isinstance(parsed_mentor, dict):
        parsed_mentor = {"mentor_overview": str(mentor_raw), "recommendations": []}

    # Record learning session
    try:
        create_learning_session(
            session_id=f"sess_{uuid.uuid4().hex[:12]}",
            student_id=student_id,
            subject="Science",
            topic=query_topic,
            activity_type="revision",
            status="completed",
            details={
                "workflow": "progress_mentor",
                "recommendations_count": len(parsed_mentor.get("recommendations", [])),
                "duration_seconds": elapsed,
            },
            custom_path=custom_path,
        )
    except Exception as exc:
        logger.warning("Failed to record mentoring learning session: %s", exc)

    return {
        "student_id": student_id,
        "duration_seconds": elapsed,
        "objective_statistics": objective_stats,
        "progress_report": parsed_progress,
        "mentor_recommendations": parsed_mentor,
    }
