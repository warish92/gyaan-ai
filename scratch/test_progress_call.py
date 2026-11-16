import sys
sys.path.insert(0, ".")
import asyncio
from backend.db.database import get_student_by_id
from backend.agents.progress_workflow import run_progress_analysis_workflow

student_id = "stu_24b4854b69b4"
print("Student:", get_student_by_id(student_id))

try:
    print("Testing run_progress_analysis_workflow for stu_24b4854b69b4...")
    res = run_progress_analysis_workflow(student_id=student_id)
    print("Keys in result:", list(res.keys()))
    print("objective_statistics:", res.get("objective_statistics"))
    print("agent_analysis:", res.get("agent_analysis"))
except Exception as e:
    import traceback
    print("Error:", e)
    traceback.print_exc()
