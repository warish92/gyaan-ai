"""Unit tests for Gyaan AI FastAPI endpoints.

Covers schema validation, health check logic, and mocked error handling.
These unit tests do NOT execute live model inference.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure workspace root is in path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint_returns_structured_schema():
    """Verify GET /health returns valid structured HealthResponse schema."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert data["status"] in ["healthy", "degraded"]
    assert data["app"] == "ok"
    assert "ollama_connected" in data
    assert isinstance(data["ollama_connected"], bool)
    assert "model_available" in data
    assert isinstance(data["model_available"], bool)
    assert data["model_name"] == "qwen2.5:3b"


def test_health_endpoint_reports_degraded_when_ollama_unreachable():
    """Verify GET /health gracefully reports degraded when Ollama is down."""
    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection refused")):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["ollama_connected"] is False
        assert data["model_available"] is False
        assert "Connection refused" in data["details"]


def test_ask_rejects_empty_question():
    """Verify POST /api/v1/ask rejects empty or whitespace-only questions with 422."""
    response = client.post("/api/v1/ask", json={"question": "   "})
    assert response.status_code == 422


def test_ask_rejects_too_short_question():
    """Verify POST /api/v1/ask rejects questions with fewer than 3 characters."""
    response = client.post("/api/v1/ask", json={"question": "hi"})
    assert response.status_code == 422


