import sys
sys.path.insert(0, ".")
from backend.db.database import save_student, get_student_by_id
from backend.services.progress_analyzer import calculate_objective_statistics
from backend.agents.progress_workflow import run_progress_analysis_workflow

test_new_student_id = "stu_test_empty_001"
save_student(test_new_student_id, display_name="New Student", grade="Class 10")

print("New student saved:", get_student_by_id(test_new_student_id))
stats = calculate_objective_statistics(test_new_student_id)
print("Stats for empty student:", stats)

try:
    res = run_progress_analysis_workflow(student_id=test_new_student_id)
    print("Success with empty student! Keys:", list(res.keys()))
    print("Analysis:", res.get("agent_analysis"))
except Exception as e:
    import traceback
    print("Failed with empty student:", e)
    traceback.print_exc()
