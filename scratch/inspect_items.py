import json

with open("live_verification_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print("Keys of item 0:", list(d[0].keys()))
for i, item in enumerate(d):
    print(f"[{i}] {item.get('test_id')}:")
    print("   duration_seconds:", item.get("duration_seconds"))
    print("   execution_duration_seconds:", item.get("execution_duration_seconds"))
    print("   execution_time_seconds:", item.get("execution_time_seconds"))
    print("   quality_criteria_evaluation count:", len(item.get("quality_criteria_evaluation", [])))
    for c in item.get("quality_criteria_evaluation", []):
        print("     - criterion:", c.get("criterion")[:40] if c.get("criterion") else None, "| pass:", c.get("passed"))
