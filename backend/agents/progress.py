"""Gyaan AI - Canonical Progress Agent Module.

Defines the Progress Agent (Student Learning Progress Analyst) responsible for
analyzing actual persisted learning data, evaluating trends, and identifying
strengths, weaknesses, and unresolved learning priorities.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from crewai import Agent, Crew, LLM, Process, Task
import json_repair

from backend.agents.teacher import LOCAL_MODEL, OLLAMA_BASE_URL


def get_ollama_llm() -> LLM:
    """Return the configured local Ollama LLM instance."""
    return LLM(
        model=LOCAL_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.2,
    )


def create_progress_agent(llm: Optional[LLM] = None) -> Agent:
    """Create a genuine CrewAI Progress Agent.

    Args:
        llm: Optional pre-configured LLM instance. Defaults to local Ollama.

    Returns:
        Agent: Configured CrewAI Agent instance.
    """
    if llm is None:
        llm = get_ollama_llm()

    return Agent(
        role="Student Learning Progress Analyst",
        goal=(
            "Analyse a student's actual persisted learning history and produce an accurate, "
            "evidence-based summary of learning progress, strengths, weaknesses, assessment "
            "performance, and unresolved learning needs."
        ),
        backstory=(
            "You are an expert secondary education learning analyst specializing in CBSE curriculum mastery. "
            "You interpret verified assessment records, topic mastery levels, and study sessions to diagnose "
            "academic progress. You are strictly evidence-based: you never invent missing statistics or "
            "extrapolate trends from insufficient evidence. When data is limited or absent, you state "
            "the exact limitation clearly and recommend foundational diagnostic steps."
        ),
        llm=llm,
        verbose=True,
        memory=False,
        allow_delegation=False,
    )


def create_progress_analysis_task(
    agent: Agent,
    student_profile: Dict[str, Any],
    objective_stats: Dict[str, Any],
    recent_history: Optional[List[Dict[str, Any]]] = None,
) -> Task:
    """Create a genuine CrewAI Task for progress analysis.

    Args:
        agent: The Progress Agent instance.
        student_profile: Student metadata (display_name, grade, preferred_language).
        objective_stats: Calculated deterministic statistics from SQLite.
        recent_history: Optional list of recent assessment attempt summaries.

    Returns:
        Task: Configured CrewAI Task instance.
    """
    display_name = student_profile.get("display_name", "Student")
    grade = student_profile.get("grade", "Class 10")
    language = student_profile.get("preferred_language", "English")

    has_history = objective_stats.get("has_sufficient_history", False)
    total_assessments = objective_stats.get("total_assessments_completed", 0)
    avg_score = objective_stats.get("average_percentage")
    trend = objective_stats.get("performance_trend", "insufficient_evidence")
    trend_desc = objective_stats.get("trend_description", "")
    strengths_raw = objective_stats.get("strengths", [])
    weaknesses_raw = objective_stats.get("areas_needing_improvement", [])
    topics_practice = objective_stats.get("topics_needing_practice", [])
    total_sessions = objective_stats.get("total_learning_sessions", 0)

    recent_scores_formatted = []
    if recent_history:
        for idx, item in enumerate(recent_history[:5], 1):
            recent_scores_formatted.append(
                f"- Attempt {idx}: Topic '{item.get('topic')}', Score: {item.get('score')}/{item.get('max_marks')} ({item.get('percentage')}%)"
            )
    recent_str = "\n".join(recent_scores_formatted) if recent_scores_formatted else "No individual assessment history recorded."

    description = (
        f"You are analyzing the academic progress for student '{display_name}' ({grade}, preferred language: {language}).\n\n"
        f"### OBJECTIVE LEARNING METRICS (From Verified SQLite Database):\n"
        f"- Total Assessments Completed: {total_assessments}\n"
        f"- Average Percentage: {f'{avg_score}%' if avg_score is not None else 'N/A (No assessments completed)'}\n"
        f"- Performance Trend: {trend} ({trend_desc})\n"
        f"- Total Learning Sessions: {total_sessions}\n"
        f"- Verified Topic Strengths: {', '.join(strengths_raw) if strengths_raw else 'None established yet'}\n"
        f"- Areas Needing Improvement: {', '.join(weaknesses_raw) if weaknesses_raw else 'None recorded'}\n"
        f"- Topics Requiring Practice: {', '.join(topics_practice) if topics_practice else 'None recorded'}\n"
        f"- Recent Assessment Scores:\n{recent_str}\n\n"
        f"### ANALYSIS REQUIREMENTS:\n"
        f"1. Interpret the student's progress strictly based on the objective metrics provided above.\n"
        f"2. Explicitly note that assessment history is limited to the tested topic(s) and that other curriculum topics remain unassessed.\n"
        f"3. Highlight demonstrated strengths and detail why specific concepts require remediation.\n"
        f"4. Provide pedagogical meaning to the performance trend.\n"
        f"5. Outline 2-3 specific, priority learning targets.\n\n"
        f"### OUTPUT FORMAT:\n"
        f"Output a valid JSON object with the following exact keys:\n"
        f"{{\n"
        f"  \"overall_summary\": \"Comprehensive pedagogical progress summary...\",\n"
        f"  \"strengths_analysis\": [\"Strength 1 with evidence...\", \"Strength 2...\"],\n"
        f"  \"weaknesses_analysis\": [\"Area needing improvement 1...\", \"Area 2...\"],\n"
        f"  \"topic_observations\": [\n"
        f"    {{\n"
        f"      \"topic\": \"Topic name\",\n"
        f"      \"observation\": \"Specific observation based on scores\",\n"
        f"      \"status\": \"mastered\" | \"in_progress\" | \"needs_revision\"\n"
        f"    }}\n"
        f"  ],\n"
        f"  \"performance_interpretation\": \"Pedagogical explanation of scores and trend\",\n"
        f"  \"data_limitations\": \"Explicitly declare that assessment data is limited to Chemical Reactions and Equations and all other syllabus topics remain unassessed\",\n"
        f"  \"recommended_priorities\": [\"Priority 1\", \"Priority 2\"]\n"
        f"}}\n\n"
        f"Provide only the JSON block without conversational preamble."
    )

    expected_output = (
        "A valid JSON object containing comprehensive progress analysis, strengths, "
        "weaknesses, topic observations, and learning priorities."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
    )


def build_progress_crew(
    student_profile: Dict[str, Any],
    objective_stats: Dict[str, Any],
    recent_history: Optional[List[Dict[str, Any]]] = None,
    llm: Optional[LLM] = None,
) -> Tuple[Crew, Task]:
    """Construct a standalone Crew for the Progress Agent."""
    progress_agent = create_progress_agent(llm=llm)
    task = create_progress_analysis_task(
        agent=progress_agent,
        student_profile=student_profile,
        objective_stats=objective_stats,
        recent_history=recent_history,
    )
    crew_kwargs = {
        "agents": [progress_agent],
        "tasks": [task],
        "process": Process.sequential,
        "verbose": True,
    }
    try:
        from backend.observability import attach_crewai_callbacks
        attach_crewai_callbacks(crew_kwargs, agent_name="Progress Agent")
    except Exception:
        pass
    crew = Crew(**crew_kwargs)
    return crew, task


def run_standalone_progress_analysis(
    student_id: Optional[str] = None,
    student_profile: Optional[Dict[str, Any]] = None,
    objective_stats: Optional[Dict[str, Any]] = None,
    recent_history: Optional[List[Dict[str, Any]]] = None,
    llm: Optional[LLM] = None,
) -> Dict[str, Any]:
    """Execute standalone Progress Agent analysis."""
    if student_profile is None:
        if student_id:
            from backend.db.database import get_student_by_id
            student_profile = get_student_by_id(student_id) or {"id": student_id, "display_name": "Student", "grade": "Class 10"}
        else:
            student_profile = {"display_name": "Student", "grade": "Class 10", "preferred_language": "English"}

    if objective_stats is None:
        if student_id:
            from backend.services.progress_analyzer import calculate_objective_statistics
            objective_stats = calculate_objective_statistics(student_id)
        else:
            objective_stats = {
                "total_assessments_completed": 0,
                "average_percentage": None,
                "performance_trend": "establishing_baseline",
                "trend_description": "Initial diagnostic baseline",
                "strengths": [],
                "areas_needing_improvement": [],
                "topics_needing_practice": [],
                "total_learning_sessions": 0,
                "has_sufficient_history": False,
            }

    if recent_history is None and student_id:
        from backend.db.database import get_student_assessment_history
        recent_history = get_student_assessment_history(student_id)

    crew, task = build_progress_crew(
        student_profile=student_profile,
        objective_stats=objective_stats,
        recent_history=recent_history,
        llm=llm,
    )
    result = crew.kickoff()
    raw_text = task.output.raw if (task.output and task.output.raw) else str(result.raw if hasattr(result, "raw") else result).strip()

    text = raw_text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        parsed = json_repair.loads(text)
    except Exception:
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = {"overall_summary": raw_text}

    if not isinstance(parsed, dict):
        parsed = {"overall_summary": str(parsed)}

    return {
        "student_id": student_id,
        "objective_statistics": objective_stats,
        "progress_report": parsed,
        "raw_output": raw_text,
    }

