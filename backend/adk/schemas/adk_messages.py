"""Gyaan AI - Google ADK Pydantic Message Contracts.

Defines validated data structures for the Google ADK Learning Intelligence Agent,
session isolation, structured inputs, and analytical outputs.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class DiagnosticEvidence(BaseModel):
    """Structured diagnostic evidence collected for a student."""

    topic_id: str = Field(..., description="Unique identifier of the topic")
    topic_name: str = Field(..., description="Human-readable topic title")
    probes_evaluated: int = Field(default=0, ge=0, description="Number of diagnostic probes evaluated")
    score: float = Field(default=0.0, ge=0.0, description="Raw score achieved")
    accuracy_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Diagnostic percentage")
    identified_misconceptions: List[str] = Field(
        default_factory=list, description="Specific verified misconceptions demonstrated"
    )
    mastery_status: str = Field(
        default="developing", description="Current status: mastered | developing | struggling"
    )


class AssessmentEvidence(BaseModel):
    """Structured evidence from completed quizzes or practice sets."""

    assessment_type: str = Field(
        default="practice_quiz", description="Assessment category (e.g. diagnostic, practice_set, formative)"
    )
    total_questions: int = Field(..., gt=0, description="Total questions evaluated")
    correct_answers: int = Field(default=0, ge=0, description="Correct questions answered")
    percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Score percentage")
    recurring_errors: List[str] = Field(
        default_factory=list, description="Common error patterns identified during evaluation"
    )
    submitted_at: Optional[str] = Field(
        default=None, description="ISO timestamp of submission"
    )


class TopicPerformance(BaseModel):
    """Student performance metrics for a specific curriculum topic."""

    topic_id: str = Field(..., description="Curriculum topic ID")
    topic_name: str = Field(..., description="Curriculum topic name")
    attempts: int = Field(default=1, ge=0, description="Total attempts or questions completed")
    average_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Average percentage score")
    current_mastery_level: str = Field(
        default="developing", description="Mastery tier: beginner | developing | proficient | mastered"
    )
    struggle_indicators: List[str] = Field(
        default_factory=list, description="Specific topic-level struggle flags"
    )


class LearningIntelligenceRequest(BaseModel):
    """Input payload for the Google ADK Learning Intelligence Agent."""

    student_id: str = Field(..., min_length=1, description="Unique student identifier")
    session_id: Optional[str] = Field(
        default=None, description="Existing ADK session ID; auto-created if omitted"
    )
    chapter_id: str = Field(..., min_length=1, description="Curriculum chapter identifier")
    chapter_name: str = Field(..., min_length=1, description="Curriculum chapter name")
    topic_id: Optional[str] = Field(default=None, description="Optional target topic ID")
    learning_objectives: List[str] = Field(
        default_factory=list, description="Curriculum objectives for reference"
    )
    diagnostic_evidence: Optional[DiagnosticEvidence] = Field(
        default=None, description="Optional diagnostic assessment evidence"
    )
    assessment_evidence: List[AssessmentEvidence] = Field(
        default_factory=list, description="History of recent assessment attempts"
    )
    topic_performances: List[TopicPerformance] = Field(
        default_factory=list, description="Topic-level performance aggregations"
    )
    query: Optional[str] = Field(
        default=None, description="Optional teacher/mentor inquiry or student question"
    )

    @field_validator("student_id")
    @classmethod
    def validate_student_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("student_id cannot be blank")
        return v


class AgentExecutionMetadata(BaseModel):
    """Runtime execution telemetry for the Google ADK agent turn."""

    agent_name: str = "Learning Intelligence Agent"
    agent_framework: str = "Google ADK"
    framework_version: str = "2.14.0"
    model: str = Field(..., description="Active LLM model identifier")
    duration_ms: float = Field(default=0.0, ge=0.0, description="Execution duration in milliseconds")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    invocation_id: Optional[str] = None
    session_id: str = Field(..., description="ADK session identifier")
    student_id: str = Field(..., description="Student associated with this execution")


class LearningIntelligenceResponse(BaseModel):
    """Validated output structure produced by the Google ADK Learning Intelligence Agent."""

    student_id: str
    session_id: str
    chapter_id: str
    chapter_name: str
    topic_id: Optional[str] = None
    execution_status: str = Field(
        default="success", description="Status of analytical run: success | partial | error"
    )
    summary: str = Field(
        ..., description="Executive synthesis of student learning intelligence findings"
    )
    identified_patterns: List[str] = Field(
        default_factory=list, description="Cognitive and conceptual patterns identified"
    )
    recurring_misconceptions: List[str] = Field(
        default_factory=list, description="Persistent misconceptions extracted from evidence"
    )
    topic_level_weaknesses: List[str] = Field(
        default_factory=list, description="Topics requiring remedial focus"
    )
    learning_priorities: List[str] = Field(
        default_factory=list, description="Ranked evidence-based learning sequence"
    )
    evidence_references: List[str] = Field(
        default_factory=list, description="Concrete citations from supplied evidence supporting insights"
    )
    confidence: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Agent confidence score in analytical findings"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Actionable pedagogical recommendations"
    )
    execution_metadata: AgentExecutionMetadata


class ADKHealthResponse(BaseModel):
    """Health check response for the Google ADK subsystem."""

    status: str = "healthy"
    adk_version: str
    framework: str = "Google Agent Development Kit (ADK)"
    model: str
    active_sessions_count: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
