import sys
sys.path.insert(0, ".")
from backend.agents.assessment import run_quiz_generation_workflow

try:
    print("Testing run_quiz_generation_workflow for Acids, Bases and Salts...")
    res = run_quiz_generation_workflow(
        grade="Class 10",
        subject="Science",
        topic="Acids, Bases and Salts",
        num_questions=3,
        question_types=["mcq", "short_answer"],
    )
    print("Workflow output keys:", list(res.keys()))
    print("Questions count:", len(res.get("questions", [])))
    for q in res.get("questions", []):
        print("  - Q:", q.get("id"), q.get("type"), q.get("question")[:50])
except Exception as e:
    import traceback
    print("Failed quiz generation:", e)
    traceback.print_exc()
