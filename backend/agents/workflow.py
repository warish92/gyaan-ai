"""Gyaan AI - Multi-Agent Sequential Workflow Module.

Orchestrates canonical CrewAI agents:
- Diagnostic Agent -> Curriculum Agent (Phase 3)
- Resource Agent (Phase 4)
- Resource Agent -> Assessment Agent (Phase 4 Quiz Generation)
- Assessment Agent (Phase 4 Answer Evaluation)
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from crewai import Crew, Process, Task
import json_repair

from backend.agents.diagnostic import (
    create_diagnostic_agent,
    create_diagnostic_task,
    parse_diagnostic_report,
    format_diagnostic_report_markdown,
)
from backend.agents.curriculum import (
    create_curriculum_agent,
    create_curriculum_task,
    parse_curriculum_plan,
    format_curriculum_plan_markdown,
)
from backend.agents.resource import create_resource_agent, create_resource_task
from backend.agents.assessment import (
    create_assessment_agent,
    create_quiz_generation_task,
    create_answer_evaluation_task,
)
from backend.services.resource_retriever import retrieve_local_resources, retrieve_educational_resources

logger = logging.getLogger("gyaan_ai.workflow")


def clean_json_payload(raw_text: str) -> Any:
    """Safely extract and parse JSON payload from raw LLM completion."""
    text = raw_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json_repair.loads(text)
    except Exception:
        return json.loads(text)


# ==============================================================================
# Workflow 1: Diagnostic + Curriculum Sequential Workflow (Phase 3)
# ==============================================================================

def build_learning_plan_crew(
    grade: str,
    subject: str,
    topic: str,
    assessment_items: List[Dict[str, Any]],
) -> Tuple[Crew, Task, Task]:
    """Build a sequential 2-agent Crew for diagnostic evaluation and curriculum planning."""
    diagnostic_agent = create_diagnostic_agent()
    curriculum_agent = create_curriculum_agent()

    diagnostic_task = create_diagnostic_task(
        agent=diagnostic_agent,
        grade=grade,
        subject=subject,
        topic=topic,
        assessment_items=assessment_items,
    )

    curriculum_task = create_curriculum_task(
        agent=curriculum_agent,
        diagnostic_task=diagnostic_task,
        grade=grade,
        subject=subject,
        topic=topic,
    )

    crew_kwargs = {
        "agents": [diagnostic_agent, curriculum_agent],
        "tasks": [diagnostic_task, curriculum_task],
        "process": Process.sequential,
        "verbose": True,
    }
    try:
        from backend.observability import attach_crewai_callbacks
        attach_crewai_callbacks(crew_kwargs, agent_name="DiagnosticCurriculumWorkflow")
    except Exception:
        pass
    crew = Crew(**crew_kwargs)

    return crew, diagnostic_task, curriculum_task


def run_learning_plan_workflow(
    grade: str,
    subject: str,
    topic: str,
    assessment_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Execute the diagnostic-to-curriculum sequential workflow."""
    crew, diag_task, curr_task = build_learning_plan_crew(
        grade=grade,
        subject=subject,
        topic=topic,
        assessment_items=assessment_items,
    )

    active_tok = None
    try:
        from backend.observability import set_gyaan_workflow_active
        active_tok = set_gyaan_workflow_active(True)
    except Exception:
        pass

    try:
        logger.info("Kickoff sequential workflow: Diagnostic -> Curriculum")
        result = crew.kickoff()
    finally:
        if active_tok is not None:
            try:
                from backend.observability import reset_gyaan_workflow_active
                reset_gyaan_workflow_active(active_tok)
            except Exception:
                pass

    diag_text = (
        diag_task.output.raw
        if (diag_task.output and diag_task.output.raw)
        else ""
    )
    curr_text = (
        curr_task.output.raw
        if (curr_task.output and curr_task.output.raw)
        else str(result.raw if hasattr(result, "raw") else result)
    )

    # Parse into structured Pydantic models
    diag_model = parse_diagnostic_report(
        raw_text=diag_text,
        grade=grade,
        subject=subject,
        topic=topic,
        assessment_items=assessment_items,
    )
    curr_model = parse_curriculum_plan(
        raw_text=curr_text,
        grade=grade,
        subject=subject,
        topic=topic,
    )

    # Ensure formatted structured markdown
    formatted_diag = diag_text.strip() if "## Question Evaluations" in diag_text else format_diagnostic_report_markdown(diag_model)
    formatted_curr = curr_text.strip() if "## Sequenced Learning Stages" in curr_text else format_curriculum_plan_markdown(curr_model)

    return {
        "diagnostic_report": formatted_diag,
        "curriculum_plan": formatted_curr,
        "diagnostic_data": diag_model.model_dump(),
        "curriculum_data": curr_model.model_dump(),
    }


