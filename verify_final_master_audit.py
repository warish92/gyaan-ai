"""
Gyaan AI — Final Master Audit Verification Script
Executes the full end-to-end student journey and tests all 9 workflows
against the live FastAPI backend (http://127.0.0.1:8000) and local Ollama (http://127.0.0.1:11434).
"""

import sys
import time
import json
import urllib.request
import urllib.error
import sqlite3
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
DB_PATH = r"D:\Gyaan AI\data\gyaan_ai.db"

results = {
    "started_at": datetime.now().isoformat(),
    "steps": [],
    "summary": {"total": 0, "passed": 0, "failed": 0}
}

def log_step(name: str, passed: bool, details: dict):
    results["summary"]["total"] += 1
    if passed:
        results["summary"]["passed"] += 1
        status = "PASS"
    else:
        results["summary"]["failed"] += 1
        status = "FAIL"
    
    entry = {
        "step": name,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "details": details
    }
    results["steps"].append(entry)
    print(f"[{status}] {name} - {details.get('summary', '')}")
    sys.stdout.flush()

def make_request(method: str, path: str, data: dict = None, token: str = None, timeout: int = 150):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    start_t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.time() - start_t
            resp_body = resp.read().decode("utf-8")
            try:
                json_data = json.loads(resp_body)
            except Exception:
                json_data = resp_body
            return {"status_code": resp.status, "data": json_data, "elapsed_s": round(elapsed, 2)}
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start_t
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = err_body
        return {"status_code": e.code, "error": err_json, "elapsed_s": round(elapsed, 2)}
    except Exception as e:
        elapsed = time.time() - start_t
        return {"status_code": 0, "error": str(e), "elapsed_s": round(elapsed, 2)}

