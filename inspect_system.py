import requests
import sqlite3
import os

print("--- HEALTH CHECKS ---")
try:
    r_ollama = requests.get('http://127.0.0.1:11434/api/tags', timeout=3)
    models = [m['name'] for m in r_ollama.json().get('models', [])]
    print(f"OLLAMA: OK -> {models}")
except Exception as e:
    print(f"OLLAMA: FAIL -> {e}")

try:
    r_backend = requests.get('http://127.0.0.1:8000/health', timeout=3)
    print(f"BACKEND: OK -> {r_backend.status_code} {r_backend.json()}")
except Exception as e:
    print(f"BACKEND: FAIL -> {e}")

try:
    r_front = requests.get('http://localhost:3000', timeout=3)
    print(f"FRONTEND: OK -> {r_front.status_code}")
except Exception as e:
    print(f"FRONTEND: FAIL -> {e}")

db_path = r'D:\Gyaan AI\data\gyaan_ai.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()
    print("\n--- DATABASE TABLES ---")
    for (t,) in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {count} rows")
    conn.close()
else:
    print("DB file not found at", db_path)
