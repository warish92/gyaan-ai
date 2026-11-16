import json

with open("scratch/phase5a_security_audit/security_test_execution_results.json", encoding="utf-8") as f:
    data = json.load(f)

for suite in data:
    print(f"{suite['test_file']}: {suite['passed']} passed, {suite['failed']} failed")
    if suite['failed'] > 0:
        for t in suite['tests']:
            if t['status'] != 'PASSED':
                print(f"   FAILED: {t['test_id']} -> {t['status']}")
