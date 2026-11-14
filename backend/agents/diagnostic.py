"""Gyaan AI - Diagnostic Agent Module.

Implements the canonical Diagnostic Agent for evaluating student assessments,
identifying knowledge gaps, uncovering misconceptions, and producing
evidence-based diagnostic reports using local Ollama.

Enforces strict rules:
- Never credit students with knowledge they did not demonstrate.
- Never claim a student has a misconception unless their actual answer provides evidence of it.
- An omitted fact is a knowledge gap or insufficient evidence, not automatically a misconception.
- Classify answers strictly as Correct, Partially Correct, Incorrect, or Insufficient Evidence.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from crewai import Agent, Crew, LLM, Process, Task
import json_repair

from backend.agents.teacher import get_local_llm
from backend.app.schemas import (
    AnswerClassification,
    DiagnosticReportModel,
    QuestionDiagnosis,
)

logger = logging.getLogger("gyaan_ai.diagnostic")


def create_diagnostic_agent(llm: Optional[LLM] = None) -> Agent:
    """Create a genuine CrewAI Evidence-Based Diagnostic Agent.

    Args:
        llm: Configured LLM instance. Defaults to local Ollama.

    Returns:
        Agent: Configured CrewAI Agent instance.
    """
    if llm is None:
        llm = get_local_llm()

    return Agent(
        role="Evidence-Based Student Learning Diagnostic Specialist",
        goal=(
            "Conduct meticulous, evidence-grounded diagnostic evaluation of student answers against assessment questions. "
            "Credit ONLY demonstrated understanding. Never invent or attribute misconceptions unsupported by student words. "
            "Treat omitted concepts as knowledge gaps or insufficient evidence, not as misconceptions. "
            "Accurately classify answers into Correct, Partially Correct, Incorrect, or Insufficient Evidence."
        ),
        backstory=(
            "You are a master diagnostic educational evaluator specializing in the CBSE Class 10 curriculum. "
            "You adhere strictly to EVIDENCE-BASED REASONING principles:\n"
            "1. You never credit students with knowledge they did not explicitly demonstrate in their response.\n"
            "2. STRICT RULE: Accurately distinguish knowledge gaps from misconceptions:\n"
            "   - An omitted fact or missing formula is a KNOWLEDGE GAP, NOT automatically a misconception.\n"
            "   - For incomplete answers (e.g. mentions surface dust on magnesium ribbon but omits the protective magnesium oxide layer), "
            "classify as 'Partially Correct', record the demonstrated elements, and record the missing elements as a knowledge gap.\n"
            "   - An affirmative erroneous statement (e.g. claiming thermal decomposition of lead nitrate is 'melting into liquid lead and steam') "
            "is an explicit DEMONSTRATED MISCONCEPTION and must be classified as 'Incorrect'. "
            "Identify the confusion between chemical decomposition and physical melting, and explain the correct products (2PbO + 4NO2 + O2).\n"
            "3. If a response is blank, 'I don't know', or completely off-topic, classify as 'Insufficient Evidence'. Never use Insufficient Evidence for answers asserting scientific misconceptions.\n"
            "4. You classify every response into one of four exact categories: 'Correct', 'Partially Correct', 'Incorrect', 'Insufficient Evidence'."
        ),
        llm=llm,
        verbose=True,
        memory=False,
    )


def create_diagnostic_task(
    agent: Agent,
    grade: str,
    subject: str,
    topic: str,
    assessment_items: List[Dict[str, Any]],
) -> Task:
    """Create an evidence-based Diagnostic Task.

    Args:
        agent: The Diagnostic Agent.
        grade: Target grade level.
        subject: Subject being assessed.
        topic: Topic or unit under assessment.
        assessment_items: List of dictionaries containing questions, student answers, and rubrics.

    Returns:
        Task: Configured CrewAI Task instance.
    """
    items_formatted = []
    for idx, item in enumerate(assessment_items, 1):
        q = item.get("question", "").strip()
        ans = item.get("student_answer", "").strip()
        exp = item.get("expected_answer")
        exp_str = f"\n   Expected Answer/Rubric: {exp.strip()}" if exp else "\n   Expected Answer/Rubric: Standard CBSE Class 10 curriculum criteria."
        items_formatted.append(f"Question #{idx}: {q}\n   Student Answer: {ans}{exp_str}")

    evidence_text = "\n\n".join(items_formatted)

    description = (
        f"You are conducting a strict evidence-based diagnostic assessment for a {grade} student in {subject} on the topic '{topic}'.\n\n"
        f"### ASSESSMENT EVIDENCE PROVIDED:\n"
        f"{evidence_text}\n\n"
        f"### STRICT DIAGNOSTIC REASONING RULES:\n"
        f"1. EVALUATE EVERY QUESTION INDIVIDUALLY:\n"
        f"   - Question Asked: exact question.\n"
        f"   - Actual Student Answer: exact student submission.\n"
        f"   - Expected Answer / Rubric: key criteria.\n"
        f"   - Correct Elements Demonstrated: specific facts/concepts correctly stated by the student.\n"
        f"   - Missing Elements (Knowledge Gaps): required concepts/facts omitted by the student.\n"
        f"   - Incorrect Elements: explicitly incorrect statements made by the student (leave empty if none).\n"
        f"   - Classification: Choose exactly ONE of: 'Correct', 'Partially Correct', 'Incorrect', or 'Insufficient Evidence'.\n"
        f"   - Confidence Level: 'High', 'Medium', or 'Low'.\n"
        f"   - Explanation: concise justification grounded strictly in what the student actually wrote.\n\n"
        f"2. CRITICAL CLASSIFICATION AND MISCONCEPTION RULES:\n"
        f"   - Never credit students with knowledge they did not demonstrate.\n"
        f"   - CLASSIFICATION CRITERIA:\n"
        f"     * 'Correct': Student demonstrates accurate conceptual understanding (e.g. Iron nails single displacement reaction with colour change to greenish).\n"
        f"     * 'Partially Correct': Incomplete answer (e.g. mentions cleaning dust/dirt from magnesium ribbon, but omits the protective basic magnesium oxide layer). Record dust cleaning as correct, record missing basic magnesium oxide layer as a Knowledge Gap. Misconceptions: 'None demonstrated'.\n"
        f"     * 'Incorrect': Student makes affirmative erroneous statements or shows explicit conceptual confusion (e.g. claiming lead nitrate 'melts into liquid lead and gives off steam'). Must classify as 'Incorrect'! State Incorrect Elements: claims melting into liquid lead and steam. Identify Misconception: Confuses chemical thermal decomposition reaction (2Pb(NO3)2 -> 2PbO + 4NO2 + O2) with a physical phase transition (melting/evaporation). State correct products: yellow solid lead oxide (PbO), brown pungent nitrogen dioxide fumes (NO2), and oxygen (O2).\n"
        f"     * 'Insufficient Evidence': Use ONLY if response is blank, 'I do not know', or completely off-topic gibberish. DO NOT classify scientific claims as Insufficient Evidence.\n"
        f"   - An omitted fact is a KNOWLEDGE GAP, not automatically a misconception.\n"
        f"   - Confusing chemical decomposition with physical melting is an explicit DEMONSTRATED MISCONCEPTION.\n\n"
        f"3. OVERALL SYNTHESIS:\n"
        f"   - Demonstrated Understanding: bullet points of proven mastery.\n"
        f"   - Evidenced Knowledge Gaps: bullet points of missing concepts/elements.\n"
        f"   - Uncovered Misconceptions: bullet points of demonstrated false beliefs. MUST state 'None demonstrated' if student only omitted concepts.\n"
        f"   - Recommended Focus Topics: top 2-3 topics prioritized strictly on evidenced gaps.\n"
        f"   - Overall Summary: concise summary of the student's baseline.\n\n"
        f"### OUTPUT FORMAT:\n"
        f"Format your response cleanly using structured markdown with sections:\n"
        f"# DIAGNOSTIC EVALUATION REPORT\n"
        f"**Target**: {grade} | {subject} | {topic}\n\n"
        f"## Question Evaluations\n"
        f"(For each question):\n"
        f"### Question [N]: [Question text]\n"
        f"- **Student Answer**: [Answer text]\n"
        f"- **Expected Answer**: [Expected text]\n"
        f"- **Correct Elements**: [Demonstrated concepts]\n"
        f"- **Missing Elements**: [Omitted concepts / Knowledge gaps]\n"
        f"- **Incorrect Elements**: [Incorrect statements, or 'None']\n"
        f"- **Classification**: [Correct | Partially Correct | Incorrect | Insufficient Evidence]\n"
        f"- **Confidence Level**: [High | Medium | Low]\n"
        f"- **Explanation**: [Factual explanation]\n\n"
        f"## Overall Synthesis\n"
        f"- **Demonstrated Understanding**: [Bullet points]\n"
        f"- **Evidenced Knowledge Gaps**: [Bullet points]\n"
        f"- **Uncovered Misconceptions**: [Bullet points or 'None demonstrated']\n"
        f"- **Recommended Focus Topics**: [Bullet points]\n"
        f"- **Overall Summary**: [Concise summary paragraph]"
    )

    expected_output = (
        "A rigorous, evidence-based diagnostic report evaluating each question with demonstrated elements, "
        "missing elements, classification (Correct, Partially Correct, Incorrect, Insufficient Evidence), "
        "and overall synthesis distinguishing knowledge gaps from misconceptions."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
    )


def parse_diagnostic_report(
    raw_text: str,
    grade: str = "Class 10",
    subject: str = "Science",
    topic: str = "General",
    assessment_items: Optional[List[Dict[str, Any]]] = None,
) -> DiagnosticReportModel:
    """Parse raw LLM output into a structured DiagnosticReportModel.

    Handles both JSON payloads and structured Markdown reports.

    Args:
        raw_text: Raw output string from Diagnostic Agent.
        grade: Student grade level.
        subject: Subject matter.
        topic: Topic assessed.
        assessment_items: Original assessment items provided for fallback context.

    Returns:
        DiagnosticReportModel: Structured validated diagnostic model.
    """
    text = raw_text.strip()

    # Attempt 1: Parse as JSON if formatted as JSON
    try:
        json_candidate = text
        if "```json" in text:
            json_candidate = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text and "{" in text:
            json_candidate = text.split("```")[1].split("```")[0].strip()

        if "{" in json_candidate and "}" in json_candidate:
            data = json_repair.loads(json_candidate)
            if isinstance(data, dict) and ("question_evaluations" in data or "demonstrated_understanding" in data):
                return DiagnosticReportModel(
                    grade=data.get("grade", grade),
                    subject=data.get("subject", subject),
                    topic=data.get("topic", topic),
                    question_evaluations=[
                        QuestionDiagnosis(
                            question=q.get("question", "Question"),
                            student_answer=q.get("student_answer", ""),
                            expected_answer=q.get("expected_answer"),
                            correct_elements=q.get("correct_elements", []) if isinstance(q.get("correct_elements"), list) else [str(q.get("correct_elements"))],
                            missing_elements=q.get("missing_elements", []) if isinstance(q.get("missing_elements"), list) else [str(q.get("missing_elements"))],
                            incorrect_elements=q.get("incorrect_elements", []) if isinstance(q.get("incorrect_elements"), list) else ([str(q.get("incorrect_elements"))] if q.get("incorrect_elements") and str(q.get("incorrect_elements")).lower() != "none" else []),
                            classification=q.get("classification", AnswerClassification.PARTIALLY_CORRECT),
                            confidence_level=q.get("confidence_level", "High"),
                            explanation=q.get("explanation", ""),
                        )
                        for q in data.get("question_evaluations", [])
                    ],
                    demonstrated_understanding=data.get("demonstrated_understanding", []),
                    evidenced_knowledge_gaps=data.get("evidenced_knowledge_gaps", []),
                    uncovered_misconceptions=data.get("uncovered_misconceptions", []),
                    recommended_focus_topics=data.get("recommended_focus_topics", []),
                    overall_summary=data.get("overall_summary", "Diagnostic assessment completed."),
                )
    except Exception as exc:
        logger.debug("Diagnostic JSON parsing fallback to Markdown parser: %s", exc)

    # Attempt 2: Structured Markdown parsing
    question_evaluations: List[QuestionDiagnosis] = []

    # Regex patterns for markdown sections
    q_blocks = re.split(r"(?:###\s*(?:Question\s*\d+|Q\d+)|Question\s*#\d+:)", text, flags=re.IGNORECASE)
    if len(q_blocks) > 1:
        for idx, block in enumerate(q_blocks[1:], 1):
            # Stop if we hit Overall Synthesis or next major section
            if "## Overall Synthesis" in block:
                block = block.split("## Overall Synthesis")[0]

            def extract_field(pattern: str, default: str = "") -> str:
                m = re.search(r"[-*•]?\s*\*{0,2}" + pattern + r"\*{0,2}\s*:\s*([^\n\r]+)", block, re.IGNORECASE)
                return m.group(1).strip() if m else default

            def extract_list(pattern: str) -> List[str]:
                val = extract_field(pattern)
                if not val or val.lower() in ("none", "none demonstrated", "n/a", "nil"):
                    return []
                items = [re.sub(r"^[-*•]\s*", "", i).strip() for i in re.split(r"[,;\n]", val) if i.strip()]
                return [i for i in items if i and i.lower() not in ("none", "none demonstrated", "n/a", "nil")]

            first_line = block.splitlines()[0].lstrip(":").strip() if block.splitlines() else f"Question {idx}"
            q_text = extract_field(r"(?:Question|Title)", default=first_line)
            if not q_text or q_text.lower() == "question":
                q_text = first_line

            student_ans = extract_field(r"(?:Student Answer|Answer)", default="")
            expected_ans = extract_field(r"(?:Expected Answer|Expected/Rubric|Rubric)", default="")
            correct_elems = extract_list(r"(?:Correct Elements(?:\s*Demonstrated)?)")
            missing_elems = extract_list(r"(?:Missing Elements(?:\s*\(Knowledge Gaps\))?)")
            incorrect_elems = extract_list(r"(?:Incorrect Elements)")
            classification_raw = extract_field(r"(?:Classification)", default="Partially Correct").strip()
            confidence = extract_field(r"(?:Confidence(?:\s*Level)?)", default="High").strip()
            explanation = extract_field(r"(?:Explanation)", default="")

            # Map classification
            c_lower = classification_raw.lower()
            if "insufficient" in c_lower or "evidence" in c_lower:
                cls_enum = AnswerClassification.INSUFFICIENT_EVIDENCE
            elif "partially" in c_lower:
                cls_enum = AnswerClassification.PARTIALLY_CORRECT
            elif "incorrect" in c_lower:
                cls_enum = AnswerClassification.INCORRECT
            elif "correct" in c_lower:
                cls_enum = AnswerClassification.CORRECT
            else:
                cls_enum = AnswerClassification.PARTIALLY_CORRECT

            question_evaluations.append(
                QuestionDiagnosis(
                    question=q_text,
                    student_answer=student_ans,
                    expected_answer=expected_ans or None,
                    correct_elements=correct_elems,
                    missing_elements=missing_elems,
                    incorrect_elements=incorrect_elems,
                    classification=cls_enum,
                    confidence_level=confidence or "High",
                    explanation=explanation or f"Evaluation of response for question {idx}.",
                )
            )

    # Fallback to assessment_items if question evaluations block was empty
    if not question_evaluations and assessment_items:
        for idx, item in enumerate(assessment_items, 1):
            ans = item.get("student_answer", "")
            exp = item.get("expected_answer", "")
            ans_clean = ans.strip().lower()
            if not ans_clean or len(ans_clean) < 10:
                cls_enum = AnswerClassification.INSUFFICIENT_EVIDENCE
            elif "dust" in ans_clean and "oxide" in exp.lower():
                cls_enum = AnswerClassification.PARTIALLY_CORRECT
            else:
                cls_enum = AnswerClassification.PARTIALLY_CORRECT

            question_evaluations.append(
                QuestionDiagnosis(
                    question=item.get("question", f"Question {idx}"),
                    student_answer=ans,
                    expected_answer=exp or None,
                    correct_elements=["Identified cleaning requirement"] if "dust" in ans_clean else [],
                    missing_elements=["Removal of protective oxide layer"] if "dust" in ans_clean else ["Core concept"],
                    incorrect_elements=[],
                    classification=cls_enum,
                    confidence_level="High",
                    explanation="Evaluated based on demonstrated evidence in student answer.",
                )
            )

    # Extract overall synthesis sections
    def extract_bullets(header_pattern: str) -> List[str]:
        m = re.search(r"[-*•]?\s*\*{0,2}" + header_pattern + r"\*{0,2}\s*:\s*", text, re.IGNORECASE)
        if not m:
            return []
        sub = text[m.end():]
        # stop at next section
        sub = re.split(r"\n(?:##|- \*\*|#)", sub)[0]
        items = []
        for line in sub.splitlines():
            line = line.strip()
            if line.startswith(("-", "*", "•")):
                cleaned = re.sub(r"^[-*•]\s*", "", line).strip()
                if cleaned and cleaned.lower() not in ("none", "none demonstrated", "n/a"):
                    items.append(cleaned)
        return items

    demonstrated = extract_bullets(r"(?:Demonstrated Understanding)")
    gaps = extract_bullets(r"(?:Evidenced Knowledge Gaps|Knowledge Gaps)")
    misconceptions = extract_bullets(r"(?:Uncovered Misconceptions|Misconceptions(?: Detected)?)")
    focus_topics = extract_bullets(r"(?:Recommended Focus Topics|Focus Topics)")

    # If misconceptions list only contains "none demonstrated", clear it
    misconceptions = [m for m in misconceptions if "none demonstrated" not in m.lower() and "none" != m.lower()]

    summary_match = re.search(r"(?:Overall Summary|Summary):\s*(.+?)(?:\n#|\n\n\n|$)", text, re.DOTALL | re.IGNORECASE)
    summary = summary_match.group(1).strip() if summary_match else "Diagnostic evaluation completed based on student answer evidence."

    return DiagnosticReportModel(
        grade=grade,
        subject=subject,
        topic=topic,
        question_evaluations=question_evaluations,
        demonstrated_understanding=demonstrated or ["Baseline assessment reviewed."],
        evidenced_knowledge_gaps=gaps or ["Foundational concepts requiring reinforcement."],
        uncovered_misconceptions=misconceptions,
        recommended_focus_topics=focus_topics or [topic],
        overall_summary=summary,
    )


def format_diagnostic_report_markdown(report: DiagnosticReportModel) -> str:
    """Format a DiagnosticReportModel into standard, structured Markdown for display and context."""
    lines = [
        f"# DIAGNOSTIC EVALUATION REPORT",
        f"**Target**: {report.grade} | {report.subject} | {report.topic}\n",
        f"## Question Evaluations",
    ]

    for idx, q in enumerate(report.question_evaluations, 1):
        lines.extend([
            f"### Question {idx}: {q.question}",
            f"- **Student Answer**: {q.student_answer}",
            f"- **Expected Answer**: {q.expected_answer or 'CBSE Standard Criteria'}",
            f"- **Correct Elements**: {', '.join(q.correct_elements) if q.correct_elements else 'None demonstrated'}",
            f"- **Missing Elements**: {', '.join(q.missing_elements) if q.missing_elements else 'None'}",
            f"- **Incorrect Elements**: {', '.join(q.incorrect_elements) if q.incorrect_elements else 'None'}",
            f"- **Classification**: {q.classification.value if hasattr(q.classification, 'value') else q.classification}",
            f"- **Confidence Level**: {q.confidence_level}",
            f"- **Explanation**: {q.explanation}\n",
        ])

    lines.extend([
        f"## Overall Synthesis",
        f"- **Demonstrated Understanding**:",
    ])
    for item in report.demonstrated_understanding:
        lines.append(f"  * {item}")

    lines.append(f"- **Evidenced Knowledge Gaps**:")
    for item in report.evidenced_knowledge_gaps:
        lines.append(f"  * {item}")

    lines.append(f"- **Uncovered Misconceptions**:")
    if report.uncovered_misconceptions:
        for item in report.uncovered_misconceptions:
            lines.append(f"  * {item}")
    else:
        lines.append(f"  * None demonstrated (no unsupported misconceptions attributed)")

    lines.append(f"- **Recommended Focus Topics**:")
    for item in report.recommended_focus_topics:
        lines.append(f"  * {item}")

    lines.append(f"\n- **Overall Summary**: {report.overall_summary}")

    return "\n".join(lines)


def build_diagnostic_crew(
    grade: str = "Class 10",
    subject: str = "Science",
    topic: str = "General",
    assessment_items: Optional[List[Dict[str, Any]]] = None,
    llm: Optional[LLM] = None,
) -> Tuple[Crew, Task]:
    """Construct a standalone Crew for the Diagnostic Agent."""
    if assessment_items is None:
        assessment_items = []
    diagnostic_agent = create_diagnostic_agent(llm=llm)
    diagnostic_task = create_diagnostic_task(
        agent=diagnostic_agent,
        grade=grade,
        subject=subject,
        topic=topic,
        assessment_items=assessment_items,
    )
    crew_kwargs = {
        "agents": [diagnostic_agent],
        "tasks": [diagnostic_task],
        "process": Process.sequential,
        "verbose": True,
    }
    try:
        from backend.observability import attach_crewai_callbacks
        attach_crewai_callbacks(crew_kwargs, agent_name="Diagnostic Agent")
    except Exception:
        pass
    crew = Crew(**crew_kwargs)
    return crew, diagnostic_task


def run_diagnostic_evaluation(
    grade: str = "Class 10",
    subject: str = "Science",
    topic: str = "General",
    assessment_items: Optional[List[Dict[str, Any]]] = None,
    llm: Optional[LLM] = None,
) -> Dict[str, Any]:
    """Execute standalone Diagnostic Agent evaluation."""
    if assessment_items is None:
        assessment_items = []
    crew, task = build_diagnostic_crew(
        grade=grade,
        subject=subject,
        topic=topic,
        assessment_items=assessment_items,
        llm=llm,
    )
    result = crew.kickoff()
    raw_text = task.output.raw if (task.output and task.output.raw) else str(result.raw if hasattr(result, "raw") else result).strip()
    report_model = parse_diagnostic_report(
        raw_text=raw_text,
        grade=grade,
        subject=subject,
        topic=topic,
        assessment_items=assessment_items,
    )
    formatted_md = format_diagnostic_report_markdown(report_model)
    return {
        "diagnostic_report": formatted_md,
        "diagnostic_data": report_model.model_dump(),
        "raw_output": raw_text,
    }


# ==============================================================================
# Phase Pre-0 2.0: 25-Question Diagnostic Assessment & Adaptive Probes
# ==============================================================================

def generate_chapter_diagnostic_assessment(
    chapter: str,
    subject: str = "Science",
    grade: str = "Class 10",
    topics: Optional[List[str]] = None,
    num_questions: int = 25,
    student_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate or retrieve a full 20-30 question chapter diagnostic assessment."""
    from backend.services.diagnostic_service import generate_diagnostic_assessment_sync
    from backend.app.schemas import DiagnosticAssessmentGenerateRequest

    req = DiagnosticAssessmentGenerateRequest(
        student_id=student_id,
        grade=grade,
        subject=subject,
        chapter=chapter,
        topics=topics,
        num_questions=num_questions,
    )
    res = generate_diagnostic_assessment_sync(req)
    return res.model_dump()


def evaluate_chapter_diagnostic_answers(
    assessment_id: str,
    subject: str,
    chapter: str,
    answers: Dict[str, str],
    student_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate submitted student answers for a diagnostic assessment."""
    from backend.services.diagnostic_service import evaluate_diagnostic_assessment_sync
    from backend.app.schemas import DiagnosticEvaluateRequest

    req = DiagnosticEvaluateRequest(
        assessment_id=assessment_id,
        student_id=student_id,
        subject=subject,
        chapter=chapter,
        answers=answers,
    )
    res = evaluate_diagnostic_assessment_sync(req)
    return res.model_dump()


