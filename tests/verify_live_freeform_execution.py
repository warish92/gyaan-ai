"""Live verification script for freeform dynamic routing and multi-agent execution.

Executes genuine requests against local Ollama (qwen2.5:3b):
1. Teacher Inquiry: "Explain the chemical reaction when iron nails are placed in copper sulphate solution."
2. Assessment Inquiry: "Create a 3-question MCQ quiz on Ohm's law."
3. Curriculum Inquiry: "What are the prerequisites for Class 10 Light Reflection and Refraction?"
4. Mentor Inquiry: "Suggest a study timetable for revising Science before the board exams."
"""

import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

QUERIES = [
    {
        "name": "Teacher Inquiry (Displacement Reaction)",
        "question": "Explain the chemical reaction when iron nails are placed in copper sulphate solution.",
        "expected_agent": "Teacher Agent",
        "expected_workflow": "teacher_answer",
    },
    {
        "name": "Assessment Inquiry (Quiz Creation)",
        "question": "Create a 3-question MCQ quiz on Ohm's law.",
        "expected_agent": "Assessment Agent",
        "expected_workflow": "quiz_generation",
    },
    {
        "name": "Curriculum Inquiry (Prerequisites Analysis)",
        "question": "What are the prerequisites for Class 10 Light Reflection and Refraction?",
        "expected_agent": "Curriculum Agent",
        "expected_workflow": "curriculum_inquiry",
    },
    {
        "name": "Mentor Inquiry (Study Timetable)",
        "question": "Suggest a study timetable for revising Science before the board exams.",
        "expected_agent": "Mentor Agent",
        "expected_workflow": "study_guidance",
    },
]

def run_live_verification():
    results = []
    print("=" * 80)
    print("GYAAN AI — LIVE MULTI-AGENT INQUIRY VERIFICATION WITH LOCAL OLLAMA")
    print("=" * 80)

    for item in QUERIES:
        print(f"\n--- Testing: {item['name']} ---")
        print(f"Student Question: \"{item['question']}\"")
        start_time = time.perf_counter()

        response = client.post(
            "/api/v1/ask",
            json={
                "student_id": "live_test_student",
                "question": item["question"],
                "grade": "Class 10",
                "subject": "Science",
            },
        )
        elapsed = round(time.perf_counter() - start_time, 2)
        print(f"Status Code: {response.status_code} (took {elapsed}s)")

        if response.status_code == 200:
            data = response.json()
            agent_name = data.get("agent_name")
            workflow = data.get("workflow_executed")
            intent = data.get("detected_intent")
            answer_preview = (data.get("answer") or "")[:200].replace("\n", " ")

            print(f"Assigned Agent:    {agent_name}")
            print(f"Workflow Executed: {workflow}")
            print(f"Detected Intent:   {intent}")
            print(f"Response Preview:  {answer_preview}...")

            success = (
                item["expected_agent"] in str(agent_name)
                and item["expected_workflow"] == workflow
            )
            print(f"Routing Verification: {'PASS' if success else 'FAIL'}")
            results.append({
                "query": item["question"],
                "expected_agent": item["expected_agent"],
                "actual_agent": agent_name,
                "expected_workflow": item["expected_workflow"],
                "actual_workflow": workflow,
                "detected_intent": intent,
                "elapsed_seconds": elapsed,
                "response_sample": answer_preview,
                "success": success,
            })
        else:
            print(f"ERROR: {response.text}")
            results.append({
                "query": item["question"],
                "error": response.text,
                "success": False,
            })

    print("\n" + "=" * 80)
    print("SUMMARY RESULTS:")
    all_passed = all(r.get("success", False) for r in results)
    for r in results:
        status = "PASS" if r.get("success") else "FAIL"
        print(f"[{status}] {r['query'][:50]} -> Agent: {r.get('actual_agent')} ({r.get('elapsed_seconds')}s)")

    print(f"\nOverall Status: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    print("=" * 80)

    with open("live_verification_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_live_verification()
