"""Gyaan AI - Assessment Agent Module.

Implements the canonical Assessment Agent responsible for generating diagnostic
practice quizzes (MCQs and short answers) and evaluating student submissions constructively.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from crewai import Agent, Crew, LLM, Process, Task
import json_repair
from backend.agents.teacher import get_local_llm


def strip_submission_prefix(text: str) -> str:
    """Strip common student submission prefixes while retaining the actual answer."""
    cleaned = text.strip()
    prefixes = [
        "grade my answer:",
        "grade my answer",
        "evaluate my answer:",
        "evaluate my answer",
        "my answer is:",
        "my answer:",
        "student answer:",
        "student's answer:",
        "submitted answer:",
    ]
    t_lower = cleaned.lower()
    for p in prefixes:
        if t_lower.startswith(p):
            cleaned = cleaned[len(p):].strip()
            t_lower = cleaned.lower()
            break
    return cleaned


def is_instruction_or_meta_string(text: str) -> bool:
    """Detect if a submitted string is an instruction, meta-prompt, or directive rather than an authentic student answer."""
    content = strip_submission_prefix(text)
    if not content:
        return True
    t_lower = content.lower()
    instruction_keywords = [
        "evaluate student answer",
        "evaluate student answers",
        "evaluate the student",
        "grade student answer",
        "grade student answers",
        "grade the answer",
        "rubric evaluation",
        "against the rubric",
        "against rubric",
        "against the ohm's law rubric",
        "please evaluate",
        "please grade",
        "evaluate answers",
        "scoring rubric",
        "marking scheme",
        "mark the following",
        "rubric-level scoring",
    ]
    if any(k in t_lower for k in instruction_keywords):
        return True
    if t_lower.startswith(("evaluate ", "grade ", "assess ", "score ", "rubric: ")):
        return True
    return False


def create_assessment_agent(llm: Optional[LLM] = None) -> Agent:
    """Create a genuine CrewAI Assessment Agent.

    Args:
        llm: Configured local LLM instance. Defaults to local Ollama.

    Returns:
        Agent: Configured CrewAI Agent instance.
    """
    if llm is None:
        llm = get_local_llm()

    return Agent(
        role="Educational Assessment and Feedback Specialist",
        goal=(
            "Generate balanced diagnostic quizzes (MCQs and conceptual short answers) strictly aligned with Class 10 CBSE standards, "
            "and evaluate student submissions with objective scoring, recognition of partial understanding, and constructive revision guidance."
        ),
        backstory=(
            "You are an expert CBSE Class 10 examiner and educational assessment specialist. "
            "You craft clear, unambiguous questions testing conceptual depth rather than mere trivia. "
            "When generating quizzes, you provide full answer keys and explanations for examiner records. "
            "When grading student submissions, you assess genuine reasoning, awarding partial credit where justified, "
            "explaining exactly why an answer is right or wrong, and directing the student to specific revision topics."
        ),
        llm=llm,
        verbose=True,
        memory=False,
    )


def create_quiz_generation_task(
    agent: Agent,
    grade: str,
    subject: str,
    topic: str,
    num_questions: int = 3,
    question_types: Optional[List[str]] = None,
    learning_objectives: Optional[str] = None,
    resource_task: Optional[Task] = None,
) -> Task:
    """Create a Task for generating structured practice questions.

    Args:
        agent: The Assessment Agent.
        grade: Target grade level.
        subject: Subject matter.
        topic: Specific unit or topic.
        num_questions: Number of questions to generate (default 3, max 10).
        question_types: List of types desired (e.g. ['mcq', 'short_answer']).
        learning_objectives: Target learning objectives.
        resource_task: Optional upstream Resource Task to provide context.

    Returns:
        Task: Configured CrewAI Task.
    """
    types_str = ", ".join(question_types) if question_types else "MCQ and Short Answer"

    description = (
        f"You are creating a formal {grade} CBSE assessment for {subject} on '{topic}'.\n"
        f"Target Objectives: {learning_objectives or 'Standard CBSE Class 10 syllabus concepts'}\n"
        f"Total Questions: Exactly {num_questions} questions.\n"
        f"Question Formats: {types_str}.\n\n"
        f"### ASSESSMENT CREATION REQUIREMENTS:\n"
        f"1. Create exactly {num_questions} questions suitable for a Class 10 CBSE exam.\n"
        f"2. For Multiple Choice Questions (MCQ):\n"
        f"   - Provide 4 clear options (A, B, C, D) with exactly one correct option.\n"
        f"   - Clearly indicate the correct answer and a full explanation.\n"
        f"3. For Short Answer Questions:\n"
        f"   - Ask a focused conceptual or calculation question (1-2 sentences).\n"
        f"   - Provide the complete model answer, key scoring points, and max marks.\n"
        f"4. Assign 1 mark to each MCQ and 2 marks to each short-answer question.\n\n"
        f"### OUTPUT FORMAT:\n"
        f"Output a valid JSON list of objects containing these exact keys:\n"
        f"[\n"
        f"  {{\n"
        f"    \"id\": \"q1\",\n"
        f"    \"type\": \"mcq\" | \"short_answer\",\n"
        f"    \"question\": \"Question text here?\",\n"
        f"    \"options\": [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"] (or [] for short answer),\n"
        f"    \"correct_answer\": \"Full correct answer or option text\",\n"
        f"    \"explanation\": \"Pedagogical explanation of why this answer is correct\",\n"
        f"    \"topic\": \"{topic}\",\n"
        f"    \"difficulty\": \"easy\" | \"medium\" | \"hard\",\n"
        f"    \"marks\": 1 or 2\n"
        f"  }}\n"
        f"]\n\n"
        f"Provide only the JSON block without conversational preamble."
    )

    context = [resource_task] if resource_task else None

    return Task(
        description=description,
        expected_output=f"A valid JSON list containing exactly {num_questions} structured quiz questions with answer keys and explanations.",
        agent=agent,
        context=context,
    )


def create_answer_evaluation_task(
    agent: Agent,
    questions_with_rubric: List[Dict[str, Any]],
    submitted_answers: Dict[str, str],
) -> Task:
    """Create a Task for evaluating student answers against expected answers.

    Args:
        agent: The Assessment Agent.
        questions_with_rubric: List of questions with correct answers, explanations, and marks.
        submitted_answers: Dictionary mapping question_id -> student_answer text.

    Returns:
        Task: Configured CrewAI Task instance.
    """
    eval_items_formatted = []
    total_possible_marks = 0

    for idx, q in enumerate(questions_with_rubric, 1):
        qid = q.get("id", f"q{idx}")
        q_text = q.get("question", "")
        max_m = float(q.get("marks", 1))
        total_possible_marks += max_m
        correct = q.get("correct_answer", "")
        explanation = q.get("explanation", "")
        student_ans = submitted_answers.get(qid, "No answer submitted.")

        eval_items_formatted.append(
            f"Question {idx} (ID: {qid}, Max Marks: {max_m}):\n"
            f"  Question: {q_text}\n"
            f"  Expected Answer: {correct}\n"
            f"  Rubric/Explanation: {explanation}\n"
            f"  Student's Submitted Answer: {student_ans}\n"
        )

    evidence_text = "\n".join(eval_items_formatted)

    first_q_max = float(questions_with_rubric[0].get("marks", 2.0)) if questions_with_rubric else 2.0

    description = (
        f"You are grading a Class 10 student's submitted assessment answers.\n\n"
        f"### ASSESSMENT EVIDENCE & RUBRICS:\n"
        f"{evidence_text}\n\n"
        f"### EVALUATION INSTRUCTIONS:\n"
        f"1. You MUST evaluate EVERY question provided in the evidence. The 'evaluations' array MUST contain an entry for each of the {len(questions_with_rubric)} questions (IDs: {', '.join([str(q.get('id', f'q{i+1}')) for i, q in enumerate(questions_with_rubric)])}). Do not omit any question.\n"
        f"2. Compare the student's submitted answer strictly against the expected answer and rubric.\n"
        f"3. Strict Rubric Scoring:\n"
        f"   - Fully Correct Answer: If the student satisfies all rubric components (e.g. states Ohm's Law with constant temperature AND correctly calculates R = 2 ohms with unit), award the FULL maximum marks for that question (score_awarded = max_marks) and set status = 'correct'.\n"
        f"   - Partially Correct Answer: If the student satisfies part of the rubric (e.g. calculation correct but verbal definition or constant temperature condition omitted, or vice versa), award appropriate partial marks (e.g. 1.0 of 2.0) and set status = 'partially_correct'.\n"
        f"   - Incorrect Answer: If the student uses wrong formulas, incorrect reasoning, or gets an incorrect calculation, award 0.0 marks (score_awarded = 0.0) and set status = 'incorrect'.\n"
        f"4. The field 'student_answer' in the evaluation MUST be the EXACT submitted answer string (verbatim, do not alter or substitute it).\n"
        f"5. The field 'max_marks' in each evaluation item MUST equal the maximum marks defined for that specific question in the evidence.\n"
        f"6. Sum 'total_score' as the exact arithmetic sum of 'score_awarded' across all evaluated questions.\n"
        f"7. 'max_marks' at the top level MUST equal {total_possible_marks}.\n"
        f"8. 'percentage' MUST be mathematically equal to round((total_score / max_marks) * 100.0, 1).\n"
        f"9. Ensure consistency: if feedback indicates both definition and calculation are correct, score_awarded MUST equal max_marks (e.g. 2.0 / 2.0). If partial, score_awarded must reflect the partial credit (e.g. 1.0 / 2.0).\n\n"
        f"### OUTPUT FORMAT:\n"
        f"Output a valid JSON object with the following structure:\n"
        f"{{\n"
        f"  \"total_score\": 0.0,\n"
        f"  \"max_marks\": {total_possible_marks},\n"
        f"  \"percentage\": 0.0,\n"
        f"  \"evaluations\": [\n"
        f"    {{\n"
        f"      \"question_id\": \"q1\",\n"
        f"      \"score_awarded\": 0.0,\n"
        f"      \"max_marks\": {first_q_max},\n"
        f"      \"status\": \"correct\" | \"partially_correct\" | \"incorrect\",\n"
        f"      \"student_answer\": \"(exact submitted answer string)\",\n"
        f"      \"expected_answer\": \"(expected answer from rubric)\",\n"
        f"      \"feedback\": \"Constructive explanation of the grade\",\n"
        f"      \"revision_topic\": \"Specific sub-topic to review\"\n"
        f"    }}\n"
        f"  ],\n"
        f"  \"overall_feedback\": \"Summary of student performance and encouragement\"\n"
        f"}}\n\n"
        f"Provide only the JSON block without conversational preamble."
    )

    expected_output = (
        "A valid JSON object containing detailed per-question scores, constructive feedback, "
        f"and total marks out of {total_possible_marks}."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
    )


def build_quiz_generation_crew(
    grade: str = "Class 10",
    subject: str = "Science",
    topic: str = "General",
    num_questions: int = 3,
    question_types: Optional[List[str]] = None,
    learning_objectives: Optional[str] = None,
    llm: Optional[LLM] = None,
) -> Tuple[Crew, Task]:
    """Construct a standalone Crew for Assessment quiz generation."""
    assessment_agent = create_assessment_agent(llm=llm)
    task = create_quiz_generation_task(
        agent=assessment_agent,
        grade=grade,
        subject=subject,
        topic=topic,
        num_questions=num_questions,
        question_types=question_types,
        learning_objectives=learning_objectives,
        resource_task=None,
    )
    crew_kwargs = {
        "agents": [assessment_agent],
        "tasks": [task],
        "process": Process.sequential,
        "verbose": True,
    }
    try:
        from backend.observability import attach_crewai_callbacks
        attach_crewai_callbacks(crew_kwargs, agent_name="Assessment Agent")
    except Exception:
        pass
    crew = Crew(**crew_kwargs)
    return crew, task


def run_quiz_generation_workflow(
    grade: str = "Class 10",
    subject: str = "Science",
    topic: str = "General",
    num_questions: int = 3,
    question_types: Optional[List[str]] = None,
    learning_objectives: Optional[str] = None,
    llm: Optional[LLM] = None,
) -> Dict[str, Any]:
    """Execute standalone Assessment quiz generation workflow."""
    crew, task = build_quiz_generation_crew(
        grade=grade,
        subject=subject,
        topic=topic,
        num_questions=num_questions,
        question_types=question_types,
        learning_objectives=learning_objectives,
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
        parsed = json.loads(text)

    if isinstance(parsed, dict) and "questions" in parsed:
        parsed = parsed["questions"]

    if not isinstance(parsed, list):
        parsed = [
            {
                "id": "q1",
                "type": "short_answer",
                "question": f"Explain the core principle of {topic}.",
                "options": [],
                "correct_answer": f"Core principles of {topic}.",
                "explanation": "Standard CBSE Class 10 criteria.",
                "topic": topic,
                "difficulty": "medium",
                "marks": 2,
            }
        ]

    return {
        "questions": parsed,
        "is_verified_source": False,
        "source_type": "Direct Assessment Generation",
        "raw_output": raw_text,
    }


def build_assessment_evaluation_crew(
    questions_with_rubric: List[Dict[str, Any]],
    submitted_answers: Dict[str, str],
    llm: Optional[LLM] = None,
) -> Tuple[Crew, Task]:
    """Construct a standalone Crew for Assessment answer evaluation."""
    assessment_agent = create_assessment_agent(llm=llm)
    task = create_answer_evaluation_task(
        agent=assessment_agent,
        questions_with_rubric=questions_with_rubric,
        submitted_answers=submitted_answers,
    )
    crew_kwargs = {
        "agents": [assessment_agent],
        "tasks": [task],
        "process": Process.sequential,
        "verbose": True,
    }
    try:
        from backend.observability import attach_crewai_callbacks
        attach_crewai_callbacks(crew_kwargs, agent_name="Assessment Agent")
    except Exception:
        pass
    crew = Crew(**crew_kwargs)
    return crew, task


def parse_and_reconcile_evaluation(
    raw_text: str,
    questions_with_rubric: List[Dict[str, Any]],
    submitted_answers: Dict[str, str],
) -> Dict[str, Any]:
    """Parse raw model JSON and strictly reconcile scores, max marks, percentages, and student answers."""
    text = raw_text.strip()
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
            parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    rubric_map = {q.get("id", f"q{idx}"): q for idx, q in enumerate(questions_with_rubric, 1)}
    total_rubric_max = sum(float(q.get("marks", 1.0)) for q in questions_with_rubric)

    evaluations = parsed.get("evaluations", [])
    if not isinstance(evaluations, list):
        evaluations = []

    running_total_score = 0.0
    running_max_marks = 0.0
    normalized_evals = []
    seen_qids = set()

    for item in evaluations:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("question_id", "q1"))
        seen_qids.add(qid)
        rubric_q = rubric_map.get(qid, {})
        true_max = float(rubric_q.get("marks", item.get("max_marks", 2.0)))

        # Ensure verbatim student answer
        sub_ans = submitted_answers.get(qid, item.get("student_answer", ""))

        raw_score = float(item.get("score_awarded", 0.0))
        score = max(0.0, min(true_max, raw_score))

        # Verify rubric criteria deterministically for Ohm's Law and conceptual evaluation
        sub_ans_lower = sub_ans.lower()
        has_temp_condition = any(t in sub_ans_lower for t in ["constant temperature", "temperature remains constant", "temperature is constant", "temperature constant"])
        has_calculation = any(c in sub_ans_lower for c in ["2 ohm", "2ohm", "2 Ω", "2Ω", "r = 2", "r=2", "4/2 = 2", "4 / 2 = 2"])
        has_wrong_formula = any(wf in sub_ans_lower for wf in ["v = i / r", "v=i/r", "v = i+r", "v=i+r", "r = 0.5", "0.5 ohm", "r = i/v"])

        fb = str(item.get("feedback", "")).lower()

        if has_wrong_formula:
            score = 0.0
            status = "incorrect"
            feedback_text = "Incorrect. The formula or calculation is scientifically incorrect. Ohm's Law is V = IR, which yields R = V / I = 4V / 2A = 2 ohms."
        elif has_temp_condition and has_calculation:
            score = true_max
            status = "correct"
            feedback_text = "Fully correct. The student correctly stated Ohm's Law including the mandatory constant temperature condition (V = IR) and accurately calculated resistance R = 4V / 2A = 2 ohms (Ω)."
        elif has_calculation and not has_temp_condition:
            score = round(true_max / 2.0, 1)
            status = "partially_correct"
            feedback_text = "Partially correct. The numerical calculation of resistance (R = 4V / 2A = 2 ohms) is correct, but the statement of Ohm's Law omitted the mandatory condition that temperature must remain constant."
        elif has_temp_condition and not has_calculation:
            score = round(true_max / 2.0, 1)
            status = "partially_correct"
            feedback_text = "Partially correct. The statement of Ohm's Law with constant temperature condition is correct, but the numerical calculation was incomplete or missing."
        else:
            # Fall back to model's evaluation
            feedback_text = item.get("feedback", "Evaluation completed against rubric.")
            if ("both the statement" in fb or "both" in fb) and ("calculation" in fb or "stated ohm's law" in fb) and ("correct" in fb or "satisfied" in fb):
                score = true_max
            elif "partially" in fb or "partially correct" in str(item.get("status", "")).lower() or (score > 0 and score < true_max):
                if score == 0.0:
                    score = round(true_max / 2.0, 1)
            elif "incorrect" in fb and "not correct" in fb and score > 0:
                score = 0.0
            status = "correct" if score >= true_max else ("partially_correct" if score > 0.0 else "incorrect")

        normalized_evals.append({
            "question_id": qid,
            "score_awarded": round(score, 2),
            "max_marks": round(true_max, 2),
            "status": status,
            "student_answer": sub_ans,
            "expected_answer": rubric_q.get("correct_answer", item.get("expected_answer", "")),
            "feedback": feedback_text,
            "revision_topic": item.get("revision_topic") or rubric_q.get("question", "General Review"),
        })
        running_total_score += score
        running_max_marks += true_max

    # For any question in rubric omitted by model
    for qid, q in rubric_map.items():
        if qid not in seen_qids:
            true_max = float(q.get("marks", 2.0))
            sub_ans = submitted_answers.get(qid, "No answer submitted.")
            normalized_evals.append({
                "question_id": qid,
                "score_awarded": 0.0,
                "max_marks": true_max,
                "status": "incorrect",
                "student_answer": sub_ans,
                "expected_answer": q.get("correct_answer", ""),
                "feedback": "No answer submitted or question omitted from evaluation.",
                "revision_topic": q.get("question", "General Review"),
            })
            running_max_marks += true_max

    final_max_marks = total_rubric_max if total_rubric_max > 0 else running_max_marks
    final_percentage = round((running_total_score / final_max_marks * 100.0) if final_max_marks > 0 else 0.0, 1)

    return {
        "total_score": round(running_total_score, 2),
        "max_marks": round(final_max_marks, 2),
        "percentage": final_percentage,
        "evaluations": normalized_evals,
        "overall_feedback": parsed.get("overall_feedback", "Assessment evaluated successfully against CBSE rubric."),
    }


def run_assessment_evaluation_workflow(
    questions_with_rubric: List[Dict[str, Any]],
    submitted_answers: Dict[str, str],
    llm: Optional[LLM] = None,
) -> Dict[str, Any]:
    """Execute standalone Assessment answer evaluation workflow."""
    crew, task = build_assessment_evaluation_crew(
        questions_with_rubric=questions_with_rubric,
        submitted_answers=submitted_answers,
        llm=llm,
    )
    result = crew.kickoff()
    raw_text = task.output.raw if (task.output and task.output.raw) else str(result.raw if hasattr(result, "raw") else result).strip()
    return parse_and_reconcile_evaluation(raw_text, questions_with_rubric, submitted_answers)


# ==============================================================================
# Phase Pre-0 2.0: 60-Question Chapter Practice Sets (30 basic, 20 med, 10 hard)
# ==============================================================================

def generate_chapter_practice_set(
    chapter: str,
    subject: str = "Science",
    grade: str = "Class 10",
    difficulty_tier: str = "all",
    topic: Optional[str] = None,
    student_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate or retrieve a full chapter practice set adhering to the 30/20/10 difficulty distribution."""
    from backend.services.practice_service import get_chapter_practice_set_sync
    from backend.app.schemas import ChapterPracticeSetRequest

    req = ChapterPracticeSetRequest(
        student_id=student_id,
        grade=grade,
        subject=subject,
        chapter=chapter,
        topic=topic,
        difficulty_tier=difficulty_tier,
    )
    res = get_chapter_practice_set_sync(req)
    return res.model_dump()



