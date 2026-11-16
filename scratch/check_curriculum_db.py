import sys
sys.path.insert(0, ".")
from backend.db.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

for table in ["curriculum_subjects", "curriculum_chapters", "curriculum_topics", "curriculum_learning_objectives", "curriculum_resources", "students", "assessment_attempts", "diagnostic_records"]:
    cursor.execute(f"SELECT count(*) FROM {table}")
    cnt = cursor.fetchone()[0]
    print(f"Table '{table}': {cnt} rows")

cursor.execute("SELECT id, name, chapter_number FROM curriculum_chapters WHERE subject_id = 'sub_sci_10' LIMIT 5")
print("\nSample Science Class 10 chapters:")
for r in cursor.fetchall():
    print(" ", r)

cursor.execute("SELECT id, title FROM curriculum_topics WHERE chapter_id = 'chap_sci_9' LIMIT 5")
print("\nSample Topics for Chapter chap_sci_9 (Light):")
for r in cursor.fetchall():
    print(" ", r)
