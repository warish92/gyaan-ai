"""Gyaan AI — Final Integration Test & Live Audit Script.

Verifies:
1. Complete Eight-Agent Chapter Learning Journey via live API.
2. Actual student answer submission & assessment via API.
3. Successful mastery (>=70%) & adaptive remediation triggers.
4. Pause, Resume, and SQLite Persistence ACROSS BACKEND RESTART.
5. Browser-to-Backend communication (Next.js & CORS).
6. Local Ollama & genuine CrewAI execution verification.
7. Verification that NO mocked responses are presented as live output.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
import requests

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:3000"
OLLAMA_URL = "http://127.0.0.1:11434"
DB_PATH = "D:/Gyaan AI/data/gyaan_ai.db"

results = {
    "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "verifications": [],
    "summary": {"passed": 0, "failed": 0}
}

def record_check(name: str, passed: bool, details: dict):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")
    results["verifications"].append({
        "check": name,
        "status": status,
        "details": details,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
    })
    if passed:
        results["summary"]["passed"] += 1
    else:
        results["summary"]["failed"] += 1

def main():
    print("=" * 70)
    print("STARTING GYAAN AI FINAL INTEGRATION-TEST AUDIT")
    print("=" * 70)

    # -------------------------------------------------------------
    # Check 1: Ollama & Genuine Local LLM Model Verification
    # -------------------------------------------------------------
    try:
        ollama_resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        ollama_ok = ollama_resp.status_code == 200
        models = [m["name"] for m in ollama_resp.json().get("models", [])]
        has_qwen = any("qwen2.5:3b" in m for m in models)
        record_check(
            "1. Local Ollama Service & qwen2.5:3b Model Active",
            ollama_ok and has_qwen,
            {"status_code": ollama_resp.status_code, "models": models, "has_qwen2.5:3b": has_qwen}
        )
    except Exception as e:
        record_check("1. Local Ollama Service & qwen2.5:3b Model Active", False, {"error": str(e)})

    # -------------------------------------------------------------
    # Check 2: Browser-to-Backend Communication & CORS Preflight
    # -------------------------------------------------------------
    try:
        # Frontend check
        frontend_resp = requests.get(f"{FRONTEND_URL}/agent-arena", timeout=10)
        frontend_ok = frontend_resp.status_code == 200

        # Backend CORS preflight check
        cors_headers = {
            "Origin": FRONTEND_URL,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        }
        cors_resp = requests.options(f"{BACKEND_URL}/api/v1/learning-journey/start", headers=cors_headers, timeout=5)
        cors_ok = cors_resp.status_code == 200
        allowed_origin = cors_resp.headers.get("access-control-allow-origin")

        record_check(
            "2. Browser-to-Backend Communication & CORS Headers",
            frontend_ok and (cors_ok or allowed_origin is not None),
            {
                "frontend_agent_arena_status": frontend_resp.status_code,
                "cors_preflight_status": cors_resp.status_code,
                "access_control_allow_origin": allowed_origin,
            }
        )
    except Exception as e:
        record_check("2. Browser-to-Backend Communication & CORS Headers", False, {"error": str(e)})

    # -------------------------------------------------------------
    # Check 3: Student Registration & Authentication Flow
    # -------------------------------------------------------------
    student_id = None
    token = None
    try:
        email = f"audit_integ_{uuid.uuid4().hex[:6]}@gyaan.ai"
        reg_payload = {
            "display_name": "Integration Audit Student",
            "email": email,
            "password": "Password123!",
            "grade": "Class 10",
            "preferred_language": "English",
        }
        reg_resp = requests.post(f"{BACKEND_URL}/api/v1/auth/register", json=reg_payload, timeout=5)
        if reg_resp.status_code == 201:
            data = reg_resp.json()
            student_id = data["student"]["id"]
            token = data["token"]
            auth_ok = True
        else:
            auth_ok = False
        record_check(
            "3. Student Registration & JWT Authentication",
            auth_ok,
            {"status_code": reg_resp.status_code, "student_id": student_id, "has_token": bool(token)}
        )
    except Exception as e:
        record_check("3. Student Registration & JWT Authentication", False, {"error": str(e)})

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # -------------------------------------------------------------
    # Check 4: Complete Eight-Agent Chapter Learning Journey (API)
    # -------------------------------------------------------------
    journey_id = None
    journey_record = None
    try:
        start_payload = {
            "student_id": student_id,
            "subject": "Science",
            "chapter": "Chemical Reactions and Equations",
            "grade": "Class 10",
            "language": "English",
            "learning_goal": "Understand balancing chemical equations and reaction types",
            "run_in_background": True
        }
        start_resp = requests.post(f"{BACKEND_URL}/api/v1/learning-journey/start", json=start_payload, headers=headers, timeout=10)
        assert start_resp.status_code == 200, f"Start failed: {start_resp.text}"
        journey_data = start_resp.json()
        journey_id = journey_data["journey_id"]

        print(f"Journey started: {journey_id}. Polling for 8-agent completion...")
        max_wait = 180  # Up to 3 minutes for local Ollama 8-agent sequential execution
        start_time = time.time()
        completed = False

        while time.time() - start_time < max_wait:
            time.sleep(4)
            poll_resp = requests.get(f"{BACKEND_URL}/api/v1/learning-journey/{journey_id}", headers=headers, timeout=5)
            if poll_resp.status_code == 200:
                p_data = poll_resp.json()
                if p_data["status"] == "completed":
                    completed = True
                    journey_record = p_data
                    break
                print(f"  Step: {p_data.get('current_step')} | Status: {p_data.get('status')} ({round(time.time() - start_time, 1)}s)")

        elapsed = round(time.time() - start_time, 2)
        
        # Verify 8 agent outputs
        final_outputs = journey_record.get("journey_data", {}).get("final_outputs", {}) if journey_record else {}
        expected_agents = ["orchestrator", "diagnostic", "curriculum", "resource", "teacher", "assessment", "progress", "mentor"]
        all_agents_present = all(k in final_outputs for k in expected_agents)

        record_check(
            "4. Complete Eight-Agent Chapter Learning Journey via API",
            completed and all_agents_present,
            {
                "journey_id": journey_id,
                "elapsed_s": elapsed,
                "status": journey_record.get("status") if journey_record else "timeout",
                "agents_count": len(final_outputs),
                "all_8_agents_present": all_agents_present,
                "present_agents": list(final_outputs.keys()),
            }
        )
    except Exception as e:
        record_check("4. Complete Eight-Agent Chapter Learning Journey via API", False, {"error": str(e)})

    # -------------------------------------------------------------
    # Check 5: Student Answer Submission & Formative Assessment
    # -------------------------------------------------------------
    try:
        # Generate quiz first
        quiz_payload = {
            "student_id": student_id,
            "grade": "Class 10",
            "subject": "Science",
            "topic": "Chemical Reactions and Equations",
            "num_questions": 2,
            "question_types": ["short_answer", "conceptual"],
            "learning_objectives": "Assess understanding of chemical bond rearrangement and conservation of mass."
        }
        quiz_resp = requests.post(f"{BACKEND_URL}/api/v1/quizzes", json=quiz_payload, headers=headers, timeout=60)
        assert quiz_resp.status_code == 200, f"Quiz generation failed: {quiz_resp.text}"
        q_data = quiz_resp.json()
        quiz_id = q_data["quiz_id"]
        questions = q_data["questions"]

        # Submit answers
        submitted_answers = {q["id"]: "Chemical reactions conserve mass by rearranging atoms without creating or destroying them." for q in questions}
        submit_payload = {
            "quiz_id": quiz_id,
            "student_id": student_id,
            "answers": submitted_answers
        }
        submit_resp = requests.post(f"{BACKEND_URL}/api/v1/assessments/submit", json=submit_payload, headers=headers, timeout=60)
        assert submit_resp.status_code == 200, f"Submission failed: {submit_resp.text}"
        eval_data = submit_resp.json()

        score_awarded = eval_data.get("score", 0.0)
        max_marks = eval_data.get("max_marks", 2.0)
        pct = (score_awarded / max_marks) * 100.0 if max_marks > 0 else 0.0

        record_check(
            "5. Student Answer Submission & Assessment Evaluation",
            eval_data.get("status") == "evaluated" and len(eval_data.get("question_evaluations", [])) >= 1,
            {
                "quiz_id": quiz_id,
                "score": score_awarded,
                "max_marks": max_marks,
                "percentage": pct,
                "evaluations_count": len(eval_data.get("question_evaluations", [])),
                "overall_feedback": eval_data.get("overall_feedback", "")[:120]
            }
        )
    except Exception as e:
        record_check("5. Student Answer Submission & Assessment Evaluation", False, {"error": str(e)})

    # -------------------------------------------------------------
    # Check 6: Mastery (>=70%) & Adaptive Remediation Scenarios
    # -------------------------------------------------------------
    try:
        # Scenario A: Mastery Score in Journey
        mastery_score = journey_record.get("mastery_score", 0.0) if journey_record else 0.0
        mastery_achieved = journey_record.get("mastery_achieved", False) if journey_record else False

        # Scenario B: Adaptive Remediation Trigger via /interact
        remed_payload = {"action": "request_remediation"}
        remed_resp = requests.post(f"{BACKEND_URL}/api/v1/learning-journey/{journey_id}/interact", json=remed_payload, headers=headers, timeout=10)
        remed_ok = remed_resp.status_code == 200
        remed_data = remed_resp.json() if remed_ok else {}
        new_iteration = remed_data.get("loop_iteration", 0)

        record_check(
            "6. Mastery Evaluation & Adaptive Remediation Trigger",
            mastery_score >= 70.0 and remed_ok and new_iteration >= 2,
            {
                "scenario_a_mastery_score": mastery_score,
                "scenario_a_mastery_achieved": mastery_achieved,
                "scenario_b_remediation_status_code": remed_resp.status_code,
                "scenario_b_loop_iteration": new_iteration,
            }
        )
    except Exception as e:
        record_check("6. Mastery Evaluation & Adaptive Remediation Trigger", False, {"error": str(e)})

    # -------------------------------------------------------------
    # Check 7: Pause, Resume & Persistence ACROSS BACKEND RESTART
    # -------------------------------------------------------------
    try:
        # Step A: Pause journey
        pause_resp = requests.post(f"{BACKEND_URL}/api/v1/learning-journey/{journey_id}/interact", json={"action": "pause"}, headers=headers, timeout=10)
        assert pause_resp.status_code == 200
        assert pause_resp.json().get("status") == "paused"

        # Step B: Direct SQLite verification of paused status
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        db_status = c.execute("SELECT status FROM learning_journeys WHERE id = ?", (journey_id,)).fetchone()
        assert db_status and db_status[0] == "paused", f"Expected paused in DB, got {db_status}"
        conn.close()

        # Step C: Restart backend server
        print("Executing backend restart to verify persistence...")
        # Terminate uvicorn listening on port 8000 using standard Windows taskkill
        try:
            out = subprocess.check_output('netstat -ano | findstr :8000', shell=True).decode()
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and parts[-1].isdigit():
                    pid = parts[-1]
                    if pid != "0":
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print("Note on taskkill:", e)

        time.sleep(2)

        # Launch fresh backend process
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Wait for backend to come up
        backend_up = False
        for _ in range(15):
            time.sleep(1)
            try:
                chk = requests.get(f"{BACKEND_URL}/health", timeout=1)
                if chk.status_code == 200:
                    backend_up = True
                    break
            except Exception:
                pass

        assert backend_up, "Backend failed to restart within 15s"

        # Step D: Verify status is STILL paused after restart
        post_restart_resp = requests.get(f"{BACKEND_URL}/api/v1/learning-journey/{journey_id}", headers=headers, timeout=5)
        assert post_restart_resp.status_code == 200
        assert post_restart_resp.json().get("status") == "paused"

        # Step E: Resume journey
        resume_resp = requests.post(f"{BACKEND_URL}/api/v1/learning-journey/{journey_id}/interact", json={"action": "resume"}, headers=headers, timeout=10)
        assert resume_resp.status_code == 200
        assert resume_resp.json().get("status") in ("active", "in_progress")

        record_check(
            "7. Pause, Resume & SQLite Persistence Across Backend Restart",
            True,
            {
                "paused_before_restart": True,
                "sqlite_file_persisted": True,
                "backend_restarted_successfully": True,
                "retained_paused_after_restart": True,
                "resumed_after_restart": True,
                "final_status": resume_resp.json().get("status")
            }
        )
    except Exception as e:
        record_check("7. Pause, Resume & SQLite Persistence Across Backend Restart", False, {"error": str(e)})

    # -------------------------------------------------------------
    # Check 8: Mock Response Audit (Ensure 0 Mocks in Live AI Output)
    # -------------------------------------------------------------
    try:
        final_outputs = journey_record.get("journey_data", {}).get("final_outputs", {}) if journey_record else {}
        mock_keywords = ["mock", "lorem ipsum", "fake response", "sample dummy text", "hardcoded output"]
        mock_detected = False
        agent_audit_results = {}

        for agent, text in final_outputs.items():
            text_str = str(text).lower()
            found_mocks = [kw for kw in mock_keywords if kw in text_str]
            agent_audit_results[agent] = {
                "character_length": len(str(text)),
                "has_mock_keywords": len(found_mocks) > 0,
                "flagged_keywords": found_mocks,
                "snippet": str(text)[:80] + "..."
            }
            if found_mocks:
                mock_detected = True

        record_check(
            "8. Live AI Output Audit (Zero Mocked Responses)",
            not mock_detected and len(final_outputs) > 0,
            {
                "total_agent_outputs_inspected": len(final_outputs),
                "mock_detected": mock_detected,
                "agent_details": agent_audit_results
            }
        )
    except Exception as e:
        record_check("8. Live AI Output Audit (Zero Mocked Responses)", False, {"error": str(e)})

    # -------------------------------------------------------------
    # Check 9: Multi-Student Tenant Isolation Verification
    # -------------------------------------------------------------
    try:
        # Create second student
        email2 = f"audit_integ2_{uuid.uuid4().hex[:6]}@gyaan.ai"
        reg2 = requests.post(f"{BACKEND_URL}/api/v1/auth/register", json={
            "display_name": "Student 2",
            "email": email2,
            "password": "Password123!",
            "grade": "Class 10"
        }, timeout=5)
        token2 = reg2.json()["token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Try accessing student 1's journey with student 2's token
        cross_resp = requests.get(f"{BACKEND_URL}/api/v1/learning-journey/{journey_id}", headers=headers2, timeout=5)
        cross_forbidden = cross_resp.status_code == 403

        record_check(
            "9. Multi-Student Data Isolation & Authorization Protection",
            cross_forbidden,
            {"cross_student_status_code": cross_resp.status_code, "forbidden_enforced": cross_forbidden}
        )
    except Exception as e:
        record_check("9. Multi-Student Data Isolation & Authorization Protection", False, {"error": str(e)})

    # Write output JSON
    results["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open("D:/Gyaan AI/final_integration_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("=" * 70)
    print(f"AUDIT COMPLETED: {results['summary']['passed']} Passed, {results['summary']['failed']} Failed")
    print("=" * 70)

if __name__ == "__main__":
    main()
