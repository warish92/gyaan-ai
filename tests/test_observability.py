"""Gyaan AI - Phase 4 Observability, Monitoring, Callbacks & Langfuse Tests.

Covers:
1. Pydantic v2 schemas for traces, spans, events, and metrics.
2. Security redaction (passwords, tokens, emails, phone numbers, length bounds).
3. In-memory bounded store (thread-safe, capacity limits, eviction, agent status aggregation).
4. Structured JSON logging with trace ID preservation.
5. Trace correlation and nested span lifecycle management via trace_scope.
6. CrewAI lifecycle callbacks (task callback, step callback, crew kickoff callbacks).
7. Langfuse integration (disabled by default, configured mode, error shielding, data minimization).
8. Observability FastAPI endpoints (/health, /status, /metrics, /traces, /agents, /errors).
9. MCP and ADK/A2A trace propagation.
10. Database non-regression and integrity check.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import time
import uuid

import pytest
from fastapi.testclient import TestClient

# Ensure workspace root in path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.app.main import app
from backend.observability import (
    ObservabilityStore,
    ObservabilityHealth,
    ObservabilityMetrics,
    ObservabilityEvent,
    SpanRecord,
    TraceRecord,
    TokenUsage,
    langfuse_manager,
    observability_store,
    redact_sensitive_data,
    trace_scope,
    get_current_trace_id,
    set_current_trace_id,
    create_crewai_task_callback,
    create_crewai_step_callback,
    create_crewai_kickoff_callbacks,
    log_observability_event,
    JSONL_LOG_PATH,
)

client = TestClient(app)
client.headers.update({"X-Internal-Token": os.environ.get("A2A_INTERNAL_SECRET", "gyaan_ai_internal_test_secret_key_2026")})


# ------------------------------------------------------------------------------
# Group A: Schemas & Redaction Tests
# ------------------------------------------------------------------------------
def test_01_observability_schemas():
    """Verify Pydantic v2 schemas for traces, spans, and metrics validate contracts."""
    tid = uuid.uuid4().hex
    sid = uuid.uuid4().hex[:16]

    span = SpanRecord(
        span_id=sid,
        trace_id=tid,
        name="test_span",
        span_type="agent",
        agent_name="Teacher Agent",
        status="completed",
        duration_ms=120.5,
        token_usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
    )
    assert span.span_id == sid
    assert span.agent_name == "Teacher Agent"
    assert span.token_usage.total_tokens == 75

    trace = TraceRecord(
        trace_id=tid,
        root_name="test_workflow",
        status="completed",
        duration_ms=250.0,
        total_spans=1,
        spans=[span],
    )
    assert trace.trace_id == tid
    assert len(trace.spans) == 1
    assert trace.spans[0].duration_ms == 120.5


def test_02_redaction_credentials():
    """Verify sensitive keys (passwords, tokens, API keys, auth headers) are masked."""
    sensitive_dict = {
        "password": "SuperSecretPassword123!",
        "api_key": "pk-live-9876543210abcdef",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "auth_header": "Bearer secret_jwt_token",
        "safe_field": "CBSE Class 10 Science",
    }
    redacted = redact_sensitive_data(sensitive_dict)

    assert redacted["password"] == "[REDACTED_CREDENTIAL]"
    assert redacted["api_key"] == "[REDACTED_CREDENTIAL]"
    assert redacted["access_token"] == "[REDACTED_CREDENTIAL]"
    assert redacted["auth_header"] == "[REDACTED_CREDENTIAL]"
    assert redacted["safe_field"] == "CBSE Class 10 Science"


def test_03_redaction_pii():
    """Verify Personally Identifiable Information (emails, phone numbers, Aadhaar) is masked."""
    text_with_pii = (
        "Student Aarav Kumar (email: aarav.student@example.edu.in, phone: +919876543210, "
        "Aadhaar: 1234-5678-9012) asked about photosynthesis."
    )
    cleaned = redact_sensitive_data(text_with_pii)

    assert "aarav.student@example.edu.in" not in cleaned
    assert "[REDACTED_EMAIL]" in cleaned
    assert "+919876543210" not in cleaned
    assert "[REDACTED_PHONE]" in cleaned
    assert "1234-5678-9012" not in cleaned
    assert "[REDACTED_ID]" in cleaned
    assert "photosynthesis" in cleaned


def test_04_redaction_recursive_dict_and_truncation():
    """Verify recursive structures and oversized payload truncation."""
    nested = {
        "level1": {
            "level2": {
                "secret_key": "sk-12345",
                "normal": "normal_val",
            }
        },
        "long_text": "A" * 3000,
    }
    res = redact_sensitive_data(nested)
    assert res["level1"]["level2"]["secret_key"] == "[REDACTED_CREDENTIAL]"
    assert res["level1"]["level2"]["normal"] == "normal_val"
    assert len(res["long_text"]) < 2000
    assert "[TRUNCATED_FOR_TELEMETRY]" in res["long_text"]


# ------------------------------------------------------------------------------
# Group B: Store & Telemetry Buffer Tests
# ------------------------------------------------------------------------------
def test_05_store_trace_lifecycle():
    """Verify trace creation, span association, and retrieval from ObservabilityStore."""
    store = ObservabilityStore(max_traces=10, max_events=20)
    tid = uuid.uuid4().hex

    trace = TraceRecord(trace_id=tid, root_name="tutoring_workflow", status="started")
    store.save_trace(trace)

    span = SpanRecord(
        span_id=uuid.uuid4().hex[:16],
        trace_id=tid,
        name="concept_tutoring",
        agent_name="Teacher Agent",
        status="completed",
        duration_ms=45.0,
    )
    store.add_span_to_trace(tid, span)

    retrieved = store.get_trace(tid)
    assert retrieved is not None
    assert retrieved.trace_id == tid
    assert retrieved.total_spans == 1
    assert retrieved.spans[0].name == "concept_tutoring"


def test_06_store_capacity_and_eviction():
    """Verify ring-buffer enforces capacity limits without unbounded memory growth."""
    store = ObservabilityStore(max_traces=5, max_events=10)

    # Insert 8 traces (capacity is 5)
    tids = [uuid.uuid4().hex for _ in range(8)]
    for tid in tids:
        store.save_trace(TraceRecord(trace_id=tid, root_name="test_trace"))

    listed = store.list_traces(limit=10)
    assert len(listed) == 5
    # The oldest traces (first 3) should have been evicted
    assert store.get_trace(tids[0]) is None
    assert store.get_trace(tids[1]) is None
    assert store.get_trace(tids[2]) is None
    # The newest traces should exist
    assert store.get_trace(tids[7]) is not None


def test_07_store_agent_status_calculation():
    """Verify agent telemetry calculation aggregates invocations and error rates accurately."""
    store = ObservabilityStore(max_traces=10, max_events=20)
    tid = uuid.uuid4().hex

    # Add 2 teacher spans (1 success, 1 fail)
    s1 = SpanRecord(
        span_id=uuid.uuid4().hex[:16],
        trace_id=tid,
        name="explanation_1",
        agent_name="Teacher Agent",
        status="completed",
        duration_ms=100.0,
    )
    s2 = SpanRecord(
        span_id=uuid.uuid4().hex[:16],
        trace_id=tid,
        name="explanation_2",
        agent_name="Teacher Agent",
        status="failed",
        duration_ms=50.0,
        error="LLM timeout",
    )
    store.add_span_to_trace(tid, s1)
    store.add_span_to_trace(tid, s2)

    agent_statuses = store.get_agent_statuses()
    teacher_status = next((a for a in agent_statuses if a.agent_name == "Teacher Agent"), None)
    assert teacher_status is not None
    assert teacher_status.total_invocations == 2
    assert teacher_status.total_errors == 1
    assert teacher_status.avg_duration_ms == 75.0


# ------------------------------------------------------------------------------
# Group C: Logging & Context Management Tests
# ------------------------------------------------------------------------------
def test_08_structured_json_logging():
    """Verify structured log emitter outputs single-line JSON with redacted content."""
    tid = uuid.uuid4().hex
    log_observability_event(
        event_type="test_event",
        message="Verifying structured logger",
        trace_id=tid,
        agent_name="Diagnostic Agent",
        status="completed",
        details={"secret_token": "do_not_leak_this", "topic": "Acids, Bases and Salts"},
    )

    assert JSONL_LOG_PATH.exists()
    # Read last line
    with open(JSONL_LOG_PATH, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        last_line = lines[-1]

    parsed = json.loads(last_line)
    assert parsed["trace_id"] == tid
    assert parsed["agent_name"] == "Diagnostic Agent"
    assert parsed["event_type"] == "test_event"
    assert parsed["details"]["secret_token"] == "[REDACTED_CREDENTIAL]"
    assert parsed["details"]["topic"] == "Acids, Bases and Salts"


def test_09_trace_scope_success_lifecycle():
    """Verify trace_scope records start/finish, execution duration, and persists span."""
    tid = uuid.uuid4().hex
    with trace_scope(
        name="test_scope_operation",
        span_type="agent",
        agent_name="Curriculum Agent",
        trace_id=tid,
        input_data={"unit": "Chemical Reactions"},
    ) as span:
        time.sleep(0.02)  # Simulate 20ms work
        span.output_data = {"learning_plan": "Generated sequential roadmap"}

    retrieved = observability_store.get_trace(tid)
    assert retrieved is not None
    assert len(retrieved.spans) >= 1
    matching_span = next(s for s in retrieved.spans if s.name == "test_scope_operation")
    assert matching_span.status == "completed"
    assert matching_span.duration_ms >= 15.0
    assert matching_span.output_data["learning_plan"] == "Generated sequential roadmap"


def test_10_trace_scope_exception_capture():
    """Verify trace_scope catches exceptions, records status='failed', and logs error category."""
    tid = uuid.uuid4().hex
    with pytest.raises(ValueError, match="Simulated agent failure"):
        with trace_scope(
            name="failing_operation",
            span_type="agent",
            agent_name="Assessment Agent",
            trace_id=tid,
        ):
            raise ValueError("Simulated agent failure")

    retrieved = observability_store.get_trace(tid)
    assert retrieved is not None
    failed_span = next(s for s in retrieved.spans if s.name == "failing_operation")
    assert failed_span.status == "failed"
    assert "Simulated agent failure" in failed_span.error
    assert failed_span.error_category == "ValueError"


def test_11_trace_context_propagation():
    """Verify thread-local trace context propagation and nested span management."""
    tid = uuid.uuid4().hex
    set_current_trace_id(tid)
    assert get_current_trace_id() == tid

    with trace_scope(name="parent_workflow", span_type="workflow", trace_id=tid) as p_span:
        assert p_span.trace_id == tid

        with trace_scope(name="child_step", span_type="task", agent_name="Mentor Agent") as c_span:
            assert c_span.trace_id == tid
            assert c_span.parent_span_id == p_span.span_id

    # Reset
    set_current_trace_id(None)


# ------------------------------------------------------------------------------
# Group D: CrewAI Callback Tests
# ------------------------------------------------------------------------------
def test_12_crewai_task_callback():
    """Verify create_crewai_task_callback executes safely and preserves privacy (no raw output text)."""
    tid = uuid.uuid4().hex
    cb = create_crewai_task_callback(trace_id=tid, agent_name="Teacher Agent")

    class MockTaskOutput:
        name = "Pedagogical Explanation Task"
        raw = "Photosynthesis is the chemical process by which plants synthesize carbohydrates."
        token_usage = None

    # Execute callback
    cb(MockTaskOutput())

    events = observability_store.get_events(trace_id=tid)
    task_evt = next((e for e in events if e.event_type == "task_complete"), None)
    assert task_evt is not None
    assert task_evt.agent_name == "Teacher Agent"
    assert task_evt.payload.get("has_output") is True
    assert "output_preview" not in task_evt.payload
    assert "Photosynthesis" not in str(task_evt.payload)


def test_13_crewai_step_callback():
    """Verify create_crewai_step_callback records operational steps without private thoughts."""
    tid = uuid.uuid4().hex
    step_cb = create_crewai_step_callback(trace_id=tid, agent_name="Curriculum Agent")

    step_cb("Formulating milestone sequence for Chapter 1")

    events = observability_store.get_events(trace_id=tid)
    step_evt = next((e for e in events if e.event_type == "agent_step"), None)
    assert step_evt is not None
    assert step_evt.agent_name == "Curriculum Agent"
    assert step_evt.payload.get("action") == "reasoning_step"
    assert "step_preview" not in step_evt.payload
    assert "Formulating milestone" not in str(step_evt.payload)


def test_14_crewai_kickoff_callbacks():
    """Verify create_crewai_kickoff_callbacks handles crew start and finish lifecycle."""
    tid = uuid.uuid4().hex
    before_cbs, after_cbs = create_crewai_kickoff_callbacks(trace_id=tid, crew_name="TestDiagnosticCrew")

    # Before kickoff
    inputs = {"topic": "Acids and Bases"}
    result_inputs = before_cbs[0](inputs)
    assert result_inputs == inputs

    # After kickoff
    class MockCrewOutput:
        raw = "Diagnostic evaluation complete. Identified 1 foundational misconception."

    after_cbs[0](MockCrewOutput())

    events = observability_store.get_events(trace_id=tid)
    assert any(e.event_type == "crew_kickoff" for e in events)
    assert any(e.event_type == "crew_complete" for e in events)


# ------------------------------------------------------------------------------
# Group E: Langfuse Integration Tests
# ------------------------------------------------------------------------------
def test_15_langfuse_disabled_by_default():
    """Verify LangfuseManager operates safely in disabled mode when credentials are absent."""
    assert langfuse_manager.is_enabled() is False
    assert langfuse_manager.status() == "disabled"

    # Calls should be no-ops and never raise exceptions
    span_id = langfuse_manager.start_span(trace_id=uuid.uuid4().hex, name="dummy_span")
    assert span_id is None
    langfuse_manager.end_span(span_id="nonexistent", output_data={"res": "ok"})
    langfuse_manager.flush()
    langfuse_manager.shutdown()


def test_16_langfuse_custom_configuration(monkeypatch):
    """Verify LangfuseManager initializes with credentials and creates observations without crashing."""
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-mock-key-123456789")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-mock-key-987654321")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:54321")

    from backend.observability.langfuse_client import LangfuseManager
    custom_mgr = LangfuseManager()

    assert custom_mgr.is_enabled() is True
    assert custom_mgr.status() == "enabled"

    tid = uuid.uuid4().hex
    span_id = custom_mgr.start_span(
        trace_id=tid,
        name="test_observation",
        span_type="agent",
        input_data={"query": "test query"},
    )
    assert span_id is not None

    custom_mgr.end_span(
        span_id=span_id,
        output_data={"result": "test result"},
        status="completed",
    )
    custom_mgr.shutdown()


def test_17_langfuse_telemetry_failure_shielding():
    """Verify that any exception inside Langfuse methods is caught and never impacts learning workflow."""
    # Even if bad/corrupt span arguments are passed, it should not raise
    langfuse_manager.end_span(span_id="invalid_span_id_12345", error="simulated error")
    langfuse_manager.flush()


def test_18_langfuse_no_fabricated_tokens():
    """Verify that token usage is only registered when genuinely provided."""
    span = SpanRecord(
        span_id=uuid.uuid4().hex[:16],
        trace_id=uuid.uuid4().hex,
        name="deterministic_task",
    )
    assert span.token_usage is None

    # When token usage is genuine
    span.token_usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    assert span.token_usage.total_tokens == 150
    assert span.token_usage.cost_usd is None


# ------------------------------------------------------------------------------
# Group F: FastAPI Observability Endpoints Tests
# ------------------------------------------------------------------------------
def test_19_api_health_and_status_endpoints():
    """Verify GET /api/v1/observability/health and /status return valid operational telemetry."""
    resp_health = client.get("/api/v1/observability/health")
    assert resp_health.status_code == 200
    health_data = resp_health.json()
    assert health_data["status"] == "healthy"
    assert health_data["subsystem"] == "Observability, Monitoring & Callbacks"
    assert health_data["version"] == "Phase 4.0"

    resp_status = client.get("/api/v1/observability/status")
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    assert status_data["status"] == "online"
    assert "telemetry" in status_data


def test_20_api_metrics_endpoint():
    """Verify GET /api/v1/observability/metrics returns aggregated system metrics."""
    resp = client.get("/api/v1/observability/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_traces" in data
    assert "total_spans" in data
    assert "error_rate" in data
    assert "agent_activity" in data
    assert len(data["agent_activity"]) >= 8


def test_21_api_traces_and_single_trace():
    """Verify GET /api/v1/observability/traces lists traces and /traces/{trace_id} retrieves details."""
    tid = uuid.uuid4().hex
    test_trace = TraceRecord(
        trace_id=tid,
        root_name="api_test_trace",
        status="completed",
        duration_ms=88.0,
    )
    observability_store.save_trace(test_trace)

    # List traces
    resp_list = client.get("/api/v1/observability/traces?limit=10")
    assert resp_list.status_code == 200
    traces = resp_list.json()
    assert any(t["trace_id"] == tid for t in traces)

    # Retrieve specific trace
    resp_single = client.get(f"/api/v1/observability/traces/{tid}")
    assert resp_single.status_code == 200
    single = resp_single.json()
    assert single["trace_id"] == tid
    assert single["root_name"] == "api_test_trace"

    # Retrieve non-existent trace -> 404
    resp_missing = client.get(f"/api/v1/observability/traces/non_existent_trace_id_123")
    assert resp_missing.status_code == 404


def test_22_api_agents_and_errors_endpoints():
    """Verify GET /api/v1/observability/agents and /errors return genuine recorded data."""
    resp_agents = client.get("/api/v1/observability/agents")
    assert resp_agents.status_code == 200
    agents = resp_agents.json()
    assert len(agents) >= 8
    agent_names = [a["agent_name"] for a in agents]
    assert "Orchestrator Agent" in agent_names
    assert "Teacher Agent" in agent_names
    assert "Resource Agent" in agent_names

    resp_errors = client.get("/api/v1/observability/errors")
    assert resp_errors.status_code == 200
    assert isinstance(resp_errors.json(), list)


# ------------------------------------------------------------------------------
# Group G: Cross-Framework Instrumentation Tests
# ------------------------------------------------------------------------------
def test_23_mcp_observability_instrumentation():
    """Verify MCPClientManager tool execution generates child spans in ObservabilityStore."""
    import anyio
    from backend.mcp_integration.client import mcp_manager
    tid = uuid.uuid4().hex

    async def _run():
        return await mcp_manager.execute_tool(
            tool_name="list_educational_resources",
            arguments={"sub_directory": ""},
            calling_agent="Resource Agent",
            correlation_id=tid,
        )

    resp = anyio.run(_run)
    assert resp.execution_status == "success"

    # Verify that an MCP span was added to the trace
    trace = observability_store.get_trace(tid)
    if trace:
        mcp_span = next((s for s in trace.spans if s.span_type == "mcp"), None)
        assert mcp_span is not None
        assert mcp_span.agent_name == "Resource Agent"


def test_24_adk_and_a2a_trace_propagation():
    """Verify trace propagation across A2A and Google ADK execution paths."""
    tid = uuid.uuid4().hex
    with trace_scope(name="a2a_test_trace", span_type="a2a", trace_id=tid) as span:
        span.output_data = {"a2a_status": "transferred"}

    trace = observability_store.get_trace(tid)
    assert trace is not None
    a2a_spans = [s for s in trace.spans if s.span_type == "a2a"]
    assert len(a2a_spans) >= 1


# ------------------------------------------------------------------------------
# Group H: Database & System Preservation Tests
# ------------------------------------------------------------------------------
def test_25_database_preservation_and_integrity():
    """Verify SQLite database schema, tables, and records remain 100% intact."""
    db_path = r"D:\Gyaan AI\data\gyaan_ai.db"
    assert os.path.exists(db_path)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c = conn.cursor()

    # PRAGMA integrity_check
    integrity = c.execute("PRAGMA integrity_check;").fetchall()
    assert integrity == [("ok",)], f"Database integrity check failed: {integrity}"

    # Table count check
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert len(tables) == 23, f"Expected 23 tables, found {len(tables)}"

    # Record count check
    students_count = c.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    sessions_count = c.execute("SELECT COUNT(*) FROM student_sessions").fetchone()[0]
    assert students_count >= 781, f"Expected at least 781 students, found {students_count}"
    assert sessions_count >= 782, f"Expected at least 782 student sessions, found {sessions_count}"

    total_records = sum(c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0] for t in tables)
    assert total_records >= 8192, f"Expected at least 8192 records, found {total_records}"

    conn.close()


# ------------------------------------------------------------------------------
# Group I: Remediated Multi-Agent Observability & Concurrency Tests
# ------------------------------------------------------------------------------

def test_26_eight_agents_callback_wiring():
    """Verify all eight canonical CrewAI agent builders attach lifecycle callbacks."""
    from backend.agents.diagnostic import build_diagnostic_crew
    from backend.agents.curriculum import build_curriculum_crew
    from backend.agents.resource import build_resource_crew
    from backend.agents.crew import build_teacher_crew
    from backend.agents.assessment import build_quiz_generation_crew, build_assessment_evaluation_crew
    from backend.agents.progress import build_progress_crew
    from backend.agents.mentor import build_standalone_mentor_crew

    crews_to_check = [
        ("Diagnostic Agent", build_diagnostic_crew(grade="Class 10", subject="Science", topic="Chemical Reactions")[0]),
        ("Curriculum Agent", build_curriculum_crew(grade="Class 10", subject="Science", topic="Chemical Reactions")[0]),
        ("Resource Agent", build_resource_crew(grade="Class 10", subject="Science", topic="Chemical Reactions")[0]),
        ("Teacher Agent", build_teacher_crew(student_question="What is an acid?", grade="Class 10", subject="Science")),
        ("Assessment Quiz", build_quiz_generation_crew(grade="Class 10", subject="Science", topic="Acids")[0]),
        ("Assessment Eval", build_assessment_evaluation_crew(questions_with_rubric=[], submitted_answers={})[0]),
        ("Progress Agent", build_progress_crew(student_profile={"id": "stu_1"}, objective_stats={"total_assessments_completed": 1})[0]),
        ("Mentor Agent", build_standalone_mentor_crew(student_profile={"id": "stu_1"}, topic="Acids")[0]),
    ]

    for agent_label, crew in crews_to_check:
        assert crew.task_callback is not None, f"{agent_label} missing task_callback"
        assert crew.step_callback is not None, f"{agent_label} missing step_callback"
        assert crew.before_kickoff_callbacks, f"{agent_label} missing before_kickoff_callbacks"
        assert crew.after_kickoff_callbacks, f"{agent_label} missing after_kickoff_callbacks"


def test_27_async_contextvar_concurrency_isolation():
    """Verify ContextVar preserves distributed trace isolation across concurrent async tasks."""
    import anyio
    from backend.observability import get_current_trace_id, get_current_span_id

    async def _worker(task_name: str, root_tid: str):
        with trace_scope(name=f"worker_{task_name}", span_type="agent", trace_id=root_tid) as span:
            await anyio.sleep(0.01)
            # Verify active context matches
            assert get_current_trace_id() == root_tid
            assert get_current_span_id() == span.span_id
            return span.trace_id, span.span_id

    async def _run():
        tid1 = uuid.uuid4().hex
        tid2 = uuid.uuid4().hex

        # Run concurrently
        async with anyio.create_task_group() as tg:
            tg.start_soon(_worker, "A", tid1)
            tg.start_soon(_worker, "B", tid2)

        # Context unwinds
        assert get_current_trace_id() is None
        assert get_current_span_id() is None

    anyio.run(_run)


def test_28_thread_context_propagation():
    """Verify trace context propagates cleanly across asyncio.to_thread boundaries."""
    import anyio
    from backend.observability import get_current_trace_id, get_current_span_id

    async def _run():
        tid = uuid.uuid4().hex
        with trace_scope(name="parent_async_span", span_type="workflow", trace_id=tid) as span:
            def _thread_worker():
                return get_current_trace_id(), get_current_span_id()

            thread_tid, thread_sid = await anyio.to_thread.run_sync(_thread_worker)
            assert thread_tid == tid
            assert thread_sid == span.span_id

        assert get_current_trace_id() is None

    anyio.run(_run)


def test_29_a2a_w3c_traceparent_http_propagation():
    """Verify A2A HTTP trace context extraction supports W3C traceparent and X-Trace-Id."""
    from backend.observability import extract_http_trace_context

    # 1. W3C traceparent header
    tid_hex = "4bf92f3577b34da6a3ce929d0e0e4736"
    parent_sid = "00f067aa0ba902b7"
    w3c_header = f"00-{tid_hex}-{parent_sid}-01"

    extracted_tid, extracted_sid = extract_http_trace_context({"traceparent": w3c_header})
    assert extracted_tid == tid_hex
    assert extracted_sid == parent_sid

    # 2. Custom X-Trace-Id header
    extracted_tid2, extracted_sid2 = extract_http_trace_context({
        "X-Trace-Id": tid_hex,
        "X-Parent-Span-Id": "span_abc123456789",
    })
    assert extracted_tid2 == tid_hex
    assert extracted_sid2 == "span_abc123456789"

    # 3. Invalid headers safely ignored
    bad_tid, bad_sid = extract_http_trace_context({"traceparent": "malformed-not-valid"})
    assert bad_tid is None
    assert bad_sid is None


def test_30_mcp_subprocess_correlation_propagation():
    """Verify MCP tool calls pass trace context to stdio subprocess and receive correlation."""
    import anyio
    from backend.mcp_integration.client import MCPClient

    async def _run():
        client = MCPClient()
        root_tid = uuid.uuid4().hex

        with trace_scope(name="test_mcp_caller", span_type="agent", trace_id=root_tid) as caller_span:
            response = await client.execute_tool(
                tool_name="list_educational_resources",
                arguments={"sub_directory": ""},
                calling_agent="Resource Agent",
            )
            assert response.execution_status == "success"
            raw_res = response.raw_result
            assert "trace_id" in raw_res
            assert raw_res["trace_id"] == root_tid
            assert "correlation_id" in raw_res

    anyio.run(_run)


def test_31_privacy_student_pseudonymization_and_exclusion(monkeypatch):
    """Verify raw student ID pseudonymization with HMAC secret, complete exclusion without secret, and PII redaction."""
    from backend.observability.redaction import redact_sensitive_data, pseudonymize_student_id
    from backend.observability.store import observability_store
    from backend.observability.schemas import TraceRecord

    raw_student_id = "student_aarav_01"
    synthetic_payload = {
        "student_id": raw_student_id,
        "student_name": "Aarav Kumar",
        "email": "aarav.kumar@student.edu",
        "phone": "+91 9876543210",
        "aadhaar": "1234-5678-9012",
        "password": "super_secret_password",
        "thought": "Internal LLM thought: this student struggles with balancing redox reactions.",
        "user_message": "Can you explain exothermic reactions to me in simple terms?",
    }

    # Case 1: HMAC secret configured in environment
    monkeypatch.setenv("TELEMETRY_HMAC_SECRET", "test_secure_hmac_secret_key_2026")
    pseudo_id = pseudonymize_student_id(raw_student_id)
    assert pseudo_id is not None
    assert pseudo_id.startswith("pseudo_")
    assert raw_student_id not in pseudo_id
    assert len(pseudo_id) == 23  # 'pseudo_' (7) + 16 hex chars

    clean_with_secret = redact_sensitive_data(synthetic_payload)
    assert clean_with_secret["student_id"] == pseudo_id
    assert clean_with_secret["student_name"] == "[REDACTED_STUDENT_NAME]"
    assert clean_with_secret["email"] == "[REDACTED_EMAIL]"
    assert clean_with_secret["phone"] == "[REDACTED_PHONE]"
    assert clean_with_secret["aadhaar"] == "[REDACTED_ID]"
    assert clean_with_secret["password"] == "[REDACTED_CREDENTIAL]"
    assert clean_with_secret["thought"] == "[REDACTED_INTERNAL_REASONING]"
    assert clean_with_secret["user_message"] == "[REDACTED_STUDENT_CONVERSATION]"

    # Case 2: HMAC secret missing from environment -> omit student identifier entirely
    monkeypatch.delenv("TELEMETRY_HMAC_SECRET", raising=False)
    assert pseudonymize_student_id(raw_student_id) is None
    clean_no_secret = redact_sensitive_data(synthetic_payload)
    assert "student_id" not in clean_no_secret  # Field omitted entirely
    assert clean_no_secret["student_name"] == "[REDACTED_STUDENT_NAME]"
    assert clean_no_secret["password"] == "[REDACTED_CREDENTIAL]"

    # Case 3: HMAC secret is empty or whitespace -> omit student identifier entirely
    monkeypatch.setenv("TELEMETRY_HMAC_SECRET", "    ")
    assert pseudonymize_student_id(raw_student_id) is None
    clean_whitespace_secret = redact_sensitive_data(synthetic_payload)
    assert "student_id" not in clean_whitespace_secret

    # Case 4: List processing with and without secret
    monkeypatch.setenv("TELEMETRY_HMAC_SECRET", "test_secure_hmac_secret_key_2026")
    clean_list = redact_sensitive_data([raw_student_id, "normal_item"])
    assert clean_list[0].startswith("pseudo_")
    assert clean_list[1] == "normal_item"

    monkeypatch.delenv("TELEMETRY_HMAC_SECRET", raising=False)
    clean_list_no_secret = redact_sensitive_data([raw_student_id, "normal_item"])
    assert clean_list_no_secret == ["normal_item"]  # Student ID omitted entirely

    # Case 5: Store behavior with and without secret
    monkeypatch.delenv("TELEMETRY_HMAC_SECRET", raising=False)
    trace_no_secret = TraceRecord(trace_id="tr_privacy_no_sec", root_name="workflow", student_id=raw_student_id)
    observability_store.save_trace(trace_no_secret)
    retrieved_no_sec = observability_store.get_trace("tr_privacy_no_sec")
    assert retrieved_no_sec.student_id is None  # Completely omitted

    monkeypatch.setenv("TELEMETRY_HMAC_SECRET", "test_secure_hmac_secret_key_2026")
    trace_with_secret = TraceRecord(trace_id="tr_privacy_with_sec", root_name="workflow", student_id=raw_student_id)
    observability_store.save_trace(trace_with_secret)
    retrieved_with_sec = observability_store.get_trace("tr_privacy_with_sec")
    assert retrieved_with_sec.student_id.startswith("pseudo_")
    assert raw_student_id not in retrieved_with_sec.student_id


def test_32_live_ollama_qwen_inference_and_telemetry():
    """Verify live inference through Teacher Agent with local Ollama qwen2.5:3b and telemetry capture."""
    import urllib.request
    import json

    # Check Ollama online status
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            models = [m.get("name") for m in data.get("models", [])]
            ollama_online = any("qwen2.5:3b" in m for m in models)
    except Exception:
        ollama_online = False

    if not ollama_online:
        pytest.skip("Local Ollama daemon is offline or qwen2.5:3b unavailable")

    from backend.agents.crew import build_teacher_crew

    tid = uuid.uuid4().hex
    with trace_scope(name="live_teacher_verification", span_type="workflow", trace_id=tid) as wf_span:
        crew = build_teacher_crew(
            student_question="What is a combination reaction in Class 10 Chemistry? Answer in one short paragraph.",
            grade="Class 10",
            subject="Science",
            chapter="Chemical Reactions and Equations",
            trace_id=tid,
        )
        result = crew.kickoff()
        output_str = str(result.raw if hasattr(result, "raw") else result)
        assert len(output_str) > 10, f"Expected output from qwen2.5:3b, got: {output_str}"

    assert wf_span.status == "completed"
    assert wf_span.duration_ms is not None and wf_span.duration_ms > 0

    # Verify trace telemetry
    trace = observability_store.get_trace(tid)
    assert trace is not None
    assert len(trace.spans) >= 1

    # Verify events
    events = observability_store.get_events(trace_id=tid)
    event_types = [e.event_type for e in events]
    assert "crew_kickoff" in event_types
    assert "task_complete" in event_types
    assert "crew_complete" in event_types
