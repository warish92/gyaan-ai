"""Analyze backend/app/main.py for authentication and authorization patterns."""

import re
from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()
main_py = (PROJECT_ROOT / "backend/app/main.py").read_text(encoding="utf-8")

print("=== Endpoint Authentication Audit in backend/app/main.py ===")

# Find all route definitions
pattern = re.compile(r"@app\.(get|post|put|delete|patch)\(\s*([\"'][^\"']+[\"'])(.*?)\n(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\((.*?)\):", re.DOTALL)
routes = list(pattern.finditer(main_py))
print(f"Total endpoints analyzed: {len(routes)}\n")

for r in routes:
    method = r.group(1).upper()
    path = r.group(2).strip("\"'")
    args = r.group(5).replace("\n", " ").strip()
    
    # Check if Depends is used
    has_auth_dep = "get_current_student" in args or "auth" in args.lower() or "token" in args.lower()
    has_student_id_param = "student_id" in path or "student_id" in args
    
    auth_status = "PROTECTED" if has_auth_dep else "PUBLIC / NO AUTH DEPENDENCY"
    print(f"[{method:5}] {path:45} | {auth_status:28} | StudentID in path/args: {has_student_id_param}")
    if has_student_id_param and not has_auth_dep:
        print(f"       >>> Potential IDOR / Unprotected Student Access: {args[:100]}")
