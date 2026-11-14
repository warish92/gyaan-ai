"""Gyaan AI - A2A Protocol Pydantic Message Contracts.

Defines the application-level data schemas exchanged across the Agent-to-Agent (A2A)
protocol boundary between the CrewAI architecture and the Google ADK architecture.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AgentExecutionMetadata(BaseModel):
    """Execution telemetry and provenance for the agent handling an A2A task."""
    model_config = ConfigDict(extra="ignore")

    agent_name: str = Field(..., description="Name of the executing agent")
    framework: str = Field(..., description="Framework powering the agent: crewai or google-adk")
    duration_ms: float = Field(..., ge=0.0, description="Execution duration in milliseconds")
    model_name: str = Field(..., description="LLM model identifier used for inference")
    execution_mode: str = Field(default="live", description="live, deterministic, or simulated")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of execution"
    )


class LearningAnalysisArtifact(BaseModel):
    """Structured learning intelligence artifact produced by the ADK Learning Intelligence Agent."""
    model_config = ConfigDict(extra="ignore")

    artifact_id: str = Field(..., description="Unique artifact identifier")
    name: str = Field(default="learning_analysis_report", description="Descriptive artifact name")
    summary: str = Field(..., description="Executive summary of student conceptual mastery and readiness")
    identified_patterns: List[str] = Field(
        default_factory=list,
        description="Empirical patterns detected across student diagnostic and assessment attempts"
    )
    recurring_misconceptions: List[str] = Field(
        default_factory=list,
        description="Identified misconceptions substantiated by direct student evidence"
    )
    topic_level_weaknesses: List[str] = Field(
        default_factory=list,
        description="Topic-level concept gaps requiring pedagogical intervention"
    )
    learning_priorities: List[str] = Field(
        default_factory=list,
        description="Ranked educational priorities for remedial or advanced guidance"
    )
    evidence_references: List[str] = Field(
        default_factory=list,
        description="Citations of specific student responses or quiz items supporting the findings"
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence score for the synthesized learning intelligence"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Actionable pedagogical recommendations for teacher/mentor agents"
    )


class A2ATaskMetadata(BaseModel):
    """Metadata tracking an A2A task's lifecycle, state transitions, and provenance."""
    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(..., description="Unique A2A task identifier")
    context_id: str = Field(..., description="A2A conversation or session context identifier")
    correlation_id: str = Field(..., description="Traceability correlation ID across agent frameworks")
    state: str = Field(..., description="Task state: submitted, working, completed, failed, or canceled")
    source_agent: str = Field(default="orchestrator", description="Agent initiating the A2A request")
    target_agent: str = Field(default="learning_intelligence_agent", description="Agent executing the task")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC creation timestamp"
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC last update timestamp"
    )


class LearningAnalysisA2ARequest(BaseModel):
    """Application-level request payload sent from CrewAI Orchestrator to ADK A2A Server."""
    model_config = ConfigDict(extra="ignore")

    student_id: str = Field(..., min_length=1, max_length=100, description="Canonical student identifier")
    session_id: str = Field(..., min_length=1, max_length=100, description="Active student session identifier")
    chapter_id: Optional[str] = Field(None, max_length=100, description="Curriculum chapter code (e.g. ch_chem_01)")
    topic_id: Optional[str] = Field(None, max_length=100, description="Curriculum topic code (e.g. topic_chem_01_01)")
    learning_objectives: List[str] = Field(
        default_factory=list,
        description="Target educational learning objectives"
    )
    diagnostic_evidence: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Structured diagnostic assessment responses and misconception flags"
    )
    assessment_evidence: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Structured practice quiz results, scores, and item-level evaluations"
    )
    correlation_id: str = Field(
        ...,
        description="Unique cross-system correlation identifier for tracing"
    )


class LearningAnalysisA2AResponse(BaseModel):
    """Application-level response payload returned across the A2A protocol boundary."""
    model_config = ConfigDict(extra="ignore")

    correlation_id: str = Field(..., description="Correlating request identifier")
    task_id: str = Field(..., description="A2A task identifier")
    execution_status: str = Field(..., description="Task execution status (completed, failed, etc.)")
    artifact: Optional[LearningAnalysisArtifact] = Field(
        None,
        description="Structured learning intelligence artifact when completed"
    )
    agent_metadata: AgentExecutionMetadata = Field(
        ...,
        description="Executing agent telemetry and model provenance"
    )


class A2AErrorResponse(BaseModel):
    """Standardized error contract for protocol-level and application-level failures."""
    model_config = ConfigDict(extra="ignore")

    error_code: str = Field(..., description="Machine-readable error classification code")
    message: str = Field(..., description="Human-readable explanation of failure")
    correlation_id: Optional[str] = Field(None, description="Request correlation identifier if known")
    retryable: bool = Field(default=False, description="Whether the request may be retried")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional debugging context")
