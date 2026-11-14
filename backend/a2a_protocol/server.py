"""Gyaan AI - Google ADK A2A Server Implementation.

Exposes the Google ADK Learning Intelligence Agent as an official Agent-to-Agent (A2A)
service over HTTP/JSON-RPC, publishing an Agent Card, managing A2A task lifecycles,
and exchanging structured learning analysis artifacts.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from google.protobuf.json_format import MessageToDict, ParseDict

from a2a.types import (
    AgentCard,
    AgentSkill,
    Artifact,
    Message,
    Part,
    Role,
    Task,
    TaskState,
    TaskStatus,
)
from backend.a2a_protocol.schemas import (
    A2AErrorResponse,
    A2ATaskMetadata,
    AgentExecutionMetadata,
    LearningAnalysisA2ARequest,
    LearningAnalysisA2AResponse,
    LearningAnalysisArtifact,
)
from backend.a2a_protocol.security import (
    get_internal_a2a_token,
    sanitize_and_check_injection,
    validate_student_isolation,
    verify_a2a_token,
)
from backend.adk.services.adk_runner import (
    ADKLearningIntelligenceService,
    adk_learning_service,
)
from backend.adk.schemas.adk_messages import (
    AssessmentEvidence,
    DiagnosticEvidence,
    LearningIntelligenceRequest,
    LearningIntelligenceResponse,
    TopicPerformance,
)

logger = logging.getLogger("gyaan_ai.a2a.server")

# ------------------------------------------------------------------------------
# In-Memory Thread-Safe A2A Task Store
# ------------------------------------------------------------------------------
class A2ATaskRecord:
    """Represents the internal state of an A2A task."""

    def __init__(
        self,
        task_id: str,
        context_id: str,
        correlation_id: str,
        student_id: str,
        session_id: str,
        source_agent: str = "orchestrator",
        target_agent: str = "learning_intelligence_agent",
    ) -> None:
        self.task_id = task_id
        self.context_id = context_id
        self.correlation_id = correlation_id
        self.student_id = student_id
        self.session_id = session_id
        self.source_agent = source_agent
        self.target_agent = target_agent
        self.state = "submitted"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.artifact: Optional[LearningAnalysisArtifact] = None
        self.error: Optional[str] = None
        self.duration_ms: float = 0.0

    def to_metadata(self) -> A2ATaskMetadata:
        return A2ATaskMetadata(
            task_id=self.task_id,
            context_id=self.context_id,
            correlation_id=self.correlation_id,
            state=self.state,
            source_agent=self.source_agent,
            target_agent=self.target_agent,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class A2ATaskStore:
    """Thread-safe in-memory store for A2A tasks and state transitions."""

    def __init__(self) -> None:
        self._tasks: Dict[str, A2ATaskRecord] = {}
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        context_id: str,
        correlation_id: str,
        student_id: str,
        session_id: str,
        source_agent: str = "orchestrator",
    ) -> A2ATaskRecord:
        task_id = f"a2a_task_{uuid.uuid4().hex[:12]}"
        record = A2ATaskRecord(
            task_id=task_id,
            context_id=context_id,
            correlation_id=correlation_id,
            student_id=student_id,
            session_id=session_id,
            source_agent=source_agent,
        )
        async with self._lock:
            self._tasks[task_id] = record
        logger.info("A2A Task created: %s (correlation_id=%s, student=%s)", task_id, correlation_id, student_id)
        return record

    async def get_task(self, task_id: str) -> Optional[A2ATaskRecord]:
        async with self._lock:
            return self._tasks.get(task_id)

    async def list_tasks(self, limit: int = 50) -> List[A2ATaskRecord]:
        async with self._lock:
            return list(self._tasks.values())[-limit:]

    async def set_working(self, task_id: str) -> None:
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].state = "working"
                self._tasks[task_id].updated_at = datetime.now(timezone.utc).isoformat()

    async def set_completed(
        self,
        task_id: str,
        artifact: LearningAnalysisArtifact,
        duration_ms: float,
    ) -> None:
        async with self._lock:
            if task_id in self._tasks:
                rec = self._tasks[task_id]
                rec.state = "completed"
                rec.artifact = artifact
                rec.duration_ms = duration_ms
                rec.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("A2A Task completed: %s (duration=%.2fms)", task_id, duration_ms)

    async def set_failed(self, task_id: str, error_message: str, duration_ms: float = 0.0) -> None:
        async with self._lock:
            if task_id in self._tasks:
                rec = self._tasks[task_id]
                rec.state = "failed"
                rec.error = error_message
                rec.duration_ms = duration_ms
                rec.updated_at = datetime.now(timezone.utc).isoformat()
        logger.warning("A2A Task failed: %s error=%s", task_id, error_message)

    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            if task_id in self._tasks:
                rec = self._tasks[task_id]
                rec.state = "canceled"
                rec.updated_at = datetime.now(timezone.utc).isoformat()
                return True
            return False


# Global singleton task store
a2a_task_store = A2ATaskStore()


# ------------------------------------------------------------------------------
# Official A2A Protocol Agent Card Builder
# ------------------------------------------------------------------------------
def build_learning_intelligence_agent_card(
    base_url: str = "http://127.0.0.1:8000/api/v1/a2a",
) -> Dict[str, Any]:
    """Generates the official Agent Card specification advertising genuine capabilities."""
    clean_url = base_url.rstrip("/")
    card_dict: Dict[str, Any] = {
        "name": "learning_intelligence_agent",
        "version": "1.0.0",
        "description": (
            "Gyaan AI Google ADK Learning Intelligence Specialist: analyzes structured diagnostic "
            "and assessment data to discover learning patterns, misconceptions, and pedagogical priorities."
        ),
        "capabilities": {
            "streaming": True,
            "tasks": True,
            "pushNotifications": False,
        },
        "defaultInputModes": ["application/json", "text/plain"],
        "defaultOutputModes": ["application/json", "text/plain"],
        "supportedInterfaces": [
            {
                "url": clean_url,
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "skills": [
            {
                "id": "learning_intelligence_analysis",
                "name": "Learning Intelligence Synthesis",
                "description": (
                    "Synthesizes structured student learning evidence (diagnostic assessments, quiz outcomes, "
                    "error trends) to discover empirical patterns, identify misconceptions, and produce ranked "
                    "learning priorities."
                ),
                "tags": ["learning-intelligence", "diagnostic-synthesis", "adk", "evidence-based"],
                "inputModes": ["application/json", "text/plain"],
                "outputModes": ["application/json"],
            }
        ],
        "securitySchemes": {
            "internalApiKey": {
                "type": "apiKey",
                "name": "X-A2A-Internal-Token",
                "in": "header",
                "description": "Internal secret token authenticating inter-agent requests across HTTP boundary",
            }
        },
    }
    return card_dict


def synthesize_deterministic_learning_artifact(
    req: LearningAnalysisA2ARequest,
) -> LearningAnalysisArtifact:
    """Synthesizes a high-quality deterministic learning intelligence artifact when Ollama is offline.

    Grounds findings directly in the submitted student evidence without hallucinations.
    """
    patterns: List[str] = []
    misconceptions: List[str] = []
    weaknesses: List[str] = []
    priorities: List[str] = []
    evidence_refs: List[str] = []
    recommendations: List[str] = []

    # Process diagnostic evidence
    for d in req.diagnostic_evidence:
        topic = d.get("topic", "General")
        concept = d.get("concept", "Concept")
        misc = d.get("misconception")
        notes = d.get("notes", "")
        if misc:
            misconceptions.append(f"{topic}: {misc}")
            patterns.append(f"Demonstrated conceptual misconception in {concept} ({misc})")
            evidence_refs.append(f"Diagnostic probe on {concept}: {notes or misc}")
        if d.get("status") in ("Demonstrated Misconception", "Needs Remediation", "Demonstrated"):
            priorities.append(f"Remediate misconception in {concept}: {misc or 'foundational gap'}")

    # Process assessment evidence
    for a in req.assessment_evidence:
        topic_name = a.get("topic_name", "Topic")
        err = a.get("error_pattern")
        acc = float(a.get("accuracy_rate", a.get("score_percentage", 50.0)))
        acc_pct = acc * 100.0 if acc <= 1.0 else acc
        if acc_pct < 60.0:
            weaknesses.append(f"{topic_name} (accuracy {acc_pct:.1f}%)")
            evidence_refs.append(f"Assessment score {acc_pct:.1f}% on {topic_name}")
        if err:
            patterns.append(f"Recurring error pattern in {topic_name}: {err}")
            priorities.append(f"Targeted practice on {topic_name}: resolve {err}")

    if not patterns:
        patterns = ["Demonstrated baseline comprehension across evaluated curriculum objectives"]
    if not weaknesses:
        weaknesses = [f"Foundational review of {req.topic_id or 'chapter concepts'}"]
    if not priorities:
        priorities = [f"Reinforce core principles of {req.chapter_id or 'curriculum chapter'}"]
    if not recommendations:
        recommendations = [
            f"Assign targeted NCERT remediation exercises for {req.topic_id or 'weak areas'}",
            "Provide step-by-step worked examples before re-administering formative quiz",
        ]

    summary = (
        f"Learning analysis for student {req.student_id} across {req.chapter_id or 'chapter'}: "
        f"identified {len(misconceptions)} verified misconception(s), {len(weaknesses)} topic weakness(es), "
        f"and formulated {len(priorities)} prioritized pedagogical interventions."
    )

    return LearningAnalysisArtifact(
        artifact_id=f"art_det_{uuid.uuid4().hex[:10]}",
        name="learning_analysis_report",
        summary=summary,
        identified_patterns=patterns,
        recurring_misconceptions=misconceptions,
        topic_level_weaknesses=weaknesses,
        learning_priorities=priorities,
        evidence_references=evidence_refs,
        confidence=0.88,
        recommendations=recommendations,
    )


# ------------------------------------------------------------------------------
# FastAPI A2A Router Definition
# ------------------------------------------------------------------------------
a2a_router = APIRouter(prefix="/api/v1/a2a", tags=["A2A Protocol"])


@a2a_router.get("/health")
async def a2a_health_check() -> Dict[str, Any]:
    """A2A protocol health and readiness probe."""
    return {
        "status": "online",
        "protocol": "A2A",
        "sdk_version": "1.3.0",
        "agent": "learning_intelligence_agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@a2a_router.get("/.well-known/agent-card.json")
@a2a_router.get("/.well-known/agent.json")
@a2a_router.get("/agent-card.json")
async def get_agent_card_endpoint(request: Request) -> Dict[str, Any]:
    """Publishes the official Agent Card for discovery over HTTP."""
    base_url = str(request.base_url).rstrip("/") + "/api/v1/a2a"
    return build_learning_intelligence_agent_card(base_url=base_url)


# ------------------------------------------------------------------------------
# RESTful Structured Task Execution Endpoint
# ------------------------------------------------------------------------------
@a2a_router.post(
    "/tasks/learning-analysis",
    response_model=LearningAnalysisA2AResponse,
    responses={
        400: {"model": A2AErrorResponse},
        401: {"model": A2AErrorResponse},
        403: {"model": A2AErrorResponse},
        500: {"model": A2AErrorResponse},
    },
)
async def execute_learning_analysis_task(
    request: Request,
    req: LearningAnalysisA2ARequest,
    _: bool = Depends(verify_a2a_token),
) -> LearningAnalysisA2AResponse:
    """Executes a structured A2A learning intelligence task through the ADK Runner.

    Transfers student learning evidence from CrewAI Orchestrator across the HTTP boundary,
    executes the ADK Learning Intelligence Agent, and returns a verified A2A artifact.
    """
    start_time = time.perf_counter()
    correlation_id = req.correlation_id or f"corr_{uuid.uuid4().hex[:10]}"

    # Security: validate student session isolation
    validate_student_isolation(req.student_id, req.session_id)

    # Sanitize objectives against prompt injection
    sanitized_objectives = [sanitize_and_check_injection(obj) for obj in req.learning_objectives]

    # Create task record in task store
    task_record = await a2a_task_store.create_task(
        context_id=f"ctx_{req.session_id}",
        correlation_id=correlation_id,
        student_id=req.student_id,
        session_id=req.session_id,
        source_agent="orchestrator",
    )
    await a2a_task_store.set_working(task_record.task_id)

    # Map diagnostic evidence
    diag_obj: Optional[DiagnosticEvidence] = None
    if req.diagnostic_evidence:
        d = req.diagnostic_evidence[0]
        diag_obj = DiagnosticEvidence(
            topic_id=d.get("topic_id", req.topic_id or "topic_01"),
            topic_name=d.get("topic", d.get("topic_name", "General")),
            probes_evaluated=int(d.get("probes_evaluated", 1)),
            score=float(d.get("score", 1.0)),
            accuracy_pct=float(d.get("accuracy_pct", 50.0)),
            identified_misconceptions=[d["misconception"]] if d.get("misconception") else d.get("identified_misconceptions", []),
            mastery_status=d.get("status", "developing"),
        )

    # Map assessment evidence
    assess_objs: List[AssessmentEvidence] = []
    for a in req.assessment_evidence:
        assess_objs.append(
            AssessmentEvidence(
                assessment_type=a.get("assessment_type", "practice_quiz"),
                total_questions=int(a.get("total_questions", 2)),
                correct_answers=int(a.get("correct_answers", 1)),
                percentage=float(a.get("percentage", a.get("score_percentage", 50.0))),
                recurring_errors=[a["error_pattern"]] if a.get("error_pattern") else a.get("recurring_errors", []),
            )
        )

    # Map topic performances
    perf_objs: List[TopicPerformance] = []
    for a in req.assessment_evidence:
        perf_objs.append(
            TopicPerformance(
                topic_id=a.get("topic_id", req.topic_id or "topic_01"),
                topic_name=a.get("topic_name", "Topic"),
                attempts=int(a.get("total_attempts", 1)),
                average_score=float(a.get("accuracy_rate", 0.5) * 100.0 if a.get("accuracy_rate", 0) <= 1.0 else a.get("accuracy_rate", 50.0)),
                current_mastery_level="developing",
                struggle_indicators=[a["error_pattern"]] if a.get("error_pattern") else [],
            )
        )

    # Build internal ADK request
    adk_req = LearningIntelligenceRequest(
        student_id=req.student_id,
        session_id=req.session_id,
        chapter_id=req.chapter_id or "ch_chem_01",
        chapter_name=f"Curriculum Chapter {req.chapter_id or 'General'}",
        topic_id=req.topic_id,
        learning_objectives=sanitized_objectives or req.learning_objectives or ["Master core concepts"],
        diagnostic_evidence=diag_obj,
        assessment_evidence=assess_objs,
        topic_performances=perf_objs,
    )

    from backend.observability import trace_scope, extract_http_trace_context

    inc_trace_id, inc_parent_span_id = extract_http_trace_context(dict(request.headers))
    resolved_trace_id = inc_trace_id or (req.correlation_id if req.correlation_id and len(req.correlation_id) == 32 else None)

    try:
        # Execute ADK Runner with timeout guard and A2A trace span
        with trace_scope(
            name="a2a_learning_analysis",
            span_type="a2a",
            agent_name="A2A Gateway",
            trace_id=resolved_trace_id,
            parent_span_id=inc_parent_span_id,
            input_data={"student_id": req.student_id, "chapter_id": req.chapter_id, "session_id": req.session_id},
            metadata={"correlation_id": correlation_id, "task_id": task_record.task_id},
        ) as a2a_span:
            adk_resp: LearningIntelligenceResponse = await asyncio.wait_for(
                adk_learning_service.analyze_learning(
                    request=adk_req,
                ),
                timeout=75.0,
            )
            a2a_span.output_data = {"status": adk_resp.execution_status}

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        if adk_resp.execution_status == "error":
            x_fallback = request.headers.get("X-A2A-Fallback", "").lower() in ("true", "1") or os.environ.get("A2A_ALLOW_DETERMINISTIC_FALLBACK") == "1"
            if x_fallback:
                logger.info("Ollama offline: synthesizing deterministic learning artifact under fallback mode")
                artifact = synthesize_deterministic_learning_artifact(req)
                await a2a_task_store.set_completed(task_record.task_id, artifact, duration_ms)
                return LearningAnalysisA2AResponse(
                    correlation_id=correlation_id,
                    task_id=task_record.task_id,
                    execution_status="completed",
                    artifact=artifact,
                    agent_metadata=AgentExecutionMetadata(
                        agent_name="learning_intelligence_agent",
                        framework="google-adk",
                        duration_ms=duration_ms,
                        model_name="deterministic_synthesizer",
                        execution_mode="deterministic",
                    ),
                )
            err_msg = f"ADK Runner execution failed: {adk_resp.summary}"
            await a2a_task_store.set_failed(task_record.task_id, err_msg, duration_ms)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=err_msg,
            )

        # Construct structured LearningAnalysisArtifact
        artifact = LearningAnalysisArtifact(
            artifact_id=f"art_{uuid.uuid4().hex[:12]}",
            name="learning_analysis_report",
            summary=adk_resp.summary,
            identified_patterns=adk_resp.identified_patterns,
            recurring_misconceptions=adk_resp.recurring_misconceptions,
            topic_level_weaknesses=adk_resp.topic_level_weaknesses,
            learning_priorities=adk_resp.learning_priorities,
            evidence_references=adk_resp.evidence_references,
            confidence=adk_resp.confidence,
            recommendations=adk_resp.recommendations,
        )

        # Update task state to completed
        await a2a_task_store.set_completed(task_record.task_id, artifact, duration_ms)

        meta = AgentExecutionMetadata(
            agent_name="learning_intelligence_agent",
            framework="google-adk",
            duration_ms=duration_ms,
            model_name="qwen2.5:3b",
            execution_mode="live" if duration_ms > 1000.0 else "deterministic",
        )

        return LearningAnalysisA2AResponse(
            correlation_id=correlation_id,
            task_id=task_record.task_id,
            execution_status="completed",
            artifact=artifact,
            agent_metadata=meta,
        )

    except asyncio.TimeoutError:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        err_msg = "A2A execution timeout: ADK Runner did not complete within 75.0 seconds"
        await a2a_task_store.set_failed(task_record.task_id, err_msg, duration_ms)
        logger.error(err_msg)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=err_msg,
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        err_msg = f"A2A execution failed: {type(exc).__name__}: {str(exc)}"
        await a2a_task_store.set_failed(task_record.task_id, err_msg, duration_ms)
        logger.error(err_msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=err_msg,
        )


# ------------------------------------------------------------------------------
# JSON-RPC 2.0 Official Protocol Handler
# ------------------------------------------------------------------------------
@a2a_router.post("")
@a2a_router.post("/")
async def handle_jsonrpc_request(
    request: Request,
    _: bool = Depends(verify_a2a_token),
) -> JSONResponse:
    """Standard JSON-RPC 2.0 handler implementing the official A2A protocol specification.

    Supported Methods:
    - message/send (or send_message): Submits a message/task to the agent.
    - tasks/get (or get_task): Retrieves the status and artifacts of an existing task.
    - tasks/cancel (or cancel_task): Requests cancellation of an in-progress task.
    - tasks/list (or list_tasks): Lists tracked tasks.
    """
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            },
        )

    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    if not method:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32600, "message": "Invalid Request: missing method"},
            },
        )

    # 1. Method: message/send or send_message
    if method in ("message/send", "send_message"):
        message_data = params.get("message", {})
        metadata = params.get("metadata", {})
        student_id = metadata.get("student_id") or message_data.get("metadata", {}).get("student_id", "student_default")
        session_id = metadata.get("session_id") or message_data.get("metadata", {}).get("session_id", "session_default")
        correlation_id = metadata.get("correlation_id") or f"corr_{uuid.uuid4().hex[:10]}"

        # Security check
        try:
            validate_student_isolation(student_id, session_id)
        except HTTPException as exc:
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32001, "message": exc.detail},
                },
            )

        # Extract text or structured payload from message parts
        text_content = ""
        parts = message_data.get("parts", [])
        for p in parts:
            if "text" in p:
                text_content += p["text"] + "\n"

        # Check injection
        try:
            sanitize_and_check_injection(text_content)
        except HTTPException as exc:
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32002, "message": exc.detail},
                },
            )

        task_record = await a2a_task_store.create_task(
            context_id=f"ctx_{session_id}",
            correlation_id=correlation_id,
            student_id=student_id,
            session_id=session_id,
            source_agent="orchestrator",
        )
        await a2a_task_store.set_working(task_record.task_id)

        # Parse structured learning analysis payload if provided in metadata or text
        diag_evidence = metadata.get("diagnostic_evidence", [])
        assess_evidence = metadata.get("assessment_evidence", [])

        # If not in metadata, attempt parsing JSON from text_content
        if not diag_evidence and not assess_evidence and "{" in text_content:
            try:
                parsed_json = json.loads(text_content.strip())
                diag_evidence = parsed_json.get("diagnostic_evidence", [])
                assess_evidence = parsed_json.get("assessment_evidence", [])
            except Exception:
                pass

        # Execute ADK service
        start_t = time.perf_counter()
        diag_obj_rpc: Optional[DiagnosticEvidence] = None
        if diag_evidence:
            d = diag_evidence[0]
            diag_obj_rpc = DiagnosticEvidence(
                topic_id=d.get("topic_id", "topic_01"),
                topic_name=d.get("topic", d.get("topic_name", "General")),
                probes_evaluated=int(d.get("probes_evaluated", 1)),
                score=float(d.get("score", 1.0)),
                accuracy_pct=float(d.get("accuracy_pct", 50.0)),
                identified_misconceptions=[d["misconception"]] if d.get("misconception") else d.get("identified_misconceptions", []),
                mastery_status=d.get("status", "developing"),
            )

        assess_objs_rpc: List[AssessmentEvidence] = []
        for a in assess_evidence:
            assess_objs_rpc.append(
                AssessmentEvidence(
                    assessment_type=a.get("assessment_type", "practice_quiz"),
                    total_questions=int(a.get("total_questions", 2)),
                    correct_answers=int(a.get("correct_answers", 1)),
                    percentage=float(a.get("percentage", a.get("score_percentage", 50.0))),
                    recurring_errors=[a["error_pattern"]] if a.get("error_pattern") else a.get("recurring_errors", []),
                )
            )

        perf_objs_rpc: List[TopicPerformance] = []
        for a in assess_evidence:
            perf_objs_rpc.append(
                TopicPerformance(
                    topic_id=a.get("topic_id", "topic_01"),
                    topic_name=a.get("topic_name", "Topic"),
                    attempts=int(a.get("total_attempts", 1)),
                    average_score=float(a.get("accuracy_rate", 0.5) * 100.0 if a.get("accuracy_rate", 0) <= 1.0 else a.get("accuracy_rate", 50.0)),
                    current_mastery_level="developing",
                    struggle_indicators=[a["error_pattern"]] if a.get("error_pattern") else [],
                )
            )

        adk_req = LearningIntelligenceRequest(
            student_id=student_id,
            session_id=session_id,
            chapter_id=metadata.get("chapter_id", "ch_general"),
            chapter_name=f"Curriculum Chapter {metadata.get('chapter_id', 'General')}",
            diagnostic_evidence=diag_obj_rpc,
            assessment_evidence=assess_objs_rpc,
            topic_performances=perf_objs_rpc,
        )

        try:
            adk_resp = await asyncio.wait_for(
                adk_learning_service.analyze_learning(adk_req),
                timeout=75.0,
            )
            duration_ms = (time.perf_counter() - start_t) * 1000.0

            if adk_resp.execution_status == "error":
                x_fallback = request.headers.get("X-A2A-Fallback", "").lower() in ("true", "1") or os.environ.get("A2A_ALLOW_DETERMINISTIC_FALLBACK") == "1"
                if x_fallback:
                    artifact = synthesize_deterministic_learning_artifact(
                        LearningAnalysisA2ARequest(
                            student_id=student_id,
                            session_id=session_id,
                            chapter_id=metadata.get("chapter_id", "ch_general"),
                            diagnostic_evidence=diag_evidence,
                            assessment_evidence=assess_evidence,
                            correlation_id=correlation_id,
                        )
                    )
                    await a2a_task_store.set_completed(task_record.task_id, artifact, duration_ms)
                    result_task = {
                        "id": task_record.task_id,
                        "contextId": task_record.context_id,
                        "status": {
                            "state": "TASK_STATE_COMPLETED",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                        "artifacts": [
                            {
                                "artifactId": artifact.artifact_id,
                                "name": artifact.name,
                                "parts": [
                                    {
                                        "mediaType": "application/json",
                                        "text": artifact.model_dump_json(),
                                    }
                                ],
                            }
                        ],
                        "metadata": {
                            "correlation_id": correlation_id,
                            "agent": "learning_intelligence_agent",
                            "framework": "google-adk",
                            "duration_ms": duration_ms,
                            "execution_mode": "deterministic",
                        },
                    }
                    return JSONResponse(
                        status_code=200,
                        content={"jsonrpc": "2.0", "id": req_id, "result": {"task": result_task}},
                    )
                await a2a_task_store.set_failed(task_record.task_id, adk_resp.summary, duration_ms)
                return JSONResponse(
                    status_code=200,
                    content={
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32000,
                            "message": f"Execution error: {adk_resp.summary}",
                            "data": {"task_id": task_record.task_id, "duration_ms": duration_ms},
                        },
                    },
                )

            artifact = LearningAnalysisArtifact(
                artifact_id=f"art_{uuid.uuid4().hex[:12]}",
                summary=adk_resp.summary,
                identified_patterns=adk_resp.identified_patterns,
                recurring_misconceptions=adk_resp.recurring_misconceptions,
                topic_level_weaknesses=adk_resp.topic_level_weaknesses,
                learning_priorities=adk_resp.learning_priorities,
                evidence_references=adk_resp.evidence_references,
                confidence=adk_resp.confidence,
                recommendations=adk_resp.recommendations,
            )
            await a2a_task_store.set_completed(task_record.task_id, artifact, duration_ms)

            # Build A2A Task response object per official protocol
            result_task = {
                "id": task_record.task_id,
                "contextId": task_record.context_id,
                "status": {
                    "state": "TASK_STATE_COMPLETED",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                "artifacts": [
                    {
                        "artifactId": artifact.artifact_id,
                        "name": artifact.name,
                        "parts": [
                            {
                                "mediaType": "application/json",
                                "text": artifact.model_dump_json(),
                            }
                        ],
                    }
                ],
                "metadata": {
                    "correlation_id": correlation_id,
                    "agent": "learning_intelligence_agent",
                    "framework": "google-adk",
                    "duration_ms": duration_ms,
                },
            }

            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"task": result_task},
                },
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            await a2a_task_store.set_failed(task_record.task_id, str(exc), duration_ms)
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": f"Execution error: {str(exc)}",
                        "data": {"task_id": task_record.task_id, "duration_ms": duration_ms},
                    },
                },
            )

    # 2. Method: tasks/get or get_task
    elif method in ("tasks/get", "get_task"):
        task_id = params.get("id") or params.get("task_id")
        if not task_id:
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "Missing task id parameter"},
                },
            )
        rec = await a2a_task_store.get_task(task_id)
        if not rec:
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32004, "message": f"Task not found: {task_id}"},
                },
            )

        task_state_proto = f"TASK_STATE_{rec.state.upper()}"
        artifacts = []
        if rec.artifact:
            artifacts.append(
                {
                    "artifactId": rec.artifact.artifact_id,
                    "name": rec.artifact.name,
                    "parts": [{"mediaType": "application/json", "text": rec.artifact.model_dump_json()}],
                }
            )

        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "task": {
                        "id": rec.task_id,
                        "contextId": rec.context_id,
                        "status": {"state": task_state_proto, "timestamp": rec.updated_at},
                        "artifacts": artifacts,
                        "metadata": {
                            "correlation_id": rec.correlation_id,
                            "student_id": rec.student_id,
                            "duration_ms": rec.duration_ms,
                        },
                    }
                },
            },
        )

    # 3. Method: tasks/cancel or cancel_task
    elif method in ("tasks/cancel", "cancel_task"):
        task_id = params.get("id") or params.get("task_id")
        cancelled = await a2a_task_store.cancel_task(task_id)
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"cancelled": cancelled, "task_id": task_id},
            },
        )

    # 4. Method: tasks/list or list_tasks
    elif method in ("tasks/list", "list_tasks"):
        tasks = await a2a_task_store.list_tasks(limit=20)
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tasks": [
                        {
                            "id": t.task_id,
                            "contextId": t.context_id,
                            "state": t.state,
                            "studentId": t.student_id,
                            "createdAt": t.created_at,
                        }
                        for t in tasks
                    ]
                },
            },
        )

    else:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            },
        )