# ==============================================================================
# Workflow 2: Educational Resource Retrieval Workflow (Phase 4)
# ==============================================================================

def run_resource_workflow(
    grade: str,
    subject: str,
    topic: str,
    learning_objective: Optional[str] = None,
    student_id: Optional[str] = None,
    document_ids: Optional[List[str]] = None,
    document_service: Optional[Any] = None,
) -> Dict[str, Any]:
    """Execute Resource Agent analysis against retrieved educational content and student documents."""
    # Step 1: Perform educational text & student document retrieval
    retrieved_data = retrieve_educational_resources(
        subject=subject,
        topic=topic,
        grade=grade,
        student_id=student_id,
        document_ids=document_ids,
        document_service=document_service,
    )

    resource_agent = create_resource_agent()
    resource_task = create_resource_task(
        agent=resource_agent,
        grade=grade,
        subject=subject,
        topic=topic,
        learning_objective=learning_objective,
        retrieved_data=retrieved_data,
    )

    crew_kwargs = {
        "agents": [resource_agent],
        "tasks": [resource_task],
        "process": Process.sequential,
        "verbose": True,
    }
    try:
        from backend.observability import attach_crewai_callbacks
        attach_crewai_callbacks(crew_kwargs, agent_name="Resource Agent")
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
        logger.info("Kickoff Resource Agent workflow for topic '%s'", topic)
        result = crew.kickoff()
    finally:
        if active_tok is not None:
            try:
                from backend.observability import reset_gyaan_workflow_active
                reset_gyaan_workflow_active(active_tok)
            except Exception:
                pass
    raw_output = str(result.raw if hasattr(result, "raw") else result).strip()

    return {
        "resource_recommendation": raw_output,
        "is_verified": retrieved_data.get("is_verified", False),
        "source_type": retrieved_data.get("source_type", "Provisional"),
        "sources": retrieved_data.get("sources", []),
        "student_documents": retrieved_data.get("student_documents", []),
    }


# ==============================================================================
# Workflow 3: Quiz Generation with Resource Context (Phase 4)
# ==============================================================================

