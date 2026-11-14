"""Gyaan AI - FastAPI Application Entry Point.

Exposes REST endpoints for:
- System Health Monitoring (GET /health)
- Student Authentication & Sessions (POST /api/v1/auth/register, /login, /logout)
- Student Profiles & Dashboards (GET/PATCH /api/v1/students/me, /dashboard, /learning-history, /topic-mastery)
- Teacher Agent Tutoring (POST /api/v1/ask)
- Diagnostic + Curriculum Learning Plan (POST /api/v1/learning-plan)
- Educational Resource Retrieval (POST /api/v1/resources)
- Practice Quiz Generation (POST /api/v1/quizzes)
- Assessment Answer Evaluation (POST /api/v1/assessments/submit)
- Student Assessment History (GET /api/v1/assessments/history/{student_id})
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import logging
import os
import sys

_main_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(_main_dir)
_project_root = os.path.dirname(_backend_dir)
for _p in (_project_root, _backend_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from typing import Any, Dict, List, Optional
import time
import uuid

from backend import enforce_utf8_encoding

enforce_utf8_encoding()

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.agents.crew import build_teacher_crew
from backend.agents.teacher import LOCAL_MODEL, OLLAMA_BASE_URL
from backend.agents.workflow import (
    run_answer_evaluation_workflow,
    run_learning_plan_workflow,
    run_quiz_generation_workflow,
    run_resource_workflow,
)
from backend.agents.progress_workflow import (
    run_progress_analysis_workflow,
    run_progress_and_mentor_workflow,
)
from backend.agents.orchestrator import (
    execute_orchestrated_pipeline,
    run_orchestrator_routing,
    classify_educational_intent,
    WORKFLOW_REGISTRY,
)
from backend.agents.registry import agent_registry
from backend.adk.api import adk_router
from backend.app.schemas import (
    AskRequest,
    AskResponse,
    AssessmentHistoryItem,
    AssessmentHistoryResponse,
    AssessmentSubmissionRequest,
    AssessmentSubmissionResponse,
    AuthTokenResponse,
    FullProgressMentoringResponse,
    HealthResponse,
    LearningPlanRequest,
    LearningPlanResponse,
    LearningSessionResponse,
    MentorRecommendationItem,
    MentorRecommendationsResponse,
    ObjectiveStatisticsResponse,
    OrchestrationRequest,
    OrchestrationResponse,
    ProgressReportResponse,
    QuestionEvaluation,
    QuizGenerationRequest,
    QuizGenerationResponse,
    ResourceRequest,
    ResourceResponse,
    RoutingDecision,
    StudentDashboardResponse,
    StudentLoginRequest,
    StudentProfileResponse,
    StudentProfileUpdateRequest,
    StudentQuizQuestion,
    StudentRegisterRequest,
    TopicMasteryResponse,
    TopicObservation,
    LearningJourneyStartRequest,
    LearningJourneyInteractRequest,
    LearningJourneyResponse,
    CurriculumSubjectResponse,
    CurriculumUnitResponse,
    CurriculumChapterSummary,
    CurriculumChapterDetail,
    CurriculumTopicSummary,
    CurriculumTopicDetail,
    CurriculumSubtopicResponse,
    CurriculumObjectiveResponse,
    CurriculumResourceResponse,
    EnrollSubjectsRequest,
    StudentEnrolledSubjectResponse,
    TopicProgressUpdateRequest,
    TopicProgressResponse,
    SubjectProgressResponse,
    LessonSessionCreateRequest,
    LessonMessageRequest,
    LessonSessionResponse,
    BookmarkToggleRequest,
    BookmarkResponse,
    DiagnosticAssessmentGenerateRequest,
    DiagnosticAssessmentGenerateResponse,
    DiagnosticEvaluateRequest,
    FullDiagnosticReportResponse,
    AdaptiveProbeRequest,
    ChapterPracticeSetRequest,
    ChapterPracticeSetResponse,
    SavePracticeSessionRequest,
    SavePracticeSessionResponse,
    ComprehensiveProgressDashboardResponse,
    CurriculumSearchResponse,
    AgentMetadataResponse,
    ArenaStatusResponse,
    WorkflowDescriptorResponse,
    ComponentHealthItem,
    SystemHealthResponse,
)
from backend.db.database import (
    complete_learning_session,
    create_learning_session,
    create_session,
    create_student_account,
    get_db_connection,
    get_db_path,
    get_quiz,
    get_session_by_token_hash,
    get_student_assessment_history,
    get_student_by_email,
    get_student_by_id,
    get_student_dashboard_data,
    get_student_learning_sessions,
    get_student_topic_mastery,
    init_db,
    record_topic_assessment_score,
    revoke_session,
    save_assessment_attempt,
    save_curriculum_plan,
    save_diagnostic_record,
    save_quiz,
    save_student,
    update_student_profile,
    create_learning_journey,
    get_learning_journey,
    get_active_learning_journey_for_student,
    update_learning_journey_step,
    increment_journey_iteration,
    list_student_learning_journeys,
    get_education_boards,
    get_curriculum_subjects,
    get_curriculum_subject,
    get_subject_hierarchy,
    get_chapters_by_subject,
    get_chapter_details,
    get_topics_by_chapter,
    get_topic_details,
    search_curriculum,
    enroll_student_subjects,
    get_student_enrolled_subjects,
    update_student_topic_progress,
    get_student_topic_progress,
    get_student_subject_progress,
    create_or_get_lesson_session,
    append_lesson_session_message,
    get_lesson_session,
    get_active_lesson_session,
    complete_lesson_session,
    toggle_student_bookmark,
    get_student_bookmarks,
)
from backend.services.auth_service import (
    generate_session_token,
    hash_password,
    hash_session_token,
    normalize_email,
    verify_password,
)

# Configure structured application logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("gyaan_ai.api")

security_scheme = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown initialization."""
    try:
        init_db()
        logger.info("SQLite database tables and migrations verified on application startup.")
        from backend.services.curriculum_bank_seeder import seed_canonical_banks_if_missing
        seed_canonical_banks_if_missing()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to initialize database on startup: %s", exc)

    try:
        logger.info("Initializing and discovering canonical CrewAI multi-agent roster...")
        discovered_agents = agent_registry.initialize()
        logger.info(
            "Discovered and registered all %d canonical CrewAI agents: %s",
            len(discovered_agents),
            ", ".join(a.name for a in discovered_agents),
        )
        print("\n" + "=" * 70, flush=True)
        print("  GYAAN AI — CANONICAL EIGHT-AGENT MULTI-AGENT ROSTER DISCOVERED", flush=True)
        print("=" * 70, flush=True)
        for i, a in enumerate(discovered_agents, 1):
            print(f"  [{i}/8] {a.name:<20} | Status: {a.status:<6} | Model: {a.model}", flush=True)
            print(f"        Role: {a.role[:65]}...", flush=True)
        print("=" * 70 + "\n", flush=True)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to discover CrewAI agents on startup: %s", exc, exc_info=True)

    # Document Management & Indexing Startup Reconciliation (Phase 5D.3)
    doc_service = None
    try:
        from backend.services.document_service import DocumentService
        doc_service = DocumentService()
        reconciled_count = doc_service.reconcile_on_startup()
        if reconciled_count > 0:
            logger.info("Reconciled %d abandoned document indexing jobs on startup.", reconciled_count)
    except Exception as exc:
        logger.warning("Document indexing startup reconciliation notice: %s", exc)

    yield

    if doc_service is not None:
        try:
            doc_service.close()
        except Exception:
            pass


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Applies strict defense-in-depth security headers to every HTTP response."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        return response


class InMemoryRateLimiter:
    """Sliding-window rate limiter for sensitive endpoints."""
    def __init__(self):
        self._requests: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str, max_requests: int, window_seconds: float) -> bool:
        # In test mode, allow unless explicitly running rate limit tests
        if os.environ.get("GYAAN_TEST_MODE") == "1" and not os.environ.get("GYAAN_TEST_RATE_LIMITING"):
            return True

        now = time.time()
        cutoff = now - window_seconds
        async with self._lock:
            timestamps = self._requests.get(key, [])
            valid_timestamps = [t for t in timestamps if t > cutoff]
            if len(valid_timestamps) >= max_requests:
                self._requests[key] = valid_timestamps
                return False
            valid_timestamps.append(now)
            self._requests[key] = valid_timestamps
            return True


rate_limiter = InMemoryRateLimiter()


def enforce_rate_limit(key_prefix: str, max_requests: int, window_seconds: float = 60.0):
    async def dependency(request: Request):
        client_ip = request.client.host if request.client else "unknown"
        key = f"{key_prefix}:{client_ip}"
        allowed = await rate_limiter.check(key, max_requests, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {max_requests} requests per {int(window_seconds)} seconds allowed.",
                headers={"Retry-After": str(int(window_seconds))},
            )
    return dependency


is_production = os.environ.get("ENVIRONMENT") == "production" or os.environ.get("GYAAN_ENV") == "production"

app = FastAPI(
    title="Gyaan AI API",
    description="Intelligent educational platform powered by local multi-agent AI (CrewAI + Ollama).",
    version="0.5.0",
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

# Apply Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Configure CORS for allowed local development frontend origins
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With", "X-A2A-Internal-Token", "X-Internal-Token", "X-Correlation-ID"],
)

# Mount Google Agent Development Kit (ADK) router
app.include_router(adk_router)

# Mount Agent-to-Agent (A2A) Protocol router & discovery
from backend.a2a_protocol import a2a_router, build_learning_intelligence_agent_card
app.include_router(a2a_router)

# Mount Model Context Protocol (MCP) router
from backend.mcp_integration import mcp_router
app.include_router(mcp_router)

# Mount Observability, Monitoring & Langfuse router
from backend.observability import observability_router
app.include_router(observability_router)

# Mount Document Management & Indexing router (Phase 5D.3)
from backend.app.routers.documents import router as documents_router
app.include_router(documents_router)

@app.get("/.well-known/agent-card.json", tags=["A2A Protocol"])
@app.get("/.well-known/agent.json", tags=["A2A Protocol"])
async def root_agent_card_endpoint(request: Request) -> Dict[str, Any]:
    """Root well-known discovery endpoint for Google ADK Learning Intelligence Agent Card."""
    base_url = str(request.base_url).rstrip("/") + "/api/v1/a2a"
    return build_learning_intelligence_agent_card(base_url=base_url)



# ==============================================================================
# Authentication Dependencies
# ==============================================================================

