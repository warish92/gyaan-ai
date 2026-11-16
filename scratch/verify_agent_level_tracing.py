"""Verify full implementation of Langfuse Agent-Level Tracing Architecture in Gyaan AI."""
import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath("."))
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from dotenv import load_dotenv
load_dotenv()

from crewai import Agent, Task
from crewai.tasks.task_output import TaskOutput
from backend.observability import (
    setup_class_level_task_instrumentation,
    datetime_to_nanoseconds_exact,
    set_gyaan_workflow_active,
    reset_gyaan_workflow_active,
    is_gyaan_workflow_active,
    get_current_trace_id,
    get_current_span_id,
    trace_scope,
    EXACT_CANONICAL_ROLES,
    CANONICAL_ROLE_TO_LABEL,
    CANONICAL_SPECIALIST_STATIC_TASK_NAMES,
)
from backend.observability.langfuse_client import langfuse_manager

results = {}

def test_1_canonical_roles_and_static_tasks():
    assert len(EXACT_CANONICAL_ROLES) == 8, f"Expected 8 roles, got {len(EXACT_CANONICAL_ROLES)}"
    for role in EXACT_CANONICAL_ROLES:
        label = CANONICAL_ROLE_TO_LABEL.get(role)
        task_name = CANONICAL_SPECIALIST_STATIC_TASK_NAMES.get(role)
        assert label is not None, f"Missing label for {role}"
        assert task_name is not None, f"Missing static task name for {role}"
    results["test_1_canonical_roles_and_static_tasks"] = "PASSED"

def test_2_nanoseconds_precision():
    dt1 = datetime(2026, 11, 16, 10, 0, 0, 123456, tzinfo=timezone.utc)
    dt2 = datetime(2026, 11, 16, 10, 0, 1, 654321, tzinfo=timezone.utc)
    ns1 = datetime_to_nanoseconds_exact(dt1)
    ns2 = datetime_to_nanoseconds_exact(dt2)
    assert isinstance(ns1, int)
    assert isinstance(ns2, int)
    diff = ns2 - ns1
    assert diff == 1_530_865_000, f"Expected 1530865000 ns, got {diff}"
    results["test_2_nanoseconds_precision"] = "PASSED"

def test_3_workflow_contextvar_gating():
    # Outside active workflow
    assert not is_gyaan_workflow_active()
    tok = set_gyaan_workflow_active(True)
    assert is_gyaan_workflow_active()
    reset_gyaan_workflow_active(tok)
    assert not is_gyaan_workflow_active()
    results["test_3_workflow_contextvar_gating"] = "PASSED"

def test_4_class_level_instrumentation_all_8_agents():
    setup_class_level_task_instrumentation()
    mock_obs = MagicMock()
    mock_obs.id = "obs_task_123"

    with patch.object(Task, "_execute_core", return_value=TaskOutput(description="Task description", raw="Simulated lesson output", agent="Specialist Agent")), \
         patch.object(langfuse_manager, "is_enabled", return_value=True), \
         patch.object(langfuse_manager, "start_task_observation", return_value=mock_obs) as mock_start, \
         patch.object(langfuse_manager, "end_task_observation") as mock_end:

        for role in EXACT_CANONICAL_ROLES:
            mock_start.reset_mock()
            mock_end.reset_mock()
            agent = Agent(role=role, goal="Goal", backstory="Backstory", llm="ollama/qwen2.5:3b")
            task = Task(description="Class 10 confidential homework text", agent=agent, expected_output="Private output")

            # With active workflow and trace_id
            with trace_scope("workflow_span", span_type="workflow", agent_name="TestAgent") as s:
                tok = set_gyaan_workflow_active(True)
                try:
                    res = task.execute_sync()
                finally:
                    reset_gyaan_workflow_active(tok)

            label = CANONICAL_ROLE_TO_LABEL[role]
            static_task = CANONICAL_SPECIALIST_STATIC_TASK_NAMES[role]
            expected_name = f"agent:{label}:{static_task}"

            assert mock_start.call_count == 1, f"Failed start for {role}"
            assert mock_end.call_count == 1, f"Failed end for {role}"

            kwargs = mock_start.call_args[1]
            assert kwargs["name"] == expected_name, f"Expected {expected_name}, got {kwargs['name']}"
            assert kwargs["metadata"]["agent_role"] == label
            assert kwargs["metadata"]["task_name"] == static_task
            assert kwargs["trace_id"] == s.trace_id

            end_kwargs = mock_end.call_args[1]
            assert end_kwargs["status_message"] == "SUCCESS"
            assert end_kwargs["level"] == "DEFAULT"

    results["test_4_class_level_instrumentation_all_8_agents"] = "PASSED"

def test_5_non_canonical_role_rejection():
    setup_class_level_task_instrumentation()
    mock_obs = MagicMock()

    with patch.object(Task, "_execute_core", return_value=TaskOutput(description="Task description", raw="Simulated lesson output", agent="Specialist Agent")), \
         patch.object(langfuse_manager, "is_enabled", return_value=True), \
         patch.object(langfuse_manager, "start_task_observation", return_value=mock_obs) as mock_start:
        agent = Agent(role="Random Custom Specialist", goal="Goal", backstory="Backstory", llm="ollama/qwen2.5:3b")
        task = Task(description="Description", agent=agent, expected_output="Output")

        with trace_scope("workflow_span", span_type="workflow") as s:
            tok = set_gyaan_workflow_active(True)
            try:
                task.execute_sync()
            finally:
                reset_gyaan_workflow_active(tok)

        assert mock_start.call_count == 0, "Non-canonical agent should NOT be instrumented"
    results["test_5_non_canonical_role_rejection"] = "PASSED"

