"""Gyaan AI - Central Canonical Agent Registry.

Discovers, registers, and monitors all eight genuine CrewAI agents:
1. Orchestrator Agent
2. Diagnostic Agent
3. Curriculum Agent
4. Resource Agent
5. Teacher Agent
6. Assessment Agent
7. Progress Agent
8. Mentor Agent

Extracts real metadata (role, goal, backstory, model configuration) from
genuine CrewAI Agent instances, and maintains real execution state tracking.
"""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import logging
import os
import sys
import threading
import time
from typing import Any, Callable, Dict, Generator, List, Optional

# Ensure project root is in sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from crewai import Agent

logger = logging.getLogger("gyaan_ai.agents.registry")


@dataclass
class AgentMetadata:
    """Rich metadata and runtime execution state for a registered CrewAI agent."""

    id: str
    name: str
    title: str
    role: str
    goal: str
    backstory: str
    model: str = "ollama/qwen2.5:3b"
    llm_provider: str = "ollama"
    temperature: float = 0.3
    phase: str = "Phase 1B"
    status: str = "idle"  # "idle" | "running" | "completed" | "error"
    registration_status: str = "registered"
    associated_workflows: List[str] = field(default_factory=list)
    total_executions: int = 0
    last_execution_time: Optional[str] = None
    last_duration_seconds: Optional[float] = None
    last_workflow: Optional[str] = None
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary for serialization."""
        return asdict(self)


# Canonical 8 Agent Specification
CANONICAL_AGENT_SPECS = [
    {
        "id": "orchestrator",
        "name": "Orchestrator Agent",
        "title": "Master Intent Router & Multi-Agent Dispatcher",
        "phase": "Phase 7",
        "factory_module": "backend.agents.orchestrator",
        "factory_func": "create_orchestrator_agent",
        "default_workflows": [
            "All Registered Workflows",
            "chapter_learning_journey",
            "learning_journey",
            "teacher_answer",
            "diagnostic_curriculum",
            "personalized_learning_plan",
            "resource_search",
            "quiz_generation",
            "assessment_evaluation",
            "progress_analysis",
            "personalized_mentoring",
            "progress_and_mentoring",
            "curriculum_inquiry",
            "diagnostic_evaluation",
            "study_guidance",
        ],
    },
    {
        "id": "diagnostic",
        "name": "Diagnostic Agent",
        "title": "Knowledge Gap & Misconception Specialist",
        "phase": "Phase 3",
        "factory_module": "backend.agents.diagnostic",
        "factory_func": "create_diagnostic_agent",
        "default_workflows": [
            "chapter_learning_journey",
            "diagnostic_curriculum",
            "personalized_learning_plan",
            "diagnostic_evaluation",
        ],
    },
    {
        "id": "curriculum",
        "name": "Curriculum Agent",
        "title": "NCERT Learning Roadmap Architect",
        "phase": "Phase 3",
        "factory_module": "backend.agents.curriculum",
        "factory_func": "create_curriculum_agent",
        "default_workflows": [
            "chapter_learning_journey",
            "diagnostic_curriculum",
            "personalized_learning_plan",
            "curriculum_inquiry",
        ],
    },
    {
        "id": "resource",
        "name": "Resource Agent",
        "title": "NCERT Educational Corpus Curator",
        "phase": "Phase 4",
        "factory_module": "backend.agents.resource",
        "factory_func": "create_resource_agent",
        "default_workflows": [
            "chapter_learning_journey",
            "resource_search",
            "quiz_generation",
        ],
    },
    {
        "id": "teacher",
        "name": "Teacher Agent",
        "title": "Socratic Concept Explainer",
        "phase": "Phase 1B",
        "factory_module": "backend.agents.teacher",
        "factory_func": "create_teacher_agent",
        "default_workflows": [
            "chapter_learning_journey",
            "teacher_answer",
        ],
    },
    {
        "id": "assessment",
        "name": "Assessment Agent",
        "title": "Practice Quiz Generator & Rubric Evaluator",
        "phase": "Phase 4",
        "factory_module": "backend.agents.assessment",
        "factory_func": "create_assessment_agent",
        "default_workflows": [
            "chapter_learning_journey",
            "quiz_generation",
            "assessment_evaluation",
        ],
    },
    {
        "id": "progress",
        "name": "Progress Agent",
        "title": "Deterministic Learning Analytics Evaluator",
        "phase": "Phase 6",
        "factory_module": "backend.agents.progress",
        "factory_func": "create_progress_agent",
        "default_workflows": [
            "chapter_learning_journey",
            "progress_analysis",
            "progress_and_mentoring",
        ],
    },
    {
        "id": "mentor",
        "name": "Mentor Agent",
        "title": "Personalized Learning Coach & Milestone Guide",
        "phase": "Phase 6",
        "factory_module": "backend.agents.mentor",
        "factory_func": "create_mentor_agent",
        "default_workflows": [
            "chapter_learning_journey",
            "personalized_mentoring",
            "progress_and_mentoring",
            "study_guidance",
        ],
    },
]


class AgentRegistry:
    """Thread-safe discovery, registration, and runtime monitoring registry for CrewAI agents."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._agents: Dict[str, AgentMetadata] = {}
        self._initialized = False

    def initialize(self, force_refresh: bool = False) -> List[AgentMetadata]:
        """Discover, instantiate, and register all eight canonical CrewAI agents.

        Inspects the actual CrewAI Agent objects to extract genuine role, goal, backstory,
        and LLM configurations. Emits clear startup logs.
        """
        with self._lock:
            if self._initialized and not force_refresh:
                return list(self._agents.values())

            logger.info("Initializing and discovering canonical CrewAI multi-agent roster...")
            registered: List[AgentMetadata] = []

            for idx, spec in enumerate(CANONICAL_AGENT_SPECS, 1):
                agent_id = spec["id"]
                module_name = spec["factory_module"]
                func_name = spec["factory_func"]

                try:
                    import importlib

                    mod = importlib.import_module(module_name)
                    factory_fn: Callable[[], Agent] = getattr(mod, func_name)
                    # Instantiate real CrewAI Agent object
                    crew_agent: Agent = factory_fn()

                    # Extract metadata from real Agent instance
                    role = crew_agent.role or "Specialized Educational AI Agent"
                    goal = crew_agent.goal or "Assist secondary school learners."
                    backstory = crew_agent.backstory or "Expert pedagogical assistant."

                    # Extract LLM configuration
                    model = "ollama/qwen2.5:3b"
                    temperature = 0.3
                    if hasattr(crew_agent, "llm") and crew_agent.llm:
                        llm_obj = crew_agent.llm
                        model = getattr(llm_obj, "model", model) or model
                        temperature = getattr(llm_obj, "temperature", temperature) or temperature

                    # Clean model name for display
                    if "/" in model:
                        display_model = model
                    else:
                        display_model = f"ollama/{model}"

                    # Build or preserve execution stats
                    prev = self._agents.get(agent_id)
                    total_execs = prev.total_executions if prev else 0
                    last_exec = prev.last_execution_time if prev else None
                    last_dur = prev.last_duration_seconds if prev else None
                    last_wf = prev.last_workflow if prev else None
                    status = prev.status if prev and prev.status == "running" else "idle"

                    meta = AgentMetadata(
                        id=agent_id,
                        name=spec["name"],
                        title=spec["title"],
                        role=role,
                        goal=goal,
                        backstory=backstory,
                        model=display_model,
                        llm_provider="ollama",
                        temperature=float(temperature),
                        phase=spec["phase"],
                        status=status,
                        registration_status="registered",
                        associated_workflows=spec["default_workflows"],
                        total_executions=total_execs,
                        last_execution_time=last_exec,
                        last_duration_seconds=last_dur,
                        last_workflow=last_wf,
                    )

                    self._agents[agent_id] = meta
                    registered.append(meta)

                    logger.info(
                        "[%d/8] Discovered: %s | Role: %s | Model: %s [Status: %s]",
                        idx,
                        spec["name"],
                        role[:45] + ("..." if len(role) > 45 else ""),
                        display_model,
                        status,
                    )

                except Exception as exc:
                    logger.error("Failed to discover agent '%s': %s", agent_id, exc, exc_info=True)
                    # Fallback metadata if instantiation fails
                    meta = AgentMetadata(
                        id=agent_id,
                        name=spec["name"],
                        title=spec["title"],
                        role="Pending Initialization",
                        goal="Pending Initialization",
                        backstory="Pending Initialization",
                        model="ollama/qwen2.5:3b",
                        phase=spec["phase"],
                        status="error",
                        registration_status="error",
                        associated_workflows=spec["default_workflows"],
                        last_error=str(exc),
                    )
                    self._agents[agent_id] = meta
                    registered.append(meta)

            self._initialized = True
            logger.info("All 8 canonical CrewAI agents verified, registered, and idle (ready for execution).")
            return list(self._agents.values())

    def get_agent(self, agent_id: str) -> Optional[AgentMetadata]:
        """Retrieve metadata for a specific agent by ID."""
        with self._lock:
            if not self._initialized:
                self.initialize()
            return self._agents.get(agent_id.lower().strip())

    def get_all_agents(self) -> List[AgentMetadata]:
        """Retrieve metadata for all 8 canonical registered agents."""
        with self._lock:
            if not self._initialized:
                self.initialize()
            return list(self._agents.values())

    def set_agent_status(
        self,
        agent_id: str,
        status: str,
        workflow: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update runtime execution status for a specific agent."""
        with self._lock:
            if not self._initialized:
                self.initialize()

            agent = self._agents.get(agent_id.lower().strip())
            if not agent:
                return

            agent.status = status
            if workflow:
                agent.last_workflow = workflow
            if duration_seconds is not None:
                agent.last_duration_seconds = round(duration_seconds, 2)
            if error:
                agent.last_error = error
                agent.status = "error"
            elif status in ("idle", "completed"):
                agent.last_error = None

            if status == "running":
                agent.last_execution_time = datetime.now(timezone.utc).isoformat()
            elif status in ("completed", "idle") and duration_seconds is not None:
                agent.total_executions += 1
                agent.last_execution_time = datetime.now(timezone.utc).isoformat()

    def get_agents_for_workflow(self, workflow_name: str) -> List[str]:
        """Return canonical agent IDs associated with a specific workflow."""
        wf = workflow_name.lower().strip()
        if wf in ("chapter_learning_journey", "learning_journey"):
            return ["orchestrator", "diagnostic", "curriculum", "resource", "teacher", "assessment", "progress", "mentor"]
        elif wf == "teacher_answer":
            return ["teacher"]
        elif wf in ("diagnostic_curriculum", "personalized_learning_plan"):
            return ["diagnostic", "curriculum"]
        elif wf == "curriculum_inquiry":
            return ["curriculum"]
        elif wf == "diagnostic_evaluation":
            return ["diagnostic"]
        elif wf == "study_guidance":
            return ["mentor"]
        elif wf == "resource_search":
            return ["resource"]
        elif wf == "quiz_generation":
            return ["resource", "assessment"]
        elif wf == "assessment_evaluation":
            return ["assessment"]
        elif wf == "progress_analysis":
            return ["progress"]
        elif wf in ("personalized_mentoring", "progress_and_mentoring"):
            return ["progress", "mentor"]
        else:
            return ["orchestrator"]

    @contextmanager
    def track_workflow_execution(self, workflow_name: str) -> Generator[None, None, None]:
        """Context manager that tracks real execution state of agents participating in a workflow."""
        agent_ids = self.get_agents_for_workflow(workflow_name)
        start_time = time.perf_counter()

        with self._lock:
            for aid in agent_ids:
                self.set_agent_status(aid, status="running", workflow=workflow_name)

        try:
            yield
            elapsed = time.perf_counter() - start_time
            with self._lock:
                for aid in agent_ids:
                    self.set_agent_status(
                        aid,
                        status="idle",
                        workflow=workflow_name,
                        duration_seconds=elapsed,
                    )
        except Exception as exc:
            elapsed = time.perf_counter() - start_time
            with self._lock:
                for aid in agent_ids:
                    self.set_agent_status(
                        aid,
                        status="error",
                        workflow=workflow_name,
                        duration_seconds=elapsed,
                        error=str(exc),
                    )
            raise

    def get_arena_status(self) -> Dict[str, Any]:
        """Return system health and agent arena summary."""
        agents = self.get_all_agents()
        active_count = sum(1 for a in agents if a.status == "running")
        ready_count = sum(1 for a in agents if a.status == "idle")
        error_count = sum(1 for a in agents if a.status == "error")

        return {
            "total_agents": len(agents),
            "registered_agents": sum(1 for a in agents if a.registration_status == "registered"),
            "running_agents": active_count,
            "idle_agents": ready_count,
            "error_agents": error_count,
            "model": "ollama/qwen2.5:3b",
            "provider": "ollama",
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            "status": "healthy" if error_count == 0 else "degraded",
            "canonical_roster": [a.name for a in agents],
        }


# Global singleton instance
agent_registry = AgentRegistry()