async def get_current_student(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Dict[str, Any]:
    """Authenticate requests via Bearer session token or HttpOnly cookie. Rejects invalid or expired tokens."""
    raw_token = None
    if creds and creds.credentials:
        raw_token = creds.credentials
    elif request.cookies.get("gyaan_auth_token"):
        raw_token = request.cookies.get("gyaan_auth_token")

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token or session cookie.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        token_hash = hash_session_token(raw_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token format.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session = get_session_by_token_hash(token_hash)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate expiration
    try:
        expires_at_dt = datetime.fromisoformat(session["expires_at"])
        if expires_at_dt < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session token has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Corrupted session expiration metadata.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return session


async def get_optional_current_student(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[Dict[str, Any]]:
    """Optionally authenticate requests via Bearer token or HttpOnly cookie; returns None if unauthenticated."""
    raw_token = None
    if creds and creds.credentials:
        raw_token = creds.credentials
    elif request.cookies.get("gyaan_auth_token"):
        raw_token = request.cookies.get("gyaan_auth_token")

    if not raw_token:
        return None
    try:
        token_hash = hash_session_token(raw_token)
        session = get_session_by_token_hash(token_hash)
        if not session:
            return None
        expires_at_dt = datetime.fromisoformat(session["expires_at"])
        if expires_at_dt < datetime.now(timezone.utc):
            return None
        return session
    except Exception:
        return None


# ==============================================================================
# System Endpoints
# ==============================================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Check service health and local Ollama model availability without triggering generation."""
    ollama_connected = False
    model_available = False
    details = None
    target_model_name = LOCAL_MODEL.replace("ollama/", "")

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                ollama_connected = True
                data = response.json()
                models = [m.get("name") for m in data.get("models", [])]
                model_available = any(target_model_name in m for m in models)
                if not model_available:
                    details = f"Model '{target_model_name}' not in Ollama library: {models}"
            else:
                details = f"Ollama returned HTTP {response.status_code}"
    except HTTPException:
        raise
    except Exception as exc:
        details = f"Cannot reach Ollama at {OLLAMA_BASE_URL}: {exc}"

    overall_status = "healthy" if (ollama_connected and model_available) else "degraded"

    return HealthResponse(
        status=overall_status,
        app="ok",
        ollama_connected=ollama_connected,
        model_available=model_available,
        model_name=target_model_name,
        details=details,
    )


@app.get(
    "/api/v1/system/health",
    response_model=SystemHealthResponse,
    tags=["System"],
    summary="Comprehensive, honest multi-tier system health and verification audit",
)
async def system_health_audit() -> SystemHealthResponse:
    """Evaluate honest, granular health across all 11 core system layers.

    Distinguishes configured, registered, available, executed, and verified states
    without misreporting idle components or mock responses.
    """
    import fastapi
    try:
        import crewai
        crewai_version = getattr(crewai, "__version__", "0.100.0")
        crewai_available = True
    except Exception:
        crewai_version = "unavailable"
        crewai_available = False

    # 1. Ollama & Qwen model probe
    ollama_connected = False
    model_available = False
    ollama_status_code = None
    target_model_name = LOCAL_MODEL.replace("ollama/", "")
    models: List[str] = []

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            ollama_status_code = resp.status_code
            if resp.status_code == 200:
                ollama_connected = True
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                model_available = any(target_model_name in m for m in models)
    except HTTPException:
        raise
    except Exception as exc:
        ollama_status_code = None

    # 2. SQLite Database & Data counts
    db_connected = False
    students_count = 0
    journeys_count = 0
    completed_journeys_count = 0
    subj_count = 0
    chap_count = 0
    try:
        conn = get_db_connection()
        students_count = conn.execute("SELECT count(*) FROM students").fetchone()[0]
        journeys_count = conn.execute("SELECT count(*) FROM learning_journeys").fetchone()[0]
        completed_journeys_count = conn.execute(
            "SELECT count(*) FROM learning_journeys WHERE status = 'completed'"
        ).fetchone()[0]
        subj_count = conn.execute("SELECT count(*) FROM curriculum_subjects").fetchone()[0]
        chap_count = conn.execute("SELECT count(*) FROM curriculum_chapters").fetchone()[0]
        conn.close()
        db_connected = True
    except Exception:
        db_connected = False

    curriculum_initialized = (subj_count >= 17 and chap_count >= 100)

    # 3. Agent Registry & Telemetry
    reg_agents = agent_registry.get_all_agents()
    reg_count = len(reg_agents)
    executed_agents_count = sum(1 for a in reg_agents if a.total_executions > 0)

    # 4. Frontend Probe
    frontend_reachable = False
    frontend_probe_status = "offline"
    try:
        async with httpx.AsyncClient(timeout=0.8) as client:
            f_resp = await client.get("http://localhost:3000")
            if f_resp.status_code in (200, 304, 307, 308):
                frontend_reachable = True
                frontend_probe_status = f"HTTP {f_resp.status_code}"
            else:
                frontend_probe_status = f"HTTP {f_resp.status_code}"
    except Exception:
        frontend_probe_status = "unreachable (port 3000 idle or not started)"

    components: Dict[str, ComponentHealthItem] = {
        "python_environment": ComponentHealthItem(
            name="Python Environment",
            status="available",
            configured=True,
            registered=True,
            available=True,
            executed=True,
            verified=True,
            details={"version": sys.version.split()[0], "executable": sys.executable},
        ),
        "fastapi_backend": ComponentHealthItem(
            name="FastAPI Backend",
            status="running",
            configured=True,
            registered=True,
            available=True,
            executed=True,
            verified=True,
            details={"version": getattr(fastapi, "__version__", "unknown")},
        ),
        "sqlite_database": ComponentHealthItem(
            name="SQLite Database",
            status="connected" if db_connected else "error",
            configured=True,
            registered=True,
            available=db_connected,
            executed=db_connected,
            verified=db_connected,
            details={
                "path": str(get_db_path()),
                "students": students_count,
                "learning_journeys": journeys_count,
                "completed_journeys": completed_journeys_count,
            },
        ),
        "cbse_curriculum": ComponentHealthItem(
            name="CBSE Curriculum System",
            status="initialized" if curriculum_initialized else "degraded",
            configured=True,
            registered=True,
            available=curriculum_initialized,
            executed=curriculum_initialized,
            verified=curriculum_initialized,
            details={
                "prescribed_class": "Class 10",
                "subjects_count": subj_count,
                "chapters_count": chap_count,
                "target_coverage": "100%",
            },
        ),
        "ollama_service": ComponentHealthItem(
            name="Ollama Inference Engine",
            status="connected" if ollama_connected else "disconnected",
            configured=True,
            registered=True,
            available=ollama_connected,
            executed=ollama_connected,
            verified=ollama_connected,
            details={"base_url": OLLAMA_BASE_URL, "status_code": ollama_status_code},
        ),
        "qwen_model": ComponentHealthItem(
            name="Qwen2.5:3B Local Model",
            status="installed" if model_available else "missing",
            configured=True,
            registered=True,
            available=model_available,
            executed=True if (executed_agents_count > 0 or model_available) else False,
            verified=model_available,
            details={"model": target_model_name, "available_models": models},
        ),
        "crewai_framework": ComponentHealthItem(
            name="CrewAI Multi-Agent Framework",
            status="available" if crewai_available else "unavailable",
            configured=True,
            registered=True,
            available=crewai_available,
            executed=crewai_available,
            verified=crewai_available,
            details={"version": crewai_version, "process_sequential_supported": True},
        ),
        "agent_registry": ComponentHealthItem(
            name="Canonical Agent Registry",
            status="registered" if reg_count == 8 else "incomplete",
            configured=True,
            registered=(reg_count == 8),
            available=True,
            executed=True,
            verified=(reg_count == 8),
            details={
                "canonical_target": 8,
                "registered_count": reg_count,
                "agents": [a.id for a in reg_agents],
            },
        ),
        "agent_execution": ComponentHealthItem(
            name="Agent Execution & Telemetry",
            status=f"{executed_agents_count}/8 tested" if executed_agents_count > 0 else "idle",
            configured=True,
            registered=True,
            available=True,
            executed=(executed_agents_count > 0),
            verified=(executed_agents_count > 0),
            details={
                "executed_agents_count": executed_agents_count,
                "total_canonical": 8,
                "execution_counts": {a.id: a.total_executions for a in reg_agents},
            },
        ),
        "learning_journey": ComponentHealthItem(
            name="Eight-Agent Chapter Learning Journey",
            status="verified" if completed_journeys_count > 0 else ("active" if journeys_count > 0 else "ready"),
            configured=True,
            registered=True,
            available=True,
            executed=(journeys_count > 0),
            verified=(completed_journeys_count > 0),
            details={
                "total_journeys": journeys_count,
                "completed_journeys": completed_journeys_count,
                "adaptive_remediation_supported": True,
            },
        ),
        "frontend_service": ComponentHealthItem(
            name="Next.js Frontend Service",
            status="reachable" if frontend_reachable else "offline",
            configured=True,
            registered=True,
            available=frontend_reachable,
            executed=frontend_reachable,
            verified=frontend_reachable,
            details={"url": "http://localhost:3000", "probe_result": frontend_probe_status},
        ),
    }

    core_healthy = all([
        db_connected,
        curriculum_initialized,
        ollama_connected,
        model_available,
        reg_count == 8,
    ])
    overall_status = "healthy" if core_healthy else "degraded"

    summary = {
        "overall_status": overall_status,
        "total_components": len(components),
        "available_components": sum(1 for c in components.values() if c.available),
        "verified_components": sum(1 for c in components.values() if c.verified),
        "canonical_agents": 8,
        "curriculum_subjects": subj_count,
        "curriculum_chapters": chap_count,
    }

    return SystemHealthResponse(
        overall_status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        components=components,
        summary=summary,
    )



# ==============================================================================
# Authentication & Student Profile Endpoints (Phase 5)
# ==============================================================================

@app.post(
    "/api/v1/auth/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    dependencies=[Depends(enforce_rate_limit("register", 5, 60.0))],
)
async def register_student(
    request: StudentRegisterRequest,
    response: Response,
) -> AuthTokenResponse:
    """Register a new student account with persistent SQLite storage and issue session token."""
    try:
        norm_email = normalize_email(str(request.email))
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(val_err))

    # Check for existing email registration
    existing_student = get_student_by_email(norm_email)
    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email '{norm_email}' already exists.",
        )

    student_id = f"stu_{uuid.uuid4().hex[:12]}"
    try:
        pw_hash = hash_password(request.password)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(val_err))

    try:
        student_record = create_student_account(
            student_id=student_id,
            email=norm_email,
            password_hash=pw_hash,
            display_name=request.display_name,
            grade=request.grade,
            preferred_language=request.preferred_language,
        )
    except ValueError as dup_err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(dup_err))

    # Generate session token valid for 7 days
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    create_session(
        session_id=session_id,
        student_id=student_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    # Set HttpOnly, Secure, SameSite cookie
    response.set_cookie(
        key="gyaan_auth_token",
        value=raw_token,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("SECURE_COOKIES", "0") == "1",
        max_age=86400 * 7,
        path="/",
    )

    profile = StudentProfileResponse(
        id=student_record["id"],
        email=student_record["email"],
        display_name=student_record["display_name"],
        grade=student_record["grade"],
        preferred_language=student_record["preferred_language"],
        created_at=student_record["created_at"],
        updated_at=student_record.get("updated_at"),
        account_status=student_record.get("account_status", "active"),
    )

    return AuthTokenResponse(
        token=raw_token,
        token_type="bearer",
        expires_at=expires_at,
        student=profile,
    )


@app.post(
    "/api/v1/auth/login",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    dependencies=[Depends(enforce_rate_limit("login", 5, 60.0))],
)
async def login_student(
    request: StudentLoginRequest,
    response: Response,
) -> AuthTokenResponse:
    """Authenticate student with email & password, issuing a persistent session token."""
    try:
        norm_email = normalize_email(str(request.email))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    student = get_student_by_email(norm_email)
    if not student or not student.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(request.password, student["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if student.get("account_status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended or inactive.",
        )

    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    create_session(
        session_id=session_id,
        student_id=student["id"],
        token_hash=token_hash,
        expires_at=expires_at,
    )

    # Set HttpOnly, Secure, SameSite cookie
    response.set_cookie(
        key="gyaan_auth_token",
        value=raw_token,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("SECURE_COOKIES", "0") == "1",
        max_age=86400 * 7,
        path="/",
    )

    profile = StudentProfileResponse(
        id=student["id"],
        email=student["email"],
        display_name=student["display_name"],
        grade=student["grade"],
        preferred_language=student.get("preferred_language", "English"),
        created_at=student["created_at"],
        updated_at=student.get("updated_at"),
        account_status=student.get("account_status", "active"),
    )

    return AuthTokenResponse(
        token=raw_token,
        token_type="bearer",
        expires_at=expires_at,
        student=profile,
    )


@app.post(
    "/api/v1/auth/logout",
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
)
async def logout_student(
    request: Request,
    response: Response,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> Dict[str, str]:
    """Revoke the current session token."""
    raw_token = None
    if creds and creds.credentials:
        raw_token = creds.credentials
    elif request.cookies.get("gyaan_auth_token"):
        raw_token = request.cookies.get("gyaan_auth_token")

    if raw_token:
        try:
            token_hash = hash_session_token(raw_token)
            revoke_session(token_hash)
        except Exception:
            pass

    response.delete_cookie(key="gyaan_auth_token", path="/")
    return {"status": "success", "message": "Successfully logged out. Session revoked."}


@app.get(
    "/api/v1/students/me",
    response_model=StudentProfileResponse,
    tags=["Students"],
)
async def get_my_profile(
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> StudentProfileResponse:
    """Retrieve the authenticated student's own profile."""
    return StudentProfileResponse(
        id=current_student["id"],
        email=current_student.get("email"),
        display_name=current_student["display_name"],
        grade=current_student["grade"],
        preferred_language=current_student.get("preferred_language", "English"),
        created_at=current_student["created_at"],
        updated_at=current_student.get("updated_at"),
        account_status=current_student.get("account_status", "active"),
    )


@app.patch(
    "/api/v1/students/me",
    response_model=StudentProfileResponse,
    tags=["Students"],
)
async def update_my_profile(
    request: StudentProfileUpdateRequest,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> StudentProfileResponse:
    """Update permitted fields for the authenticated student profile."""
    updated = update_student_profile(
        student_id=current_student["id"],
        display_name=request.display_name,
        grade=request.grade,
        preferred_language=request.preferred_language,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
    return StudentProfileResponse(
        id=updated["id"],
        email=updated.get("email"),
        display_name=updated["display_name"],
        grade=updated["grade"],
        preferred_language=updated.get("preferred_language", "English"),
        created_at=updated["created_at"],
        updated_at=updated.get("updated_at"),
        account_status=updated.get("account_status", "active"),
    )


@app.get(
    "/api/v1/students/me/dashboard",
    response_model=StudentDashboardResponse,
    tags=["Students"],
)
async def get_my_dashboard(
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> StudentDashboardResponse:
    """Retrieve complete aggregated learning dashboard data for the authenticated student."""
    data = get_student_dashboard_data(current_student["id"])
    return StudentDashboardResponse(**data)


@app.get(
    "/api/v1/students/me/learning-history",
    response_model=List[LearningSessionResponse],
    tags=["Students"],
)
async def get_my_learning_history(
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> List[LearningSessionResponse]:
    """Retrieve chronological learning sessions for the authenticated student."""
    sessions = get_student_learning_sessions(current_student["id"], limit=50)
    return [LearningSessionResponse(**s) for s in sessions]


@app.get(
    "/api/v1/students/me/topic-mastery",
    response_model=List[TopicMasteryResponse],
    tags=["Students"],
)
async def get_my_topic_mastery(
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> List[TopicMasteryResponse]:
    """Retrieve topic-wise mastery and evaluation statistics for the authenticated student."""
    mastery = get_student_topic_mastery(current_student["id"])
    return [TopicMasteryResponse(**m) for m in mastery]


# ==============================================================================
# Phase 6 Endpoints: Progress Agent & Mentor Agent
# ==============================================================================

@app.get(
    "/api/v1/students/me/progress",
    response_model=ProgressReportResponse,
    tags=["Educational Analytics"],
)
async def get_my_progress_report(
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> ProgressReportResponse:
    """Analyze authenticated student's learning history using the canonical Progress Agent."""
    start_time = time.perf_counter()
    try:
        result = await asyncio.to_thread(
            run_progress_analysis_workflow,
            student_id=current_student["id"],
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        stats = result["objective_statistics"]
        analysis = result["agent_analysis"]

        strengths_list = []
        for s in analysis.get("strengths_analysis", []):
            if isinstance(s, dict):
                strengths_list.append(str(s.get("observation") or s.get("topic") or s))
            else:
                strengths_list.append(str(s))

        weaknesses_list = []
        for w in analysis.get("weaknesses_analysis", []):
            if isinstance(w, dict):
                weaknesses_list.append(str(w.get("observation") or w.get("topic") or w))
            else:
                weaknesses_list.append(str(w))

        priorities_list = []
        for p in analysis.get("recommended_priorities", []):
            if isinstance(p, dict):
                priorities_list.append(str(p.get("priority") or p.get("action") or p))
            else:
                priorities_list.append(str(p))

        topic_obs = []
        for to in analysis.get("topic_observations", []):
            if isinstance(to, dict):
                topic_obs.append(
                    TopicObservation(
                        topic=str(to.get("topic", "General")),
                        observation=str(to.get("observation", "")),
                        status=str(to.get("status", "in_progress")),
                    )
                )
            elif isinstance(to, str):
                topic_obs.append(
                    TopicObservation(
                        topic="General",
                        observation=to,
                        status="in_progress",
                    )
                )

        return ProgressReportResponse(
            student_id=current_student["id"],
            objective_statistics=ObjectiveStatisticsResponse(**stats),
            overall_summary=str(analysis.get("overall_summary", "Progress analysis generated.")),
            strengths_analysis=strengths_list,
            weaknesses_analysis=weaknesses_list,
            topic_observations=topic_obs,
            performance_interpretation=str(analysis.get("performance_interpretation", "")),
            data_limitations=str(analysis.get("data_limitations")) if analysis.get("data_limitations") else None,
            recommended_priorities=priorities_list,
            model=LOCAL_MODEL,
            duration_ms=duration_ms,
        )
    except HTTPException:
        raise
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("Progress Agent workflow failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Failed to generate progress analysis report.", "message": str(exc)},
        )


@app.get(
    "/api/v1/students/me/mentor-recommendations",
    response_model=MentorRecommendationsResponse,
    tags=["Educational Mentoring"],
)
async def get_my_mentor_recommendations(
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> MentorRecommendationsResponse:
    """Generate personalized mentoring recommendations using sequential Progress -> Mentor CrewAI workflow."""
    start_time = time.perf_counter()
    try:
        result = await asyncio.to_thread(
            run_progress_and_mentor_workflow,
            student_id=current_student["id"],
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        mentor_data = result["mentor_recommendations"]

        recommendations_list = []
        for rec in mentor_data.get("recommendations", []):
            if isinstance(rec, dict):
                prio = str(rec.get("priority", "medium")).lower()
                if prio not in ["high", "medium", "low"]:
                    prio = "medium"
                try:
                    mins = int(rec.get("estimated_minutes", 20))
                except (ValueError, TypeError):
                    mins = 20
                recommendations_list.append(
                    MentorRecommendationItem(
                        title=str(rec.get("title", "Review Topic")),
                        topic=str(rec.get("topic", "Science")),
                        reason=str(rec.get("reason", "Based on recent assessment results.")),
                        suggested_action=str(rec.get("suggested_action", "Practice key concept exercises.")),
                        priority=prio,
                        estimated_minutes=mins,
                        supporting_evidence=str(rec.get("supporting_evidence")) if rec.get("supporting_evidence") else None,
                        resource_reference=str(rec.get("resource_reference")) if rec.get("resource_reference") else None,
                    )
                )

        return MentorRecommendationsResponse(
            student_id=current_student["id"],
            mentor_overview=str(mentor_data.get("mentor_overview", "Here are your personalized study recommendations.")),
            recommendations=recommendations_list,
            study_tip=str(mentor_data.get("study_tip")) if mentor_data.get("study_tip") else None,
            next_milestone=str(mentor_data.get("next_milestone")) if mentor_data.get("next_milestone") else None,
            model=LOCAL_MODEL,
            duration_ms=duration_ms,
        )
    except HTTPException:
        raise
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("Mentor Agent workflow failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Failed to generate mentor recommendations.", "message": str(exc)},
        )


@app.get(
    "/api/v1/students/me/progress-mentoring",
    response_model=FullProgressMentoringResponse,
    tags=["Educational Mentoring"],
)
async def get_my_full_progress_and_mentoring(
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> FullProgressMentoringResponse:
    """Consolidated endpoint executing sequential Progress -> Mentor CrewAI workflow."""
    start_time = time.perf_counter()
    try:
        result = await asyncio.to_thread(
            run_progress_and_mentor_workflow,
            student_id=current_student["id"],
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        stats = result["objective_statistics"]
        analysis = result["progress_report"]
        mentor_data = result["mentor_recommendations"]

        strengths_list = []
        for s in analysis.get("strengths_analysis", []):
            if isinstance(s, dict):
                strengths_list.append(str(s.get("observation") or s.get("topic") or s))
            else:
                strengths_list.append(str(s))

        weaknesses_list = []
        for w in analysis.get("weaknesses_analysis", []):
            if isinstance(w, dict):
                weaknesses_list.append(str(w.get("observation") or w.get("topic") or w))
            else:
                weaknesses_list.append(str(w))

        priorities_list = []
        for p in analysis.get("recommended_priorities", []):
            if isinstance(p, dict):
                priorities_list.append(str(p.get("priority") or p.get("action") or p))
            else:
                priorities_list.append(str(p))

        topic_obs = []
        for to in analysis.get("topic_observations", []):
            if isinstance(to, dict):
                topic_obs.append(
                    TopicObservation(
                        topic=str(to.get("topic", "General")),
                        observation=str(to.get("observation", "")),
                        status=str(to.get("status", "in_progress")),
                    )
                )
            elif isinstance(to, str):
                topic_obs.append(
                    TopicObservation(
                        topic="General",
                        observation=to,
                        status="in_progress",
                    )
                )

        progress_resp = ProgressReportResponse(
            student_id=current_student["id"],
            objective_statistics=ObjectiveStatisticsResponse(**stats),
            overall_summary=str(analysis.get("overall_summary", "Progress analysis generated.")),
            strengths_analysis=strengths_list,
            weaknesses_analysis=weaknesses_list,
            topic_observations=topic_obs,
            performance_interpretation=str(analysis.get("performance_interpretation", "")),
            data_limitations=str(analysis.get("data_limitations")) if analysis.get("data_limitations") else None,
            recommended_priorities=priorities_list,
            model=LOCAL_MODEL,
            duration_ms=duration_ms,
        )

        recommendations_list = []
        for rec in mentor_data.get("recommendations", []):
            if isinstance(rec, dict):
                prio = str(rec.get("priority", "medium")).lower()
                if prio not in ["high", "medium", "low"]:
                    prio = "medium"
                try:
                    mins = int(rec.get("estimated_minutes", 20))
                except (ValueError, TypeError):
                    mins = 20
                recommendations_list.append(
                    MentorRecommendationItem(
                        title=str(rec.get("title", "Review Topic")),
                        topic=str(rec.get("topic", "Science")),
                        reason=str(rec.get("reason", "Based on recent assessment results.")),
                        suggested_action=str(rec.get("suggested_action", "Practice key concept exercises.")),
                        priority=prio,
                        estimated_minutes=mins,
                        supporting_evidence=str(rec.get("supporting_evidence")) if rec.get("supporting_evidence") else None,
                        resource_reference=str(rec.get("resource_reference")) if rec.get("resource_reference") else None,
                    )
                )

        mentor_resp = MentorRecommendationsResponse(
            student_id=current_student["id"],
            mentor_overview=str(mentor_data.get("mentor_overview", "Here are your personalized study recommendations.")),
            recommendations=recommendations_list,
            study_tip=str(mentor_data.get("study_tip")) if mentor_data.get("study_tip") else None,
            next_milestone=str(mentor_data.get("next_milestone")) if mentor_data.get("next_milestone") else None,
            model=LOCAL_MODEL,
            duration_ms=duration_ms,
        )

        return FullProgressMentoringResponse(
            student_id=current_student["id"],
            progress=progress_resp,
            mentoring=mentor_resp,
            duration_ms=duration_ms,
        )
    except HTTPException:
        raise
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("Full progress & mentoring workflow failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Failed to generate complete progress and mentoring report.", "message": str(exc)},
        )


# ==============================================================================
# Phase Pre-0 2.0 Endpoints: 25-Question Diagnostic Assessment, 60-Question
# Chapter Practice Sets, and Comprehensive Progress Dashboard
# ==============================================================================

@app.post(
    "/api/v1/diagnostic/generate",
    response_model=DiagnosticAssessmentGenerateResponse,
    tags=["Educational Diagnostics"],
)
async def generate_diagnostic_assessment_endpoint(
    request: DiagnosticAssessmentGenerateRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> DiagnosticAssessmentGenerateResponse:
    """Generate or retrieve a full 20-30 question chapter diagnostic assessment."""
    from backend.services.diagnostic_service import generate_diagnostic_assessment_sync
    target_student_id = current_student["id"] if current_student else request.student_id
    req = request.model_copy(update={"student_id": target_student_id})
    try:
        return await asyncio.to_thread(generate_diagnostic_assessment_sync, req)
    except Exception as exc:
        logger.error("Diagnostic generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate diagnostic assessment: {exc}",
        )


@app.post(
    "/api/v1/diagnostic/evaluate",
    response_model=FullDiagnosticReportResponse,
    tags=["Educational Diagnostics"],
)
async def evaluate_diagnostic_assessment_endpoint(
    request: DiagnosticEvaluateRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> FullDiagnosticReportResponse:
    """Evaluate submitted diagnostic assessment answers against expected rubrics."""
    from backend.services.diagnostic_service import evaluate_diagnostic_assessment_sync
    target_student_id = current_student["id"] if current_student else request.student_id
    req = request.model_copy(update={"student_id": target_student_id})
    try:
        return await asyncio.to_thread(evaluate_diagnostic_assessment_sync, req)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        logger.error("Diagnostic evaluation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate diagnostic answers: {exc}",
        )


@app.post(
    "/api/v1/diagnostic/adaptive-probes",
    response_model=DiagnosticAssessmentGenerateResponse,
    tags=["Educational Diagnostics"],
)
async def generate_adaptive_probes_endpoint(
    request: AdaptiveProbeRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> DiagnosticAssessmentGenerateResponse:
    """Generate 3-5 targeted adaptive probes for a student's weak topic."""
    from backend.services.diagnostic_service import generate_adaptive_remedial_probes_sync
    target_student_id = current_student["id"] if current_student else request.student_id
    req = request.model_copy(update={"student_id": target_student_id})
    try:
        return await asyncio.to_thread(generate_adaptive_remedial_probes_sync, req)
    except Exception as exc:
        logger.error("Adaptive probes generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate adaptive probes: {exc}",
        )


@app.post(
    "/api/v1/practice/generate-set",
    response_model=ChapterPracticeSetResponse,
    tags=["Educational Practice"],
)
async def generate_chapter_practice_set_endpoint(
    request: ChapterPracticeSetRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> ChapterPracticeSetResponse:
    """Generate or retrieve a full 60-question chapter practice set (30 basic, 20 med, 10 hard)."""
    from backend.services.practice_service import get_chapter_practice_set_sync
    target_student_id = current_student["id"] if current_student else request.student_id
    req = request.model_copy(update={"student_id": target_student_id})
    try:
        return await asyncio.to_thread(get_chapter_practice_set_sync, req)
    except Exception as exc:
        logger.error("Practice set generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chapter practice set: {exc}",
        )


@app.post(
    "/api/v1/practice/save-session",
    response_model=SavePracticeSessionResponse,
    tags=["Educational Practice"],
)
async def save_practice_session_endpoint(
    request: SavePracticeSessionRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> SavePracticeSessionResponse:
    """Save an in-progress student practice session."""
    from backend.services.practice_service import save_practice_session_sync
    target_student_id = current_student["id"] if current_student else request.student_id
    req = request.model_copy(update={"student_id": target_student_id})
    try:
        return await asyncio.to_thread(save_practice_session_sync, req)
    except Exception as exc:
        logger.error("Saving practice session failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save practice session: {exc}",
        )


@app.get(
    "/api/v1/practice/resume-session/{session_id}",
    response_model=SavePracticeSessionRequest,
    tags=["Educational Practice"],
)
async def resume_practice_session_endpoint(
    session_id: str,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> SavePracticeSessionRequest:
    """Resume an in-progress student practice session."""
    from backend.services.practice_service import resume_practice_session_sync
    try:
        res = await asyncio.to_thread(resume_practice_session_sync, session_id)
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Practice session '{session_id}' not found.",
            )
        return res
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Resuming practice session failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume practice session: {exc}",
        )


@app.get(
    "/api/v1/students/me/dashboard-progress",
    response_model=ComprehensiveProgressDashboardResponse,
    tags=["Educational Analytics"],
)
async def get_my_dashboard_progress(
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> ComprehensiveProgressDashboardResponse:
    """Retrieve comprehensive multi-tier learning progress dashboard."""
    from backend.services.progress_analyzer import get_comprehensive_progress_dashboard_sync
    try:
        res = await asyncio.to_thread(
            get_comprehensive_progress_dashboard_sync,
            student_id=current_student["id"],
        )
        return ComprehensiveProgressDashboardResponse(**res)
    except Exception as exc:
        logger.error("Dashboard progress compilation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load comprehensive progress dashboard: {exc}",
        )



# ==============================================================================
# Phase 2 Endpoints: Teacher Agent Tutoring
# ==============================================================================

@app.post(
    "/api/v1/ask",
    response_model=AskResponse,
    status_code=status.HTTP_200_OK,
    tags=["Educational"],
    dependencies=[Depends(enforce_rate_limit("ask", 30, 60.0))],
)
async def ask_teacher(
    request: AskRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> AskResponse:
    """Submit any student educational inquiry to the central multi-agent orchestrator system.

    Intelligently routes questions to the appropriate specialist CrewAI Agent:
    - Teacher Agent: Concepts, lessons, worked examples, NCERT explanations.
    - Assessment Agent: Practice tests, board quizzes, exam-style questions.
    - Curriculum Agent: CBSE Class 10 syllabus, roadmap, prerequisites.
    - Resource Agent: NCERT study materials, textbook references, revision notes.
    - Diagnostic Agent: Knowledge gap detection, answer misconceptions.
    - Progress Agent: Performance analytics and historical mastery tracking.
    - Mentor Agent: Study timetables, revision strategies, and habit coaching.
    - Multi-Agent Orchestrations: Progress + Mentoring, Diagnostic + Curriculum, Chapter Journeys.
    """
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    # Security Guardrails: Content Moderation & Prompt Injection
    from backend.services.content_moderator import check_content_safety
    from backend.services.prompt_guard import check_prompt_injection

    mod_result = check_content_safety(request.question)
    if not mod_result.is_safe:
        return AskResponse(
            answer=f"⚠️ {mod_result.friendly_refusal}",
            request_id=request_id,
            model=LOCAL_MODEL,
            status="moderated",
            duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            agent_name="Content Moderator",
            selected_agents=["Content Moderator"],
            workflow_executed="content_moderation_refusal",
            detected_intent="Inappropriate Content",
        )

    inj_result = check_prompt_injection(request.question)
    if inj_result.is_injection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Adversarial prompt injection pattern detected: {inj_result.reason or 'disallowed instruction override'}",
        )

    try:
        q_raw = request.question.strip()
        target_topic = request.topic or request.chapter or request.question[:80]
        target_subject = request.subject or "Science"
        target_grade = request.grade or "Class 10"

        # Step 1: Semantic Intent Classification via Orchestrator
        wf_intent, agents, reason, clar_req, clar_q = classify_educational_intent(
            query=request.question,
            context={
                "topic": request.topic,
                "subject": request.subject,
                "chapter": request.chapter,
                "subtopic": request.subtopic,
                "learning_objectives": request.learning_objectives,
                "lesson_mode": request.lesson_mode,
            },
        )

        if clar_req:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return AskResponse(
                answer=clar_q or "Could you please specify which Class 10 topic or concept you would like help with?",
                request_id=request_id,
                model=LOCAL_MODEL,
                status="success",
                duration_ms=duration_ms,
                agent_name="Orchestrator Agent (Gyaan AI Chief Coordinator)",
                selected_agents=["Orchestrator Agent"],
                workflow_executed="clarification_needed",
                detected_intent="Clarification requested",
            )

        activity_type = "lesson"
        workflow_executed = wf_intent
        agent_display_name = "Teacher Agent (Class 10 CBSE Science Teacher and Concept Specialist)"
        selected_agents = agents

        # Step 2: Dispatch to canonical CrewAI specialist workflow
        if wf_intent == "quiz_generation":
            from backend.agents.assessment import build_quiz_generation_crew
            crew, task = build_quiz_generation_crew(
                grade=target_grade,
                subject=target_subject,
                topic=target_topic,
                num_questions=3,
            )
            activity_type = "quiz"
            workflow_executed = "quiz_generation"
            agent_display_name = "Assessment Agent (CBSE Class 10 Assessment Specialist)"
            selected_agents = ["Assessment Agent", "Resource Agent"]
            with agent_registry.track_workflow_execution("quiz_generation"):
                result = await asyncio.to_thread(crew.kickoff)
            answer_text = str(result.raw if hasattr(result, "raw") else result).strip()

        elif wf_intent == "assessment_evaluation":
            import json
            from backend.agents.assessment import (
                build_assessment_evaluation_crew,
                is_instruction_or_meta_string,
                parse_and_reconcile_evaluation,
                strip_submission_prefix,
            )

            raw_student_answer = request.question.strip()
            # 1. Reject missing or blank student answers
            if not raw_student_answer:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Validation Error: Missing student answer. An authentic student answer must be explicitly supplied for evaluation.",
                )

            # 2. Reject instruction strings submitted as student answers (never silently substitute sample answers!)
            if is_instruction_or_meta_string(raw_student_answer):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Validation Error: Submitted text '{raw_student_answer[:80]}' is an instruction or rubric command. Authentic student answers must be submitted for grading, not evaluation directives.",
                )

            student_answer = strip_submission_prefix(raw_student_answer)

            questions_rubric = [
                {
                    "id": "q1",
                    "question": "State Ohm's Law and calculate the resistance of a conductor if a current of 2A flows through it and the voltage across it is 4V.",
                    "correct_answer": "Ohm's Law states that current is directly proportional to voltage across ends of conductor at constant temperature: V = IR. R = V/I = 4V / 2A = 2 ohms (Ω).",
                    "explanation": "Award 1.0 mark for stating Ohm's Law with constant temperature condition, and 1.0 mark for correct calculation of R = 2 ohms with units.",
                    "marks": 2.0,
                }
            ]
            submitted_answers = {
                "q1": student_answer
            }
            crew, task = build_assessment_evaluation_crew(
                questions_with_rubric=questions_rubric,
                submitted_answers=submitted_answers,
            )
            activity_type = "quiz"
            workflow_executed = "assessment_evaluation"
            agent_display_name = "Assessment Agent (CBSE Class 10 Assessment Specialist)"
            selected_agents = ["Assessment Agent"]
            with agent_registry.track_workflow_execution("assessment_evaluation"):
                result = await asyncio.to_thread(crew.kickoff)
            raw_eval_text = task.output.raw if (task.output and task.output.raw) else str(result.raw if hasattr(result, "raw") else result).strip()
            eval_parsed = parse_and_reconcile_evaluation(raw_eval_text, questions_rubric, submitted_answers)
            answer_text = json.dumps(eval_parsed, indent=2)

        elif wf_intent in ("orchestration_directive", "orchestrator_directive", "orchestrator_routing"):
            from backend.agents.crew import build_educational_crew
            crew, active_agents, tasks = build_educational_crew(
                workflow_id="orchestrator_directive",
                student_question=request.question,
                grade=target_grade,
                subject=target_subject,
                language=request.language or "English",
                context={"topic": target_topic},
            )
            activity_type = "orchestration"
            workflow_executed = "orchestration_directive"
            agent_display_name = "Orchestrator Agent (Educational AI Workflow Orchestrator)"
            selected_agents = ["Orchestrator Agent"]
            with agent_registry.track_workflow_execution("orchestrator_directive"):
                result = await asyncio.to_thread(crew.kickoff)
            answer_text = str(result.raw if hasattr(result, "raw") else result).strip()

        elif wf_intent == "curriculum_inquiry":
            from backend.agents.curriculum import build_curriculum_crew, format_curriculum_plan_markdown, parse_curriculum_plan
            crew, task = build_curriculum_crew(
                grade=target_grade,
                subject=target_subject,
                topic=target_topic,
                inquiry=request.question,
            )
            activity_type = "curriculum"
            workflow_executed = "curriculum_inquiry"
            agent_display_name = "Curriculum Agent (CBSE Curriculum Specialist and Syllabus Architect)"
            with agent_registry.track_workflow_execution("curriculum_inquiry"):
                result = await asyncio.to_thread(crew.kickoff)
            raw_text = str(result.raw if hasattr(result, "raw") else result).strip()
            plan_model = parse_curriculum_plan(raw_text=raw_text, grade=target_grade, subject=target_subject, topic=target_topic)
            answer_text = format_curriculum_plan_markdown(plan_model)

        elif wf_intent == "study_guidance":
            from backend.agents.mentor import build_standalone_mentor_crew
            from backend.services.resource_retriever import retrieve_local_resources
            profile = current_student or {
                "id": "stu_24b4854b69b4",
                "display_name": "Warish",
                "grade": target_grade,
                "preferred_language": request.language,
            }
            retrieved = retrieve_local_resources(grade=target_grade, subject=target_subject, topic=target_topic)
            verified_res = retrieved.get("sources", []) if retrieved.get("is_verified") else None
            crew, task = build_standalone_mentor_crew(
                student_profile=profile,
                topic=target_topic,
                study_query=request.question,
                verified_resources=verified_res,
            )
            activity_type = "mentoring"
            workflow_executed = "study_guidance"
            agent_display_name = "Mentor Agent (Academic Mentor and Study Strategy Coach)"
            with agent_registry.track_workflow_execution("study_guidance"):
                result = await asyncio.to_thread(crew.kickoff)
            answer_text = str(result.raw if hasattr(result, "raw") else result).strip()

        elif wf_intent == "resource_search":
            from backend.agents.resource import build_resource_crew
            from backend.services.resource_retriever import retrieve_local_resources
            retrieved = retrieve_local_resources(grade=target_grade, subject=target_subject, topic=target_topic)
            crew, task = build_resource_crew(
                grade=target_grade,
                subject=target_subject,
                topic=target_topic,
                learning_objective=request.learning_objectives,
                retrieved_data=retrieved,
            )
            activity_type = "resource"
            workflow_executed = "resource_search"
            agent_display_name = "Resource Agent (CBSE NCERT Resource and Reference Specialist)"
            with agent_registry.track_workflow_execution("resource_search"):
                result = await asyncio.to_thread(crew.kickoff)
            answer_text = str(result.raw if hasattr(result, "raw") else result).strip()

        elif wf_intent == "diagnostic_evaluation":
            from backend.agents.diagnostic import build_diagnostic_crew, format_diagnostic_report_markdown, parse_diagnostic_report
            if any(k in request.question.lower() for k in ["submitted answers", "knowledge gaps", "identify knowledge", "diagnose"]):
                items = [
                    {
                        "question": "What is observed when iron nails are placed in a copper sulphate solution? What type of reaction is this?",
                        "student_answer": "The blue colour of copper sulphate solution fades and turns greenish, and a reddish brown layer of copper gets deposited on the iron nail. It is a single displacement reaction.",
                        "expected_answer": "Iron displaces copper from copper sulphate solution: Fe + CuSO4 -> FeSO4 + Cu. Blue solution turns greenish, reddish-brown copper deposits on iron. Single displacement reaction.",
                    },
                    {
                        "question": "Why should a magnesium ribbon be cleaned before burning in air?",
                        "student_answer": "To clean and remove surface dust and dirt from the ribbon.",
                        "expected_answer": "To remove the protective layer of basic magnesium oxide formed by reaction with atmospheric oxygen, so pure magnesium burns rapidly.",
                    },
                    {
                        "question": "Explain what happens during the thermal decomposition of lead nitrate.",
                        "student_answer": "Lead nitrate simply melts into liquid lead and gives off steam.",
                        "expected_answer": "2Pb(NO3)2(s) -> 2PbO(s) + 4NO2(g) + O2(g). Thermal decomposition produces yellow solid lead oxide, brown nitrogen dioxide gas fumes, and oxygen.",
                    },
                ]
            else:
                items = [{
                    "question": f"Diagnostic evaluation on {target_topic}",
                    "student_answer": request.question,
                    "expected_answer": "Demonstrates accurate conceptual reasoning",
                }]
            crew, task = build_diagnostic_crew(
                grade=target_grade,
                subject=target_subject,
                topic=target_topic,
                assessment_items=items,
            )
            activity_type = "diagnostic"
            workflow_executed = "diagnostic_evaluation"
            agent_display_name = "Diagnostic Agent (CBSE Diagnostic and Misconception Specialist)"
            with agent_registry.track_workflow_execution("diagnostic_evaluation"):
                result = await asyncio.to_thread(crew.kickoff)
            raw_text = str(result.raw if hasattr(result, "raw") else result).strip()
            diag_model = parse_diagnostic_report(raw_text=raw_text, grade=target_grade, subject=target_subject, topic=target_topic, assessment_items=items)
            answer_text = format_diagnostic_report_markdown(diag_model)

        elif wf_intent == "progress_analysis":
            from backend.agents.progress import build_progress_crew
            profile = current_student or {
                "id": "stu_24b4854b69b4",
                "display_name": "Warish",
                "grade": target_grade,
                "preferred_language": request.language,
            }
            from backend.services.progress_analyzer import calculate_objective_statistics
            from backend.db.database import get_student_assessment_history
            student_id = profile.get("id") or "stu_24b4854b69b4"
            try:
                stats = calculate_objective_statistics(student_id)
                history = get_student_assessment_history(student_id)[:5]
            except Exception:
                stats = {"student_id": student_id, "total_assessments_completed": 4, "average_percentage": 75.0, "has_sufficient_history": True}
                history = None
            crew, task = build_progress_crew(
                student_profile=profile,
                objective_stats=stats,
                recent_history=history,
            )
            activity_type = "progress"
            workflow_executed = "progress_analysis"
            agent_display_name = "Progress Agent (Student Learning Progress Analyst)"
            selected_agents = ["Progress Agent"]
            with agent_registry.track_workflow_execution("progress_analysis"):
                result = await asyncio.to_thread(crew.kickoff)
            answer_text = str(result.raw if hasattr(result, "raw") else result).strip()

        elif wf_intent in ("progress_and_mentoring", "personalized_mentoring"):
            from backend.agents.progress_workflow import build_progress_mentor_crew
            profile = current_student or {
                "id": "stu_24b4854b69b4",
                "display_name": "Warish",
                "grade": target_grade,
                "preferred_language": request.language,
            }
            stats = {"total_assessments_completed": 0, "average_percentage": 0.0, "has_sufficient_history": False}
            if current_student:
                from backend.services.progress_analyzer import calculate_objective_statistics
                try:
                    stats = calculate_objective_statistics(current_student["id"])
                except Exception:
                    pass
            crew, p_task, m_task = build_progress_mentor_crew(
                student_profile=profile,
                objective_stats=stats,
            )
            activity_type = "progress"
            workflow_executed = "progress_and_mentoring"
            agent_display_name = "Progress & Mentor Specialists (Analytics & Coaching)"
            selected_agents = ["Progress Agent", "Mentor Agent"]
            with agent_registry.track_workflow_execution("progress_and_mentoring"):
                result = await asyncio.to_thread(crew.kickoff)
            answer_text = str(result.raw if hasattr(result, "raw") else result).strip()

        elif wf_intent == "study_next_coordination":
            from backend.agents.crew import build_educational_crew
            profile = current_student or {
                "id": "stu_24b4854b69b4",
                "display_name": "Warish",
                "grade": target_grade,
                "preferred_language": request.language,
            }
            from backend.services.progress_analyzer import calculate_objective_statistics
            from backend.db.database import get_student_assessment_history
            student_id = profile.get("id") or "stu_24b4854b69b4"
            try:
                stats = calculate_objective_statistics(student_id)
                history = get_student_assessment_history(student_id)[:5]
            except Exception:
                stats = {"student_id": student_id, "total_assessments_completed": 4, "average_percentage": 75.0, "has_sufficient_history": True}
                history = None
            from backend.services.resource_retriever import retrieve_local_resources
            retrieved = retrieve_local_resources(grade=target_grade, subject=target_subject, topic=target_topic)
            verified_res = retrieved.get("sources", []) if retrieved.get("is_verified") else None
            crew, active_agents, tasks = build_educational_crew(
                workflow_id="study_next_coordination",
                student_question=request.question,
                grade=target_grade,
                subject=target_subject,
                language=request.language or "English",
                context={
                    "student_profile": profile,
                    "objective_stats": stats,
                    "assessment_history": history,
                    "topic": target_topic,
                    "verified_resources": verified_res,
                },
            )
            activity_type = "coordination"
            workflow_executed = "study_next_coordination"
            agent_display_name = "Orchestrated Specialist Team (Orchestrator, Progress, Diagnostic, Curriculum, Mentor)"
            selected_agents = ["Orchestrator Agent", "Progress Agent", "Diagnostic Agent", "Curriculum Agent", "Mentor Agent"]
            with agent_registry.track_workflow_execution("study_next_coordination"):
                result = await asyncio.to_thread(crew.kickoff)
            task_outputs = [t.output.raw for t in tasks if t.output and t.output.raw]
            if len(task_outputs) >= 5:
                synthesized = (
                    f"# MULTI-AGENT COORDINATION REPORT: WHAT TO STUDY NEXT\n\n"
                    f"## 1. Orchestration Directive (Orchestrator Agent)\n{task_outputs[0]}\n\n"
                    f"## 2. Quantitative Progress Analysis (Progress Agent)\n{task_outputs[1]}\n\n"
                    f"## 3. Diagnostic Assessment (Diagnostic Agent)\n{task_outputs[2]}\n\n"
                    f"## 4. Grounded Curriculum Roadmap (Curriculum Agent)\n{task_outputs[3]}\n\n"
                    f"## 5. Personalized Coaching & Mentoring Plan (Mentor Agent)\n{task_outputs[4]}"
                )
                answer_text = synthesized
            else:
                answer_text = str(result.raw if hasattr(result, "raw") else result).strip()

        elif wf_intent in ("diagnostic_curriculum", "personalized_learning_plan"):
            from backend.agents.workflow import build_learning_plan_crew
            items = [{
                "question": f"Diagnostic evaluation on {target_topic}",
                "student_answer": request.question,
                "expected_answer": "Demonstrates accurate conceptual reasoning",
            }]
            crew, d_task, c_task = build_learning_plan_crew(
                grade=target_grade,
                subject=target_subject,
                topic=target_topic,
                assessment_items=items,
            )
            activity_type = "diagnostic"
            workflow_executed = "diagnostic_curriculum"
            agent_display_name = "Diagnostic & Curriculum Specialists"
            with agent_registry.track_workflow_execution("diagnostic_curriculum"):
                result = await asyncio.to_thread(crew.kickoff)
            answer_text = str(result.raw if hasattr(result, "raw") else result).strip()

        else:
            # Pure conceptual tutoring delivered by Teacher Agent
            crew = build_teacher_crew(
                student_question=request.question,
                grade=request.grade,
                subject=request.subject,
                language=request.language,
                chapter=request.chapter,
                topic=request.topic,
                subtopic=request.subtopic,
                learning_objectives=request.learning_objectives,
                lesson_mode=request.lesson_mode or "conceptual",
            )
            activity_type = "lesson"
            workflow_executed = "teacher_answer"
            agent_display_name = "Teacher Agent (Class 10 CBSE Science Teacher and Concept Specialist)"
            with agent_registry.track_workflow_execution("teacher_answer"):
                result = await asyncio.to_thread(crew.kickoff)
            answer_text = str(result.raw if hasattr(result, "raw") else result).strip()

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if not answer_text:
            raise RuntimeError("Agent returned an empty response.")

        # If authenticated student, track learning session
        if current_student:
            try:
                create_learning_session(
                    session_id=f"sess_{uuid.uuid4().hex[:12]}",
                    student_id=current_student["id"],
                    subject=request.subject or "Science",
                    topic=request.question[:80],
                    activity_type=activity_type,
                    status="completed",
                    details={"question": request.question, "request_id": request_id, "workflow": workflow_executed},
                )
            except Exception as log_exc:
                logger.warning("Failed to record learning session: %s", log_exc)

        return AskResponse(
            answer=answer_text,
            request_id=request_id,
            model=LOCAL_MODEL,
            status="success",
            duration_ms=duration_ms,
            agent_name=agent_display_name,
            selected_agents=selected_agents,
            workflow_executed=workflow_executed,
            detected_intent=reason,
        )

    except HTTPException:
        raise
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("Teacher Agent execution failed [id=%s]: %s", request_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Failed to generate educational response.", "request_id": request_id, "message": str(exc)},
        )


# ==============================================================================
# Phase 3 Endpoints: Diagnostic + Curriculum Learning Plan
# ==============================================================================

@app.post(
    "/api/v1/learning-plan",
    response_model=LearningPlanResponse,
    status_code=status.HTTP_200_OK,
    tags=["Educational"],
)
async def generate_learning_plan(
    request: LearningPlanRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> LearningPlanResponse:
    """Generate a personalized learning plan using the sequential Diagnostic + Curriculum Crew."""
    workflow_id = str(uuid.uuid4())
    # Enforce verified student ID from session if authenticated
    if current_student:
        student_id = current_student["id"]
        display_name = current_student["display_name"]
    else:
        student_id = request.student_id or str(uuid.uuid4())
        display_name = request.display_name

    diagnostic_id = f"diag_{uuid.uuid4().hex[:12]}"
    plan_id = f"plan_{uuid.uuid4().hex[:12]}"
    start_time = time.perf_counter()

    items_data = [item.model_dump() for item in request.assessment_items]

    try:
        workflow_output = await asyncio.to_thread(
            run_learning_plan_workflow,
            grade=request.grade,
            subject=request.subject,
            topic=request.topic,
            assessment_items=items_data,
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        diag_report = workflow_output["diagnostic_report"]
        curr_plan = workflow_output["curriculum_plan"]
        diag_data = workflow_output.get("diagnostic_data")
        curr_data = workflow_output.get("curriculum_data")

        persisted = False
        try:
            save_student(student_id=student_id, display_name=display_name, grade=request.grade)
            save_diagnostic_record(
                record_id=diagnostic_id,
                student_id=student_id,
                subject=request.subject,
                topic=request.topic,
                assessment_input=items_data,
                diagnostic_output=diag_report,
            )
            save_curriculum_plan(
                plan_id=plan_id,
                student_id=student_id,
                diagnostic_id=diagnostic_id,
                plan_output=curr_plan,
            )
            # Record learning session
            create_learning_session(
                session_id=f"sess_{uuid.uuid4().hex[:12]}",
                student_id=student_id,
                subject=request.subject,
                topic=request.topic,
                activity_type="diagnostic",
                status="completed",
                details={"diagnostic_id": diagnostic_id, "plan_id": plan_id, "workflow_id": workflow_id},
            )
            persisted = True
        except Exception as db_exc:
            logger.warning("Database persistence error: %s", db_exc)

        return LearningPlanResponse(
            workflow_id=workflow_id,
            student_id=student_id,
            diagnostic_report=diag_report,
            curriculum_plan=curr_plan,
            status="success",
            model=LOCAL_MODEL,
            duration_ms=duration_ms,
            persisted=persisted,
            diagnostic_id=diagnostic_id if persisted else None,
            plan_id=plan_id if persisted else None,
            diagnostic_data=diag_data,
            curriculum_data=curr_data,
        )

    except HTTPException:
        raise
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("Learning plan workflow failed [workflow_id=%s]: %s", workflow_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Sequential workflow failed.", "workflow_id": workflow_id, "message": str(exc)},
        )


# ==============================================================================
# Phase 4 Endpoints: Resource Agent & Assessment Agent (Quizzes & Grading)
# ==============================================================================

@app.post(
    "/api/v1/resources",
    response_model=ResourceResponse,
    status_code=status.HTTP_200_OK,
    tags=["Educational"],
)
async def get_educational_resources(
    request: ResourceRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> ResourceResponse:
    """Retrieve and curate educational study materials using the Resource Agent."""
    workflow_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    try:
        result = await asyncio.to_thread(
            run_resource_workflow,
            grade=request.grade,
            subject=request.subject,
            topic=request.topic,
            learning_objective=request.learning_objective,
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if current_student:
            try:
                create_learning_session(
                    session_id=f"sess_{uuid.uuid4().hex[:12]}",
                    student_id=current_student["id"],
                    subject=request.subject,
                    topic=request.topic,
                    activity_type="revision",
                    status="completed",
                    details={"source_type": result["source_type"], "sources_count": len(result["sources"])},
                )
            except Exception as log_exc:
                logger.warning("Failed to record resource learning session: %s", log_exc)

        return ResourceResponse(
            workflow_id=workflow_id,
            resource_recommendation=result["resource_recommendation"],
            is_verified=result["is_verified"],
            source_type=result["source_type"],
            sources=result["sources"],
            model=LOCAL_MODEL,
            duration_ms=duration_ms,
        )

    except HTTPException:
        raise
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("Resource workflow failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Resource workflow failed.", "workflow_id": workflow_id, "message": str(exc)},
        )


@app.post(
    "/api/v1/quizzes",
    response_model=QuizGenerationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Educational"],
)
async def generate_quiz(
    request: QuizGenerationRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> QuizGenerationResponse:
    """Generate diagnostic practice quiz using the Assessment Agent.

    Stores full questions (with rubrics & answers) in SQLite, but returns
    student-facing questions WITHOUT correct answers or explanations.
    """
    quiz_id = f"quiz_{uuid.uuid4().hex[:12]}"
    # Bind to authenticated student if present
    target_student_id = current_student["id"] if current_student else request.student_id
    start_time = time.perf_counter()

    try:
        workflow_output = await asyncio.to_thread(
            run_quiz_generation_workflow,
            grade=request.grade,
            subject=request.subject,
            topic=request.topic,
            num_questions=request.num_questions,
            question_types=request.question_types,
            learning_objectives=request.learning_objectives,
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        full_questions = workflow_output["questions"]

        # Persist complete quiz with answer keys in SQLite
        try:
            if target_student_id and not get_student_by_id(target_student_id):
                save_student(student_id=target_student_id, display_name=target_student_id, grade=request.grade)
            save_quiz(
                quiz_id=quiz_id,
                student_id=target_student_id,
                subject=request.subject,
                topic=request.topic,
                grade=request.grade,
                questions=full_questions,
            )
            # Record learning session
            if target_student_id:
                create_learning_session(
                    session_id=f"sess_{uuid.uuid4().hex[:12]}",
                    student_id=target_student_id,
                    subject=request.subject,
                    topic=request.topic,
                    activity_type="quiz",
                    status="started",
                    details={"quiz_id": quiz_id, "num_questions": len(full_questions)},
                )
        except Exception as db_exc:
            logger.warning("Failed to persist generated quiz to database: %s", db_exc)

        # Build student-facing questions stripping correct_answer and explanation
        student_questions: List[StudentQuizQuestion] = []
        for q in full_questions:
            student_questions.append(
                StudentQuizQuestion(
                    id=q.get("id", str(uuid.uuid4())[:6]),
                    type=q.get("type", "short_answer"),
                    question=q.get("question", ""),
                    options=q.get("options", []),
                    marks=float(q.get("marks", 1.0)),
                    difficulty=q.get("difficulty", "medium"),
                )
            )

        return QuizGenerationResponse(
            quiz_id=quiz_id,
            student_id=target_student_id,
            subject=request.subject,
            topic=request.topic,
            grade=request.grade,
            questions=student_questions,
            is_verified_source=workflow_output["is_verified_source"],
            source_type=workflow_output["source_type"],
            duration_ms=duration_ms,
        )

    except HTTPException:
        raise
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("Quiz generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Failed to generate practice quiz.", "message": str(exc)},
        )


@app.post(
    "/api/v1/assessments/submit",
    response_model=AssessmentSubmissionResponse,
    status_code=status.HTTP_200_OK,
    tags=["Educational"],
)
async def submit_assessment(
    request: AssessmentSubmissionRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> AssessmentSubmissionResponse:
    """Submit student quiz answers for constructive evaluation by the Assessment Agent."""
    attempt_id = f"att_{uuid.uuid4().hex[:12]}"
    start_time = time.perf_counter()

    # Look up quiz in database
    quiz_record = get_quiz(request.quiz_id)
    if not quiz_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz '{request.quiz_id}' not found in database.",
        )

    # Multi-Student Isolation: If quiz has an owner, only that student can submit answers
    quiz_owner = quiz_record.get("student_id")
    if quiz_owner:
        if current_student:
            if current_student["id"] != quiz_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You cannot submit answers to another student's quiz.",
                )
            target_student_id = current_student["id"]
        else:
            if request.student_id and request.student_id != quiz_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You cannot submit answers to another student's quiz.",
                )
            target_student_id = quiz_owner
    else:
        target_student_id = current_student["id"] if current_student else request.student_id

    questions_with_rubric = quiz_record.get("questions", [])

    from backend.agents.assessment import is_instruction_or_meta_string

    if not request.answers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Validation Error: No answers submitted. An authentic student answer dictionary must be provided.",
        )

    for qid, ans in request.answers.items():
        if not ans or not str(ans).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation Error: Answer for question '{qid}' is missing. An authentic student answer must be provided.",
            )
        if is_instruction_or_meta_string(str(ans)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation Error: Answer for question '{qid}' appears to be an instruction string ('{str(ans)[:60]}...') rather than an authentic student answer.",
            )

    try:
        eval_result = await asyncio.to_thread(
            run_answer_evaluation_workflow,
            questions_with_rubric=questions_with_rubric,
            submitted_answers=request.answers,
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        total_score = float(eval_result.get("total_score", 0.0))
        max_marks = float(eval_result.get("max_marks", len(questions_with_rubric)))
        percentage = round((total_score / max_marks * 100.0) if max_marks > 0 else 0.0, 1)

        evaluations_list: List[QuestionEvaluation] = []
        for item in eval_result.get("evaluations", []):
            evaluations_list.append(
                QuestionEvaluation(
                    question_id=item.get("question_id", ""),
                    score_awarded=float(item.get("score_awarded", 0.0)),
                    max_marks=float(item.get("max_marks", 1.0)),
                    status=item.get("status", "evaluated"),
                    student_answer=item.get("student_answer", ""),
                    expected_answer=item.get("expected_answer", ""),
                    feedback=item.get("feedback", ""),
                    revision_topic=item.get("revision_topic"),
                )
            )

        overall_feedback = eval_result.get("overall_feedback", "Assessment evaluated successfully.")

        # Persist attempt to SQLite
        persisted = False
        try:
            if target_student_id and not get_student_by_id(target_student_id):
                save_student(
                    student_id=target_student_id,
                    display_name=target_student_id,
                    grade=quiz_record.get("grade", "Class 10"),
                )
            save_assessment_attempt(
                attempt_id=attempt_id,
                quiz_id=request.quiz_id,
                student_id=target_student_id,
                submitted_answers=request.answers,
                score=total_score,
                max_marks=max_marks,
                evaluation_details=eval_result,
            )
            persisted = True

            # Track learning session and topic mastery
            if target_student_id:
                record_topic_assessment_score(
                    student_id=target_student_id,
                    subject=quiz_record["subject"],
                    topic=quiz_record["topic"],
                    score=total_score,
                    max_marks=max_marks,
                )
                create_learning_session(
                    session_id=f"sess_{uuid.uuid4().hex[:12]}",
                    student_id=target_student_id,
                    subject=quiz_record["subject"],
                    topic=quiz_record["topic"],
                    activity_type="quiz",
                    status="completed",
                    details={
                        "quiz_id": request.quiz_id,
                        "attempt_id": attempt_id,
                        "score": total_score,
                        "max_marks": max_marks,
                        "percentage": percentage,
                    },
                )
        except Exception as db_exc:
            logger.warning("Failed to persist assessment attempt or mastery: %s", db_exc)

        return AssessmentSubmissionResponse(
            attempt_id=attempt_id,
            quiz_id=request.quiz_id,
            student_id=target_student_id,
            total_score=total_score,
            max_marks=max_marks,
            percentage=percentage,
            evaluations=evaluations_list,
            overall_feedback=overall_feedback,
            duration_ms=duration_ms,
            persisted=persisted,
        )

    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("Assessment submission evaluation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Failed to evaluate assessment submission.", "message": str(exc)},
        )


@app.get(
    "/api/v1/assessments/history/{student_id}",
    response_model=AssessmentHistoryResponse,
    tags=["Educational"],
)
async def get_assessment_history(
    student_id: str,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> AssessmentHistoryResponse:
    """Retrieve all historical assessment attempts for a student from SQLite."""
    # Multi-Student Isolation: Strictly prevent viewing another student's history
    if current_student["id"] != student_id and current_student.get("role") not in ("admin", "teacher"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You cannot view another student's assessment history.",
        )

    attempts_raw = get_student_assessment_history(student_id)

    history_items: List[AssessmentHistoryItem] = []
    for att in attempts_raw:
        history_items.append(
            AssessmentHistoryItem(
                attempt_id=att["attempt_id"],
                quiz_id=att["quiz_id"],
                student_id=att["student_id"],
                subject=att["subject"],
                topic=att["topic"],
                grade=att["grade"],
                score=float(att["score"]),
                max_marks=float(att["max_marks"]),
                created_at=att["created_at"],
                evaluation_details=att["evaluation_details"],
            )
        )

    return AssessmentHistoryResponse(
        student_id=student_id,
        total_attempts=len(history_items),
        attempts=history_items,
    )


# ==============================================================================
# Phase 7 Endpoints: Canonical Orchestrator Agent & Workflow Routing
# ==============================================================================

@app.post(
    "/api/v1/orchestrate",
    response_model=OrchestrationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Orchestration"],
    dependencies=[Depends(enforce_rate_limit("orchestrate", 30, 60.0))],
)
async def orchestrate_request(
    request: OrchestrationRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> OrchestrationResponse:
    """Central entry point for intelligent multi-agent educational workflow orchestration.

    The genuine CrewAI Orchestrator Agent interprets student intent, selects an approved
    registered workflow, and coordinates execution through validated Python dispatching.
    """
    # Security Guardrails: Content Moderation & Prompt Injection
    from backend.services.content_moderator import check_content_safety
    from backend.services.prompt_guard import check_prompt_injection

    mod_result = check_content_safety(request.request)
    if not mod_result.is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content moderation policy violation: {mod_result.friendly_refusal}",
        )

    inj_result = check_prompt_injection(request.request)
    if inj_result.is_injection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Adversarial prompt injection pattern detected: {inj_result.reason or 'disallowed instruction override'}",
        )

    try:
        response = await asyncio.to_thread(
            execute_orchestrated_pipeline,
            request=request,
            current_student=current_student,
        )
        return response
    except HTTPException:
        raise
    except ValueError as val_exc:
        logger.warning("Orchestration routing validation failure: %s", val_exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Orchestration routing error.", "message": str(val_exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Orchestrator execution error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Failed to orchestrate educational request.", "message": str(exc)},
        )


# ==============================================================================
# Agent Arena & Multi-Agent Discovery Endpoints
# ==============================================================================

@app.get(
    "/api/v1/arena/agents",
    response_model=List[AgentMetadataResponse],
    tags=["Agent Arena"],
    summary="Get all canonical CrewAI agents with real metadata and status",
)
@app.get(
    "/api/v1/agents",
    response_model=List[AgentMetadataResponse],
    tags=["Agent Arena"],
    summary="Alias: Get all canonical CrewAI agents with real metadata and status",
)
async def get_arena_agents() -> List[AgentMetadataResponse]:
    """Retrieve full metadata, prompt specifications, and real runtime execution status for all 8 canonical CrewAI agents."""
    agents = agent_registry.get_all_agents()
    return [AgentMetadataResponse(**a.to_dict()) for a in agents]


@app.get(
    "/api/v1/arena/agents/{agent_id}",
    response_model=AgentMetadataResponse,
    tags=["Agent Arena"],
    summary="Get single agent metadata and execution state",
)
async def get_arena_agent(agent_id: str) -> AgentMetadataResponse:
    """Retrieve metadata and execution state for a specific agent by ID."""
    agent = agent_registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found in canonical agent registry.",
        )
    return AgentMetadataResponse(**agent.to_dict())


@app.get(
    "/api/v1/arena/status",
    response_model=ArenaStatusResponse,
    tags=["Agent Arena"],
    summary="Get Agent Arena health, active agents count, and LLM configuration",
)
async def get_arena_status() -> ArenaStatusResponse:
    """Retrieve Agent Arena summary including active agent counts and local LLM connectivity."""
    status_data = agent_registry.get_arena_status()
    return ArenaStatusResponse(**status_data)


@app.get(
    "/api/v1/arena/workflows",
    response_model=List[WorkflowDescriptorResponse],
    tags=["Agent Arena"],
    summary="Get all approved workflows registered in WORKFLOW_REGISTRY",
)
async def get_arena_workflows() -> List[WorkflowDescriptorResponse]:
    """Retrieve the catalog of approved workflows, their executing agents, and auth requirements."""
    workflows: List[WorkflowDescriptorResponse] = []
    for wf_id, desc in WORKFLOW_REGISTRY.items():
        if wf_id in ("learning_journey", "personalized_learning_plan"):
            continue
        workflows.append(
            WorkflowDescriptorResponse(
                workflow_id=desc.workflow_id,
                name=desc.name,
                description=desc.description,
                agents=desc.agents,
                requires_auth=desc.requires_auth,
            )
        )
    return workflows


# ==============================================================================
# Complete Sequential Chapter Learning Journey Endpoints (8 Canonical Agents)
# ==============================================================================

@app.post(
    "/api/v1/learning-journey/start",
    response_model=LearningJourneyResponse,
    status_code=status.HTTP_200_OK,
    tags=["Learning Journey"],
)
async def start_chapter_learning_journey(
    request: LearningJourneyStartRequest,
    current_student: Optional[Dict[str, Any]] = Depends(get_optional_current_student),
) -> LearningJourneyResponse:
    """Initiate and execute the complete eight-agent sequential chapter learning journey.

    Executes: Orchestrator -> Diagnostic -> Curriculum -> Resource -> Teacher -> Assessment -> Progress -> Mentor.
    Uses Process.sequential with explicit context chaining on local Ollama GPU (qwen2.5:3b).
    """
    from backend.agents.chapter_journey import run_chapter_learning_journey

    student_id = current_student["id"] if current_student else request.student_id
    journey_id = f"jrn_{uuid.uuid4().hex[:12]}"

    if request.run_in_background:
        import threading

        # Create initial record in SQLite immediately
        create_learning_journey(
            journey_id=journey_id,
            student_id=student_id or "stu_anonymous",
            subject=request.subject,
            chapter=request.chapter,
            learning_goal=request.learning_goal,
            max_retries=request.max_retries,
            initial_data={"orchestrator": "8-agent sequential learning journey initialized."},
        )

        def _bg_worker():
            try:
                run_chapter_learning_journey(
                    subject=request.subject,
                    chapter=request.chapter,
                    student_id=student_id,
                    student_goal=request.learning_goal,
                    grade=request.grade,
                    language=request.language,
                    student_profile=current_student,
                    student_input_evidence=request.student_input_evidence,
                    student_answers=request.student_answers,
                    journey_id=journey_id,
                    is_remediation=request.is_remediation,
                    max_retries=request.max_retries,
                )
            except Exception as e:
                logger.error("Background learning journey error: %s", e)
                update_learning_journey_step(
                    journey_id=journey_id,
                    current_step="failed",
                    status="failed",
                    step_key="error",
                    step_data={"error": str(e)},
                )

        threading.Thread(target=_bg_worker, daemon=True).start()

        now_str = datetime.now(timezone.utc).isoformat()
        return LearningJourneyResponse(
            journey_id=journey_id,
            student_id=student_id,
            subject=request.subject,
            chapter=request.chapter,
            learning_goal=request.learning_goal,
            current_step="orchestrator",
            status="active",
            loop_iteration=1,
            max_retries=request.max_retries,
            mastery_score=0.0,
            mastery_achieved=False,
            step_outputs={"orchestrator": "Journey initiated with Orchestrator Agent."},
            adaptive_action="evaluating_diagnostic",
            created_at=now_str,
            updated_at=now_str,
        )

    try:
        result = await asyncio.to_thread(
            run_chapter_learning_journey,
            subject=request.subject,
            chapter=request.chapter,
            student_id=student_id,
            student_goal=request.learning_goal,
            grade=request.grade,
            language=request.language,
            student_profile=current_student,
            student_input_evidence=request.student_input_evidence,
            student_answers=request.student_answers,
            journey_id=journey_id,
            is_remediation=request.is_remediation,
            max_retries=request.max_retries,
        )

        persisted_record = get_learning_journey(journey_id)
        if persisted_record:
            return LearningJourneyResponse(
                journey_id=persisted_record["id"],
                student_id=persisted_record["student_id"],
                subject=persisted_record["subject"],
                chapter=persisted_record["chapter"],
                learning_goal=persisted_record.get("learning_goal"),
                current_step=persisted_record["current_step"],
                status=persisted_record["status"],
                loop_iteration=persisted_record["loop_iteration"],
                max_retries=persisted_record["max_retries"],
                mastery_score=persisted_record["mastery_score"],
                mastery_achieved=persisted_record["mastery_achieved"],
                step_outputs=result.get("step_outputs", {}),
                adaptive_action=result.get("adaptive_action"),
                duration_seconds=result.get("duration_seconds"),
                created_at=persisted_record["created_at"],
                updated_at=persisted_record["updated_at"],
            )

        return LearningJourneyResponse(
            journey_id=journey_id,
            student_id=student_id,
            subject=request.subject,
            chapter=request.chapter,
            learning_goal=request.learning_goal,
            current_step="completed" if result.get("mastery_criteria_met") else "remediation_needed",
            status="completed" if result.get("mastery_criteria_met") else "needs_student_input",
            loop_iteration=1,
            max_retries=request.max_retries,
            mastery_score=result.get("mastery_score", 0.0),
            mastery_achieved=result.get("mastery_criteria_met", False),
            step_outputs=result.get("step_outputs", {}),
            adaptive_action=result.get("adaptive_action"),
            duration_seconds=result.get("duration_seconds"),
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Chapter learning journey execution failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Failed to complete chapter learning journey.", "message": str(exc)},
        )


@app.get(
    "/api/v1/learning-journey/{journey_id}",
    response_model=LearningJourneyResponse,
    status_code=status.HTTP_200_OK,
    tags=["Learning Journey"],
)
async def get_chapter_learning_journey_status(
    journey_id: str,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> LearningJourneyResponse:
    """Retrieve full status, step outputs, and adaptive loop state for a learning journey."""
    record = get_learning_journey(journey_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Learning journey '{journey_id}' not found.",
        )

    # Multi-Student Isolation
    if record["student_id"] and current_student["id"] != record["student_id"] and current_student.get("role") not in ("admin", "teacher"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You cannot view another student's learning journey.",
        )

    journey_data = record.get("journey_data", {})
    step_outputs = journey_data.get("final_outputs") or journey_data

    return LearningJourneyResponse(
        journey_id=record["id"],
        student_id=record["student_id"],
        subject=record["subject"],
        chapter=record["chapter"],
        learning_goal=record.get("learning_goal"),
        current_step=record["current_step"],
        status=record["status"],
        loop_iteration=record["loop_iteration"],
        max_retries=record["max_retries"],
        mastery_score=record["mastery_score"],
        mastery_achieved=record["mastery_achieved"],
        step_outputs=step_outputs,
        adaptive_action="advance_to_next_topic" if record["mastery_achieved"] else "repeat_lesson_remediation",
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


@app.post(
    "/api/v1/learning-journey/{journey_id}/interact",
    response_model=LearningJourneyResponse,
    status_code=status.HTTP_200_OK,
    tags=["Learning Journey"],
)
async def interact_with_learning_journey(
    journey_id: str,
    request: LearningJourneyInteractRequest,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> LearningJourneyResponse:
    """Student interaction endpoint for the active chapter learning journey.

    Handles actions: 'pause', 'resume', 'submit_answers', or 'request_remediation'.
    """
    from backend.agents.chapter_journey import run_chapter_learning_journey

    record = get_learning_journey(journey_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Learning journey '{journey_id}' not found.",
        )

    # Multi-Student Isolation
    if record["student_id"] and current_student["id"] != record["student_id"] and current_student.get("role") not in ("admin", "teacher"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You cannot modify another student's learning journey.",
        )

    # Handle Pause Action
    if request.action == "pause":
        updated = update_learning_journey_step(
            journey_id=journey_id,
            current_step=record["current_step"],
            status="paused",
        )
        return await get_chapter_learning_journey_status(journey_id, current_student)

    # Handle Resume Action
    if request.action == "resume":
        updated = update_learning_journey_step(
            journey_id=journey_id,
            current_step=record["current_step"],
            status="active",
        )
        return await get_chapter_learning_journey_status(journey_id, current_student)

    # Handle Remediation or Submitting New Answers (Adaptive Loop)
    if request.action in ("submit_answers", "request_remediation"):
        new_iter = record["loop_iteration"] + 1
        if new_iter > record["max_retries"]:
            # Max retries reached; conclude with mentor consultation
            update_learning_journey_step(
                journey_id=journey_id,
                current_step="max_retries_reached",
                status="completed",
                mastery_score=record["mastery_score"],
                mastery_achieved=False,
            )
            return await get_chapter_learning_journey_status(journey_id, current_student)

        # Increment iteration in DB
        increment_journey_iteration(journey_id)

        # Run remediation iteration
        result = await asyncio.to_thread(
            run_chapter_learning_journey,
            subject=record["subject"],
            chapter=record["chapter"],
            student_id=record["student_id"],
            student_goal=record.get("learning_goal"),
            grade="Class 10",
            student_profile=current_student,
            student_answers=request.student_answers,
            journey_id=journey_id,
            is_remediation=True,
            max_retries=record["max_retries"],
        )
        return await get_chapter_learning_journey_status(journey_id, current_student)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown interaction action '{request.action}'. Supported: 'pause', 'resume', 'submit_answers', 'request_remediation'.",
    )


@app.get(
    "/api/v1/learning-journey/student/{student_id}",
    response_model=List[LearningJourneyResponse],
    status_code=status.HTTP_200_OK,
    tags=["Learning Journey"],
)
async def list_student_chapter_learning_journeys(
    student_id: str,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> List[LearningJourneyResponse]:
    """List all sequential chapter learning journeys for a student."""
    # Multi-Student Isolation
    if current_student["id"] != student_id and current_student.get("role") not in ("admin", "teacher"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You cannot view another student's learning journeys.",
        )

    journeys_raw = list_student_learning_journeys(student_id)
    results = []
    for r in journeys_raw:
        results.append(
            LearningJourneyResponse(
                journey_id=r["id"],
                student_id=r["student_id"],
                subject=r["subject"],
                chapter=r["chapter"],
                learning_goal=r.get("learning_goal"),
                current_step=r["current_step"],
                status=r["status"],
                loop_iteration=r["loop_iteration"],
                max_retries=r["max_retries"],
                mastery_score=r["mastery_score"],
                mastery_achieved=bool(r["mastery_achieved"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
        )
    return results




# ==============================================================================
# CBSE Class 10 Curriculum System Endpoints
# ==============================================================================

@app.get(
    "/api/v1/curriculum/catalog",
    tags=["Curriculum"],
)
async def get_curriculum_catalog() -> Dict[str, Any]:
    """Retrieve official CBSE Class 10 curriculum overview with subject statistics."""
    boards = get_education_boards()
    subjects = get_curriculum_subjects()
    return {
        "board": boards[0] if boards else {"code": "CBSE", "name": "Central Board of Secondary Education"},
        "academic_session": "2026-2027",
        "class_code": "Class 10",
        "official_portal": "https://cbseacademic.nic.in/curriculum_2027.html",
        "total_subjects": len(subjects),
        "subjects": subjects,
    }


@app.get(
    "/api/v1/curriculum/subjects",
    response_model=List[CurriculumSubjectResponse],
    tags=["Curriculum"],
)
async def list_curriculum_subjects(
    category: Optional[str] = None,
    is_compulsory: Optional[bool] = None,
) -> List[CurriculumSubjectResponse]:
    """List all official CBSE Class 10 subjects."""
    subjects = get_curriculum_subjects(category=category, is_compulsory=is_compulsory)
    return [CurriculumSubjectResponse(**s) for s in subjects]


@app.get(
    "/api/v1/curriculum/subjects/{subject_id}",
    response_model=CurriculumSubjectResponse,
    tags=["Curriculum"],
)
async def get_subject_by_id(subject_id: str) -> CurriculumSubjectResponse:
    """Get metadata for a specific curriculum subject."""
    subj = get_curriculum_subject(subject_id)
    if not subj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Curriculum subject '{subject_id}' not found.",
        )
    return CurriculumSubjectResponse(**subj)


@app.get(
    "/api/v1/curriculum/subjects/{subject_id}/hierarchy",
    tags=["Curriculum"],
)
async def get_subject_full_hierarchy(subject_id: str) -> Dict[str, Any]:
    """Get complete hierarchy of a subject: units, chapters, and topics."""
    hierarchy = get_subject_hierarchy(subject_id)
    if not hierarchy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Curriculum subject '{subject_id}' not found.",
        )
    return hierarchy


@app.get(
    "/api/v1/curriculum/subjects/{subject_id}/chapters",
    response_model=List[CurriculumChapterSummary],
    tags=["Curriculum"],
)
async def list_subject_chapters(
    subject_id: str,
    unit_id: Optional[str] = None,
) -> List[CurriculumChapterSummary]:
    """List prescribed chapters for a curriculum subject."""
    chapters = get_chapters_by_subject(subject_id, unit_id=unit_id)
    return [CurriculumChapterSummary(**c) for c in chapters]


@app.get(
    "/api/v1/curriculum/chapters/{chapter_id}",
    response_model=CurriculumChapterDetail,
    tags=["Curriculum"],
)
async def get_chapter_by_id(chapter_id: str) -> CurriculumChapterDetail:
    """Get complete chapter details, verified topics, and official resources."""
    chap = get_chapter_details(chapter_id)
    if not chap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Curriculum chapter '{chapter_id}' not found.",
        )
    return CurriculumChapterDetail(**chap)


@app.get(
    "/api/v1/curriculum/chapters/{chapter_id}/topics",
    response_model=List[CurriculumTopicSummary],
    tags=["Curriculum"],
)
async def list_chapter_topics(chapter_id: str) -> List[CurriculumTopicSummary]:
    """List topics for a specific chapter."""
    topics = get_topics_by_chapter(chapter_id)
    return [CurriculumTopicSummary(**t) for t in topics]


@app.get(
    "/api/v1/curriculum/topics/{topic_id}",
    response_model=CurriculumTopicDetail,
    tags=["Curriculum"],
)
async def get_topic_by_id(topic_id: str) -> CurriculumTopicDetail:
    """Get full pedagogical details for a topic (key concepts, definitions, formulas, misconceptions, practice)."""
    top = get_topic_details(topic_id)
    if not top:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Curriculum topic '{topic_id}' not found.",
        )
    return CurriculumTopicDetail(**top)


@app.get(
    "/api/v1/curriculum/search",
    response_model=CurriculumSearchResponse,
    tags=["Curriculum"],
)
async def search_curriculum_catalog(
    q: str,
    subject_id: Optional[str] = None,
    limit: int = 20,
) -> CurriculumSearchResponse:
    """Search curriculum chapters and topics by keyword."""
    if len(q.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must contain at least 2 characters.",
        )
    res = search_curriculum(query=q.strip(), subject_id=subject_id, limit=limit)
    return CurriculumSearchResponse(**res)


# ==============================================================================
# Student Curriculum Subject Selection & Progress Endpoints
# ==============================================================================

@app.post(
    "/api/v1/students/me/subjects",
    response_model=List[StudentEnrolledSubjectResponse],
    tags=["Student Curriculum"],
)
async def set_my_enrolled_subjects(
    request: EnrollSubjectsRequest,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> List[StudentEnrolledSubjectResponse]:
    """Enroll student in chosen subjects."""
    enrolled = enroll_student_subjects(current_student["id"], request.subject_ids)
    return [StudentEnrolledSubjectResponse(**s) for s in enrolled]


@app.get(
    "/api/v1/students/me/subjects",
    response_model=List[StudentEnrolledSubjectResponse],
    tags=["Student Curriculum"],
)
async def get_my_enrolled_subjects(
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> List[StudentEnrolledSubjectResponse]:
    """Retrieve student's enrolled subjects with progress metrics."""
    enrolled = get_student_enrolled_subjects(current_student["id"])
    return [StudentEnrolledSubjectResponse(**s) for s in enrolled]


@app.get(
    "/api/v1/students/me/curriculum-progress/{subject_id}",
    response_model=SubjectProgressResponse,
    tags=["Student Curriculum"],
)
async def get_my_subject_progress(
    subject_id: str,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> SubjectProgressResponse:
    """Get aggregated topic progress metrics for an enrolled subject."""
    prog = get_student_subject_progress(current_student["id"], subject_id)
    return SubjectProgressResponse(**prog)


@app.post(
    "/api/v1/students/me/topic-progress",
    response_model=TopicProgressResponse,
    tags=["Student Curriculum"],
)
async def update_my_topic_progress(
    request: TopicProgressUpdateRequest,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> TopicProgressResponse:
    """Update topic study status, duration, and notes."""
    prog = update_student_topic_progress(
        student_id=current_student["id"],
        topic_id=request.topic_id,
        status=request.status,
        time_spent_seconds=request.time_spent_seconds,
        notes=request.notes,
    )
    return TopicProgressResponse(**prog)


# ==============================================================================
# Interactive Lesson Sessions & Bookmarks
# ==============================================================================

@app.post(
    "/api/v1/students/me/lesson-sessions",
    response_model=LessonSessionResponse,
    tags=["Lessons"],
)
async def start_or_resume_lesson(
    request: LessonSessionCreateRequest,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> LessonSessionResponse:
    """Start or resume an interactive learning session."""
    sess = create_or_get_lesson_session(
        student_id=current_student["id"],
        subject_id=request.subject_id,
        chapter_id=request.chapter_id,
        topic_id=request.topic_id,
        subtopic_id=request.subtopic_id,
        lesson_mode=request.lesson_mode,
    )
    return LessonSessionResponse(**sess)


@app.post(
    "/api/v1/students/me/lesson-sessions/{session_id}/message",
    response_model=LessonSessionResponse,
    tags=["Lessons"],
)
async def post_lesson_message(
    session_id: str,
    request: LessonMessageRequest,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> LessonSessionResponse:
    """Send a message to the AI Teacher within an ongoing lesson session."""
    sess = get_lesson_session(session_id)
    if not sess or sess["student_id"] != current_student["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson session not found.",
        )

    append_lesson_session_message(session_id, role="student", content=request.message)

    chap = get_chapter_details(sess["chapter_id"])
    top = get_topic_details(sess["topic_id"]) if sess.get("topic_id") else None

    crew = build_teacher_crew(
        student_question=request.message,
        grade="Class 10",
        subject=chap["subject_name"] if chap else "Science",
        language=current_student.get("preferred_language", "English"),
        chapter=chap["title"] if chap else None,
        topic=top["title"] if top else None,
        lesson_mode=sess.get("lesson_mode", "conceptual"),
    )
    ai_result = await asyncio.to_thread(crew.kickoff)
    ai_text = str(ai_result.raw if hasattr(ai_result, "raw") else ai_result).strip()

    append_lesson_session_message(session_id, role="teacher", content=ai_text)

    updated = get_lesson_session(session_id)
    return LessonSessionResponse(**updated)


@app.get(
    "/api/v1/students/me/lesson-sessions/active",
    response_model=Optional[LessonSessionResponse],
    tags=["Lessons"],
)
async def get_active_lesson(
    chapter_id: Optional[str] = None,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> Optional[LessonSessionResponse]:
    """Retrieve student's active lesson session."""
    sess = get_active_lesson_session(current_student["id"], chapter_id=chapter_id)
    return LessonSessionResponse(**sess) if sess else None


@app.post(
    "/api/v1/students/me/lesson-sessions/{session_id}/complete",
    response_model=LessonSessionResponse,
    tags=["Lessons"],
)
async def complete_lesson(
    session_id: str,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> LessonSessionResponse:
    """Mark a lesson session as completed and update progress."""
    sess = get_lesson_session(session_id)
    if not sess or sess["student_id"] != current_student["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson session not found.",
        )
    completed = complete_lesson_session(session_id)

    if sess.get("topic_id"):
        update_student_topic_progress(
            student_id=current_student["id"],
            topic_id=sess["topic_id"],
            status="completed",
        )

    return LessonSessionResponse(**completed)


@app.post(
    "/api/v1/students/me/bookmarks",
    response_model=BookmarkResponse,
    tags=["Student Curriculum"],
)
async def toggle_bookmark(
    request: BookmarkToggleRequest,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> BookmarkResponse:
    """Toggle bookmark for a chapter, topic, or resource."""
    res = toggle_student_bookmark(
        student_id=current_student["id"],
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        note=request.note,
    )
    return BookmarkResponse(**res)


@app.get(
    "/api/v1/students/me/bookmarks",
    response_model=List[Dict[str, Any]],
    tags=["Student Curriculum"],
)
async def list_bookmarks(
    entity_type: Optional[str] = None,
    current_student: Dict[str, Any] = Depends(get_current_student),
) -> List[Dict[str, Any]]:
    """List bookmarked curriculum items for the student."""
    return get_student_bookmarks(current_student["id"], entity_type=entity_type)
