"""Inspect authentication implementations in sub-routers."""

from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()

files_to_check = [
    "backend/mcp_integration/service.py",
    "backend/adk/api.py",
    "backend/a2a_protocol/server.py",
    "backend/observability/service.py",
]

for fp in files_to_check:
    print(f"\n==================== {fp} ====================")
    text = (PROJECT_ROOT / fp).read_text(encoding="utf-8")
    for line in text.splitlines()[:60]:
        print(line)
