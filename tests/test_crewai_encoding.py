"""Test Suite for CrewAI Event Bus Unicode & Windows UTF-8 Encoding Safety.

Verifies:
1. ConsoleFormatter renders '📋 Task Started' and '📋 Task Completion' without charmap UnicodeEncodeError.
2. CrewAIEventsBus sync handlers on_task_started and on_task_completed execute cleanly.
3. sys.stdout encoding is properly configured for UTF-8 on Windows.
"""

import sys
from unittest.mock import MagicMock
import pytest

from backend import enforce_utf8_encoding
from crewai.events.event_bus import crewai_event_bus
from crewai.events.types.task_events import TaskStartedEvent, TaskCompletedEvent
from crewai.events.utils.console_formatter import ConsoleFormatter
from crewai.tasks.task_output import TaskOutput


def test_utf8_enforcement_configures_streams():
    """Verify enforce_utf8_encoding sets UTF-8 encoding on standard streams."""
    enforce_utf8_encoding()
    if hasattr(sys.stdout, "encoding") and sys.stdout.encoding:
        assert sys.stdout.encoding.lower() in ("utf-8", "utf8")
    if hasattr(sys.stderr, "encoding") and sys.stderr.encoding:
        assert sys.stderr.encoding.lower() in ("utf-8", "utf8")


def test_console_formatter_renders_unicode_emojis_without_charmap_error():
    """Verify ConsoleFormatter handles '\U0001f4cb' (clipboard emoji) without charmap error."""
    enforce_utf8_encoding()
    formatter = ConsoleFormatter(verbose=True)

    # 1. Test Task Started panel (contains \U0001f4cb '📋 Task Started')
    formatter.handle_task_started("task_test_encoding_01", "Chemical Reactions Diagnosis")

    # 2. Test Task Completed panel (contains \U0001f4cb '📋 Task Completion')
    formatter.handle_task_status("task_test_encoding_01", "Diagnostic Specialist", "completed", "Chemical Reactions Diagnosis")

    # 3. Test Task Failure panel (contains \U0001f4cb '📋 Task Failure')
    formatter.handle_task_status("task_test_encoding_01", "Diagnostic Specialist", "failed", "Chemical Reactions Diagnosis")


def test_crewai_event_bus_handlers_execute_cleanly():
    """Verify CrewAI event bus handlers for task_started and task_completed execute cleanly without charmap error."""
    enforce_utf8_encoding()

    # Mock Task source
    mock_task = MagicMock()
    mock_task.id = "task_event_mock_99"
    mock_task.description = "Test task with unicode: \U0001f4cb \u2728"
    mock_task.name = "Test Unicode Task"
    mock_task.agent.role = "Test Teacher"
    mock_task.agent.crew = MagicMock()

    # Emit TaskStartedEvent
    started_event = TaskStartedEvent(task=mock_task, context="Sample task context with \U0001f4cb")
    crewai_event_bus.emit(mock_task, event=started_event)

    # Emit TaskCompletedEvent
    task_out = TaskOutput(
        description="Diagnose chemical reaction prerequisites",
        raw="Prerequisites verified: atoms and molecules (\U0001f4cb)",
        agent="Diagnostic Specialist",
    )
    completed_event = TaskCompletedEvent(task=mock_task, output=task_out, context="Sample output")
    crewai_event_bus.emit(mock_task, event=completed_event)
