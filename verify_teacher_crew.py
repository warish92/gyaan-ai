"""Verification script for CrewAI Teacher Agent with local Ollama LLM.

Executes a real CrewAI workflow consisting of:
Student question -> CrewAI Teacher Agent -> CrewAI Task -> Ollama (qwen2.5:3b) -> Response
"""

import sys
import time
from pathlib import Path

# Ensure backend package is in python search path
workspace_dir = Path(__file__).resolve().parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.agents.crew import build_teacher_crew


def main():
    # Ensure Windows console supports UTF-8 for chemical notation and emojis
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    test_question = (
        "Explain the difference between acids and bases to a Class 10 CBSE student. "
        "Give two examples of each."
    )

    print("=" * 70)
    print("GYAAN AI - CREWAI TEACHER AGENT INTEGRATION TEST")
    print("=" * 70)
    print(f"Target Question : {test_question}")
    print("Configured Model: ollama/qwen2.5:3b via http://127.0.0.1:11434")
    print("Orchestration   : CrewAI Sequential Execution")
    print("-" * 70)

    crew = build_teacher_crew(student_question=test_question)

    print("\n[1/3] Initiating Crew kickoff...")
    start_time = time.perf_counter()

    try:
        result = crew.kickoff()
        elapsed_seconds = round(time.perf_counter() - start_time, 2)
        print(f"\n[2/3] Crew execution completed in {elapsed_seconds} seconds.")

        # Extract answer from CrewOutput
        answer_text = str(result.raw if hasattr(result, "raw") else result).strip()

        print("\n" + "=" * 70)
        print("GENUINE CREWAI TEACHER AGENT ANSWER:")
        print("=" * 70)
        print(answer_text)
        print("=" * 70)

        # Verification checks
        print("\n[3/3] Inspecting execution artifacts & quality...")
        has_content = len(answer_text) > 100
        mentions_acids = "acid" in answer_text.lower()
        mentions_bases = "base" in answer_text.lower()
        has_examples = any(
            ex in answer_text.lower()
            for ex in ["hydrochloric", "citric", "acetic", "sodium hydroxide", "vinegar", "lemon", "hcl", "naoh", "soap", "baking soda"]
        )

        print(f" - Output length: {len(answer_text)} characters")
        print(f" - Content non-empty: {has_content}")
        print(f" - Mentions acids: {mentions_acids}")
        print(f" - Mentions bases: {mentions_bases}")
        print(f" - Contains expected examples: {has_examples}")

        if has_content and mentions_acids and mentions_bases:
            print("\n>>> INTEGRATION TEST STATUS: PASS")
            return 0
        else:
            print("\n>>> INTEGRATION TEST STATUS: FAIL (Incomplete content)")
            return 1

    except Exception as exc:
        elapsed_seconds = round(time.perf_counter() - start_time, 2)
        print(f"\n[ERROR] Crew execution failed after {elapsed_seconds}s: {exc}")
        import traceback
        traceback.print_exc()
        print("\n>>> INTEGRATION TEST STATUS: FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