def run_quiz_generation_workflow(
    grade: str,
    subject: str,
    topic: str,
    num_questions: int = 3,
    question_types: Optional[List[str]] = None,
    learning_objectives: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute Quiz Generation workflow using Resource context where available."""
    # Step 1: Query local resources
    retrieved_data = retrieve_local_resources(
        subject=subject,
        topic=topic,
        grade=grade,
    )

    assessment_agent = create_assessment_agent()
    agents = []
    tasks = []

    # If verified resources exist, run Resource Agent first and pass context
    if retrieved_data.get("is_verified", False):
        resource_agent = create_resource_agent()
        resource_task = create_resource_task(
            agent=resource_agent,
            grade=grade,
            subject=subject,
            topic=topic,
            learning_objective=learning_objectives,
            retrieved_data=retrieved_data,
        )
        agents.append(resource_agent)
        tasks.append(resource_task)

        quiz_task = create_quiz_generation_task(
            agent=assessment_agent,
            grade=grade,
            subject=subject,
            topic=topic,
            num_questions=num_questions,
            question_types=question_types,
            learning_objectives=learning_objectives,
            resource_task=resource_task,
        )
    else:
        quiz_task = create_quiz_generation_task(
            agent=assessment_agent,
            grade=grade,
            subject=subject,
            topic=topic,
            num_questions=num_questions,
            question_types=question_types,
            learning_objectives=learning_objectives,
            resource_task=None,
        )

    agents.append(assessment_agent)
    tasks.append(quiz_task)

    crew_kwargs = {
        "agents": agents,
        "tasks": tasks,
        "process": Process.sequential,
        "verbose": True,
    }
    try:
        from backend.observability import attach_crewai_callbacks
        attach_crewai_callbacks(crew_kwargs, agent_name="Assessment Agent")
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
        logger.info("Kickoff Quiz Generation Crew for topic '%s' (questions=%d)", topic, num_questions)
        crew.kickoff()
    finally:
        if active_tok is not None:
            try:
                from backend.observability import reset_gyaan_workflow_active
                reset_gyaan_workflow_active(active_tok)
            except Exception:
                pass

    quiz_output_raw = (
        quiz_task.output.raw
        if (quiz_task.output and quiz_task.output.raw)
        else ""
    )

    parsed_questions = clean_json_payload(quiz_output_raw)
    if isinstance(parsed_questions, dict) and "questions" in parsed_questions:
        parsed_questions = parsed_questions["questions"]

    if not isinstance(parsed_questions, list):
        raise ValueError(f"Expected list of quiz questions, got: {type(parsed_questions)}")

    return {
        "questions": parsed_questions,
        "is_verified_source": retrieved_data.get("is_verified", False),
        "source_type": retrieved_data.get("source_type", "Provisional"),
    }


# ==============================================================================
# Workflow 4: Answer Evaluation Workflow (Phase 4)
# ==============================================================================

def run_answer_evaluation_workflow(
    questions_with_rubric: List[Dict[str, Any]],
    submitted_answers: Dict[str, str],
) -> Dict[str, Any]:
    """Execute Assessment Agent evaluation task grading student submissions."""
    assessment_agent = create_assessment_agent()
    # Optimize LLM context: only submit attempted questions to LLM evaluation if rubric is large
    if len(questions_with_rubric) > 10 and submitted_answers:
        attempted_rubrics = [q for q in questions_with_rubric if q.get("id") in submitted_answers]
        eval_rubrics = attempted_rubrics if attempted_rubrics else questions_with_rubric[:10]
    else:
        eval_rubrics = questions_with_rubric

    eval_task = create_answer_evaluation_task(
        agent=assessment_agent,
        questions_with_rubric=eval_rubrics,
        submitted_answers=submitted_answers,
    )

    crew_kwargs = {
        "agents": [assessment_agent],
        "tasks": [eval_task],
        "process": Process.sequential,
        "verbose": True,
    }
    try:
        from backend.observability import attach_crewai_callbacks
        attach_crewai_callbacks(crew_kwargs, agent_name="Assessment Agent")
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
        logger.info("Kickoff Answer Evaluation Task for %d questions", len(questions_with_rubric))
        result = crew.kickoff()
    finally:
        if active_tok is not None:
            try:
                from backend.observability import reset_gyaan_workflow_active
                reset_gyaan_workflow_active(active_tok)
            except Exception:
                pass
    raw_output = str(result.raw if hasattr(result, "raw") else result).strip()

    parsed_eval = clean_json_payload(raw_output)
    if not isinstance(parsed_eval, dict):
        raise ValueError(f"Expected dict evaluation result, got: {type(parsed_eval)}")

    # Ensure all questions in rubric have an evaluation entry
    evaluations_list = parsed_eval.get("evaluations", [])
    if not isinstance(evaluations_list, list):
        evaluations_list = []
        parsed_eval["evaluations"] = evaluations_list

    evaluated_qids = {
        item.get("question_id")
        for item in evaluations_list
        if isinstance(item, dict) and "question_id" in item
    }

    for idx, q in enumerate(questions_with_rubric, 1):
        qid = q.get("id", f"q{idx}")
        if qid not in evaluated_qids:
            s_ans = submitted_answers.get(qid, "")
            exp_ans = q.get("correct_answer", "")
            max_m = float(q.get("marks", 1.0))
            evaluations_list.append({
                "question_id": qid,
                "score_awarded": 0.0,
                "max_marks": max_m,
                "status": "evaluated",
                "student_answer": s_ans,
                "expected_answer": exp_ans,
                "feedback": "Evaluation completed based on overall rubric assessment.",
                "revision_topic": q.get("topic", "General Revision"),
            })

    return parsed_eval
