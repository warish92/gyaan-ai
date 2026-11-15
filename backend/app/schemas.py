"""Pydantic schemas for Gyaan AI API request and response validation."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ==============================================================================
# Phase 2 Schemas: Health and Ask
# ==============================================================================

class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(..., description="Overall service status ('healthy' or 'degraded').")
    app: str = Field("ok", description="FastAPI application status.")
    ollama_connected: bool = Field(..., description="Whether local Ollama service is reachable.")
    model_available: bool = Field(..., description="Whether the target model is loaded or listed.")
    model_name: str = Field(..., description="Configured local LLM model name.")
    details: Optional[str] = Field(None, description="Optional diagnostic details.")


class AskRequest(BaseModel):
    """Student educational query request schema."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="The educational question to ask.",
        examples=["Explain the difference between acids and bases. Give two examples of each."],
    )
    grade: str = Field(
        default="Class 10",
        max_length=50,
        description="Target grade level (default: Class 10).",
    )
    subject: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Academic subject (e.g. 'Science', 'Chemistry').",
    )
    chapter: Optional[str] = Field(
        default=None,
        max_length=150,
        description="Optional chapter context for targeted tutoring.",
    )
    topic: Optional[str] = Field(
        default=None,
        max_length=150,
        description="Optional topic context.",
    )
    subtopic: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional subtopic context.",
    )
    learning_objectives: Optional[List[str]] = Field(
        default=None,
        description="Specific learning objectives for the lesson.",
    )
    lesson_mode: Optional[str] = Field(
        default="conceptual",
        max_length=50,
        description="Mode: 'conceptual', 'simplified', 'real_world', 'practice', 'doubt_clearing'.",
    )
    language: str = Field(
        default="English",
        max_length=50,
        description="Response language (e.g. 'English', 'Hindi').",
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of student document IDs to ground pedagogical explanation in student uploads.",
    )

    @field_validator("question")
    @classmethod
    def validate_question_non_empty(cls, value: str) -> str:
        """Ensure question contains meaningful non-whitespace content."""
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Question must contain at least 3 non-whitespace characters.")
        return cleaned


class AskResponse(BaseModel):
    """Structured response schema for student educational queries."""

    answer: str = Field(..., description="The generated educational explanation from Teacher Agent or specialist agent.")
    request_id: str = Field(..., description="Unique tracking identifier for this request.")
    model: str = Field(..., description="Model used for generation.")
    status: str = Field(..., description="Execution status ('success' or 'error').")
    duration_ms: float = Field(..., description="Total execution time in milliseconds.")
    agent_name: Optional[str] = Field(default=None, description="Name of the canonical agent or specialist that responded.")
    selected_agents: Optional[List[str]] = Field(default=None, description="List of agents involved in processing the request.")
    workflow_executed: Optional[str] = Field(default=None, description="The workflow executed by the multi-agent system.")
    detected_intent: Optional[str] = Field(default=None, description="The educational intent detected by the Orchestrator.")
    student_documents: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional list of retrieved student document chunks with 7-field provenance grounding the lesson.")


# ==============================================================================
# Phase 3 Schemas: Diagnostic and Curriculum Learning Plan
# ==============================================================================