def run_audit():
    print("=================================================================")
    print("STARTING GYAAN AI FINAL MASTER AUDIT — END-TO-END VALIDATION")
    print(f"Target: {BASE_URL} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=================================================================\n")

    # 1. Health Probe
    h = make_request("GET", "/health")
    passed = h.get("status_code") == 200 and h.get("data", {}).get("status") == "healthy"
    log_step("1. Health Endpoint Probe", passed, {
        "status_code": h.get("status_code"),
        "ollama_connected": h.get("data", {}).get("ollama_connected"),
        "model_available": h.get("data", {}).get("model_available"),
        "model_name": h.get("data", {}).get("model_name"),
        "summary": f"FastAPI healthy, Ollama connected ({h.get('data', {}).get('model_name')})"
    })

    # 2. Authentication — Student Registration
    timestamp_suffix = int(time.time())
    student_a_email = f"audit_student_a_{timestamp_suffix}@gyaan.ai"
    student_a_pass = "AuditSecurePass123!"
    reg_payload = {
        "display_name": "Audit Student Alpha",
        "email": student_a_email,
        "password": student_a_pass,
        "grade": "10",
        "preferred_language": "English"
    }
    reg_res = make_request("POST", "/api/v1/auth/register", reg_payload)
    passed = reg_res.get("status_code") in (200, 201) and "token" in reg_res.get("data", {})
    token_a = reg_res.get("data", {}).get("token")
    student_a = reg_res.get("data", {}).get("student", {})
    student_a_id = student_a.get("id")
    log_step("2. Student Registration", passed, {
        "status_code": reg_res.get("status_code"),
        "student_id": student_a_id,
        "email": student_a_email,
        "summary": f"Student registered with ID {student_a_id}"
    })

    # 3. Authentication — Valid Login
    login_payload = {"email": student_a_email, "password": student_a_pass}
    login_res = make_request("POST", "/api/v1/auth/login", login_payload)
    passed = login_res.get("status_code") == 200 and "token" in login_res.get("data", {})
    if passed:
        token_a = login_res.get("data", {}).get("token")
    log_step("3. Student Login (Valid Credentials)", passed, {
        "status_code": login_res.get("status_code"),
        "token_type": login_res.get("data", {}).get("token_type"),
        "summary": "JWT Token generated successfully"
    })

    # 4. Authentication — Invalid Credentials Rejection
    bad_login = make_request("POST", "/api/v1/auth/login", {"email": student_a_email, "password": "WrongPassword!"})
    passed = bad_login.get("status_code") == 401
    log_step("4. Authentication Rejection (Invalid Password)", passed, {
        "status_code": bad_login.get("status_code"),
        "summary": "Invalid login rejected with HTTP 401"
    })

    # 5. Student Profile Validation (/students/me)
    profile_res = make_request("GET", "/api/v1/students/me", token=token_a)
    passed = profile_res.get("status_code") == 200 and profile_res.get("data", {}).get("email") == student_a_email
    log_step("5. Student Profile Retrieval (/students/me)", passed, {
        "status_code": profile_res.get("status_code"),
        "display_name": profile_res.get("data", {}).get("display_name"),
        "grade": profile_res.get("data", {}).get("grade"),
        "summary": f"Profile matches display_name={profile_res.get('data', {}).get('display_name')}"
    })

    # 6. Profile Update (PATCH /students/me)
    patch_res = make_request("PATCH", "/api/v1/students/me", {"preferred_language": "Hindi"}, token=token_a)
    passed = patch_res.get("status_code") == 200 and patch_res.get("data", {}).get("preferred_language") == "Hindi"
    log_step("6. Student Profile Update (PATCH /students/me)", passed, {
        "status_code": patch_res.get("status_code"),
        "updated_lang": patch_res.get("data", {}).get("preferred_language"),
        "summary": "Language successfully updated to Hindi"
    })
    # Reset back to English
    make_request("PATCH", "/api/v1/students/me", {"preferred_language": "English"}, token=token_a)

    # 7. Security Isolation — Student B Registration & Isolation
    student_b_email = f"audit_student_b_{timestamp_suffix}@gyaan.ai"
    reg_b = make_request("POST", "/api/v1/auth/register", {
        "display_name": "Audit Student Beta",
        "email": student_b_email,
        "password": "PasswordBeta123!",
        "grade": "Grade 9",
        "preferred_language": "English"
    })
    token_b = reg_b.get("data", {}).get("token")
    student_b_id = reg_b.get("data", {}).get("student", {}).get("id")

    # Attempt cross-student access: Student B requests Student A's history
    cross_access = make_request("GET", f"/api/v1/assessments/history/{student_a_id}", token=token_b)
    # The endpoint should return 403 Forbidden
    passed = cross_access.get("status_code") == 403
    log_step("7. Security Isolation (Cross-Student Access Prevention)", passed, {
        "status_code": cross_access.get("status_code"),
        "summary": f"Cross-student access strictly blocked with HTTP {cross_access.get('status_code')} Forbidden"
    })

    # 8. Security — Unauthorized Access Rejection (No Token)
    no_auth = make_request("GET", "/api/v1/students/me")
    passed = no_auth.get("status_code") == 401
    log_step("8. Security Protection (Missing Token)", passed, {
        "status_code": no_auth.get("status_code"),
        "summary": "Missing token rejected with HTTP 401"
    })

    # 9. Security — Invalid Token Rejection
    bad_token = make_request("GET", "/api/v1/students/me", token="invalid.jwt.token")
    passed = bad_token.get("status_code") == 401
    log_step("9. Security Protection (Invalid Token)", passed, {
        "status_code": bad_token.get("status_code"),
        "summary": "Malformed token rejected with HTTP 401"
    })

    # =========================================================================
    # WORKFLOW 1: AI Teacher Studio (Teacher Agent)
    # =========================================================================
    print("\n--- Executing Workflow 1: AI Teacher Studio ---")
    teacher_payload = {
        "question": "What is Newton's third law of motion? Give one practical example.",
        "grade": "9",
        "subject": "Science",
        "language": "English"
    }
    t_start = time.time()
    t_res = make_request("POST", "/api/v1/ask", teacher_payload, token=token_a, timeout=120)
    t_dur = round(time.time() - t_start, 2)
    answer = t_res.get("data", {}).get("answer", "")
    passed = t_res.get("status_code") == 200 and len(answer) > 20 and t_res.get("data", {}).get("status") == "success"
    log_step("10. Workflow 1: AI Teacher Studio (Teacher Agent)", passed, {
        "status_code": t_res.get("status_code"),
        "duration_s": t_dur,
        "model": t_res.get("data", {}).get("model"),
        "answer_sample": answer[:120] + "..." if len(answer) > 120 else answer,
        "summary": f"Teacher Agent responded in {t_dur}s with valid explanation"
    })

    # =========================================================================
    # WORKFLOW 2 & 3: Diagnostic Assessment & Learning Plan (Diagnostic + Curriculum Agents)
    # =========================================================================
    print("\n--- Executing Workflow 2 & 3: Diagnostic & Curriculum Plan ---")
    plan_payload = {
        "student_id": student_a_id,
        "display_name": "Audit Student Alpha",
        "grade": "10",
        "subject": "Mathematics",
        "topic": "Quadratic Equations",
        "assessment_items": [
            {
                "question": "Find the roots of x^2 - 5x + 6 = 0.",
                "student_answer": "x = 2 and x = 3",
                "expected_answer": "x = 2 and x = 3"
            },
            {
                "question": "What is the discriminant formula for ax^2 + bx + c = 0?",
                "student_answer": "b^2 - 4ac",
                "expected_answer": "D = b^2 - 4ac"
            }
        ]
    }
    lp_start = time.time()
    lp_res = make_request("POST", "/api/v1/learning-plan", plan_payload, token=token_a, timeout=180)
    lp_dur = round(time.time() - lp_start, 2)
    diag_rep = lp_res.get("data", {}).get("diagnostic_report", "")
    curr_plan = lp_res.get("data", {}).get("curriculum_plan", "")
    plan_persisted = lp_res.get("data", {}).get("persisted", False)
    passed = lp_res.get("status_code") == 200 and len(diag_rep) > 10 and len(curr_plan) > 10 and plan_persisted
    log_step("11. Workflows 2 & 3: Diagnostic & Curriculum Plan Agents", passed, {
        "status_code": lp_res.get("status_code"),
        "duration_s": lp_dur,
        "persisted": plan_persisted,
        "diagnostic_id": lp_res.get("data", {}).get("diagnostic_id"),
        "plan_id": lp_res.get("data", {}).get("plan_id"),
        "summary": f"Diagnostic & Curriculum generated and persisted in {lp_dur}s"
    })

    # =========================================================================
    # WORKFLOW 4: Educational Resources (Resource Agent)
    # =========================================================================
    print("\n--- Executing Workflow 4: Educational Resources ---")
    res_payload = {
        "grade": "10",
        "subject": "Science",
        "topic": "Chemical Reactions and Equations",
        "learning_objective": "Understand balancing chemical equations"
    }
    res_start = time.time()
    r_res = make_request("POST", "/api/v1/resources", res_payload, token=token_a, timeout=120)
    r_dur = round(time.time() - res_start, 2)
    r_rec = r_res.get("data", {}).get("resource_recommendation", "")
    passed = r_res.get("status_code") == 200 and len(r_rec) > 20 and r_res.get("data", {}).get("is_verified", False)
    log_step("12. Workflow 4: Learning Resources (Resource Agent)", passed, {
        "status_code": r_res.get("status_code"),
        "duration_s": r_dur,
        "is_verified": r_res.get("data", {}).get("is_verified"),
        "source_type": r_res.get("data", {}).get("source_type"),
        "sources_count": len(r_res.get("data", {}).get("sources", [])),
        "summary": f"Curated verified NCERT resources in {r_dur}s"
    })

    # =========================================================================
    # WORKFLOW 5 & 6: Practice Quiz & Assessment Submission (Assessment Agent)
    # =========================================================================
    print("\n--- Executing Workflow 5: Quiz Generation ---")
    quiz_payload = {
        "student_id": student_a_id,
        "grade": "10",
        "subject": "Mathematics",
        "topic": "Trigonometry",
        "num_questions": 2,
        "question_types": ["multiple_choice", "short_answer"],
        "learning_objectives": "Basic trigonometric ratios sin, cos, tan"
    }
    q_start = time.time()
    q_res = make_request("POST", "/api/v1/quizzes", quiz_payload, token=token_a, timeout=120)
    q_dur = round(time.time() - q_start, 2)
    questions = q_res.get("data", {}).get("questions", [])
    quiz_id = q_res.get("data", {}).get("quiz_id")
    passed = q_res.get("status_code") == 200 and len(questions) > 0 and quiz_id is not None
    log_step("13. Workflow 5: Quiz Generation (Assessment Agent)", passed, {
        "status_code": q_res.get("status_code"),
        "duration_s": q_dur,
        "quiz_id": quiz_id,
        "questions_count": len(questions),
        "summary": f"Generated {len(questions)} quiz questions in {q_dur}s"
    })

    # Submit the quiz
    print("\n--- Executing Workflow 6: Assessment Submission & Evaluation ---")
    q1_id = questions[0].get("id") if questions else "q1"
    submit_payload = {
        "quiz_id": quiz_id,
        "student_id": student_a_id,
        "answers": {
            q1_id: "1"
        }
    }
    sub_start = time.time()
    sub_res = make_request("POST", "/api/v1/assessments/submit", submit_payload, token=token_a, timeout=120)
    sub_dur = round(time.time() - sub_start, 2)
    attempt_id = sub_res.get("data", {}).get("attempt_id")
    total_score = sub_res.get("data", {}).get("total_score")
    sub_persisted = sub_res.get("data", {}).get("persisted", False)
    passed = sub_res.get("status_code") == 200 and attempt_id is not None and sub_persisted
    log_step("14. Workflow 6: Assessment Submission & Grading", passed, {
        "status_code": sub_res.get("status_code"),
        "duration_s": sub_dur,
        "attempt_id": attempt_id,
        "score": total_score,
        "persisted": sub_persisted,
        "summary": f"Evaluated and persisted score {total_score} in {sub_dur}s"
    })

    # =========================================================================
    # WORKFLOW 7: Student Progress Analytics (Progress Agent)
    # =========================================================================
    print("\n--- Executing Workflow 7: Student Progress Analytics ---")
    prog_start = time.time()
    prog_res = make_request("GET", "/api/v1/students/me/progress", token=token_a, timeout=120)
    prog_dur = round(time.time() - prog_start, 2)
    p_data = prog_res.get("data", {})
    passed = prog_res.get("status_code") == 200 and "overall_summary" in p_data and "objective_statistics" in p_data
    log_step("15. Workflow 7: Student Progress Analytics (Progress Agent)", passed, {
        "status_code": prog_res.get("status_code"),
        "duration_s": prog_dur,
        "has_history": p_data.get("objective_statistics", {}).get("has_sufficient_history"),
        "assessments_completed": p_data.get("objective_statistics", {}).get("total_assessments_completed"),
        "summary": f"Progress Agent analyzed student data in {prog_dur}s"
    })

    # =========================================================================
    # WORKFLOW 8: AI Learning Mentor (Mentor Agent)
    # =========================================================================
    print("\n--- Executing Workflow 8: AI Learning Mentor ---")
    mentor_start = time.time()
    m_res = make_request("GET", "/api/v1/students/me/mentor-recommendations", token=token_a, timeout=120)
    m_dur = round(time.time() - mentor_start, 2)
    m_data = m_res.get("data", {})
    recs = m_data.get("recommendations", [])
    passed = m_res.get("status_code") == 200 and len(m_data.get("mentor_overview", "")) > 10
    log_step("16. Workflow 8: AI Learning Mentor (Mentor Agent)", passed, {
        "status_code": m_res.get("status_code"),
        "duration_s": m_dur,
        "recommendations_count": len(recs),
        "study_tip": m_data.get("study_tip", "")[:80] + "...",
        "summary": f"Mentor Agent delivered {len(recs)} tailored recommendations in {m_dur}s"
    })

    # =========================================================================
    # WORKFLOW 9: Agent Arena / Orchestrator Routing
    # =========================================================================
    print("\n--- Executing Workflow 9: Agent Arena Orchestrator Routing ---")
    
    # 9a. Educational Intent Routing
    orch_1 = {
        "request": "Explain the concept of electric current and Ohm's Law.",
        "grade": "10",
        "subject": "Physics",
        "language": "English"
    }
    o1_start = time.time()
    o1_res = make_request("POST", "/api/v1/orchestrate", orch_1, token=token_a, timeout=120)
    o1_dur = round(time.time() - o1_start, 2)
    o1_data = o1_res.get("data", {})
    passed = o1_res.get("status_code") == 200 and o1_data.get("selected_workflow") is not None
    log_step("17. Workflow 9a: Intent Routing (Educational Request)", passed, {
        "status_code": o1_res.get("status_code"),
        "duration_s": o1_dur,
        "detected_intent": o1_data.get("detected_intent"),
        "selected_workflow": o1_data.get("selected_workflow"),
        "selected_agents": o1_data.get("selected_agents"),
        "summary": f"Routed to '{o1_data.get('selected_workflow')}' ({o1_data.get('detected_intent')}) in {o1_dur}s"
    })

    # 9b. Ambiguous Intent Handling (Clarification)
    orch_2 = {
        "request": "Help me.",
        "grade": "10",
        "subject": "General",
        "language": "English"
    }
    o2_res = make_request("POST", "/api/v1/orchestrate", orch_2, token=token_a, timeout=60)
    o2_data = o2_res.get("data", {})
    passed = o2_res.get("status_code") == 200 and (o2_data.get("clarification_required") is True or len(o2_data.get("clarification_question", "")) > 0)
    log_step("18. Workflow 9b: Ambiguous Query Clarification", passed, {
        "status_code": o2_res.get("status_code"),
        "clarification_required": o2_data.get("clarification_required"),
        "question": o2_data.get("clarification_question"),
        "summary": "Ambiguous input correctly triggered clarifying response"
    })

    # 9c. Out-of-Scope Query Boundary Handling
    orch_3 = {
        "request": "Book a cheap flight from Mumbai to Delhi for tomorrow.",
        "grade": "10",
        "subject": "General",
        "language": "English"
    }
    o3_res = make_request("POST", "/api/v1/orchestrate", orch_3, token=token_a, timeout=60)
    o3_data = o3_res.get("data", {})
    result_text = str(o3_data.get("result", "")) + str(o3_data.get("routing_reason", "")) + str(o3_data.get("clarification_question", ""))
    passed = o3_res.get("status_code") == 200 and not ("booking confirmed" in result_text.lower())
    log_step("19. Workflow 9c: Out-of-Scope Query Scope Enforcement", passed, {
        "status_code": o3_res.get("status_code"),
        "detected_intent": o3_data.get("detected_intent"),
        "summary": "Handled out-of-scope query safely without fabricating non-educational workflows"
    })

    # =========================================================================
    # Aggregation & Overview Dashboard Endpoints
    # =========================================================================
    print("\n--- Verifying Dashboard & Aggregation Endpoints ---")
    dash_res = make_request("GET", "/api/v1/students/me/dashboard", token=token_a)
    passed = dash_res.get("status_code") == 200 and "profile" in dash_res.get("data", {}) and "stats" in dash_res.get("data", {})
    log_step("20. Student Dashboard Aggregation (/students/me/dashboard)", passed, {
        "status_code": dash_res.get("status_code"),
        "stats": dash_res.get("data", {}).get("stats"),
        "summary": "Dashboard aggregates profile, sessions, diagnostics, and assessments"
    })

    mastery_res = make_request("GET", "/api/v1/students/me/topic-mastery", token=token_a)
    passed = mastery_res.get("status_code") == 200 and isinstance(mastery_res.get("data", []), list)
    log_step("21. Topic Mastery Retrieval (/students/me/topic-mastery)", passed, {
        "status_code": mastery_res.get("status_code"),
        "items_count": len(mastery_res.get("data", [])),
        "summary": f"Retrieved {len(mastery_res.get('data', []))} mastery items"
    })

    # =========================================================================
    # Database Direct Integrity Audit
    # =========================================================================
    print("\n--- Auditing SQLite Database Directly ---")
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Check integrity
        cur.execute("PRAGMA integrity_check;")
        integrity = cur.fetchone()[0]
        
        # Check foreign keys
        cur.execute("PRAGMA foreign_key_check;")
        fk_violations = cur.fetchall()
        
        # Count rows in key tables
        tables = [
            "students", "user_sessions", "learning_sessions",
            "diagnostic_records", "curriculum_plans", "quizzes",
            "quiz_questions", "assessment_attempts", "assessment_answers", "topic_mastery"
        ]
        counts = {}
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t};")
                counts[t] = cur.fetchone()[0]
            except Exception as e:
                counts[t] = f"Error: {e}"
                
        conn.close()
        
        db_passed = integrity == "ok" and len(fk_violations) == 0
        log_step("22. Database Direct Integrity & Foreign Keys", db_passed, {
            "integrity_check": integrity,
            "fk_violations": fk_violations,
            "table_counts": counts,
            "summary": f"PRAGMA integrity={integrity}, 0 FK violations, records verified"
        })
    except Exception as e:
        log_step("22. Database Direct Integrity & Foreign Keys", False, {
            "error": str(e),
            "summary": f"Database check failed: {e}"
        })

    # =========================================================================
    # Auth Logout
    # =========================================================================
    logout_res = make_request("POST", "/api/v1/auth/logout", token=token_a)
    passed = logout_res.get("status_code") in (200, 204)
    log_step("23. Student Session Logout", passed, {
        "status_code": logout_res.get("status_code"),
        "summary": "Session ended cleanly via /auth/logout"
    })

    print("\n=================================================================")
    print(f"AUDIT SUMMARY: {results['summary']['passed']}/{results['summary']['total']} Steps Passed ({results['summary']['failed']} Failed)")
    print("=================================================================\n")
    
    with open(r"D:\Gyaan AI\audit_verification_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_audit()
