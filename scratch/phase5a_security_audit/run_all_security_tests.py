"""
Pytest Security Test Suite Runner for Phase 5A Audit.
Runs individual test files, measures runtime, extracts test names, status, and classification.
"""
import json
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

TEST_SUITES = [
    {
        "file": "tests/test_auth_and_persistence.py",
        "category": "Authentication & Database Access",
        "type": "Unit / Mocked Integration",
        "is_mocked": True,
    },
    {
        "file": "tests/test_database.py",
        "category": "Database Security & Schema Access",
        "type": "Database access tests",
        "is_mocked": True,
    },
    {
        "file": "tests/test_api_unit.py",
        "category": "API Unit & Request Validation",
        "type": "API unit tests",
        "is_mocked": True,
    },
    {
        "file": "tests/test_mcp_integration.py",
        "category": "MCP Security & Tool Access",
        "type": "MCP security tests",
        "is_mocked": True,
    },
    {
        "file": "tests/test_a2a_interoperability.py",
        "category": "A2A Security & Protocol Interoperability",
        "type": "A2A security tests",
        "is_mocked": True,
    },
    {
        "file": "tests/test_adk_foundation.py",
        "category": "Google ADK Foundation & Runner Security",
        "type": "ADK security tests",
        "is_mocked": True,
    },
    {
        "file": "tests/test_observability.py",
        "category": "Observability, Telemetry & Privacy Redaction",
        "type": "Unit / Mocked Integration",
        "is_mocked": True,
    },
]

all_results = []

for suite in TEST_SUITES:
    test_file = suite["file"]
    cmd = [str(PYTHON_EXE), "-m", "pytest", test_file, "-v", "--tb=short"]
    cmd_str = f".venv\\Scripts\\python -m pytest {test_file} -v"
    print(f"\nRunning {cmd_str}...")
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace"
        )
        runtime = round(time.time() - t0, 3)
        stdout = proc.stdout
        exit_code = proc.returncode
    except Exception as e:
        runtime = round(time.time() - t0, 3)
        stdout = str(e)
        exit_code = -1

    # Parse individual tests from pytest -v output
    tests = []
    for line in stdout.splitlines():
        line_s = line.strip()
        if "::" in line_s and any(s in line_s for s in ["PASSED", "FAILED", "SKIPPED", "XFAIL"]):
            parts = line_s.split()
            test_id = parts[0]
            status = "UNKNOWN"
            for p in parts[1:]:
                if p in ["PASSED", "FAILED", "SKIPPED", "XFAIL"]:
                    status = p
                    break
            test_name = test_id.split("::")[-1] if "::" in test_id else test_id
            tests.append({
                "test_id": test_id,
                "test_name": test_name,
                "status": status,
            })

    passed_count = sum(1 for t in tests if t["status"] == "PASSED")
    failed_count = sum(1 for t in tests if t["status"] == "FAILED")
    skipped_count = sum(1 for t in tests if t["status"] == "SKIPPED")

    suite_result = {
        "test_file": test_file,
        "exact_command": cmd_str,
        "category": suite["category"],
        "classification": suite["type"],
        "is_mocked": suite["is_mocked"],
        "exit_code": exit_code,
        "runtime_seconds": runtime,
        "total_tests": len(tests),
        "passed": passed_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "tests": tests,
        "summary_line": [l for l in stdout.splitlines() if "passed" in l or "failed" in l][-1:]
    }
    all_results.append(suite_result)
    print(f"Finished {test_file}: {passed_count} passed, {failed_count} failed in {runtime}s (exit {exit_code})")

# Write out full results
out_file = PROJECT_ROOT / "scratch/phase5a_security_audit/security_test_execution_results.json"
out_file.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
print(f"\nAll security test execution results saved to: {out_file}")