class AssessmentItem(BaseModel):
    """Single diagnostic assessment item with question and student answer."""

    question: str = Field(..., min_length=3, max_length=1000, description="The test question asked.")
    student_answer: str = Field(..., min_length=1, max_length=2000, description="The student's submitted response.")
    expected_answer: Optional[str] = Field(None, max_length=1000, description="Optional rubric or reference answer.")

    @field_validator("question", "student_answer")
    @classmethod
    def validate_item_text(cls, value: str) -> str:
        """Ensure non-empty text."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text fields cannot be blank or whitespace-only.")
        return cleaned


class AnswerClassification(str, Enum):
    CORRECT = "Correct"
    PARTIALLY_CORRECT = "Partially Correct"
    INCORRECT = "Incorrect"
    INSUFFICIENT_EVIDENCE = "Insufficient Evidence"


class QuestionDiagnosis(BaseModel):
    """Detailed evidence-based evaluation for a single assessment question."""

    question: str = Field(..., description="The test question asked.")
    student_answer: str = Field(..., description="The student's actual submitted answer.")
    expected_answer: Optional[str] = Field(None, description="Expected answer or grading rubric.")
    correct_elements: List[str] = Field(default_factory=list, description="Specific concepts/facts correctly demonstrated in the answer.")
    missing_elements: List[str] = Field(default_factory=list, description="Expected concepts/facts omitted by the student (knowledge gaps).")
    incorrect_elements: List[str] = Field(default_factory=list, description="Explicitly incorrect statements made by the student.")
    classification: AnswerClassification = Field(..., description="Classification: Correct, Partially Correct, Incorrect, or Insufficient Evidence.")
    confidence_level: str = Field(default="High", description="Confidence level: High, Medium, or Low.")
    explanation: str = Field(..., description="Pedagogical explanation strictly grounded in what the student actually wrote.")


class DiagnosticReportModel(BaseModel):
    """Structured evidence-based diagnostic report model."""

    grade: str = Field(default="Class 10", description="Grade level assessed.")
    subject: str = Field(..., description="Subject assessed.")
    topic: str = Field(..., description="Topic assessed.")
    question_evaluations: List[QuestionDiagnosis] = Field(default_factory=list, description="Individual question diagnostic evaluations.")
    demonstrated_understanding: List[str] = Field(default_factory=list, description="Proven concepts mastered across all answers.")
    evidenced_knowledge_gaps: List[str] = Field(default_factory=list, description="Missing concepts/elements omitted by the student.")
    uncovered_misconceptions: List[str] = Field(default_factory=list, description="Conceptual errors explicitly evidenced. MUST be empty if only omissions occurred.")
    recommended_focus_topics: List[str] = Field(default_factory=list, description="Top 2-3 focus topics prioritized strictly on evidenced gaps.")
    overall_summary: str = Field(..., description="Evidence-grounded summary of student baseline.")


class LearningStage(BaseModel):
    """A distinct learning stage within a personalized curriculum plan."""

    stage_number: int = Field(..., ge=1, le=5, description="Sequential stage order.")
    stage_name: str = Field(..., description="Stage title, e.g. Prerequisite Recovery, Core Concept Mastery, Applied Problem Solving.")
    focus_topic: str = Field(..., description="The prioritized topic addressed in this stage, directly tied to diagnostic evidence.")
    prerequisite_concepts: List[str] = Field(default_factory=list, description="Foundational concepts required before starting this stage.")
    measurable_objectives: List[str] = Field(default_factory=list, description="Observable learning objectives the student will achieve.")
    learning_activities: List[str] = Field(default_factory=list, description="Actionable study tasks. Must be labeled as 'General learning activity' unless verified NCERT resource is provided.")
    assessment_checkpoint: str = Field(..., description="Checkpoint question/task to verify stage mastery without repeating identical questions.")
    evidence_justification: str = Field(..., description="Why this stage/topic is necessary based on specific diagnostic evidence.")


class CurriculumPlanModel(BaseModel):
    """Structured curriculum plan model generated based on diagnostic evidence."""

    grade: str = Field(default="Class 10", description="Grade level.")
    subject: str = Field(..., description="Subject.")
    topic: str = Field(..., description="Topic.")
    primary_mastery_goal: str = Field(..., description="Primary motivating mastery goal.")
    mastery_criterion: str = Field(
        default="A minimum 70% threshold on formative assessment checkpoints is required before advancing.",
        description="Explicit quantitative mastery criterion.",
    )
    prioritized_topics: List[str] = Field(default_factory=list, description="Topics prioritized strictly by evidenced diagnostic knowledge gaps.")
    learning_stages: List[LearningStage] = Field(default_factory=list, description="Sequenced distinct learning stages.")
    resource_alignment_status: str = Field(
        default="General learning activities (Unverified against live NCERT textbook content)",
        description="Explicit statement of resource grounding. Must not claim NCERT alignment without verified content.",
    )
    summary: str = Field(..., description="Pedagogical overview of the personalized study plan.")


class LearningPlanRequest(BaseModel):
    """Request schema for generating a personalized diagnostic learning plan."""

    student_id: Optional[str] = Field(None, description="Optional existing student ID. Generated if omitted.")
    display_name: str = Field(default="Student", max_length=100, description="Student display name or handle.")
    grade: str = Field(default="Class 10", max_length=50, description="Educational grade level.")
    subject: str = Field(..., min_length=2, max_length=100, description="Subject (e.g. 'Science').")
    topic: str = Field(..., min_length=2, max_length=150, description="Topic (e.g. 'Acids, Bases and Salts').")
    assessment_items: List[AssessmentItem] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of assessment questions and student answers to evaluate.",
    )


class LearningPlanResponse(BaseModel):
    """Structured response schema for diagnostic assessment and curriculum plan."""

    workflow_id: str = Field(..., description="Unique workflow execution ID.")
    student_id: str = Field(..., description="Student identifier associated with the plan.")
    diagnostic_report: str = Field(..., description="Diagnostic report generated by the Diagnostic Agent.")
    curriculum_plan: str = Field(..., description="Personalized learning plan generated by the Curriculum Agent.")
    status: str = Field(..., description="Workflow execution status ('success' or 'error').")
    model: str = Field(..., description="Model identifier used for generation.")
    duration_ms: float = Field(..., description="Workflow execution duration in milliseconds.")
    persisted: bool = Field(..., description="Whether records were successfully persisted to SQLite.")
    diagnostic_id: Optional[str] = Field(None, description="Persisted diagnostic record ID.")
    plan_id: Optional[str] = Field(None, description="Persisted curriculum plan ID.")
    diagnostic_data: Optional[DiagnosticReportModel] = Field(None, description="Structured diagnostic evaluations and gap analysis.")
    curriculum_data: Optional[CurriculumPlanModel] = Field(None, description="Structured curriculum stages, objectives, and checkpoints.")


# ==============================================================================
# Phase 4 Schemas: Resource Agent & Assessment Agent (Quizzes & Grading)
# ==============================================================================

class ResourceRequest(BaseModel):
    """Request schema for retrieving and curating educational resources."""

    grade: str = Field(default="Class 10", max_length=50, description="Target educational level.")
    subject: str = Field(..., min_length=2, max_length=100, description="Subject matter (e.g. 'Science').")
    topic: str = Field(..., min_length=2, max_length=150, description="Topic or unit to curate resources for.")
    learning_objective: Optional[str] = Field(None, max_length=300, description="Target learning objective.")
    document_ids: Optional[List[str]] = Field(None, description="Optional target student document IDs for RAG retrieval.")


class ResourceResponse(BaseModel):
    """Response schema containing Resource Agent analysis and verified excerpts."""

    workflow_id: str = Field(..., description="Unique workflow tracking ID.")
    resource_recommendation: str = Field(..., description="Educational guidance from Resource Agent.")
    is_verified: bool = Field(..., description="Whether source excerpts were verified against local NCERT corpus.")
    source_type: str = Field(..., description="Corpus type (e.g. 'Verified Local NCERT Corpus' or 'Provisional').")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Retrieved source excerpts and metadata.")
    student_documents: List[Dict[str, Any]] = Field(default_factory=list, description="Retrieved student document excerpts with full provenance.")
    model: str = Field(..., description="Model used for curation analysis.")
    duration_ms: float = Field(..., description="Total execution duration in milliseconds.")


class QuizGenerationRequest(BaseModel):
    """Request schema for generating a practice quiz."""

    student_id: Optional[str] = Field(None, description="Optional student ID for tracking.")
    grade: str = Field(default="Class 10", max_length=50, description="Grade level.")
    subject: str = Field(..., min_length=2, max_length=100, description="Subject (e.g. 'Science').")
    topic: str = Field(..., min_length=2, max_length=150, description="Specific topic to test.")
    num_questions: int = Field(default=3, ge=1, le=10, description="Number of questions (1-10).")
    question_types: List[str] = Field(
        default=["mcq", "short_answer"],
        description="Desired question types (e.g. ['mcq', 'short_answer']).",
    )
    learning_objectives: Optional[str] = Field(None, max_length=300, description="Target learning objectives.")


class StudentQuizQuestion(BaseModel):
    """Student-facing quiz question WITHOUT correct answer or explanation."""

    id: str = Field(..., description="Unique question identifier within quiz.")
    type: str = Field(..., description="Question type ('mcq' or 'short_answer').")
    question: str = Field(..., description="Question prompt.")
    options: List[str] = Field(default_factory=list, description="Answer choices for MCQs.")
    marks: float = Field(default=1.0, description="Maximum marks for this question.")
    difficulty: Optional[str] = Field("medium", description="Question difficulty level.")


class QuizGenerationResponse(BaseModel):
    """Student-facing quiz generation response."""

    quiz_id: str = Field(..., description="Unique identifier for generated quiz.")
    student_id: Optional[str] = Field(None, description="Associated student ID.")
    subject: str = Field(..., description="Subject of the quiz.")
    topic: str = Field(..., description="Tested topic.")
    grade: str = Field(..., description="Grade level.")
    questions: List[StudentQuizQuestion] = Field(..., description="List of questions for the student to answer.")
    is_verified_source: bool = Field(..., description="Whether questions were based on verified NCERT corpus.")
    source_type: str = Field(..., description="Source verification status.")
    duration_ms: float = Field(..., description="Generation execution duration in ms.")


class AssessmentSubmissionRequest(BaseModel):
    """Request schema for submitting student answers for evaluation."""

    quiz_id: str = Field(..., min_length=3, description="ID of the quiz being answered.")
    student_id: Optional[str] = Field(None, description="Student ID submitting the quiz.")
    answers: Dict[str, str] = Field(
        ...,
        min_length=1,
        description="Map of question_id to student's submitted answer text.",
    )


class QuestionEvaluation(BaseModel):
    """Detailed evaluation of a single student response."""

    question_id: str = Field(..., description="Question identifier.")
    score_awarded: float = Field(..., description="Marks awarded to student.")
    max_marks: float = Field(..., description="Maximum marks possible.")
    status: str = Field(..., description="'correct', 'partially_correct', or 'incorrect'.")
    student_answer: str = Field(..., description="Student's submitted answer.")
    expected_answer: str = Field(..., description="Model answer or rubric key.")
    feedback: str = Field(..., description="Constructive feedback explaining marks awarded.")
    revision_topic: Optional[str] = Field(None, description="Suggested revision topic if marks were missed.")


class AssessmentSubmissionResponse(BaseModel):
    """Response schema containing full grading, rubric feedback, and persisted attempt record."""

    attempt_id: str = Field(..., description="Unique assessment attempt identifier.")
    quiz_id: str = Field(..., description="Associated quiz ID.")
    student_id: Optional[str] = Field(None, description="Student ID.")
    total_score: float = Field(..., description="Total marks earned.")
    max_marks: float = Field(..., description="Total marks possible.")
    percentage: float = Field(..., description="Calculated percentage score.")
    evaluations: List[QuestionEvaluation] = Field(..., description="Per-question grading and feedback.")
    overall_feedback: str = Field(..., description="Overall constructive performance summary.")
    duration_ms: float = Field(..., description="Evaluation execution duration in ms.")
    persisted: bool = Field(..., description="Whether attempt was saved to database.")


class AssessmentHistoryItem(BaseModel):
    """Single historical quiz attempt entry."""

    attempt_id: str
    quiz_id: str
    student_id: Optional[str]
    subject: str
    topic: str
    grade: str
    score: float
    max_marks: float
    created_at: str
    evaluation_details: Dict[str, Any]


class AssessmentHistoryResponse(BaseModel):
    """Student historical assessments list."""

    student_id: str
    total_attempts: int
    attempts: List[AssessmentHistoryItem]


# ==============================================================================
# Phase 5 Schemas: Student Accounts, Authentication & Learning Dashboard
# ==============================================================================

class StudentRegisterRequest(BaseModel):
    """Student account registration request schema."""

    display_name: str = Field(..., min_length=2, max_length=100, description="Student's full or preferred name.")
    email: EmailStr = Field(..., description="Student's unique email address.")
    password: str = Field(..., min_length=6, max_length=128, description="Password (minimum 6 characters).")
    grade: str = Field(default="Class 10", min_length=2, max_length=50, description="Student's academic grade/class.")
    preferred_language: str = Field(
        default="English",
        min_length=2,
        max_length=50,
        description="Preferred language for explanations (e.g. English, Hindi).",
    )

    @field_validator("display_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Display name cannot be blank or whitespace-only.")
        return stripped


class StudentLoginRequest(BaseModel):
    """Student login request schema."""

    email: EmailStr = Field(..., description="Registered email address.")
    password: str = Field(..., min_length=1, max_length=128, description="Account password.")


class StudentProfileResponse(BaseModel):
    """Safe student profile information (never exposes password or password hash)."""

    id: str = Field(..., description="Unique student ID.")
    email: Optional[str] = Field(None, description="Registered email address.")
    display_name: str = Field(..., description="Student's display name.")
    grade: str = Field(..., description="Current academic grade.")
    preferred_language: str = Field("English", description="Preferred explanation language.")
    created_at: str = Field(..., description="Account creation timestamp.")
    updated_at: Optional[str] = Field(None, description="Last profile update timestamp.")
    account_status: str = Field("active", description="Account status ('active' or 'suspended').")


class AuthTokenResponse(BaseModel):
    """Authentication response returning raw session token and profile."""

    token: str = Field(..., description="Opaque session bearer token (returned once).")
    token_type: str = Field("bearer", description="Token type.")
    expires_at: str = Field(..., description="Token expiration timestamp in ISO 8601 UTC.")
    student: StudentProfileResponse = Field(..., description="Authenticated student profile.")


class StudentProfileUpdateRequest(BaseModel):
    """Request schema for updating permitted student profile fields."""

    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    grade: Optional[str] = Field(None, min_length=2, max_length=50)
    preferred_language: Optional[str] = Field(None, min_length=2, max_length=50)

    @field_validator("display_name")
    @classmethod
    def validate_update_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Display name cannot be blank.")
        return v.strip() if v else None


class LearningSessionResponse(BaseModel):
    """Persistent learning session history item."""

    id: str
    student_id: str
    subject: str
    topic: str
    activity_type: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class TopicMasteryResponse(BaseModel):
    """Topic-wise mastery evaluation record."""

    id: str
    student_id: str
    subject: str
    topic: str
    latest_score: float
    max_marks: float
    percentage: float
    attempts_count: int
    mastery_status: str
    last_assessed_at: str
    updated_at: str


class StudentDashboardResponse(BaseModel):
    """Aggregated student dashboard learning data."""

    profile: StudentProfileResponse
    recent_learning_sessions: List[LearningSessionResponse]
    recent_diagnostics: List[Dict[str, Any]]
    recent_curriculum_plans: List[Dict[str, Any]]
    recent_assessments: List[AssessmentHistoryItem]
    topic_mastery: List[TopicMasteryResponse]
    stats: Dict[str, Any]


# ==============================================================================
# Phase 6 Schemas: Progress Agent & Mentor Agent
# ==============================================================================

class ObjectiveStatisticsResponse(BaseModel):
    """Deterministic, verified statistical learning metrics."""

    student_id: str
    has_sufficient_history: bool
    total_assessments_completed: int
    unique_quizzes_taken: int
    total_questions_answered: int
    correct_answers_count: int
    partially_correct_answers_count: int
    incorrect_answers_count: int
    average_percentage: Optional[float]
    performance_trend: str
    trend_description: str
    strengths: List[str]
    areas_needing_improvement: List[str]
    topics_needing_practice: List[str]
    total_learning_sessions: int
    completed_sessions_count: int
    sessions_by_type: Dict[str, int]
    diagnostic_records_count: int
    curriculum_plans_count: int
    most_recent_activity_date: Optional[str]


class TopicObservation(BaseModel):
    """Observation regarding student understanding in a specific topic."""

    topic: str
    observation: str
    status: str = Field("in_progress", description="'mastered', 'in_progress', or 'needs_revision'")


class ProgressReportResponse(BaseModel):
    """Validated output from the canonical Progress Agent."""

    student_id: str
    objective_statistics: ObjectiveStatisticsResponse
    overall_summary: str
    strengths_analysis: List[str]
    weaknesses_analysis: List[str]
    topic_observations: List[TopicObservation]
    performance_interpretation: str
    data_limitations: Optional[str] = None
    recommended_priorities: List[str]
    model: str
    duration_ms: float


class MentorRecommendationItem(BaseModel):
    """Structured, actionable recommendation from the canonical Mentor Agent."""

    title: str = Field(..., description="Actionable title of recommendation.")
    topic: str = Field(..., description="Related academic concept.")
    reason: str = Field(..., description="Evidence-backed justification.")
    suggested_action: str = Field(..., description="Concrete learning task to execute.")
    priority: str = Field("medium", description="'high', 'medium', or 'low'.")
    estimated_minutes: Optional[int] = Field(20, description="Estimated duration in minutes.")
    supporting_evidence: Optional[str] = Field(None, description="Observed scores/records supporting action.")
    resource_reference: Optional[str] = Field(None, description="Curriculum or chapter excerpt reference.")


class MentorRecommendationsResponse(BaseModel):
    """Validated output from the canonical Mentor Agent."""

    student_id: str
    mentor_overview: str
    recommendations: List[MentorRecommendationItem]
    study_tip: Optional[str] = None
    next_milestone: Optional[str] = None
    model: str
    duration_ms: float


class FullProgressMentoringResponse(BaseModel):
    """Consolidated response executing sequential Progress -> Mentor multi-agent workflow."""

    student_id: str
    progress: ProgressReportResponse
    mentoring: MentorRecommendationsResponse
    duration_ms: float


# ==============================================================================
# Phase 7 Schemas: Orchestrator Agent & Workflow Routing
# ==============================================================================

class OrchestrationRequest(BaseModel):
    """Incoming student request to the central AI workflow orchestrator."""

    request: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="The student's educational request or inquiry.",
        examples=[
            "Explain the difference between acids and bases.",
            "Can you give me a 3-question practice quiz on chemical reactions?",
            "How am I progressing in science and what should I study next?",
        ],
    )
    grade: str = Field(
        default="Class 10",
        max_length=50,
        description="Target grade level (default: Class 10).",
    )
    subject: Optional[str] = Field(
        default="Science",
        max_length=100,
        description="Academic subject.",
    )
    language: str = Field(
        default="English",
        max_length=50,
        description="Response language preference.",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional additional context (e.g. quiz_id, assessment_items, previous answers).",
    )

    @field_validator("request")
    @classmethod
    def validate_request_non_empty(cls, value: str) -> str:
        """Ensure request contains meaningful non-whitespace content."""
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Request must contain at least 3 non-whitespace characters.")
        return cleaned


class RoutingDecision(BaseModel):
    """Structured routing decision produced by the canonical Orchestrator Agent."""

    request_id: str
    detected_intent: str
    selected_workflow: str
    selected_agents: List[str]
    normalized_request: str
    clarification_required: bool = False
    clarification_question: Optional[str] = None
    routing_reason: str
    extracted_parameters: Optional[Dict[str, Any]] = None


class OrchestrationResponse(BaseModel):
    """Validated response from the central orchestration endpoint."""

    request_id: str
    workflow_id: str
    detected_intent: str
    selected_workflow: str
    selected_agents: List[str]
    routing_reason: str
    clarification_required: bool = False
    clarification_question: Optional[str] = None
    result: Optional[Any] = None
    status: str = Field("success", description="'success', 'clarification_needed', 'error', etc.")
    duration_ms: float
    model: str
    trace_id: Optional[str] = Field(None, description="Root distributed trace identifier for observability")


# ==============================================================================
# Sequential Chapter Learning Journey Schemas
# ==============================================================================

class LearningJourneyStartRequest(BaseModel):
    """Request schema for initiating or executing the 8-agent sequential chapter learning journey."""

    subject: str = Field(..., min_length=2, description="Target academic subject (e.g. 'Science', 'Mathematics').")
    chapter: str = Field(..., min_length=2, description="Target chapter or unit (e.g. 'Chemical Reactions and Equations').")
    learning_goal: Optional[str] = Field(None, description="Student's specific learning aspiration.")
    grade: str = Field(default="Class 10", min_length=2, description="Student's academic grade.")
    language: str = Field(default="English", description="Target language for instruction and mentoring.")
    student_id: Optional[str] = Field(None, description="Optional student ID if already authenticated.")
    document_ids: Optional[List[str]] = Field(None, description="Optional target student document IDs to ground chapter learning in student uploads.")
    student_input_evidence: Optional[str] = Field(None, description="Diagnostic input or answers for Task 2.")
    student_answers: Optional[Dict[str, str]] = Field(None, description="Assessment answers submitted by student.")
    is_remediation: bool = Field(default=False, description="Whether this is a repeated remediation iteration.")
    max_retries: int = Field(default=3, ge=1, le=5, description="Maximum adaptive retry loops.")
    run_in_background: bool = Field(default=True, description="Whether to execute the 8-agent sequential workflow in background.")


class LearningJourneyInteractRequest(BaseModel):
    """Request schema for student interaction in an active learning journey."""

    action: str = Field(..., description="Action type: 'submit_answers', 'acknowledge_lesson', 'pause', 'resume', 'request_remediation'.")
    student_answers: Optional[Dict[str, str]] = Field(None, description="Student responses to comprehension or assessment questions.")
    feedback: Optional[str] = Field(None, description="Optional student feedback or questions.")


class LearningJourneyResponse(BaseModel):
    """Full response schema for a chapter learning journey."""

    journey_id: str = Field(..., description="Unique journey identifier.")
    student_id: Optional[str] = Field(None, description="Associated student ID.")
    subject: str = Field(..., description="Subject.")
    chapter: str = Field(..., description="Chapter.")
    learning_goal: Optional[str] = Field(None, description="Learning goal.")
    current_step: str = Field(..., description="Active step in the 8-agent journey.")
    status: str = Field(..., description="'active', 'needs_student_input', 'completed', 'paused'.")
    loop_iteration: int = Field(1, description="Adaptive retry iteration counter.")
    max_retries: int = Field(3, description="Max allowed iterations.")
    mastery_score: float = Field(0.0, description="Evaluated mastery score percentage.")
    mastery_achieved: bool = Field(False, description="Whether 70% mastery criteria are satisfied.")
    step_outputs: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Outputs from individual agents.")
    adaptive_action: Optional[str] = Field(None, description="'advance_to_next_topic' or 'repeat_lesson_remediation'.")
    duration_seconds: Optional[float] = Field(None, description="Total execution time.")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None






# ==============================================================================
# CBSE Class 10 Curriculum Schemas
# ==============================================================================

class CurriculumSubjectResponse(BaseModel):
    """CBSE Class 10 curriculum subject representation."""

    id: str = Field(..., description="Unique subject identifier (e.g. 'subj_science_086').")
    class_id: str = Field(..., description="Target class identifier.")
    code: str = Field(..., description="CBSE official subject code (e.g. '086', '041').")
    name: str = Field(..., description="Official subject title.")
    short_name: Optional[str] = Field(None, description="Concise display title.")
    category: str = Field(..., description="Category: 'Science', 'Mathematics', 'Languages', 'Skill Subjects', etc.")
    is_compulsory: bool = Field(False, description="Whether subject is compulsory in CBSE standard stream.")
    description: Optional[str] = Field(None, description="Curriculum description.")
    official_syllabus_url: Optional[str] = Field(None, description="Direct URL to official CBSE syllabus.")
    verification_status: str = Field("VERIFIED", description="Official verification status.")
    unit_count: Optional[int] = Field(0, description="Number of units in this subject.")
    chapter_count: Optional[int] = Field(0, description="Number of prescribed chapters.")


class CurriculumUnitResponse(BaseModel):
    """CBSE curriculum unit/section representation."""

    id: str = Field(..., description="Unique unit identifier.")
    subject_id: str = Field(..., description="Parent subject identifier.")
    unit_number: int = Field(..., description="Unit order number.")
    title: str = Field(..., description="Unit title.")
    section_tag: Optional[str] = Field(None, description="Disciplinary domain (e.g. 'Physics', 'History').")
    description: Optional[str] = Field(None, description="Unit syllabus summary.")
    weightage_marks: int = Field(0, description="CBSE board exam marks weightage.")


class CurriculumChapterSummary(BaseModel):
    """Summary of a curriculum chapter."""

    id: str = Field(..., description="Unique chapter identifier (e.g. 'chap_sci_1').")
    subject_id: str = Field(..., description="Parent subject identifier.")
    unit_id: Optional[str] = Field(None, description="Parent unit identifier.")
    chapter_number: int = Field(..., description="Chapter order number.")
    title: str = Field(..., description="Prescribed chapter title.")
    slug: Optional[str] = Field(None, description="URL-friendly slug.")
    section_tag: Optional[str] = Field(None, description="Section or domain tag.")
    description: Optional[str] = Field(None, description="Chapter description.")
    estimated_minutes: int = Field(360, description="Estimated study duration in minutes.")
    is_prescribed: bool = Field(True, description="Whether prescribed in current board examination.")
    topic_count: int = Field(0, description="Number of verified topics.")
    unit_title: Optional[str] = Field(None, description="Title of parent unit.")


class CurriculumTopicSummary(BaseModel):
    """Summary of a topic in a curriculum chapter."""

    id: str = Field(..., description="Unique topic identifier.")
    chapter_id: str = Field(..., description="Parent chapter identifier.")
    topic_number: int = Field(..., description="Topic order number.")
    title: str = Field(..., description="Topic title.")
    slug: Optional[str] = Field(None, description="URL slug.")
    summary: Optional[str] = Field(None, description="Brief concept summary.")
    importance: str = Field("High", description="Board exam importance.")
    difficulty_level: str = Field("Intermediate", description="Difficulty level.")


class CurriculumSubtopicResponse(BaseModel):
    """Subtopic entry."""

    id: str = Field(..., description="Unique subtopic identifier.")
    topic_id: str = Field(..., description="Parent topic identifier.")
    subtopic_number: int = Field(..., description="Order index.")
    title: str = Field(..., description="Subtopic title.")
    explanation: Optional[str] = Field(None, description="Core explanation.")


class CurriculumObjectiveResponse(BaseModel):
    """Specific learning objective mapped to Bloom's taxonomy."""

    id: str = Field(..., description="Unique objective identifier.")
    topic_id: str = Field(..., description="Parent topic identifier.")
    objective_code: Optional[str] = Field(None, description="Academic objective code.")
    description: str = Field(..., description="Measurable objective statement.")
    bloom_level: str = Field("Understand", description="Bloom's Taxonomy Level: 'Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate'.")


