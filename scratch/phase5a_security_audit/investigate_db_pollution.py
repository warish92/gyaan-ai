import sqlite3
from pathlib import Path

db_path = Path("D:/Gyaan AI/data/gyaan_ai.db")
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

# Check student records
print("=== INVESTIGATING STUDENTS IN ACTIVE PROJECT DATABASE ===")
students = cur.execute("SELECT id, display_name, grade, created_at FROM students ORDER BY rowid DESC LIMIT 30").fetchall()
print(f"Total students count: {len(cur.execute('SELECT id FROM students').fetchall())}")

# Check when the last 15 were added
print("\nMost recent 15 student records:")
for s in students[:15]:
    print("  ", s)

# Check student_sessions count
session_count = cur.execute("SELECT count(*) FROM student_sessions").fetchone()[0]
print(f"\nTotal student_sessions count: {session_count}")

# Check backup file
bak_path = Path("D:/Gyaan AI/data/gyaan_ai.db.bak_phase4")
print(f"\nBackup file exists: {bak_path.exists()}, size: {bak_path.stat().st_size}")
if bak_path.exists():
    bak_conn = sqlite3.connect(str(bak_path))
    bak_cur = bak_conn.cursor()
    bak_student_count = bak_cur.execute("SELECT count(*) FROM students").fetchone()[0]
    bak_session_count = bak_cur.execute("SELECT count(*) FROM student_sessions").fetchone()[0]
    print(f"Backup student count: {bak_student_count}")
    print(f"Backup session count: {bak_session_count}")
    bak_conn.close()

conn.close()
