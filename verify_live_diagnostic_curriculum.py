"""Live Ollama Verification of Diagnostic & Curriculum Reasoning Quality.

Runs genuine CrewAI Diagnostic Agent and Curriculum Agent against local Ollama (qwen2.5:3b).
Tests Problem 1 Test Case:
- Question: Why should magnesium ribbon be cleaned before burning?
- Student Answer: To remove dust from its surface.
- Expected Answer: To remove the protective layer of magnesium oxide/basic magnesium carbonate.
"""

import json
import re
import time

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
from backend.app.schemas import AnswerClassification
from crewai import Crew, Process


def main():
    print("=" * 70)
    print("STARTING LIVE DIAGNOSTIC & CURRICULUM QUALITY VERIFICATION (OLLAMA)")
    print("=" * 70)

    # 1. Setup Assessment Item (Problem 1 Test Case)
    assessment_items = [
        {
            "question": "Why should magnesium ribbon be cleaned before burning in air?",
            "student_answer": "To remove dust from its surface.",
            "expected_answer": "To remove the protective layer of basic magnesium oxide/carbonate so that it can react readily with oxygen."
        }
    ]

    # 2. Build Genuine CrewAI Agents
    print("\n[Step 1] Initializing genuine CrewAI Diagnostic & Curriculum Agents...")
    diag_agent = create_diagnostic_agent()
    curr_agent = create_curriculum_agent()

    diag_task = create_diagnostic_task(
        agent=diag_agent,
        grade="Class 10",
        subject="Science",
        topic="Chemical Reactions and Equations",
        assessment_items=assessment_items,
    )

    curr_task = create_curriculum_task(
        agent=curr_agent,
        diagnostic_task=diag_task,
        grade="Class 10",
        subject="Science",
        topic="Chemical Reactions and Equations",
    )

    crew = Crew(
        agents=[diag_agent, curr_agent],
        tasks=[diag_task, curr_task],
        process=Process.sequential,
        verbose=True,
    )

    # 3. Kick off live Crew execution
    print("\n[Step 2] Executing live CrewAI sequential workflow with Ollama (qwen2.5:3b)...")
    start_time = time.perf_counter()
    crew_result = crew.kickoff()
    elapsed = round(time.perf_counter() - start_time, 2)
    print(f"\n[Step 2 Completed] Total Crew kickoff duration: {elapsed}s")

    diag_raw = diag_task.output.raw if (diag_task.output and diag_task.output.raw) else ""
    curr_raw = curr_task.output.raw if (curr_task.output and curr_task.output.raw) else str(crew_result.raw if hasattr(crew_result, "raw") else crew_result)

    print("\n" + "=" * 50)
    print("RAW DIAGNOSTIC AGENT OUTPUT:")
    print("=" * 50)
    print(diag_raw[:1000] + ("..." if len(diag_raw) > 1000 else ""))

    print("\n" + "=" * 50)
    print("RAW CURRICULUM AGENT OUTPUT:")
    print("=" * 50)
    print(curr_raw[:1000] + ("..." if len(curr_raw) > 1000 else ""))

    # 4. Parse into Structured Pydantic Models
    diag_model = parse_diagnostic_report(
        raw_text=diag_raw,
        grade="Class 10",
        subject="Science",
        topic="Chemical Reactions and Equations",
        assessment_items=assessment_items,
    )

    curr_model = parse_curriculum_plan(
        raw_text=curr_raw,
        grade="Class 10",
        subject="Science",
        topic="Chemical Reactions and Equations",
    )

    print("\n" + "=" * 50)
    print("STRUCTURED EVALUATION VERIFICATIONS:")
    print("=" * 50)

    # Verification 1: Classification must NOT be fully Correct
    print(f"Total Question Evaluations: {len(diag_model.question_evaluations)}")
    if diag_model.question_evaluations:
        q_eval = diag_model.question_evaluations[0]
        print(f" - Question: {q_eval.question}")
        print(f" - Student Answer: {q_eval.student_answer}")
        print(f" - Classification: {q_eval.classification}")
        print(f" - Correct Elements: {q_eval.correct_elements}")
        print(f" - Missing Elements: {q_eval.missing_elements}")
        print(f" - Incorrect Elements: {q_eval.incorrect_elements}")
        print(f" - Explanation: {q_eval.explanation}")

        # The student only mentioned dust, not the oxide layer
        is_partially_correct = q_eval.classification in (AnswerClassification.PARTIALLY_CORRECT, AnswerClassification.INSUFFICIENT_EVIDENCE) or "partial" in str(q_eval.classification).lower()
        print(f"\n[Check 1] Correctly classified as Partially Correct / Incomplete: {is_partially_correct}")
        assert is_partially_correct or q_eval.classification != AnswerClassification.CORRECT, "Student must not be marked fully Correct!"

    # Verification 2: Strict Rule - No unevidenced misconceptions
    print(f"\n[Check 2] Uncovered Misconceptions: {diag_model.uncovered_misconceptions}")
    # Student did not claim magnesium ribbon cannot burn, so no wild misconception should be invented
    has_false_misconception = any("cannot burn" in m.lower() for m in diag_model.uncovered_misconceptions)
    print(f"No wild unevidenced misconception attributed: {not has_false_misconception}")
    assert not has_false_misconception, "Violated strict rule: attributed unevidenced misconception!"

    # Verification 3: Curriculum Grounding - No hallucinated textbook exercises
    curr_markdown = format_curriculum_plan_markdown(curr_model)
    has_hallucinated_exercise = bool(re.search(r"Exercise\s*\d+\.\d+", curr_markdown, re.IGNORECASE))
    print(f"\n[Check 3] Hallucinated textbook exercise numbers: {has_hallucinated_exercise} (Must be False)")
    assert not has_hallucinated_exercise, "Curriculum plan hallucinated textbook exercise numbers!"

    # Verification 4: Mastery criterion in curriculum plan
    print(f"[Check 4] Mastery Criterion: {curr_model.mastery_criterion}")
    assert "70%" in curr_model.mastery_criterion, "Curriculum plan must state 70% threshold!"

    # Verification 5: Number of learning stages
    print(f"[Check 5] Number of distinct learning stages: {len(curr_model.learning_stages)}")
    assert len(curr_model.learning_stages) >= 2, "Must generate at least 2 distinct stages!"

    # Save validation metrics to file
    metrics = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_seconds": elapsed,
        "diagnostic": {
            "classification": str(diag_model.question_evaluations[0].classification) if diag_model.question_evaluations else None,
            "correct_elements": diag_model.question_evaluations[0].correct_elements if diag_model.question_evaluations else [],
            "missing_elements": diag_model.question_evaluations[0].missing_elements if diag_model.question_evaluations else [],
            "uncovered_misconceptions": diag_model.uncovered_misconceptions,
        },
        "curriculum": {
            "mastery_criterion": curr_model.mastery_criterion,
            "stages_count": len(curr_model.learning_stages),
            "stages": [s.stage_name for s in curr_model.learning_stages],
            "resource_alignment": curr_model.resource_alignment_status,
        },
        "all_checks_passed": True,
    }
    with open("D:/Gyaan AI/diagnostic_curriculum_live_results.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print("\n" + "=" * 70)
    print("LIVE DIAGNOSTIC & CURRICULUM QUALITY VERIFICATION COMPLETED: ALL PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()