class CurriculumResourceResponse(BaseModel):
    """Curriculum resource link."""

    id: str = Field(..., description="Unique resource identifier.")
    chapter_id: Optional[str] = Field(None, description="Chapter ID.")
    topic_id: Optional[str] = Field(None, description="Topic ID.")
    title: str = Field(..., description="Resource title.")
    resource_type: str = Field(..., description="Type: 'NCERT Textbook', 'Exemplar', 'Reference Guide'.")
    url: Optional[str] = Field(None, description="URL to resource.")
    notes: Optional[str] = Field(None, description="Helpful notes.")


class CurriculumTopicDetail(BaseModel):
    """Complete topic details with pedagogical components."""

    id: str = Field(..., description="Unique topic identifier.")
    chapter_id: str = Field(..., description="Parent chapter identifier.")
    topic_number: int = Field(..., description="Topic order number.")
    title: str = Field(..., description="Topic title.")
    slug: Optional[str] = Field(None, description="URL slug.")
    summary: Optional[str] = Field(None, description="Brief concept summary.")
    importance: str = Field("High", description="Board exam importance.")
    difficulty_level: str = Field("Intermediate", description="Difficulty level.")
    key_concepts: List[Any] = Field(default_factory=list, description="Prescribed key concepts.")
    definitions: Dict[str, Any] = Field(default_factory=dict, description="Formal definitions.")
    formulas: List[Any] = Field(default_factory=list, description="Formulas, rules, or theorems.")
    common_misconceptions: List[Any] = Field(default_factory=list, description="Frequent student pitfalls.")
    practice_questions: List[Any] = Field(default_factory=list, description="Curated practice problems.")
    subtopics: List[CurriculumSubtopicResponse] = Field(default_factory=list, description="Nested subtopics.")
    learning_objectives: List[CurriculumObjectiveResponse] = Field(default_factory=list, description="Bloom's learning objectives.")
    resources: List[CurriculumResourceResponse] = Field(default_factory=list, description="Associated learning materials.")
    chapter_title: Optional[str] = Field(None, description="Parent chapter title.")
    subject_name: Optional[str] = Field(None, description="Parent subject name.")


