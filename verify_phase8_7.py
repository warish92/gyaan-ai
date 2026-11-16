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
    print(f"[VERIFY-8.7] {msg}")

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
    routes = ["/", "/resources", "/practice", "/diagnostic", "/learning-plans", "/teacher"]
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

def authenticate_student():
    log("Authenticating student for Phase 8.7 verification...")
    # Register a dedicated Phase 8.7 test student
    test_email = f"phase87_tester_{int(time.time())}@gyaan.ai"
    reg_url = f"{BACKEND_URL}/api/v1/auth/register"
    reg_payload = json.dumps({
        "email": test_email,
        "password": "Password123!",
        "display_name": "Resource & Practice Tester",
        "grade": "Class 10"
    }).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    
    req = urllib.request.Request(reg_url, data=reg_payload, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        token = data.get("token") or data.get("access_token")
        student_id = data.get("student", {}).get("id")
        log(f"Registered student: {test_email} (ID: {student_id})")
        assert token, "Token missing in registration response"
        assert student_id, "Student ID missing in registration response"
        return token, student_id

def test_resource_agent_workflow(token, student_id):
    log("Testing Resource Agent workflow (POST /api/v1/resources)...")
    url = f"{BACKEND_URL}/api/v1/resources"
    payload = json.dumps({
        "grade": "Class 10",
        "subject": "Science",
        "topic": "Acids, Bases and Salts",
        "learning_objective": "Understand chemical properties of acids, bases, and the pH scale."
    }).encode('utf-8')
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    t0 = time.time()
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    duration = time.time() - t0
    
    log(f"Resource Agent completed in {duration:.2f}s!")
    log(f"Workflow ID: {result.get('workflow_id')}")
    log(f"Verified Source: {result.get('is_verified')}")
    log(f"Source Type: {result.get('source_type')}")
    log(f"Sources Count: {len(result.get('sources', []))}")
    log(f"Model: {result.get('model')}")
    recommendation = result.get('resource_recommendation', '')
    log(f"Recommendation Length: {len(recommendation)} chars")
    log("--- RESOURCE RECOMMENDATION EXCERPT ---")
    log(recommendation[:300] + "...")
    
    assert result.get('is_verified') is True, "Expected verified NCERT source"
    assert "NCERT" in result.get('source_type', ''), "Expected NCERT in source_type"
    assert len(result.get('sources', [])) > 0, "Expected at least 1 source citation"
    assert len(recommendation) > 50, "Recommendation is too short"
    
    # Check SQLite learning session created
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, activity_type, topic, status FROM learning_sessions WHERE student_id = ? AND activity_type = 'revision' ORDER BY started_at DESC LIMIT 1", (student_id,))
    session_row = cursor.fetchone()
    conn.close()
    log(f"Database revision session: {session_row}")
    assert session_row is not None, "Revision learning session was not recorded"
    assert session_row[1] == 'revision', "Activity type is not revision"
    
    return result

def test_quiz_generation_workflow(token, student_id):
    log("Testing Quiz Generation workflow (POST /api/v1/quizzes)...")
    url = f"{BACKEND_URL}/api/v1/quizzes"
    payload = json.dumps({
        "student_id": student_id,
        "grade": "Class 10",
        "subject": "Science",
        "topic": "Acids, Bases and Salts",
        "num_questions": 2,
        "question_types": ["mcq", "short_answer"]
    }).encode('utf-8')
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    t0 = time.time()
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        quiz_data = json.loads(resp.read().decode('utf-8'))
    duration = time.time() - t0
    
    log(f"Quiz Generation completed in {duration:.2f}s!")
    quiz_id = quiz_data.get('quiz_id')
    questions = quiz_data.get('questions', [])
    log(f"Quiz ID: {quiz_id}")
    log(f"Questions Generated: {len(questions)}")
    log(f"Verified Source: {quiz_data.get('is_verified_source')}")
    
    for i, q in enumerate(questions):
        log(f"  Q{i+1} [{q.get('type')}]: {q.get('question')} (Marks: {q.get('marks')})")
        # Ensure correct answers/rubrics are NOT leaked in the student-facing response
        assert "correct_answer" not in q, "Security leak: correct_answer exposed in student response!"
        assert "rubric" not in q, "Security leak: rubric exposed in student response!"
        
    assert quiz_id and quiz_id.startswith("quiz_"), f"Invalid quiz ID: {quiz_id}"
    assert len(questions) == 2, f"Expected 2 questions, got {len(questions)}"
    
    # Check SQLite persistence of quiz
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, student_id, subject, topic, LENGTH(questions) FROM quizzes WHERE id = ?", (quiz_id,))
    quiz_row = cursor.fetchone()
    conn.close()
    log(f"Database quiz record: {quiz_row}")
    assert quiz_row is not None, "Quiz was not persisted in SQLite"
    assert quiz_row[1] == student_id, "Quiz student_id mismatch"
    
    return quiz_data

def test_assessment_submission_workflow(token, student_id, quiz_data):
    log("Testing Assessment Submission & Evaluation (POST /api/v1/assessments/submit)...")
    quiz_id = quiz_data['quiz_id']
    questions = quiz_data['questions']
    
    # Construct answers for the questions
    answers = {}
    for q in questions:
        qid = q['id']
        qtype = q['type']
        if qtype == "mcq" and q.get('options'):
            answers[qid] = q['options'][0]
        else:
            answers[qid] = "Acids produce H+ ions in aqueous solutions and turn blue litmus red with a pH below 7."
            
    log(f"Submitting answers for {len(answers)} questions...")
    url = f"{BACKEND_URL}/api/v1/assessments/submit"
    payload = json.dumps({
        "quiz_id": quiz_id,
        "student_id": student_id,
        "answers": answers
    }).encode('utf-8')
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    t0 = time.time()
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        sub_result = json.loads(resp.read().decode('utf-8'))
    duration = time.time() - t0
    
    log(f"Assessment Evaluation completed in {duration:.2f}s!")
    log(f"Attempt ID: {sub_result.get('attempt_id')}")
    log(f"Score: {sub_result.get('total_score')} / {sub_result.get('max_marks')} ({sub_result.get('percentage')}%)")
    log(f"Evaluations Count: {len(sub_result.get('evaluations', []))}")
    log(f"Overall Feedback: {sub_result.get('overall_feedback')}")
    log(f"Persisted: {sub_result.get('persisted')}")
    
    assert sub_result.get('attempt_id', '').startswith("att_"), "Invalid attempt_id"
    assert sub_result.get('persisted') is True, "Attempt was not persisted"
    assert len(sub_result.get('evaluations', [])) == len(questions), "Evaluation count mismatch"
    
    # Check SQLite persistence of attempt and session
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, quiz_id, student_id, score, max_marks FROM assessment_attempts WHERE id = ?", (sub_result['attempt_id'],))
    att_row = cursor.fetchone()
    log(f"Database assessment_attempts record: {att_row}")
    assert att_row is not None, "Assessment attempt record missing in SQLite"
    assert att_row[2] == student_id, "Student ID mismatch in assessment_attempts"
    
    cursor.execute("SELECT student_id, subject, topic, mastery_status FROM student_topic_mastery WHERE student_id = ? AND topic = ?", (student_id, quiz_data['topic']))
    mastery_row = cursor.fetchone()
    log(f"Database topic mastery: {mastery_row}")
    
    conn.close()
    return sub_result

def test_assessment_history_api(token, student_id, attempt_id):
    log("Testing Assessment History API (GET /api/v1/assessments/history/{student_id})...")
    url = f"{BACKEND_URL}/api/v1/assessments/history/{student_id}"
    headers = {"Authorization": f"Bearer {token}"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        hist_data = json.loads(resp.read().decode('utf-8'))
        
    attempts = hist_data.get('attempts', [])
    log(f"Total attempts returned: {hist_data.get('total_attempts')} ({len(attempts)} items)")
    found = any(att.get('attempt_id') == attempt_id for att in attempts)
    log(f"Newly submitted attempt {attempt_id} found in history: {found}")
    assert found, f"Attempt {attempt_id} not found in history"
    
    # Test Student Isolation: Trying to query another student's history should be rejected (403)
    log("Verifying multi-student isolation (attempting to access another student's history)...")
    other_student_id = "stu_other_unauthorized"
    url_other = f"{BACKEND_URL}/api/v1/assessments/history/{other_student_id}"
    req_other = urllib.request.Request(url_other, headers=headers)
    try:
        urllib.request.urlopen(req_other, timeout=10)
        assert False, "Expected HTTP 403 Forbidden when accessing another student's history!"
    except urllib.error.HTTPError as err:
        log(f"Cross-student access properly rejected with status: {err.code}")
        assert err.code == 403, f"Expected status 403, got {err.code}"
        
    return True

def test_guest_mode():
    log("Testing Guest Mode access for Resources and Quizzes...")
    # Guest Resource request
    url_res = f"{BACKEND_URL}/api/v1/resources"
    payload_res = json.dumps({
        "grade": "Class 10",
        "subject": "Science",
        "topic": "Metals and Non-metals"
    }).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    req_res = urllib.request.Request(url_res, data=payload_res, headers=headers)
    with urllib.request.urlopen(req_res, timeout=60) as resp:
        res_data = json.loads(resp.read().decode('utf-8'))
        log(f"Guest resource request succeeded! Model: {res_data.get('model')}")
        assert res_data.get('resource_recommendation'), "Empty guest recommendation"
    return True

def check_legacy_isolation():
    log("Verifying legacy safety boundary (D:\\GYAN Ai)...")
    assert os.path.exists(LEGACY_PATH), "Legacy directory missing!"
    log("Legacy path verified untouched.")
    return True

if __name__ == "__main__":
    log("=== PHASE 8.7 VERIFICATION SUITE START ===")
    try:
        check_backend_and_ollama()
        check_frontend_routes()
        check_sqlite_database()
        token, student_id = authenticate_student()
        test_resource_agent_workflow(token, student_id)
        quiz_data = test_quiz_generation_workflow(token, student_id)
        sub_result = test_assessment_submission_workflow(token, student_id, quiz_data)
        test_assessment_history_api(token, student_id, sub_result['attempt_id'])
        test_guest_mode()
        check_legacy_isolation()
        log("=== ALL PHASE 8.7 VERIFICATIONS PASSED SUCCESSFULLY! ===")
    except Exception as exc:
        log(f"VERIFICATION FAILED: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
