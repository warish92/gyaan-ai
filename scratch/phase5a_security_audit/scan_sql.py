"""Scan for SQL query patterns across all backend files."""

import re
from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()

for p in PROJECT_ROOT.glob("backend/**/*.py"):
    content = p.read_text(encoding="utf-8", errors="ignore")
    # Search for execute calls
    matches = re.finditer(r"\.execute\s*\(([^;]+?)\)", content, re.DOTALL)
    for m in matches:
        snippet = m.group(1).strip()
        # Check if f-string or % or .format used
        is_formatted = ("f\"" in snippet or "f'" in snippet or "%" in snippet or ".format(" in snippet) and ("SELECT" in snippet.upper() or "INSERT" in snippet.upper() or "UPDATE" in snippet.upper() or "DELETE" in snippet.upper())
        if is_formatted:
            rel = p.relative_to(PROJECT_ROOT).as_posix()
            print(f"[POTENTIAL SQL INJECTION] {rel}:")
            first_line = snippet.splitlines()[0]
            print(f"   {first_line[:120]}")
