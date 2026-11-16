import os
import shutil
import sqlite3
import time
from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()

# 1. Database check
db_path = PROJECT_ROOT / "data/gyaan_ai.db"
bak_path = PROJECT_ROOT / "data/gyaan_ai.db.bak_phase4"

conn = sqlite3.connect(str(db_path))
cur = conn.cursor()
db_integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
db_tables = len(cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
db_students = cur.execute("SELECT count(*) FROM students").fetchone()[0]
db_sessions = cur.execute("SELECT count(*) FROM student_sessions").fetchone()[0]
conn.close()

conn = sqlite3.connect(str(bak_path))
cur = conn.cursor()
bak_integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
bak_tables = len(cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
bak_students = cur.execute("SELECT count(*) FROM students").fetchone()[0]
bak_sessions = cur.execute("SELECT count(*) FROM student_sessions").fetchone()[0]
conn.close()

print(f"Active DB: integrity={db_integrity}, tables={db_tables}, students={db_students}, sessions={db_sessions}")
print(f"Backup DB: integrity={bak_integrity}, tables={bak_tables}, students={bak_students}, sessions={bak_sessions}, size={bak_path.stat().st_size}")

# 2. Identify files that may be modified in Phase 5B
target_files = [
    # Priority Zero: Test isolation & DB protection
    "tests/conftest.py",
    "tests/test_auth_and_persistence.py",
    "tests/test_database.py",
    "tests/test_api_unit.py",
    "tests/test_mcp_integration.py",
    "tests/test_a2a_interoperability.py",
    "tests/test_adk_foundation.py",
    "tests/test_observability.py",
    "backend/db/database.py",
    
    # Priority 1: High severity (SEC-FIND-01 to 05)
    "backend/app/main.py",
    "backend/mcp_integration/client.py",
    "backend/mcp_integration/security.py",
    "backend/adk/api.py",
    "backend/observability/service.py",
    "backend/agents/teacher.py",
    "backend/agents/orchestrator.py",
    
    # Priority 2: Medium severity (SEC-FIND-06 to 11)
    "backend/a2a_protocol/security.py",
    "backend/a2a_protocol/server.py",
    
    # Priority 3: Low severity
    ".env.example",
]

# 3. Create a timestamped backup directory
timestamp_str = time.strftime("%Y%m%d_%H%M%S")
backup_dir = PROJECT_ROOT / f"scratch/phase5b_implementation/pre_phase5b_backup_{timestamp_str}"
backup_dir.mkdir(parents=True, exist_ok=True)

backed_up = []
for rel_path in target_files:
    src_file = PROJECT_ROOT / rel_path
    if src_file.exists():
        dest_file = backup_dir / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
        backed_up.append((rel_path, dest_file.stat().st_size))

print(f"\nCreated timestamped backup at: {backup_dir}")
print(f"Backed up {len(backed_up)} files:")
for rel, size in backed_up:
    print(f"  {rel} ({size} bytes)")

# Verify backup readability
all_readable = True
for rel_path in target_files:
    dest_file = backup_dir / rel_path
    if dest_file.exists():
        try:
            with open(dest_file, "rb") as f:
                _ = f.read(100)
        except Exception as e:
            all_readable = False
            print(f"ERROR reading backup file: {dest_file} -> {e}")

print(f"\nBackup verified readable: {all_readable}")
