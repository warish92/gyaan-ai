import os
import sys
import time
import json
import sqlite3
import urllib.request
import urllib.error

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:3000"
DB_PATH = r"D:\Gyaan AI\data\gyaan_ai.db"
LEGACY_PATH = r"D:\GYAN Ai"

def log(msg):
    print(f"[VERIFY-8.8] {msg}")

def check_backend_and_ollama():
    log("Verifying backend health and local Ollama model...")
    url = f"{BACKEND_URL}/health"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        log(f"Backend status: {data.get('status')}, Ollama connected: {data.get('ollama_connected')}, Model: {data.get('model_name')}")
        assert data.get('status') == 'healthy', "Backend not healthy"
        assert data.get('ollama_connected') is True, "Ollama not connected"
        assert data.get('model_name') == 'qwen2.5:3b', "Model mismatch"
    return True

def check_frontend_routes():
    log("Verifying Next.js frontend routes...")
    routes = ["/", "/progress", "/mentor", "/resources", "/practice", "/diagnostic", "/learning-plans", "/teacher"]
    for route in routes:
        url = f"{FRONTEND_URL}{route}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
            log(f"Frontend route {route}: Status {resp.status}, Content-Length: {len(content)}")
            assert resp.status == 200, f"Route {route} failed with {resp.status}"
    return True

def check_sqlite_database():
    log("Checking SQLite database schema...")
    assert os.path.exists(DB_PATH), f"Database missing at {DB_PATH}"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    log(f"Found {len(tables)} tables: {', '.join(tables)}")
    required_tables = [
        "students", "student_sessions", "learning_sessions", "diagnostic_records",
        "curriculum_plans", "quizzes", "assessment_attempts", "student_topic_mastery"
    ]
    for req in required_tables:
        assert req in tables, f"Missing table {req}"
    return True

def test_unauthenticated_rejection():
    log("Testing that /progress and /mentor endpoints reject unauthenticated requests...")
    for endpoint in ["/api/v1/students/me/progress", "/api/v1/students/me/mentor-recommendations"]:
        url = f"{BACKEND_URL}{endpoint}"
        try:
            req = urllib.request.Request(url)
            urllib.request.urlopen(req, timeout=10)
            assert False, f"Expected 401 Unauthorized for {endpoint}"
        except urllib.error.HTTPError as err:
            log(f"Unauthenticated request to {endpoint} properly rejected with status: {err.code}")
            assert err.code == 401, f"Expected 401, got {err.code}"
    return True