class CurriculumChapterDetail(BaseModel):
    """Complete chapter details with topics and resources."""

    id: str = Field(..., description="Unique chapter identifier.")
    subject_id: str = Field(..., description="Subject identifier.")
    unit_id: Optional[str] = Field(None, description="Unit identifier.")
    chapter_number: int = Field(..., description="Chapter order number.")
    title: str = Field(..., description="Chapter title.")
    slug: Optional[str] = Field(None, description="URL slug.")
    section_tag: Optional[str] = Field(None, description="Section or domain tag.")
    description: Optional[str] = Field(None, description="Detailed description.")
    estimated_minutes: int = Field(360, description="Estimated study duration.")
    prerequisites: Optional[List[str]] = Field(default_factory=list, description="Prerequisite concepts.")
    is_prescribed: bool = Field(True, description="Assessed in board exams.")
    excluded_topics: Optional[str] = Field(None, description="Excluded syllabus portions.")
    source_reference: Optional[str] = Field(None, description="Prescribed NCERT source reference.")
    verification_status: str = Field("VERIFIED", description="Verification status.")
    unit_title: Optional[str] = Field(None, description="Parent unit title.")
    subject_name: Optional[str] = Field(None, description="Parent subject name.")
    subject_code: Optional[str] = Field(None, description="CBSE subject code.")
    topics: List[CurriculumTopicDetail] = Field(default_factory=list, description="Chapters topics.")
    resources: List[CurriculumResourceResponse] = Field(default_factory=list, description="Prescribed chapter resources.")