def test_ask_returns_documented_schema_with_mocked_crew():
    """Verify POST /api/v1/ask returns the documented AskResponse schema.

    Uses a mock for the CrewAI kickoff to test the API boundary without LLM latency.
    """
    mock_result = MagicMock()
    mock_result.raw = "This is a mocked educational explanation about cells."

    with patch("backend.app.main.build_teacher_crew") as mock_builder:
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_result
        mock_builder.return_value = mock_crew

        payload = {
            "question": "What is the powerhouse of the cell?",
            "grade": "Class 10",
            "subject": "Biology",
            "language": "English",
        }
        response = client.post("/api/v1/ask", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert data["answer"] == "This is a mocked educational explanation about cells."
        assert "request_id" in data
        assert len(data["request_id"]) > 10
        assert data["model"] == "ollama/qwen2.5:3b"
        assert data["status"] == "success"
        assert "duration_ms" in data
        assert data["duration_ms"] >= 0

        # Verify arguments passed to builder
        mock_builder.assert_called_once_with(
            student_question="What is the powerhouse of the cell?",
            grade="Class 10",
            subject="Biology",
            language="English",
            chapter=None,
            topic=None,
            subtopic=None,
            learning_objectives=None,
            lesson_mode="conceptual",
        )


def test_ask_handles_crewai_failure_safely():
    """Verify POST /api/v1/ask returns HTTP 503 when CrewAI execution raises an exception."""
    with patch("backend.app.main.build_teacher_crew") as mock_builder:
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = RuntimeError("Simulated Ollama inference timeout")
        mock_builder.return_value = mock_crew

        payload = {"question": "Explain Newton's third law of motion."}
        response = client.post("/api/v1/ask", json=payload)

        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert "request_id" in detail
        assert "Simulated Ollama inference timeout" in detail["message"]


def test_learning_plan_rejects_empty_assessment_items():
    """Verify POST /api/v1/learning-plan rejects requests with empty assessment_items list."""
    payload = {
        "grade": "Class 10",
        "subject": "Chemistry",
        "topic": "Chemical Reactions",
        "assessment_items": [],
    }
    response = client.post("/api/v1/learning-plan", json=payload)
    assert response.status_code == 422


def test_learning_plan_rejects_blank_question_or_answer():
    """Verify POST /api/v1/learning-plan rejects items with blank question or answer."""
    payload = {
        "grade": "Class 10",
        "subject": "Chemistry",
        "topic": "Chemical Reactions",
        "assessment_items": [{"question": "What is rust?", "student_answer": "   "}],
    }
    response = client.post("/api/v1/learning-plan", json=payload)
    assert response.status_code == 422


def test_learning_plan_returns_documented_schema_with_mock():
    """Verify POST /api/v1/learning-plan returns valid LearningPlanResponse schema."""
    mock_workflow_output = {
        "diagnostic_report": "Demonstrated understanding: basic reactions. Gap: redox concepts.",
        "curriculum_plan": "Step 1: Oxidation definitions. Step 2: Practice problems.",
    }

    with patch("backend.app.main.run_learning_plan_workflow", return_value=mock_workflow_output):
        payload = {
            "display_name": "Test Student",
            "grade": "Class 10",
            "subject": "Science",
            "topic": "Chemical Reactions and Equations",
            "assessment_items": [
                {
                    "question": "What happens when magnesium ribbon burns in air?",
                    "student_answer": "It burns with white light and makes ash.",
                    "expected_answer": "Magnesium reacts with oxygen to form magnesium oxide (2Mg + O2 -> 2MgO).",
                }
            ],
        }
        response = client.post("/api/v1/learning-plan", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert "workflow_id" in data
        assert "student_id" in data
        assert data["diagnostic_report"] == mock_workflow_output["diagnostic_report"]
        assert data["curriculum_plan"] == mock_workflow_output["curriculum_plan"]
        assert data["status"] == "success"
        assert data["model"] == "ollama/qwen2.5:3b"
        assert "duration_ms" in data
        assert "persisted" in data
        assert isinstance(data["persisted"], bool)


def test_learning_plan_handles_workflow_failure():
    """Verify POST /api/v1/learning-plan returns HTTP 503 when workflow execution raises an error."""
    with patch("backend.app.main.run_learning_plan_workflow", side_effect=RuntimeError("Ollama CUDA Out Of Memory")):
        payload = {
            "grade": "Class 10",
            "subject": "Physics",
            "topic": "Electricity",
            "assessment_items": [
                {"question": "State Ohm's Law.", "student_answer": "V = IR"}
            ],
        }
        response = client.post("/api/v1/learning-plan", json=payload)

        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "Ollama CUDA Out Of Memory" in data["detail"]["message"]


# ==============================================================================
# Phase 4 Unit Tests: Resources, Quizzes, Assessment Submission & History
# ==============================================================================

def test_resources_endpoint_validation():
    """Verify POST /api/v1/resources rejects requests with missing or empty required fields."""
    response = client.post("/api/v1/resources", json={"grade": "Class 10"})
    assert response.status_code == 422


def test_resources_endpoint_success_with_mock():
    """Verify POST /api/v1/resources returns valid ResourceResponse schema."""
    mock_resource_result = {
        "resource_recommendation": "Study NCERT Class 10 Chapter 2: Acids, Bases and Salts.",
        "is_verified": True,
        "source_type": "verified_local",
        "sources": [
            {
                "title": "NCERT Class 10 Science - Chapter 2",
                "chapter": "Acids, Bases and Salts",
                "grade": "Class 10",
                "subject": "Science",
                "source_file": "ncert_class10_science.json",
            }
        ],
    }

    with patch("backend.app.main.run_resource_workflow", return_value=mock_resource_result):
        payload = {
            "grade": "Class 10",
            "subject": "Science",
            "topic": "Acids, Bases and Salts",
            "learning_objective": "Understand acid-base indicators.",
        }
        response = client.post("/api/v1/resources", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "workflow_id" in data
        assert data["resource_recommendation"] == mock_resource_result["resource_recommendation"]
        assert data["is_verified"] is True
        assert data["source_type"] == "verified_local"
        assert len(data["sources"]) == 1
        assert data["model"] == "ollama/qwen2.5:3b"
        assert "duration_ms" in data


def test_resources_endpoint_handles_failure():
    """Verify POST /api/v1/resources returns HTTP 503 on execution failure."""
    with patch("backend.app.main.run_resource_workflow", side_effect=RuntimeError("Retrieval error")):
        payload = {
            "grade": "Class 10",
            "subject": "Science",
            "topic": "Acids, Bases and Salts",
        }
        response = client.post("/api/v1/resources", json=payload)
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "Retrieval error" in data["detail"]["message"]


def test_quizzes_endpoint_validation():
    """Verify POST /api/v1/quizzes validates question bounds."""
    # num_questions too small (0)
    response = client.post(
        "/api/v1/quizzes",
        json={"grade": "Class 10", "subject": "Science", "topic": "Acids", "num_questions": 0},
    )
    assert response.status_code == 422

    # num_questions too large (> 10)
    response = client.post(
        "/api/v1/quizzes",
        json={"grade": "Class 10", "subject": "Science", "topic": "Acids", "num_questions": 15},
    )
    assert response.status_code == 422


def test_quizzes_endpoint_strips_answer_keys_from_student_response():
    """CRITICAL SECURITY CHECK: Verify POST /api/v1/quizzes never returns correct answers to students."""
    mock_workflow_output = {
        "questions": [
            {
                "id": "q1",
                "type": "multiple_choice",
                "question": "What is the pH of a neutral solution?",
                "options": ["A) 5", "B) 7", "C) 9", "D) 14"],
                "correct_answer": "B",
                "marks": 1.0,
                "explanation": "A pH of 7 is neutral on the pH scale at 25 degrees C.",
                "difficulty": "easy",
            },
            {
                "id": "q2",
                "type": "short_answer",
                "question": "Name the acid present in sting of an ant.",
                "options": [],
                "correct_answer": "Methanoic acid (formic acid)",
                "marks": 2.0,
                "explanation": "Ant stings contain methanoic acid which causes a burning sensation.",
                "difficulty": "medium",
            },
        ],
        "is_verified_source": True,
        "source_type": "verified_local",
    }

    with patch("backend.app.main.run_quiz_generation_workflow", return_value=mock_workflow_output), \
         patch("backend.app.main.save_quiz") as mock_save:

        payload = {
            "student_id": "test_stu_01",
            "grade": "Class 10",
            "subject": "Science",
            "topic": "Acids, Bases and Salts",
            "num_questions": 2,
        }
        response = client.post("/api/v1/quizzes", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "quiz_id" in data
        assert data["student_id"] == "test_stu_01"
        assert len(data["questions"]) == 2
        assert data["is_verified_source"] is True

        # Ensure correct_answer and explanation are NOT in the student-facing response
        for q in data["questions"]:
            assert "correct_answer" not in q
            assert "explanation" not in q
            assert "question" in q
            assert "options" in q
            assert "marks" in q
            assert "difficulty" in q

        # Verify full questions (with rubrics) WERE saved to SQLite
        mock_save.assert_called_once()
        saved_call = mock_save.call_args[1]
        assert saved_call["questions"][0]["correct_answer"] == "B"
        assert saved_call["questions"][0]["explanation"] == "A pH of 7 is neutral on the pH scale at 25 degrees C."


def test_quizzes_endpoint_handles_generation_failure():
    """Verify POST /api/v1/quizzes returns HTTP 503 on model or workflow failure."""
    with patch("backend.app.main.run_quiz_generation_workflow", side_effect=RuntimeError("LLM parse failure")):
        payload = {
            "grade": "Class 10",
            "subject": "Science",
            "topic": "Acids, Bases and Salts",
            "num_questions": 3,
        }
        response = client.post("/api/v1/quizzes", json=payload)
        assert response.status_code == 503
        data = response.json()
        assert "LLM parse failure" in data["detail"]["message"]


def test_assessments_submit_rejects_missing_quiz():
    """Verify POST /api/v1/assessments/submit returns 404 when quiz does not exist."""
    with patch("backend.app.main.get_quiz", return_value=None):
        payload = {
            "quiz_id": "nonexistent_quiz_999",
            "answers": {"q1": "Option B"},
        }
        response = client.post("/api/v1/assessments/submit", json=payload)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_assessments_submit_evaluates_and_persists_attempt():
    """Verify POST /api/v1/assessments/submit scores answers, returns feedback and persists attempt."""
    mock_stored_quiz = {
        "quiz_id": "quiz_abc123",
        "student_id": "student_01",
        "subject": "Science",
        "topic": "Acids, Bases and Salts",
        "grade": "Class 10",
        "questions": [
            {
                "id": "q1",
                "question": "What is the pH of a neutral solution?",
                "correct_answer": "7",
                "marks": 1.0,
            },
            {
                "id": "q2",
                "question": "Name the acid in ant stings.",
                "correct_answer": "Methanoic acid",
                "marks": 2.0,
            },
        ],
    }

    mock_eval_output = {
        "total_score": 3.0,
        "max_marks": 3.0,
        "overall_feedback": "Excellent performance! Both answers are precise and accurate.",
        "evaluations": [
            {
                "question_id": "q1",
                "score_awarded": 1.0,
                "max_marks": 1.0,
                "status": "correct",
                "student_answer": "7",
                "expected_answer": "7",
                "feedback": "Correct value for neutral solution.",
                "revision_topic": None,
            },
            {
                "question_id": "q2",
                "score_awarded": 2.0,
                "max_marks": 2.0,
                "status": "correct",
                "student_answer": "Methanoic acid",
                "expected_answer": "Methanoic acid",
                "feedback": "Correct common chemical name provided.",
                "revision_topic": None,
            },
        ],
    }

    with patch("backend.app.main.get_quiz", return_value=mock_stored_quiz), \
         patch("backend.app.main.run_answer_evaluation_workflow", return_value=mock_eval_output), \
         patch("backend.app.main.save_assessment_attempt") as mock_save_attempt:

        payload = {
            "quiz_id": "quiz_abc123",
            "student_id": "student_01",
            "answers": {
                "q1": "7",
                "q2": "Methanoic acid",
            },
        }
        response = client.post("/api/v1/assessments/submit", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "attempt_id" in data
        assert data["quiz_id"] == "quiz_abc123"
        assert data["total_score"] == 3.0
        assert data["max_marks"] == 3.0
        assert data["percentage"] == 100.0
        assert len(data["evaluations"]) == 2
        assert data["evaluations"][0]["score_awarded"] == 1.0
        assert data["evaluations"][1]["score_awarded"] == 2.0
        assert data["overall_feedback"] == mock_eval_output["overall_feedback"]
        assert data["persisted"] is True

        mock_save_attempt.assert_called_once()


def test_assessments_submit_handles_evaluation_error():
    """Verify POST /api/v1/assessments/submit returns HTTP 503 on evaluation workflow error."""
    mock_stored_quiz = {
        "quiz_id": "quiz_error_case",
        "questions": [{"id": "q1", "question": "Test", "correct_answer": "Ans", "marks": 1.0}],
    }

    with patch("backend.app.main.get_quiz", return_value=mock_stored_quiz), \
         patch("backend.app.main.run_answer_evaluation_workflow", side_effect=RuntimeError("Evaluation model crash")):

        payload = {
            "quiz_id": "quiz_error_case",
            "answers": {"q1": "Ans"},
        }
        response = client.post("/api/v1/assessments/submit", json=payload)
        assert response.status_code == 503
        data = response.json()
        assert "Evaluation model crash" in data["detail"]["message"]


def test_assessment_history_endpoint():
    """Verify GET /api/v1/assessments/history/{student_id} returns student historical attempts for authenticated owner."""
    mock_history_records = [
        {
            "attempt_id": "att_01",
            "quiz_id": "quiz_01",
            "student_id": "student_deep",
            "subject": "Science",
            "topic": "Acids and Bases",
            "grade": "Class 10",
            "score": 3.0,
            "max_marks": 3.0,
            "created_at": "2026-10-29T12:00:00",
            "evaluation_details": {"summary": "Great"},
        }
    ]

    from backend.app.main import get_current_student
    app.dependency_overrides[get_current_student] = lambda: {"id": "student_deep", "email": "student_deep@example.com", "role": "student"}
    try:
        with patch("backend.app.main.get_student_assessment_history", return_value=mock_history_records):
            response = client.get("/api/v1/assessments/history/student_deep")
            assert response.status_code == 200
            data = response.json()

            assert data["student_id"] == "student_deep"
            assert data["total_attempts"] == 1
            assert len(data["attempts"]) == 1
            assert data["attempts"][0]["attempt_id"] == "att_01"
            assert data["attempts"][0]["score"] == 3.0
    finally:
        app.dependency_overrides.pop(get_current_student, None)


# ==============================================================================
# Phase 7: Orchestrator Endpoint Tests
# ==============================================================================

def test_orchestrate_endpoint_validation():
    """Verify that POST /api/v1/orchestrate validates request input and rejects empty text."""
    # Empty request
    resp = client.post("/api/v1/orchestrate", json={"request": ""})
    assert resp.status_code == 422

    # Too short
    resp = client.post("/api/v1/orchestrate", json={"request": "a"})
    assert resp.status_code == 422


def test_orchestrate_endpoint_success_with_mock():
    """Verify that POST /api/v1/orchestrate returns valid OrchestrationResponse with mock pipeline."""
    from backend.app.schemas import OrchestrationResponse

    mock_response = OrchestrationResponse(
        request_id="mock-req-1",
        workflow_id="wf_mock_1",
        detected_intent="Tutoring query on acids",
        selected_workflow="teacher_answer",
        selected_agents=["Teacher Agent"],
        routing_reason="Tutoring request.",
        clarification_required=False,
        clarification_question=None,
        result={"answer": "Acids are substances with pH < 7."},
        status="success",
        duration_ms=120.0,
        model="ollama/qwen2.5:3b",
    )

    with patch("backend.app.main.execute_orchestrated_pipeline", return_value=mock_response):
        resp = client.post("/api/v1/orchestrate", json={"request": "Explain what acids are"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"] == "mock-req-1"
        assert data["selected_workflow"] == "teacher_answer"
        assert data["selected_agents"] == ["Teacher Agent"]
        assert data["result"]["answer"] == "Acids are substances with pH < 7."
        assert data["status"] == "success"


def test_orchestrate_endpoint_clarification_response():
    """Verify that POST /api/v1/orchestrate returns clarification_needed status when clarification requested."""
    from backend.app.schemas import OrchestrationResponse

    mock_response = OrchestrationResponse(
        request_id="mock-req-2",
        workflow_id="wf_mock_2",
        detected_intent="Ambiguous query",
        selected_workflow="teacher_answer",
        selected_agents=["Teacher Agent"],
        routing_reason="Ambiguous.",
        clarification_required=True,
        clarification_question="What specific concept would you like to review?",
        result=None,
        status="clarification_needed",
        duration_ms=85.0,
        model="ollama/qwen2.5:3b",
    )

    with patch("backend.app.main.execute_orchestrated_pipeline", return_value=mock_response):
        resp = client.post("/api/v1/orchestrate", json={"request": "help please"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "clarification_needed"
        assert data["clarification_required"] is True
        assert data["clarification_question"] == "What specific concept would you like to review?"
        assert data["result"] is None


def test_orchestrate_endpoint_handles_pipeline_failure():
    """Verify that POST /api/v1/orchestrate handles pipeline exceptions and returns HTTP 503."""
    with patch("backend.app.main.execute_orchestrated_pipeline", side_effect=RuntimeError("Ollama timeout")):
        resp = client.post("/api/v1/orchestrate", json={"request": "Explain chemical bonding"})
        assert resp.status_code == 503
        data = resp.json()
        assert "Failed to orchestrate educational request" in data["detail"]["error"]


# ==============================================================================
# Phase 8.2: CORS Preflight and Origin Validation Tests
# ==============================================================================

def test_cors_preflight_allowed_origins():
    """Verify CORS preflight OPTIONS requests succeed for approved local frontend origins."""
    for origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
        resp = client.options(
            "/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == origin
        assert "GET" in resp.headers.get("access-control-allow-methods", "")
        assert "Authorization" in resp.headers.get("access-control-allow-headers", "")


def test_cors_preflight_disallowed_origin():
    """Verify CORS preflight requests from unapproved origins do not receive allow headers."""
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://malicious-site.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # FastAPI returns 400 or omits access-control-allow-origin for invalid CORS preflights
    assert resp.headers.get("access-control-allow-origin") is None




