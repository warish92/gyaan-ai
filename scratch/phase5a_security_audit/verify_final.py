import os
import sqlite3
from pathlib import Path

# Invariant 1: Protected project
p_legacy = Path("D:/GYAN Ai")
print("Protected project exists:", p_legacy.exists())

# Invariant 2: Database integrity
conn = sqlite3.connect("data/gyaan_ai.db")
cur = conn.cursor()
print("DB integrity:", cur.execute("PRAGMA integrity_check").fetchone()[0])
print("Tables count:", len(cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()))
print("Students count:", cur.execute("SELECT count(*) FROM students").fetchone()[0])
conn.close()

# Invariant 3: Backup
bak = Path("data/gyaan_ai.db.bak_phase4")
print("Backup exists:", bak.exists(), f"({bak.stat().st_size} bytes)")

# Invariant 4: Deliverables in root
for f in ["PHASE_5A_SECURITY_AUDIT_REPORT.md", "PHASE_5A_SECURITY_AUDIT.json", "PHASE_5A_SECURITY_REMEDIATION_ROADMAP.md"]:
    p = Path(f)
    print(f"Root file {f}: exists={p.exists()}, size={p.stat().st_size}")

# Invariant 5: Deliverables in artifact directory
art_dir = Path(r"C:\Users\waris\.gemini\antigravity\brain\ee824e43-49ad-452b-908c-5e2df1c3a7ca")
for f in ["PHASE_5A_SECURITY_AUDIT_REPORT.md", "PHASE_5A_SECURITY_AUDIT.json", "PHASE_5A_SECURITY_REMEDIATION_ROADMAP.md"]:
    p = art_dir / f
    print(f"Artifact file {f}: exists={p.exists()}, size={p.stat().st_size}")
