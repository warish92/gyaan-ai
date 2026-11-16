import json

with open("scratch/phase5a_security_audit/security_test_execution_results.json", encoding="utf-8") as f:
    suites = json.load(f)

total_tests = 0
total_passed = 0
total_failed = 0
total_skipped = 0

print("=== TEST SUITE BREAKDOWN FROM security_test_execution_results.json ===")
for s in suites:
    file_name = s["test_file"]
    print(f"\nSuite: {file_name}")
    print(f"  Suite metadata: total={s['total_tests']}, passed={s['passed']}, failed={s['failed']}, skipped={s['skipped']}")
    t_list = s["tests"]
    p_c = sum(1 for t in t_list if t["status"] == "PASSED")
    f_c = sum(1 for t in t_list if t["status"] == "FAILED")
    s_c = sum(1 for t in t_list if t["status"] == "SKIPPED")
    u_c = sum(1 for t in t_list if t["status"] not in ["PASSED", "FAILED", "SKIPPED"])
    print(f"  Tests list len={len(t_list)}: passed={p_c}, failed={f_c}, skipped={s_c}, other={u_c}")
    for t in t_list:
        if t["status"] != "PASSED":
            print(f"    Non-passed item: {t}")
    print(f"  Summary line: {s.get('summary_line')}")
    total_tests += len(t_list)
    total_passed += p_c
    total_failed += f_c
    total_skipped += s_c

print("\n=== TOTALS ===")
print(f"Total entries: {total_tests}, Passed: {total_passed}, Failed: {total_failed}, Skipped: {total_skipped}")
