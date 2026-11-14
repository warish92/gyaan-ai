"""Automated integration test for Gyaan AI CrewAI Teacher Agent.

Verifies end-to-end integration between CrewAI, Agent, Task, and local Ollama model.
"""

import sys
from pathlib import Path
import pytest

# Ensure workspace root is in path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.agents.crew import build_teacher_crew


@pytest.mark.integration
def test_teacher_agent_ollama_integration():
    """Verify that Teacher Agent successfully executes through CrewAI with Ollama."""
    question = (
        "Explain the difference between acids and bases to a Class 10 CBSE student. "
        "Give two examples of each."
    )

    crew = build_teacher_crew(student_question=question)
    assert crew is not None
    assert len(crew.agents) == 1
    assert len(crew.tasks) == 1

    # Execute crew
    result = crew.kickoff()
    assert result is not None

    answer = str(result.raw if hasattr(result, "raw") else result)
    assert len(answer) > 50, "Answer should be substantive and non-empty"

    lower_ans = answer.lower()
    assert "acid" in lower_ans, "Answer must explain acids"
    assert "base" in lower_ans, "Answer must explain bases"
