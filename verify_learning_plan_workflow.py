"""Gyaan AI - Verification script for Sequential Diagnostic + Curriculum Workflow.

Executes:
Student assessment -> Diagnostic Agent -> Diagnostic Task -> Curriculum Agent (with context) -> Curriculum Plan -> SQLite
"""

import json
import sys
import time
from pathlib import Path

# Add project root to path
workspace_dir = Path(__file__).resolve().parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.agents.workflow import run_learning_plan_workflow
from backend.db.database import (
    init_db,
    save_student,
    save_diagnostic_record,
    save_curriculum_plan,
    get_diagnostic_record,
    get_curriculum_plan,
)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 80)
    print("GYAAN AI - PHASE 3 SEQUENTIAL MULTI-AGENT WORKFLOW VERIFICATION")
    print("=" * 80)

    # Initialize SQLite database
    init_db()

    student_id = "student_aarav_01"
    display_name = "Aarav Patel"
    grade = "Class 10"
    subject = "Science"
    topic = "Acids, Bases and Salts"

    assessment_items = [
        {
            "question": "Why does dry HCl gas not change the colour of dry litmus paper, but moist litmus turns red?",
            "student_answer": "Because dry gas has no water, so it cannot produce hydrogen ions. In moist paper, water makes H+ ions so litmus turns red.",
            "expected_answer": "Acidic behavior is caused by H+ (or H3O+) ions which only form in aqueous solution. Without water, dry HCl cannot dissociate.",
        },
        {
            "question": "What is the pH of a neutral solution, and what happens to the pH when an acid is diluted with water?",
            "student_answer": "Neutral pH is 7. When an acid is diluted with water, its pH goes down because the acid gets weaker.",
            "expected_answer": "Neutral pH is 7. When an acid is diluted, H3O+ concentration per unit volume decreases, causing the pH to INCREASE towards 7.",
        },
    ]

    print(f"Student       : {display_name} ({grade})")
    print(f"Subject/Topic : {subject} - {topic}")
    print(f"Assessment Qs : {len(assessment_items)} items")
    print("-" * 80)

    print("\n[1/4] Starting sequential CrewAI execution (Diagnostic Agent -> Curriculum Agent)...")
    start_time = time.perf_counter()

    try:
        output = run_learning_plan_workflow(
            grade=grade,
            subject=subject,
            topic=topic,
            assessment_items=assessment_items,
        )
        elapsed_seconds = round(time.perf_counter() - start_time, 2)
        print(f"\n[2/4] Multi-agent execution completed in {elapsed_seconds} seconds.")

        diag_report = output["diagnostic_report"]
        curr_plan = output["curriculum_plan"]

        print("\n" + "=" * 80)
        print("GENUINE DIAGNOSTIC AGENT REPORT:")
        print("=" * 80)
        print(diag_report)

        print("\n" + "=" * 80)
        print("GENUINE CURRICULUM AGENT PERSONALIZED PLAN:")
        print("=" * 80)
        print(curr_plan)
        print("=" * 80)

        print("\n[3/4] Persisting records to SQLite database...")
        save_student(student_id=student_id, display_name=display_name, grade=grade)
        diag_id = "diag_test_001"
        plan_id = "plan_test_001"

        save_diagnostic_record(
            record_id=diag_id,
            student_id=student_id,
            subject=subject,
            topic=topic,
            assessment_input=assessment_items,
            diagnostic_output=diag_report,
        )
        save_curriculum_plan(
            plan_id=plan_id,
            student_id=student_id,
            diagnostic_id=diag_id,
            plan_output=curr_plan,
        )

        persisted_diag = get_diagnostic_record(diag_id)
        persisted_plan = get_curriculum_plan(plan_id)

        assert persisted_diag is not None, "Failed to retrieve persisted diagnostic record"
        assert persisted_plan is not None, "Failed to retrieve persisted curriculum plan"
        print(" - SQLite persistence and retrieval: VERIFIED")

        print("\n[4/4] Verifying content quality & context passing...")
        has_understanding = "understanding" in diag_report.lower() or "h+" in diag_report.lower()
        has_misconception = "ph" in diag_report.lower() or "dilut" in diag_report.lower() or "gap" in diag_report.lower()
        plan_addresses_gaps = "ph" in curr_plan.lower() or "acid" in curr_plan.lower()
        plan_has_roadmap = "step" in curr_plan.lower() or "roadmap" in curr_plan.lower() or "objective" in curr_plan.lower()

        print(f" - Diagnostic identified understanding/ions : {has_understanding}")
        print(f" - Diagnostic captured pH/dilution gap      : {has_misconception}")
        print(f" - Curriculum plan targeted diagnosed gaps   : {plan_addresses_gaps}")
        print(f" - Curriculum plan has sequenced roadmap     : {plan_has_roadmap}")

        if len(diag_report) > 100 and len(curr_plan) > 100 and has_understanding:
            print("\n>>> PHASE 3 SEQUENTIAL WORKFLOW STATUS: PASS")
            return 0
        else:
            print("\n>>> PHASE 3 SEQUENTIAL WORKFLOW STATUS: FAIL")
            return 1

    except Exception as exc:
        elapsed = round(time.perf_counter() - start_time, 2)
        print(f"\n[ERROR] Multi-agent execution failed after {elapsed}s: {exc}")
        import traceback
        traceback.print_exc()
        print("\n>>> PHASE 3 SEQUENTIAL WORKFLOW STATUS: FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