class EnrollSubjectsRequest(BaseModel):
    """Student subject enrollment request."""

    subject_ids: List[str] = Field(..., min_length=1, description="List of subject IDs to enroll in.")


class StudentEnrolledSubjectResponse(BaseModel):
    """Enrolled subject details with progress metrics."""

    id: str = Field(..., description="Subject ID.")
    code: str = Field(..., description="CBSE subject code.")
    name: str = Field(..., description="Subject name.")
    short_name: Optional[str] = Field(None, description="Short name.")
    category: str = Field(..., description="Category.")
    is_compulsory: bool = Field(False, description="Whether compulsory.")
    description: Optional[str] = Field(None, description="Description.")
    chapter_count: int = Field(0, description="Total chapters.")
    total_topics: int = Field(0, description="Total topics.")
    completed_topics: int = Field(0, description="Topics completed or mastered.")
    progress_percentage: float = Field(0.0, description="Completion percentage.")
    enrolled_at: Optional[str] = None


class TopicProgressUpdateRequest(BaseModel):
    """Topic progress update request."""

    topic_id: str = Field(..., description="Target topic ID.")
    status: str = Field(..., description="'not_started', 'in_progress', 'completed', 'mastered'.")
    time_spent_seconds: int = Field(0, ge=0, description="Study duration in seconds.")
    notes: Optional[str] = Field(None, max_length=1000, description="Personal study notes.")


