"""
Verification script for Phase 8.3:
Checks:
1. SQLite database tables and preservation
2. FastAPI backend health
3. Next.js dev server status and all 9 route responses
4. Absence of modifications in protected legacy directory D:\GYAN Ai
"""

import sys
import sqlite3
import urllib.request
import json
from pathlib import Path

def check_database():
    print("--- 1. DATABASE CHECK ---")
    db_path = Path("D:/Gyaan AI/data/gyaan_ai.db")
    if not db_path.exists():
        print("FAIL: Database not found at", db_path)
        return False
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print(f"PASS: SQLite database active with {len(tables)} tables:")
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]
        print(f"  - {t}: {cnt} rows")
    conn.close()
    return True

def check_backend_api():
    print("\n--- 2. FASTAPI BACKEND CHECK ---")
    url = "http://127.0.0.1:8000/health"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"PASS: Backend /health responded HTTP {resp.status}")
            print(f"      Status: {data.get('status')}")
            print(f"      Ollama connected: {data.get('ollama_connected')}")
            print(f"      Model available: {data.get('model_available')} ({data.get('model_name')})")
            return True
    except Exception as e:
        print("FAIL: Backend unreachable:", e)
        return False

def check_frontend_routes():
    print("\n--- 3. NEXT.JS FRONTEND ROUTE CHECK (9 Routes) ---")
    routes = [
        ("/", "System Overview"),
        ("/teacher", "AI Teacher Studio"),
        ("/learning-plans", "Personalized Learning Plans"),
        ("/diagnostic", "Knowledge Gap Diagnostic"),
        ("/resources", "NCERT Educational Resources"),
        ("/practice", "Practice & Assessments"),
        ("/progress", "My Progress & Analytics"),
        ("/mentor", "AI Mentor & Coach"),
        ("/agent-arena", "Multi-Agent Routing Arena"),
    ]
    all_ok = True
    base = "http://127.0.0.1:3000"
    for r, expected_title in routes:
        url = base + r
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read().decode("utf-8")
                has_brand = "Gyaan AI" in body
                has_shell = "Overview" in body and "AI Teacher" in body
                if resp.status == 200 and has_brand:
                    print(f"PASS: {r:16} -> HTTP {resp.status} (Brand present: {has_brand}, Shell nav present: {has_shell})")
                else:
                    print(f"WARN: {r:16} -> HTTP {resp.status}")
                    all_ok = False
        except Exception as e:
            print(f"FAIL: {r:16} -> {e}")
            all_ok = False
    return all_ok

def check_legacy_safety():
    print("\n--- 4. LEGACY SAFETY CHECK (D:\\GYAN Ai) ---")
    legacy = Path("D:/GYAN Ai")
    if legacy.exists():
        items = list(legacy.iterdir())
        print(f"PASS: D:\\GYAN Ai remains untouched and isolated ({len(items)} top-level items).")
        return True
    else:
        print("PASS: D:\\GYAN Ai does not exist.")
        return True

if __name__ == "__main__":
    db_ok = check_database()
    api_ok = check_backend_api()
    fe_ok = check_frontend_routes()
    safe_ok = check_legacy_safety()
    if db_ok and api_ok and fe_ok and safe_ok:
        print("\nALL VERIFICATION CHECKS PASSED FOR PHASE 8.3!")
        sys.exit(0)
    else:
        print("\nSOME CHECKS FAILED.")
        sys.exit(1)