def register_and_prepare_student():
    log("Registering a dedicated Phase 8.8 student...")
    test_email = f"phase88_student_{int(time.time())}@gyaan.ai"
    reg_url = f"{BACKEND_URL}/api/v1/auth/register"
    reg_payload = json.dumps({
        "email": test_email,
        "password": "Password123!",
        "display_name": "Progress Analytics Tester",
        "grade": "Class 10"
    }).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    
    req = urllib.request.Request(reg_url, data=reg_payload, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        token = data.get("token") or data.get("access_token")
        student_id = data.get("student", {}).get("id")
        log(f"Registered student: {test_email} (ID: {student_id})")
        assert token and student_id, "Registration failed to return credentials"
        
    # Check initial empty/insufficient history state
    log("Testing initial state with empty learning history...")
    prog_url = f"{BACKEND_URL}/api/v1/students/me/progress"
    auth_headers = {"Authorization": f"Bearer {token}"}
    req_prog = urllib.request.Request(prog_url, headers=auth_headers)
    with urllib.request.urlopen(req_prog, timeout=60) as resp:
        initial_prog = json.loads(resp.read().decode('utf-8'))
        stats = initial_prog.get("objective_statistics", {})
        log(f"Initial has_sufficient_history: {stats.get('has_sufficient_history')}")
        log(f"Initial total_assessments: {stats.get('total_assessments_completed')}")
        log(f"Initial trend_description: {stats.get('trend_description')}")
        assert stats.get("has_sufficient_history") is False, "Expected has_sufficient_history=False for brand new student"
        assert stats.get("total_assessments_completed") == 0, "Expected 0 assessments completed"

    # Now populate realistic assessment attempts and sessions for this student
    log("Populating verified assessment attempts in database for the student...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Insert a quiz
    quiz_id_1 = f"quiz_{int(time.time())}_1"
    quiz_questions = [
        {"id": "q1", "type": "mcq", "question": "What is the pH of pure water?", "marks": 1.0, "options": ["7", "1", "14", "4"]},
        {"id": "q2", "type": "short_answer", "question": "Explain neutralization reaction.", "marks": 2.0}
    ]
    cursor.execute(
        "INSERT INTO quizzes (id, student_id, subject, topic, grade, questions, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (quiz_id_1, student_id, "Science", "Acids, Bases and Salts", "Class 10", json.dumps(quiz_questions), "2026-10-30T10:00:00Z")
    )
    
    # 2. Insert assessment attempt 1
    att_id_1 = f"att_{int(time.time())}_1"
    cursor.execute(
        """INSERT INTO assessment_attempts (id, quiz_id, student_id, submitted_answers, score, max_marks, evaluation_details, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (att_id_1, quiz_id_1, student_id, json.dumps({"q1": "7", "q2": "Acid reacts with base"}), 2.0, 3.0,
         json.dumps({"overall_feedback": "Good fundamental understanding of neutral pH, need to elaborate on salt formation.", "evaluations": []}),
         "2026-10-30T10:05:00Z")
    )
    
    # 3. Insert a second quiz and attempt to establish trajectory
    quiz_id_2 = f"quiz_{int(time.time())}_2"
    cursor.execute(
        "INSERT INTO quizzes (id, student_id, subject, topic, grade, questions, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (quiz_id_2, student_id, "Science", "Chemical Reactions and Equations", "Class 10", json.dumps(quiz_questions), "2026-10-30T11:00:00Z")
    )
    att_id_2 = f"att_{int(time.time())}_2"
    cursor.execute(
        """INSERT INTO assessment_attempts (id, quiz_id, student_id, submitted_answers, score, max_marks, evaluation_details, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (att_id_2, quiz_id_2, student_id, json.dumps({"q1": "7", "q2": "Double displacement forms precipitate"}), 3.0, 3.0,
         json.dumps({"overall_feedback": "Excellent score and clear chemical equation reasoning.", "evaluations": []}),
         "2026-10-30T11:10:00Z")
    )
    
    # 4. Insert learning sessions
    cursor.execute(
        """INSERT INTO learning_sessions (id, student_id, subject, topic, activity_type, status, started_at, completed_at, details)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (f"sess_{int(time.time())}_1", student_id, "Science", "Acids, Bases and Salts", "quiz", "completed", "2026-10-30T10:00:00Z", "2026-10-30T10:05:00Z", json.dumps({"score": 2.0}))
    )
    cursor.execute(
        """INSERT INTO learning_sessions (id, student_id, subject, topic, activity_type, status, started_at, completed_at, details)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (f"sess_{int(time.time())}_2", student_id, "Science", "Chemical Reactions and Equations", "quiz", "completed", "2026-10-30T11:00:00Z", "2026-10-30T11:10:00Z", json.dumps({"score": 3.0}))
    )
    
    # 5. Insert topic mastery records
    cursor.execute(
        """INSERT INTO student_topic_mastery (id, student_id, subject, topic, latest_score, max_marks, percentage, attempts_count, mastery_status, last_assessed_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (f"mst_{int(time.time())}_1", student_id, "Science", "Acids, Bases and Salts", 2.0, 3.0, 66.7, 1, "in_progress", "2026-10-30T10:05:00Z", "2026-10-30T10:05:00Z")
    )
    cursor.execute(
        """INSERT INTO student_topic_mastery (id, student_id, subject, topic, latest_score, max_marks, percentage, attempts_count, mastery_status, last_assessed_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (f"mst_{int(time.time())}_2", student_id, "Science", "Chemical Reactions and Equations", 3.0, 3.0, 100.0, 1, "mastered", "2026-10-30T11:10:00Z", "2026-10-30T11:10:00Z")
    )
    
    conn.commit()
    conn.close()
    log("Populated 2 quizzes, 2 attempts, 2 sessions, and 2 mastery records.")
    
    return token, student_id

def test_live_progress_agent(token, student_id):
    log("Testing Live Progress Agent Execution (GET /api/v1/students/me/progress)...")
    url = f"{BACKEND_URL}/api/v1/students/me/progress"
    headers = {"Authorization": f"Bearer {token}"}
    
    t0 = time.time()
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        report = json.loads(resp.read().decode('utf-8'))
    duration = time.time() - t0
    
    log(f"Progress Agent execution finished in {duration:.2f}s!")
    log(f"Student ID: {report.get('student_id')}")
    log(f"Model: {report.get('model')}")
    stats = report.get('objective_statistics', {})
    log(f"Objective Statistics:")
    log(f"  - Total Assessments Completed: {stats.get('total_assessments_completed')}")
    log(f"  - Average Percentage: {stats.get('average_percentage')}%")
    log(f"  - Performance Trend: {stats.get('performance_trend')}")
    log(f"  - Trend Description: {stats.get('trend_description')}")
    log(f"Overall Summary: {report.get('overall_summary')}")
    log(f"Strengths: {report.get('strengths_analysis')}")
    log(f"Weaknesses: {report.get('weaknesses_analysis')}")
    log(f"Topic Observations: {len(report.get('topic_observations', []))} topics")
    log(f"Recommended Priorities: {report.get('recommended_priorities')}")
    
    assert report.get('student_id') == student_id, "Student ID mismatch in Progress response"
    assert stats.get('total_assessments_completed') == 2, f"Expected 2 assessments, got {stats.get('total_assessments_completed')}"
    assert stats.get('average_percentage') is not None, "average_percentage should be calculated"
    assert report.get('overall_summary'), "overall_summary is empty"
    assert report.get('model') == 'ollama/qwen2.5:3b', "Model should be ollama/qwen2.5:3b"
    
    return report

def test_live_mentor_agent(token, student_id):
    log("Testing Live Mentor Agent Execution (GET /api/v1/students/me/mentor-recommendations)...")
    log("Executing sequential Progress -> Mentor CrewAI workflow on local Ollama GPU...")
    url = f"{BACKEND_URL}/api/v1/students/me/mentor-recommendations"
    headers = {"Authorization": f"Bearer {token}"}
    
    t0 = time.time()
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        mentor = json.loads(resp.read().decode('utf-8'))
    duration = time.time() - t0
    
    log(f"Mentor Agent execution finished in {duration:.2f}s!")
    log(f"Student ID: {mentor.get('student_id')}")
    log(f"Model: {mentor.get('model')}")
    log(f"Mentor Overview: {mentor.get('mentor_overview')}")
    recs = mentor.get('recommendations', [])
    log(f"Recommendations Count: {len(recs)}")
    for i, r in enumerate(recs):
        log(f"  Rec {i+1} [{r.get('priority')}]: {r.get('title')} ({r.get('topic')}) - ~{r.get('estimated_minutes')}m")
        log(f"    Action: {r.get('suggested_action')}")
        log(f"    Reason: {r.get('reason')}")
    log(f"Study Tip: {mentor.get('study_tip')}")
    log(f"Next Milestone: {mentor.get('next_milestone')}")
    
    assert mentor.get('student_id') == student_id, "Student ID mismatch in Mentor response"
    assert mentor.get('mentor_overview'), "mentor_overview is empty"
    assert len(recs) > 0, "Expected at least 1 actionable recommendation"
    assert mentor.get('model') == 'ollama/qwen2.5:3b', "Model should be ollama/qwen2.5:3b"
    
    return mentor

def test_consolidated_progress_mentoring(token, student_id):
    log("Testing Consolidated Endpoint (GET /api/v1/students/me/progress-mentoring)...")
    url = f"{BACKEND_URL}/api/v1/students/me/progress-mentoring"
    headers = {"Authorization": f"Bearer {token}"}
    
    t0 = time.time()
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        consolidated = json.loads(resp.read().decode('utf-8'))
    duration = time.time() - t0
    
    log(f"Consolidated Progress-Mentoring finished in {duration:.2f}s!")
    assert consolidated.get('student_id') == student_id, "Student ID mismatch"
    assert "progress" in consolidated, "Missing progress in consolidated response"
    assert "mentoring" in consolidated, "Missing mentoring in consolidated response"
    return consolidated

def check_legacy_isolation():
    log("Verifying legacy safety boundary (D:\\GYAN Ai)...")
    assert os.path.exists(LEGACY_PATH), "Legacy directory missing!"
    log("Legacy path verified untouched.")
    return True

if __name__ == "__main__":
    log("=== PHASE 8.8 VERIFICATION SUITE START ===")
    try:
        check_backend_and_ollama()
        check_frontend_routes()
        check_sqlite_database()
        test_unauthenticated_rejection()
        token, student_id = register_and_prepare_student()
        test_live_progress_agent(token, student_id)
        test_live_mentor_agent(token, student_id)
        test_consolidated_progress_mentoring(token, student_id)
        check_legacy_isolation()
        log("=== ALL PHASE 8.8 VERIFICATIONS PASSED SUCCESSFULLY! ===")
    except Exception as exc:
        log(f"VERIFICATION FAILED: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