class TopicProgressResponse(BaseModel):
    """Topic progress status."""

    id: str
    student_id: str
    topic_id: str
    status: str
    time_spent_seconds: int
    last_studied_at: Optional[str] = None
    notes: Optional[str] = None
    updated_at: str


class SubjectProgressResponse(BaseModel):
    """Aggregated subject progress metrics."""

    student_id: str
    subject_id: str
    total_topics: int
    completed_topics: int
    in_progress_topics: int
    mastered_topics: int
    progress_percentage: float
    total_study_time_seconds: int


class LessonSessionCreateRequest(BaseModel):
    """Request to initiate or resume an interactive lesson."""

    subject_id: str = Field(..., description="Target subject ID.")
    chapter_id: str = Field(..., description="Target chapter ID.")
    topic_id: Optional[str] = Field(None, description="Optional topic ID.")
    subtopic_id: Optional[str] = Field(None, description="Optional subtopic ID.")
    lesson_mode: str = Field("conceptual", description="Mode: 'conceptual', 'simplified', 'real_world', 'practice', 'doubt_clearing'.")


class LessonMessageRequest(BaseModel):
    """Student response or query inside an active lesson."""

    message: str = Field(..., min_length=1, max_length=2000, description="Student input message.")


class LessonSessionResponse(BaseModel):
    """Active lesson session state."""

    id: str
    student_id: str
    subject_id: str
    chapter_id: str
    topic_id: Optional[str] = None
    subtopic_id: Optional[str] = None
    lesson_mode: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    status: str
    started_at: str
    updated_at: str
    completed_at: Optional[str] = None


