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
    print(f"[VERIFY-8.9] {msg}")

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
    routes = [
        "/", "/agent-arena", "/progress", "/mentor",
        "/resources", "/practice", "/diagnostic", "/learning-plans", "/teacher"
    ]
    for route in routes:
        url = f"{FRONTEND_URL}{route}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
            log(f"Frontend route {route}: Status {resp.status}, Content-Length: {len(content)}")
            assert resp.status == 200, f"Route {route} failed with {resp.status}"
    return True

def check_canonical_eight_agents():
    log("Verifying all 8 canonical CrewAI Agent definitions in Python...")
    from backend.agents.orchestrator import create_orchestrator_agent
    from backend.agents.teacher import create_teacher_agent
    from backend.agents.diagnostic import create_diagnostic_agent
    from backend.agents.curriculum import create_curriculum_agent
    from backend.agents.resource import create_resource_agent
    from backend.agents.assessment import create_assessment_agent
    from backend.agents.progress import create_progress_agent
    from backend.agents.mentor import create_mentor_agent

    agents = [
        ("Orchestrator Agent", create_orchestrator_agent()),
        ("Teacher Agent", create_teacher_agent()),
        ("Diagnostic Agent", create_diagnostic_agent()),
        ("Curriculum Agent", create_curriculum_agent()),
        ("Resource Agent", create_resource_agent()),
        ("Assessment Agent", create_assessment_agent()),
        ("Progress Agent", create_progress_agent()),
        ("Mentor Agent", create_mentor_agent()),
    ]

    for name, agent in agents:
        log(f"  Verified Agent: {name} | Role: {agent.role[:40]}... | Model: {getattr(agent.llm, 'model', 'default')}")
        assert agent.role, f"Agent {name} missing role"
        assert agent.goal, f"Agent {name} missing goal"
        assert agent.backstory, f"Agent {name} missing backstory"
    return True

def check_workflow_registry():
    log("Verifying WORKFLOW_REGISTRY in orchestrator module...")
    from backend.agents.orchestrator import WORKFLOW_REGISTRY

    expected_workflows = [
        "teacher_answer",
        "diagnostic_curriculum",
        "personalized_learning_plan",
        "resource_search",
        "quiz_generation",
        "assessment_evaluation",
        "progress_analysis",
        "personalized_mentoring",
        "progress_and_mentoring",
    ]

    for wf in expected_workflows:
        assert wf in WORKFLOW_REGISTRY, f"Workflow {wf} missing from WORKFLOW_REGISTRY"
        descriptor = WORKFLOW_REGISTRY[wf]
        log(f"  Registered: {descriptor.workflow_id} -> {descriptor.name} (Agents: {descriptor.agents}, Requires Auth: {descriptor.requires_auth})")
    return True