def test_6_zero_privacy_leakage():
    setup_class_level_task_instrumentation()
    mock_obs = MagicMock()

    with patch.object(Task, "_execute_core", return_value=TaskOutput(description="Task description", raw="Simulated lesson output", agent="Specialist Agent")), \
         patch.object(langfuse_manager, "is_enabled", return_value=True), \
         patch.object(langfuse_manager, "start_task_observation", return_value=mock_obs) as mock_start, \
         patch.object(langfuse_manager, "end_task_observation") as mock_end:

        teacher_role = "Class 10 CBSE Science Teacher and Concept Specialist"
        agent = Agent(role=teacher_role, goal="Teach", backstory="NCERT", llm="ollama/qwen2.5:3b")
        private_prompt = "CONFIDENTIAL_STUDENT_QUESTION_DO_NOT_EXPOSE"
        task = Task(description=private_prompt, agent=agent, expected_output="Private lesson")

        with trace_scope("workflow_span", span_type="workflow"):
            tok = set_gyaan_workflow_active(True)
            try:
                task.execute_sync()
            finally:
                reset_gyaan_workflow_active(tok)

        start_kwargs = mock_start.call_args[1]
        assert private_prompt not in str(start_kwargs), "Private prompt leaked in start kwargs!"
        end_kwargs = mock_end.call_args[1]
        assert private_prompt not in str(end_kwargs), "Private prompt leaked in end kwargs!"

    results["test_6_zero_privacy_leakage"] = "PASSED"

def test_7_exception_and_signal_propagation():
    setup_class_level_task_instrumentation()
    mock_obs = MagicMock()

    teacher_role = "Class 10 CBSE Science Teacher and Concept Specialist"
    agent = Agent(role=teacher_role, goal="Teach", backstory="NCERT", llm="ollama/qwen2.5:3b")

    # 1. Custom ValueError
    task1 = Task(description="Task 1", agent=agent, expected_output="Out")
    with patch.object(task1, "_execute_core", side_effect=ValueError("Custom error")), \
         patch.object(langfuse_manager, "is_enabled", return_value=True), \
         patch.object(langfuse_manager, "start_task_observation", return_value=mock_obs), \
         patch.object(langfuse_manager, "end_task_observation") as mock_end:
            with trace_scope("workflow_span", span_type="workflow"):
                tok = set_gyaan_workflow_active(True)
                try:
                    try:
                        task1.execute_sync()
                        assert False, "Should have raised ValueError"
                    except ValueError as ve:
                        assert str(ve) == "Custom error"
                finally:
                    reset_gyaan_workflow_active(tok)
            end_kwargs = mock_end.call_args[1]
            assert end_kwargs["level"] == "ERROR"
            assert "ValueError" in end_kwargs["status_message"]

    # 2. asyncio.CancelledError
    task2 = Task(description="Task 2", agent=agent, expected_output="Out")
    with patch.object(task2, "_execute_core", side_effect=asyncio.CancelledError()), \
         patch.object(langfuse_manager, "is_enabled", return_value=True), \
         patch.object(langfuse_manager, "start_task_observation", return_value=mock_obs), \
         patch.object(langfuse_manager, "end_task_observation") as mock_end:
            with trace_scope("workflow_span", span_type="workflow"):
                tok = set_gyaan_workflow_active(True)
                try:
                    try:
                        task2.execute_sync()
                        assert False, "Should have raised CancelledError"
                    except asyncio.CancelledError:
                        pass
                finally:
                    reset_gyaan_workflow_active(tok)
            end_kwargs = mock_end.call_args[1]
            assert end_kwargs["level"] == "ERROR"
            assert "CANCELLED" in end_kwargs["status_message"]

    results["test_7_exception_and_signal_propagation"] = "PASSED"

async def test_8_concurrency_isolation():
    setup_class_level_task_instrumentation()

    with patch.object(Task, "_execute_core", return_value=TaskOutput(description="Task description", raw="Simulated lesson output", agent="Specialist Agent")):
        async def run_worker(role: str, worker_id: int):
            trace_id = uuid.uuid4().hex
            with trace_scope(f"worker_{worker_id}", span_type="workflow", trace_id=trace_id) as s:
                tok = set_gyaan_workflow_active(True)
                try:
                    agent = Agent(role=role, goal="Goal", backstory="Backstory", llm="ollama/qwen2.5:3b")
                    task = Task(description=f"Task {worker_id}", agent=agent, expected_output="Out")
                    assert get_current_trace_id() == trace_id
                    await asyncio.sleep(0.01)
                    task.execute_sync()
                    assert get_current_trace_id() == trace_id
                    return s.trace_id
                finally:
                    reset_gyaan_workflow_active(tok)

        roles = list(EXACT_CANONICAL_ROLES)
        tasks = [run_worker(roles[i % len(roles)], i) for i in range(16)]
        trace_ids = await asyncio.gather(*tasks)
        assert len(trace_ids) == 16
        assert len(set(trace_ids)) == 16, "Trace IDs must not cross-contaminate across concurrent tasks!"
        results["test_8_concurrency_isolation"] = "PASSED"

def run_all():
    print("Running Agent Tracing Verification Suite...")
    test_1_canonical_roles_and_static_tasks()
    test_2_nanoseconds_precision()
    test_3_workflow_contextvar_gating()
    test_4_class_level_instrumentation_all_8_agents()
    test_5_non_canonical_role_rejection()
    test_6_zero_privacy_leakage()
    test_7_exception_and_signal_propagation()
    asyncio.run(test_8_concurrency_isolation())

    for k, v in results.items():
        print(f"  {k}: {v}")
    print("\nALL 8 TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_all()