class BookmarkToggleRequest(BaseModel):
    """Bookmark toggle request."""

    entity_type: str = Field(..., description="'chapter', 'topic', 'resource', 'question'.")
    entity_id: str = Field(..., description="Identifier of the bookmarked entity.")
    note: Optional[str] = Field(None, max_length=500, description="Optional note.")


class BookmarkResponse(BaseModel):
    """Bookmark toggle result."""

    action: str = Field(..., description="'created' or 'removed'.")
    entity_type: str
    entity_id: str
    note: Optional[str] = None
    id: Optional[str] = None


class CurriculumSearchResponse(BaseModel):
    """Curriculum search response."""

    query: str
    chapters: List[Dict[str, Any]]
    topics: List[Dict[str, Any]]
    total_matches: int


# ==============================================================================
# Agent Arena & Multi-Agent Discovery Schemas
# ==============================================================================

class AgentMetadataResponse(BaseModel):
    """Rich metadata and runtime execution state of a canonical CrewAI agent."""

    id: str = Field(..., description="Canonical agent identifier.")
    name: str = Field(..., description="Full display name of the agent.")
    title: str = Field(..., description="Descriptive pedagogical title.")
    role: str = Field(..., description="Role extracted directly from CrewAI Agent definition.")
    goal: str = Field(..., description="Goal extracted directly from CrewAI Agent definition.")
    backstory: str = Field(..., description="Backstory extracted directly from CrewAI Agent definition.")
    model: str = Field(default="ollama/qwen2.5:3b", description="Model configuration.")
    llm_provider: str = Field(default="ollama", description="Local LLM provider.")
    temperature: float = Field(default=0.3, description="LLM sampling temperature.")
    phase: str = Field(default="Phase 1B", description="Development milestone phase.")
    status: str = Field(default="idle", description="Current runtime state: 'idle', 'running', 'completed', 'error'.")
    registration_status: str = Field(default="registered", description="Registration status: 'registered' or 'error'.")
    associated_workflows: List[str] = Field(default_factory=list, description="Approved workflows involving this agent.")
    total_executions: int = Field(default=0, description="Total executions since server startup.")
    last_execution_time: Optional[str] = Field(None, description="ISO timestamp of last execution.")
    last_duration_seconds: Optional[float] = Field(None, description="Duration of last execution in seconds.")
    last_workflow: Optional[str] = Field(None, description="Last workflow executed by this agent.")
    last_error: Optional[str] = Field(None, description="Last error message if in error state.")


class ArenaStatusResponse(BaseModel):
    """System health and Agent Arena overview."""

    total_agents: int = Field(..., description="Total canonical agents (8).")
    registered_agents: int = Field(..., description="Number of successfully registered agents.")
    running_agents: int = Field(..., description="Number of agents currently executing.")
    idle_agents: int = Field(..., description="Number of idle / ready agents.")
    error_agents: int = Field(..., description="Number of agents in error state.")
    model: str = Field(..., description="Default local LLM model.")
    provider: str = Field(..., description="Inference engine provider.")
    base_url: str = Field(..., description="Ollama API endpoint.")
    status: str = Field(..., description="'healthy' or 'degraded'.")
    canonical_roster: List[str] = Field(default_factory=list, description="Names of all canonical agents.")


class WorkflowDescriptorResponse(BaseModel):
    """Approved workflow definition from central registry."""

    workflow_id: str
    name: str
    description: str
    agents: List[str]
    requires_auth: bool


# ==============================================================================
# Phase 10: Honest System Health & Component Verification Schemas
# ==============================================================================

class ComponentHealthItem(BaseModel):
    """Granular health, lifecycle, and verification state of a system component."""

    name: str = Field(..., description="Canonical component name.")
    status: str = Field(..., description="Component status (e.g. 'available', 'running', 'connected', 'verified').")
    configured: bool = Field(..., description="Whether the component is configured.")
    registered: bool = Field(..., description="Whether the component is registered.")
    available: bool = Field(..., description="Whether the component is available / online.")
    executed: bool = Field(..., description="Whether the component has been executed in the runtime.")
    verified: bool = Field(..., description="Whether the component behavior has been verified.")
    details: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic, version, and telemetry metadata.")


class SystemHealthResponse(BaseModel):
    """Honest and granular system health overview across all 11 core tiers."""

    overall_status: str = Field(..., description="Overall system status ('healthy', 'degraded', or 'offline').")
    timestamp: str = Field(..., description="ISO 8601 evaluation timestamp.")
    components: Dict[str, ComponentHealthItem] = Field(..., description="Health status breakdown per component.")
    summary: Dict[str, Any] = Field(..., description="High-level operational metrics.")


# ==============================================================================
# Phase Pre-0 2.0 Schemas: Diagnostic Assessment (25q), Practice Sets (60q),
# Multi-Difficulty Distribution, and Enhanced Progress Reporting
# ==============================================================================

class DiagnosticQuestionItem(BaseModel):
    """Single diagnostic question item with full curriculum metadata and rubric."""
    id: str = Field(..., description="Unique question ID, e.g. diag_q1")
    subject_id: Optional[str] = None
    chapter_id: Optional[str] = None
    topic_id: Optional[str] = None
    topic: str = Field(..., description="Topic or concept assessed.")
    learning_objective_id: Optional[str] = None
    difficulty: str = Field("medium", description="'basic', 'medium', or 'hard'")
    question_type: str = Field(..., description="'mcq', 'true_false', 'fill_blank', 'short_answer', 'conceptual', 'numerical', 'assertion_reason', 'case_based'")
    question: str = Field(..., description="The question text.")
    options: List[str] = Field(default_factory=list, description="Options for MCQ/TF/Assertion.")
    marks: int = Field(default=1, ge=1, le=5)
    expected_answer: Optional[str] = Field(None, description="Model answer or key.")
    marking_rubric: Optional[str] = Field(None, description="Rubric criteria.")
    explanation: Optional[str] = Field(None, description="Pedagogical explanation.")
    source_reference: Optional[str] = Field(None, description="NCERT textbook citation.")


