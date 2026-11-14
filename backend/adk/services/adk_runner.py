"""Gyaan AI - Google ADK Learning Intelligence Runner & Service.

Coordinates session lifecycle, prompt synthesis, Google ADK Runner execution,
event stream processing, structured output parsing, and error recovery.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
import uuid

import json_repair
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.errors.session_not_found_error import SessionNotFoundError

from backend.adk.agents.learning_analysis_agent import (
    create_learning_intelligence_agent,
)
from backend.adk.config import (
    ADK_APP_NAME,
    ADK_MODEL_NAME,
    ADK_OLLAMA_API_BASE,
    ADK_TIMEOUT_SECONDS,
)
from backend.adk.schemas.adk_messages import (
    AgentExecutionMetadata,
    LearningIntelligenceRequest,
    LearningIntelligenceResponse,
)

logger = logging.getLogger("gyaan_ai.adk.service")


class ADKLearningIntelligenceService:
    """Production service managing Google ADK agent execution and sessions."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.model_name = model_name or ADK_MODEL_NAME
        self.api_base = api_base or ADK_OLLAMA_API_BASE
        self.timeout_seconds = timeout_seconds or ADK_TIMEOUT_SECONDS

        # Google ADK In-Memory Session Service
        self.session_service = InMemorySessionService()

        # Google ADK Learning Intelligence Agent
        self.agent = create_learning_intelligence_agent(
            model_name=self.model_name,
            api_base=self.api_base,
        )

        # Google ADK Runner
        self.runner = Runner(
            agent=self.agent,
            session_service=self.session_service,
            app_name=ADK_APP_NAME,
        )

        # Student session registry tracking (student_id -> set of session_ids)
        self._student_sessions: Dict[str, set] = {}

    def _register_session_owner(self, student_id: str, session_id: str) -> None:
        """Register student session ownership for isolation enforcement."""
        if student_id not in self._student_sessions:
            self._student_sessions[student_id] = set()
        self._student_sessions[student_id].add(session_id)

    def is_session_owned_by_student(self, student_id: str, session_id: str) -> bool:
        """Verify whether a session is owned by the requested student."""
        return session_id in self._student_sessions.get(student_id, set())

    def get_active_sessions_count(self) -> int:
        """Return total active session count."""
        return sum(len(s) for s in self._student_sessions.values())

    async def get_or_create_session(
        self, student_id: str, session_id: Optional[str] = None
    ):
        """Retrieve existing student session with strict isolation, or create a new one."""
        if session_id:
            # Check ownership isolation
            for other_student, sessions in self._student_sessions.items():
                if session_id in sessions and other_student != student_id:
                    raise PermissionError(
                        f"Access denied: Session '{session_id}' belongs to another student."
                    )
            try:
                session = await self.session_service.get_session(
                    app_name=ADK_APP_NAME,
                    user_id=student_id,
                    session_id=session_id,
                )
                self._register_session_owner(student_id, session.id)
                return session
            except (SessionNotFoundError, Exception):
                logger.info(
                    "Session %s not found for student %s; creating new session.",
                    session_id,
                    student_id,
                )

        new_session_id = f"adk-sess-{student_id}-{uuid.uuid4().hex[:8]}"
        session = await self.session_service.create_session(
            app_name=ADK_APP_NAME,
            user_id=student_id,
            session_id=new_session_id,
        )
        self._register_session_owner(student_id, session.id)
        return session

    def _build_evidence_prompt(self, request: LearningIntelligenceRequest) -> str:
        """Format structured student evidence into an evidence-grounded prompt."""
        sections = [
            f"STUDENT IDENTIFIER: {request.student_id}",
            f"CHAPTER: {request.chapter_name} (ID: {request.chapter_id})",
        ]

        if request.topic_id:
            sections.append(f"TARGET TOPIC ID: {request.topic_id}")

        if request.learning_objectives:
            sections.append("CURRICULUM OBJECTIVES:")
            for obj in request.learning_objectives:
                sections.append(f"- {obj}")

        if request.diagnostic_evidence:
            diag = request.diagnostic_evidence
            sections.append(
                f"\nDIAGNOSTIC EVIDENCE:\n"
                f"- Topic: {diag.topic_name} (ID: {diag.topic_id})\n"
                f"- Score: {diag.score}/{diag.probes_evaluated} ({diag.accuracy_pct:.1f}%)\n"
                f"- Mastery Status: {diag.mastery_status}\n"
                f"- Demonstrated Misconceptions: {', '.join(diag.identified_misconceptions) if diag.identified_misconceptions else 'None demonstrated'}"
            )

        if request.assessment_evidence:
            sections.append("\nRECENT ASSESSMENT HISTORY:")
            for i, att in enumerate(request.assessment_evidence, 1):
                errors = ", ".join(att.recurring_errors) if att.recurring_errors else "None"
                sections.append(
                    f"{i}. Type: {att.assessment_type} | Questions: {att.total_questions} | "
                    f"Correct: {att.correct_answers} ({att.percentage:.1f}%) | Errors: {errors}"
                )

        if request.topic_performances:
            sections.append("\nTOPIC-LEVEL PERFORMANCE AGGREGATIONS:")
            for tp in request.topic_performances:
                struggles = ", ".join(tp.struggle_indicators) if tp.struggle_indicators else "None"
                sections.append(
                    f"- Topic: {tp.topic_name} | Attempts: {tp.attempts} | Avg Score: {tp.average_score:.1f}% | "
                    f"Mastery: {tp.current_mastery_level} | Indicators: {struggles}"
                )

        if request.query:
            sections.append(f"\nSPECIFIC PEDAGOGICAL QUERY: {request.query}")

        sections.append(
            "\nAnalyze the above student evidence thoroughly. Return your complete structured findings in JSON."
        )

        return "\n".join(sections)

    def _extract_json_response(self, raw_text: str) -> Dict[str, Any]:
        """Safely extract and parse JSON object from LLM response text."""
        cleaned = raw_text.strip()
        # Look for markdown code fence
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Look for outermost braces
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_str = cleaned[first_brace : last_brace + 1]
            else:
                json_str = cleaned

        try:
            return json.loads(json_str)
        except Exception:
            repaired = json_repair.repair_json(json_str, return_objects=True)
            if isinstance(repaired, dict):
                return repaired
            raise ValueError(f"Unable to parse structured JSON from response: {raw_text[:200]}")

    async def analyze_learning(
        self, request: LearningIntelligenceRequest
    ) -> LearningIntelligenceResponse:
        """Execute the Google ADK Learning Intelligence Agent and produce validated response.

        Args:
            request: Validated LearningIntelligenceRequest.

        Returns:
            Validated LearningIntelligenceResponse with execution telemetry.
        """
        start_time = time.perf_counter()
        invocation_id = f"adk-inv-{uuid.uuid4().hex[:12]}"

        # 1. Retrieve or create session with isolation enforcement
        session = await self.get_or_create_session(
            student_id=request.student_id,
            session_id=request.session_id,
        )

        from backend.observability import trace_scope
        with trace_scope(
            name="adk_learning_intelligence",
            span_type="adk",
            agent_name="Learning Intelligence Agent (ADK)",
            input_data={"student_id": request.student_id, "chapter_id": request.chapter_id, "session_id": session.id},
            metadata={"model": self.model_name, "invocation_id": invocation_id},
        ) as adk_span:
            # 2. Build structured evidence prompt
            evidence_prompt = self._build_evidence_prompt(request)
            new_message = types.Content(
                role="user",
                parts=[types.Part.from_text(text=evidence_prompt)],
            )

            # 3. Execute Google ADK Runner with bounded timeout
            raw_output = ""
            execution_status = "success"
            error_msg: Optional[str] = None

            try:
                async def _run_loop():
                    nonlocal raw_output
                    async for event in self.runner.run_async(
                        user_id=request.student_id,
                        session_id=session.id,
                        invocation_id=invocation_id,
                        new_message=new_message,
                    ):
                        if event.is_final_response() and event.content and event.content.parts:
                            for part in event.content.parts:
                                if part.text:
                                    raw_output += part.text

                await asyncio.wait_for(_run_loop(), timeout=self.timeout_seconds)

            except asyncio.TimeoutError:
                logger.error("ADK Agent execution timed out after %ds", self.timeout_seconds)
                execution_status = "error"
                error_msg = f"ADK Agent execution timed out after {self.timeout_seconds}s"
            except Exception as e:
                logger.exception("ADK Agent execution failed: %s", str(e))
                execution_status = "error"
                error_msg = f"ADK Agent execution error: {type(e).__name__} - {str(e)}"

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # 4. Construct execution metadata
            metadata = AgentExecutionMetadata(
                agent_name="Learning Intelligence Agent",
                agent_framework="Google ADK",
                framework_version="2.14.0",
                model=self.model_name,
                duration_ms=round(elapsed_ms, 2),
                timestamp=datetime.now(timezone.utc).isoformat(),
                invocation_id=invocation_id,
                session_id=session.id,
                student_id=request.student_id,
            )

            if execution_status == "error":
                adk_span.status = "failed"
                adk_span.error = error_msg
            else:
                adk_span.output_data = {"status": "success", "duration_ms": elapsed_ms}

            # 5. Build response
            if execution_status == "error":
                return LearningIntelligenceResponse(
                    student_id=request.student_id,
                    session_id=session.id,
                    chapter_id=request.chapter_id,
                    chapter_name=request.chapter_name,
                    topic_id=request.topic_id,
                    execution_status="error",
                    summary=f"Analysis failed: {error_msg}",
                    identified_patterns=[],
                    recurring_misconceptions=[],
                    topic_level_weaknesses=[],
                    learning_priorities=[],
                    evidence_references=[],
                    confidence=0.0,
                    recommendations=["Please retry with smaller evidence batch or verify Ollama service."],
                    execution_metadata=metadata,
                )

            # 6. Parse structured findings
            try:
                parsed = self._extract_json_response(raw_output)
                return LearningIntelligenceResponse(
                    student_id=request.student_id,
                    session_id=session.id,
                    chapter_id=request.chapter_id,
                    chapter_name=request.chapter_name,
                    topic_id=request.topic_id,
                    execution_status="success",
                    summary=parsed.get("summary", "Student learning analysis completed successfully."),
                    identified_patterns=parsed.get("identified_patterns", []),
                    recurring_misconceptions=parsed.get("recurring_misconceptions", []),
                    topic_level_weaknesses=parsed.get("topic_level_weaknesses", []),
                    learning_priorities=parsed.get("learning_priorities", []),
                    evidence_references=parsed.get("evidence_references", []),
                    confidence=float(parsed.get("confidence", 0.85)),
                    recommendations=parsed.get("recommendations", []),
                    execution_metadata=metadata,
                )
            except Exception as parse_err:
                logger.warning("Failed to parse JSON response cleanly: %s; falling back", parse_err)
                return LearningIntelligenceResponse(
                    student_id=request.student_id,
                    session_id=session.id,
                    chapter_id=request.chapter_id,
                    chapter_name=request.chapter_name,
                    topic_id=request.topic_id,
                    execution_status="partial",
                    summary=raw_output[:500] if raw_output else "Analysis generated non-standard JSON output.",
                    identified_patterns=["Pattern extraction completed with partial structuring"],
                    recurring_misconceptions=[],
                    topic_level_weaknesses=[],
                    learning_priorities=["Revisit chapter core concepts"],
                    evidence_references=["Extracted from student diagnostic and assessment submissions"],
                    confidence=0.6,
                    recommendations=["Conduct guided teacher review of topic foundations"],
                    execution_metadata=metadata,
                )


# Global Singleton Service
adk_learning_service = ADKLearningIntelligenceService()
