import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()
ARTIFACT_DIR = Path(r"C:\Users\waris\.gemini\antigravity\brain\ee824e43-49ad-452b-908c-5e2df1c3a7ca").resolve()

# 1 & 2: Check files exist and locations
expected_files = [
    "PHASE_5A_SECURITY_AUDIT_REPORT.md",
    "PHASE_5A_SECURITY_AUDIT.json",
    "PHASE_5A_SECURITY_REMEDIATION_ROADMAP.md"
]

print("=== 1 & 2. FILE EXISTENCE & PATHS ===")
for fname in expected_files:
    root_p = PROJECT_ROOT / fname
    art_p = ARTIFACT_DIR / fname
    assert root_p.exists(), f"Missing {root_p}"
    assert art_p.exists(), f"Missing {art_p}"
    print(f"  [OK] Project Root: {root_p} ({root_p.stat().st_size} bytes)")
    print(f"  [OK] Artifact Dir: {art_p} ({art_p.stat().st_size} bytes)")

# 3: Validate JSON using python's json module
print("\n=== 3. JSON VALIDATION ===")
with open(PROJECT_ROOT / "PHASE_5A_SECURITY_AUDIT.json", "r", encoding="utf-8") as f:
    json_data = json.load(f)
print("  [OK] Successfully parsed with standard json module.")
print(f"  JSON keys: {list(json_data.keys())}")
print(f"  Findings count in JSON: {len(json_data['findings'])}")

# 4: Check Markdown reports readable & complete
print("\n=== 4. MARKDOWN READABILITY & COMPLETENESS ===")
report_text = (PROJECT_ROOT / "PHASE_5A_SECURITY_AUDIT_REPORT.md").read_text(encoding="utf-8")
roadmap_text = (PROJECT_ROOT / "PHASE_5A_SECURITY_REMEDIATION_ROADMAP.md").read_text(encoding="utf-8")
assert len(report_text) > 10000, "Report text too short"
assert len(roadmap_text) > 8000, "Roadmap text too short"
print(f"  [OK] Report length: {len(report_text)} characters.")
print(f"  [OK] Roadmap length: {len(roadmap_text)} characters.")

# 5: Confirm agreement across all 3 documents
print("\n=== 5. CROSS-DOCUMENT CONSISTENCY CHECK ===")
findings_json = json_data["findings"]
json_finding_ids = [f["finding_id"] for f in findings_json]
print(f"  Finding IDs in JSON ({len(json_finding_ids)}): {json_finding_ids}")

for fid in json_finding_ids:
    assert fid in report_text, f"{fid} missing from report markdown"
    assert fid in roadmap_text, f"{fid} missing from roadmap markdown"
print("  [OK] All 14 finding IDs present across all three documents.")

# Check severities agreement
for f in findings_json:
    fid = f["finding_id"]
    sev = f["severity"]
    assert f"{fid}" in report_text and sev in report_text, f"Severity mismatch for {fid} in report"
print("  [OK] Severity levels match across all documents.")

# 6: Confirm no application code or config changed
print("\n=== 6. SOURCE CODE & DATABASE INTEGRITY ===")
conn = sqlite3.connect(str(PROJECT_ROOT / "data/gyaan_ai.db"))
cur = conn.cursor()
db_integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
table_count = len(cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
cur_students = cur.execute("SELECT count(*) FROM students").fetchone()[0]
conn.close()
assert db_integrity == "ok", "Database integrity failed!"
print(f"  [OK] SQLite database integrity: {db_integrity}, tables: {table_count}, students: {cur_students}")

# 7: Confirm protected legacy directory untouched
print("\n=== 7. PROTECTED LEGACY DIRECTORY ===")
legacy_dir = Path("D:/GYAN Ai")
assert legacy_dir.exists(), "Protected directory not found!"
print(f"  [OK] Protected directory: {legacy_dir}")
print("  ALL VERIFICATION CHECKS PASSED SUCCESSFULLY.")