class DiagnosticAssessmentGenerateRequest(BaseModel):
    """Request to generate a comprehensive 20-30 question chapter diagnostic assessment."""
    student_id: Optional[str] = None
    grade: str = Field(default="Class 10")
    subject: str = Field(default="Science")
    chapter: str = Field(..., description="Chapter title, e.g. 'Electricity' or 'Chemical Reactions and Equations'")
    chapter_id: Optional[str] = None
    topics: Optional[List[str]] = Field(None, description="Specific topics or None for all chapter topics.")
    prerequisite_topics: Optional[List[str]] = None
    num_questions: int = Field(default=25, ge=10, le=35, description="Target question count (default 25).")
    question_formats: Optional[List[str]] = None


class DiagnosticAssessmentGenerateResponse(BaseModel):
    """Response containing generated diagnostic assessment."""
    assessment_id: str
    student_id: Optional[str] = None
    grade: str
    subject: str
    chapter: str
    target_topics: List[str]
    total_questions: int
    questions: List[DiagnosticQuestionItem]
    duration_ms: float
    is_cached: bool = False


class DiagnosticEvaluateRequest(BaseModel):
    """Request to evaluate submitted diagnostic answers."""
    assessment_id: str
    student_id: Optional[str] = None
    subject: str
    chapter: str
    answers: Dict[str, str] = Field(..., description="Mapping of question ID to student's answer text.")


class TopicDiagnosticResult(BaseModel):
    """Topic-wise diagnostic breakdown."""
    topic: str
    total_questions: int
    correct_count: int
    partially_correct_count: int
    incorrect_count: int
    score: float
    max_marks: float
    percentage: float
    mastery_status: str = Field(default="in_progress", description="'mastered', 'in_progress', 'needs_revision', 'prerequisite_gap'")
    misconceptions: List[str] = Field(default_factory=list)
    knowledge_gaps: List[str] = Field(default_factory=list)


class FullDiagnosticReportResponse(BaseModel):
    """Comprehensive persistent diagnostic report."""
    report_id: str
    assessment_id: str
    student_id: Optional[str] = None
    subject: str
    chapter: str
    total_questions: int
    correct_answers: int
    partially_correct_answers: int
    incorrect_answers: int
    total_score: float
    max_marks: float
    percentage: float
    overall_classification: str
    topic_results: List[TopicDiagnosticResult]
    demonstrated_understanding: List[str]
    evidenced_knowledge_gaps: List[str]
    uncovered_misconceptions: List[str]
    prerequisite_gaps: List[str]
    recommended_remediation: List[str]
    recommended_focus_topics: List[str]
    adaptive_probes_recommended: bool
    overall_summary: str
    duration_ms: float
    persisted: bool = True


class AdaptiveProbeRequest(BaseModel):
    """Request to generate adaptive follow-up questions for a weak topic."""
    student_id: Optional[str] = None
    subject: str
    chapter: str
    weak_topic: str
    previous_misconception: Optional[str] = None
    num_probes: int = Field(default=3, ge=2, le=5)


class PracticeQuestionItem(BaseModel):
    """Standardized practice question with full metadata."""
    id: str
    subject_id: Optional[str] = None
    chapter_id: Optional[str] = None
    topic_id: Optional[str] = None
    topic: str
    learning_objective_id: Optional[str] = None
    difficulty: str = Field(default="basic", description="'basic', 'medium', or 'hard'")
    question_type: str = Field(default="mcq", description="'mcq', 'true_false', 'fill_blank', 'short_answer', 'long_answer', 'numerical', 'conceptual', 'assertion_reason', 'case_based', 'application'")
    question: str
    options: List[str] = Field(default_factory=list)
    marks: int = Field(default=1)
    expected_answer: Optional[str] = None
    marking_rubric: Optional[str] = None
    explanation: Optional[str] = None
    source_reference: Optional[str] = None


class ChapterPracticeSetRequest(BaseModel):
    """Request for chapter practice questions with selectable difficulty tiers."""
    student_id: Optional[str] = None
    grade: str = Field(default="Class 10")
    subject: str = Field(default="Science")
    chapter: str
    topic: Optional[str] = None
    difficulty_tier: str = Field(default="all", description="'basic' (30 q), 'medium' (20 q), 'hard' (10 q), or 'all' (60 q)")
    question_types: Optional[List[str]] = None


class ChapterPracticeSetResponse(BaseModel):
    """Response containing practice questions according to requested tier."""
    practice_set_id: str
    student_id: Optional[str] = None
    grade: str
    subject: str
    chapter: str
    difficulty_tier: str
    total_questions: int
    basic_count: int
    medium_count: int
    hard_count: int
    questions: List[PracticeQuestionItem]
    duration_ms: float
    is_cached: bool = False


class SavePracticeSessionRequest(BaseModel):
    """Save in-progress practice session."""
    session_id: str
    student_id: Optional[str] = None
    practice_set_id: str
    chapter: str
    answers: Dict[str, str] = Field(default_factory=dict)
    current_index: int = 0
    time_spent_seconds: int = 0


class SavePracticeSessionResponse(BaseModel):
    session_id: str
    status: str
    saved_at: str


class SubjectProgressItem(BaseModel):
    subject: str
    quizzes_taken: int
    average_score: Optional[float]
    topics_mastered: int
    topics_in_progress: int
    topics_needing_revision: int


class ChapterCompletionItem(BaseModel):
    chapter_id: str
    title: str
    subject: str
    status: str = Field(default="not_started", description="'not_started', 'in_progress', 'completed'")
    mastery_percentage: float = 0.0
    objectives_completed: int = 0
    total_objectives: int = 0


class ComprehensiveProgressDashboardResponse(BaseModel):
    """Complete multi-tier progress analytics dashboard."""
    student_id: str
    student_name: str
    grade: str
    has_sufficient_history: bool
    overall_accuracy: Optional[float]
    total_assessments: int
    total_questions_answered: int
    performance_trend: str
    trend_description: str
    subject_progress: List[SubjectProgressItem]
    chapter_completion: List[ChapterCompletionItem]
    topic_mastery: List[TopicObservation]
    strengths: List[str]
    weaknesses: List[str]
    recent_attempts: List[AssessmentHistoryItem]
    recommended_priorities: List[str]
    empty_state_guide: Optional[str] = None
    duration_ms: float


