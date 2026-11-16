import sqlite3
from pathlib import Path

db_path = Path("data/gyaan_ai.db")
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()
cur.execute("PRAGMA integrity_check;")
print("DB integrity:", cur.fetchone()[0])
cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
print("DB tables:", cur.fetchone()[0])
cur.execute("SELECT count(*) FROM students;")
print("DB students:", cur.fetchone()[0])
cur.execute("SELECT count(*) FROM student_sessions;")
print("DB sessions:", cur.fetchone()[0])
tbls = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()]
total = sum([cur.execute(f'SELECT count(*) FROM "{t}";').fetchone()[0] for t in tbls])
print("DB total rows:", total)
conn.close()

bak = Path("data/gyaan_ai.db.bak_phase4")
print("Backup size:", bak.stat().st_size if bak.exists() else 0)