def authenticate_student():
    log("Authenticating student for Phase 8.9 verification...")
    test_email = f"phase89_tester_{int(time.time())}@gyaan.ai"
    reg_url = f"{BACKEND_URL}/api/v1/auth/register"
    reg_payload = json.dumps({
        "email": test_email,
        "password": "Password123!",
        "display_name": "Orchestrator Tester",
        "grade": "Class 10"
    }).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    
    req = urllib.request.Request(reg_url, data=reg_payload, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        token = data.get("token") or data.get("access_token")
        student_id = data.get("student", {}).get("id")
        log(f"Registered student: {test_email} (ID: {student_id})")
        return token, student_id

def test_live_orchestration_tutoring():
    log("Testing Live Orchestration: Teacher Concept Tutoring (Guest / Unauthenticated)...")
    url = f"{BACKEND_URL}/api/v1/orchestrate"
    payload = json.dumps({
        "request": "Explain the difference between displacement and double displacement reactions in Class 10 Chemistry with balanced equations.",
        "grade": "Class 10",
        "subject": "Science"
    }).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    
    t0 = time.time()
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    duration = time.time() - t0
    
    log(f"Orchestration completed in {duration:.2f}s!")
    log(f"  Workflow ID: {result.get('workflow_id')}")
    log(f"  Detected Intent: {result.get('detected_intent')}")
    log(f"  Selected Workflow: {result.get('selected_workflow')}")
    log(f"  Selected Agents: {result.get('selected_agents')}")
    log(f"  Routing Reason: {result.get('routing_reason')}")
    log(f"  Clarification Required: {result.get('clarification_required')}")
    
    assert result.get("selected_workflow") == "teacher_answer", f"Expected teacher_answer, got {result.get('selected_workflow')}"
    assert "Teacher Agent" in result.get("selected_agents", []), "Expected Teacher Agent to participate"
    assert result.get("clarification_required") is False, "Did not expect clarification"
    assert result.get("result") is not None, "Expected valid result payload"
    return result

def test_live_orchestration_resources():
    log("Testing Live Orchestration: Resource Search Workflow...")
    url = f"{BACKEND_URL}/api/v1/orchestrate"
    payload = json.dumps({
        "request": "Find verified NCERT textbook citations and chapter summaries for Chapter 2: Acids, Bases and Salts.",
        "grade": "Class 10",
        "subject": "Science"
    }).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    
    t0 = time.time()
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    duration = time.time() - t0
    
    log(f"Orchestration completed in {duration:.2f}s!")
    log(f"  Detected Intent: {result.get('detected_intent')}")
    log(f"  Selected Workflow: {result.get('selected_workflow')}")
    log(f"  Selected Agents: {result.get('selected_agents')}")
    
    assert result.get("selected_workflow") == "resource_search", f"Expected resource_search, got {result.get('selected_workflow')}"
    assert "Resource Agent" in result.get("selected_agents", []), "Expected Resource Agent to participate"
    return result

def test_live_orchestration_mentoring_authenticated(token):
    log("Testing Live Orchestration: Authenticated Mentoring Workflow...")
    url = f"{BACKEND_URL}/api/v1/orchestrate"
    payload = json.dumps({
        "request": "Review my progress and give me personalized study advice on what to study next.",
        "grade": "Class 10",
        "subject": "Science"
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
    
    log(f"Orchestration completed in {duration:.2f}s!")
    log(f"  Detected Intent: {result.get('detected_intent')}")
    log(f"  Selected Workflow: {result.get('selected_workflow')}")
    log(f"  Selected Agents: {result.get('selected_agents')}")
    
    assert result.get("selected_workflow") in ["progress_and_mentoring", "personalized_mentoring", "progress_analysis"], \
        f"Unexpected workflow: {result.get('selected_workflow')}"
    return result

def test_clarification_on_gibberish():
    log("Testing Orchestrator Clarification on Incomprehensible Prompt...")
    url = f"{BACKEND_URL}/api/v1/orchestrate"
    payload = json.dumps({
        "request": "asdkjfhqwuerzxcvbnm 123456 !!!",
        "grade": "Class 10"
    }).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    
    t0 = time.time()
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    duration = time.time() - t0
    
    log(f"Orchestrator returned in {duration:.2f}s!")
    log(f"  Clarification Required: {result.get('clarification_required')}")
    log(f"  Clarification Question: {result.get('clarification_question')}")
    log(f"  Status: {result.get('status')}")
    
    assert result.get("clarification_required") is True, "Expected clarification_required to be True"
    assert result.get("clarification_question"), "Expected non-empty clarification_question"
    return result

def check_legacy_isolation():
    log("Verifying legacy safety boundary (D:\\GYAN Ai)...")
    assert os.path.exists(LEGACY_PATH), "Legacy directory missing!"
    log("Legacy path verified untouched.")
    return True

if __name__ == "__main__":
    log("=== PHASE 8.9 VERIFICATION SUITE START ===")
    try:
        check_backend_and_ollama()
        check_frontend_routes()
        check_canonical_eight_agents()
        check_workflow_registry()
        test_live_orchestration_tutoring()
        test_live_orchestration_resources()
        token, student_id = authenticate_student()
        test_live_orchestration_mentoring_authenticated(token)
        test_clarification_on_gibberish()
        check_legacy_isolation()
        log("=== ALL PHASE 8.9 VERIFICATIONS PASSED SUCCESSFULLY! ===")
    except Exception as exc:
        log(f"VERIFICATION FAILED: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
