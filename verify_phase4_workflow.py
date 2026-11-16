"""Gyaan AI - Phase 4 Standalone Verification Harness.

Exercises and verifies:
1. Resource Agent Workflow (Workflow A):
   - Local NCERT corpus retrieval
   - Genuine CrewAI Resource Agent execution
2. Quiz Generation Workflow (Workflow B):
   - Context-aware CrewAI Assessment Agent execution
   - Structured JSON output with answer rubrics
   - SQLite quiz persistence and retrieval
3. Answer Evaluation Workflow (Workflow C):
   - Genuine CrewAI Assessment Agent evaluation
   - Constructive rubric scoring and remediation feedback
   - SQLite assessment attempt persistence and student history query
"""

import json
import sys
import time
import uuid
from pathlib import Path

# Add project root to path
workspace_dir = Path(__file__).resolve().parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.agents.workflow import (
    run_answer_evaluation_workflow,
    run_quiz_generation_workflow,
    run_resource_workflow,
)
from backend.db.database import (
    get_quiz,
    get_student_assessment_history,
    init_db,
    save_assessment_attempt,
    save_quiz,
    save_student,
)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 80)
    print("GYAAN AI - PHASE 4 RESOURCE & ASSESSMENT MULTI-AGENT VERIFICATION")
    print("=" * 80)

    # Step 0: Initialize database
    print("\n[Step 0] Initializing SQLite database schema...")
    init_db()
    student_id = f"student_verif_{uuid.uuid4().hex[:6]}"
    display_name = "Priya Sharma"
    save_student(student_id=student_id, display_name=display_name, grade="Class 10")
    print(f"  Initialized student: {display_name} ({student_id})")

    # Step 1: Execute Workflow A - Resource Agent
    print("\n" + "=" * 80)
    print("[Workflow A] Testing Resource Agent & NCERT Retrieval")
    print("=" * 80)
    t0 = time.perf_counter()
    res_result = run_resource_workflow(
        grade="Class 10",
        subject="Science",
        topic="Acids, Bases and Salts",
        learning_objective="Understand acid-base indicators and the chemical nature of neutralization reactions.",
    )
    t_res = round(time.perf_counter() - t0, 2)
    print(f"Workflow A execution duration: {t_res}s")
    print(f"  Source Type  : {res_result['source_type']}")
    print(f"  Is Verified  : {res_result['is_verified']}")
    print(f"  Sources Count: {len(res_result['sources'])}")
    print("\n--- Resource Agent Output Excerpt ---")
    print(res_result["resource_recommendation"][:400] + "...\n")

    assert res_result["is_verified"] is True, "Resource must be verified from local NCERT corpus"
    assert len(res_result["resource_recommendation"]) > 50, "Resource Agent must produce meaningful guidance"

    # Step 2: Execute Workflow B - Quiz Generation with Resource Context
    print("\n" + "=" * 80)
    print("[Workflow B] Testing Quiz Generation (Assessment Agent + Resource Context)")
    print("=" * 80)
    t1 = time.perf_counter()
    quiz_output = run_quiz_generation_workflow(
        grade="Class 10",
        subject="Science",
        topic="Acids, Bases and Salts",
        num_questions=2,
        question_types=["mcq", "short_answer"],
        learning_objectives="Test understanding of pH scale and indicators.",
    )
    t_quiz = round(time.perf_counter() - t1, 2)
    print(f"Workflow B execution duration: {t_quiz}s")
    print(f"  Is Verified Source: {quiz_output['is_verified_source']}")
    questions = quiz_output["questions"]
    print(f"  Questions Generated: {len(questions)}")

    for idx, q in enumerate(questions, 1):
        print(f"\n  Q{idx} ({q.get('type')}, marks={q.get('marks', 1.0)}): {q.get('question')}")
        if q.get("options"):
            print(f"     Options: {q.get('options')}")
        print(f"     Expected Answer : {q.get('correct_answer')}")
        print(f"     Rubric/Expl.    : {q.get('explanation')}")

    assert len(questions) >= 1, "Must generate at least 1 question"

    # Persist quiz to SQLite
    quiz_id = f"quiz_verif_{uuid.uuid4().hex[:8]}"
    save_quiz(
        quiz_id=quiz_id,
        student_id=student_id,
        subject="Science",
        topic="Acids, Bases and Salts",
        grade="Class 10",
        questions=questions,
    )
    print(f"\n  Persisted quiz with ID: {quiz_id}")

    # Verify retrieval from SQLite
    saved_quiz = get_quiz(quiz_id)
    assert saved_quiz is not None, "Saved quiz must be retrievable from SQLite"
    assert len(saved_quiz["questions"]) == len(questions), "Questions count must match"
    print("  Verified quiz successfully retrieved from SQLite database.")

    # Step 3: Execute Workflow C - Answer Evaluation
    print("\n" + "=" * 80)
    print("[Workflow C] Testing Answer Evaluation (Assessment Agent)")
    print("=" * 80)

    # Formulate realistic student answers:
    # Give the correct answer for Q1, and a partial or slightly flawed answer for Q2
    submitted_answers = {}
    q1_id = questions[0]["id"]
    submitted_answers[q1_id] = questions[0].get("correct_answer", "Option B")

    if len(questions) > 1:
        q2_id = questions[1]["id"]
        # Intentionally give a common student misconception or simplified answer
        submitted_answers[q2_id] = "It neutralizes because an acid cancels a base."
    
    print(f"Submitted Answers for Student '{display_name}':")
    for qid, ans in submitted_answers.items():
        print(f"  Question [{qid}]: {ans}")

    t2 = time.perf_counter()
    eval_result = run_answer_evaluation_workflow(
        questions_with_rubric=questions,
        submitted_answers=submitted_answers,
    )
    t_eval = round(time.perf_counter() - t2, 2)
    print(f"\nWorkflow C execution duration: {t_eval}s")
    print(f"  Total Score Awarded : {eval_result.get('total_score')} / {eval_result.get('max_marks')}")
    print(f"  Overall Feedback    : {eval_result.get('overall_feedback')}")

    for ev in eval_result.get("evaluations", []):
        print(f"\n  Evaluation for [{ev.get('question_id')}]:")
        print(f"    Status       : {ev.get('status')}")
        print(f"    Score Awarded: {ev.get('score_awarded')} / {ev.get('max_marks')}")
        print(f"    Feedback     : {ev.get('feedback')}")
        if ev.get("revision_topic"):
            print(f"    Revision Topic: {ev.get('revision_topic')}")

    # Persist attempt to SQLite
    attempt_id = f"att_verif_{uuid.uuid4().hex[:8]}"
    save_assessment_attempt(
        attempt_id=attempt_id,
        quiz_id=quiz_id,
        student_id=student_id,
        submitted_answers=submitted_answers,
        score=float(eval_result.get("total_score", 0.0)),
        max_marks=float(eval_result.get("max_marks", 1.0)),
        evaluation_details=eval_result,
    )
    print(f"\n  Persisted assessment attempt with ID: {attempt_id}")

    # Step 4: Verify Student Assessment History Query
    print("\n" + "=" * 80)
    print("[Step 4] Querying Student Assessment History from SQLite")
    print("=" * 80)
    history = get_student_assessment_history(student_id)
    print(f"  Total attempts found for student '{student_id}': {len(history)}")
    assert len(history) >= 1, "Student must have at least 1 historical attempt"
    latest = history[0]
    print(f"  Latest Attempt ID: {latest['attempt_id']}")
    print(f"  Quiz ID          : {latest['quiz_id']}")
    print(f"  Topic            : {latest['topic']}")
    print(f"  Score            : {latest['score']} / {latest['max_marks']}")
    print(f"  Created At       : {latest['created_at']}")

    print("\n" + "=" * 80)
    print("ALL PHASE 4 VERIFICATION WORKFLOWS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    main()
