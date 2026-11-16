import json

with open("live_verification_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

if isinstance(d, list):
    print(f"Loaded list of {len(d)} items.")
    for item in d:
        if isinstance(item, dict):
            print("Item keys:", list(item.keys())[:6])
            tid = item.get("test_id")
            exec_s = item.get("execution_status")
            qual_s = item.get("output_quality_status")
            dur = item.get("duration_seconds")
            eval_list = item.get("quality_criteria_evaluation", [])
            passed = sum(1 for c in eval_list if c.get("passed"))
            total = len(eval_list)
            print(f"  {tid}: Exec={exec_s}, Quality={qual_s}, Time={dur}s, Criteria={passed}/{total}")
elif isinstance(d, dict):
    print("Loaded dict with keys:", list(d.keys()))
