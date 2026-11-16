import json

with open("live_verification_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

for i, item in enumerate(d):
    tid = item.get("test_id")
    exec_s = item.get("execution_status")
    qual_s = item.get("output_quality_status")
    dur = item.get("execution_duration_seconds")
    eval_list = item.get("quality_criteria_evaluation", [])
    verified_count = sum(1 for c in eval_list if c.get("status") == "VERIFIED")
    partial_count = sum(1 for c in eval_list if c.get("status") == "PARTIALLY_VERIFIED")
    failed_count = sum(1 for c in eval_list if c.get("status") == "FAILED")
    total = len(eval_list)
    print(f"{tid:25} | Exec: {exec_s:24} | Qual: {qual_s:18} | Time: {dur:5.2f}s | Criteria: {verified_count}/{total} V, {partial_count} P, {failed_count} F")
    for c in eval_list:
        if c.get("status") != "VERIFIED":
            print(f"     -> [{c.get('status')}] {c.get('criterion')}: {c.get('evidence')}")
