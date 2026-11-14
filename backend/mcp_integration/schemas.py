"""Gyaan AI - Model Context Protocol (MCP) Pydantic v2 Contracts.

Defines the application-level data schemas exchanged across the MCP client-server
boundary, providing strict validation, provenance tracking, and security contracts
for educational tool execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MCPSourceReference(BaseModel):
    """Citation or provenance reference for data retrieved via an MCP tool."""
    model_config = ConfigDict(extra="ignore")

    source_id: str = Field(..., description="Unique identifier for the source")
    title: str = Field(..., description="Title or descriptor of the source")
    url: Optional[str] = Field(None, description="Direct URL if retrieved via Web Search MCP")
    file_path: Optional[str] = Field(None, description="Relative approved file path if retrieved via Filesystem MCP")
    publisher_or_corpus: str = Field(
        default="Verified NCERT Educational Corpus",
        description="Originating educational authority or search provider"
    )
    snippet: str = Field(..., description="Relevant textual excerpt or finding")
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence/relevance score")


class MCPExecutionMetadata(BaseModel):
    """Telemetry and operational metadata for an MCP tool invocation."""
    model_config = ConfigDict(extra="ignore")

    tool_name: str = Field(..., description="Name of the MCP tool executed")
    server_name: str = Field(..., description="Name of the MCP server providing the tool")
    calling_agent: str = Field(default="Resource Agent", description="Agent requesting the MCP tool execution")
    correlation_id: str = Field(..., description="Traceability correlation ID across system layers")
    execution_duration_ms: float = Field(..., ge=0.0, description="Duration of MCP execution in milliseconds")
    protocol_version: str = Field(default="2025-11-25", description="MCP protocol version")
    transport: str = Field(default="stdio", description="MCP transport: stdio, sse, or streamable_http")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of execution"
    )


class MCPExecutionError(BaseModel):
    """Structured error descriptor when an MCP tool invocation fails."""
    model_config = ConfigDict(extra="ignore")

    error_code: str = Field(..., description="Categorical error code (e.g. TIMEOUT, PERMISSION_DENIED)")
    message: str = Field(..., description="Human-readable explanation of failure")
    tool_name: Optional[str] = Field(None, description="Tool that failed")
    server_name: Optional[str] = Field(None, description="Server that reported the error")
    retryable: bool = Field(default=False, description="Whether the operation may be retried")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional diagnostic context")


class MCPToolRequest(BaseModel):
    """Application-level request to execute an MCP tool."""
    model_config = ConfigDict(extra="ignore")

    tool_name: str = Field(..., min_length=1, max_length=100, description="Name of the MCP tool to call")
    server_name: str = Field(..., min_length=1, max_length=100, description="Target MCP server")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool-specific input arguments")
    calling_agent: str = Field(default="Resource Agent", description="Agent requesting tool execution")
    correlation_id: str = Field(..., description="Traceability correlation identifier")
    timeout_seconds: float = Field(default=30.0, gt=0.0, le=120.0, description="Maximum execution timeout")


class MCPToolResponse(BaseModel):
    """Standardized response from an MCP tool execution."""
    model_config = ConfigDict(extra="ignore")

    request_id: str = Field(..., description="Unique request identifier")
    correlation_id: str = Field(..., description="Correlating request identifier")
    execution_status: str = Field(..., description="Status: 'success', 'failed', or 'degraded'")
    validated_output: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured tool response validated against application schema"
    )
    sources: List[MCPSourceReference] = Field(
        default_factory=list,
        description="Extracted provenance references or citations"
    )
    metadata: MCPExecutionMetadata = Field(..., description="Telemetry and execution metadata")
    error: Optional[MCPExecutionError] = Field(None, description="Error details if execution failed")

    @property
    def raw_result(self) -> Dict[str, Any]:
        """Convenience alias for validated_output."""
        return self.validated_output


class MCPResearchWorkflowRequest(BaseModel):
    """Request for the integrated multi-agent research workflow (Orchestrator -> Resource -> MCP -> Teacher)."""
    model_config = ConfigDict(extra="ignore")

    student_query: str = Field(..., min_length=2, max_length=1000, description="Student learning query or topic")
    subject: str = Field(default="Science", description="Academic subject")
    grade: str = Field(default="Class 10", description="Grade level")
    student_id: Optional[str] = Field(default="student_aarav_01", description="Student identifier")
    session_id: Optional[str] = Field(default="sess_mcp_01", description="Session identifier")
    use_web_search: bool = Field(default=True, description="Whether Web Search MCP may be queried")
    use_filesystem: bool = Field(default=True, description="Whether Filesystem MCP may be queried")
    correlation_id: Optional[str] = Field(None, description="Optional cross-system correlation identifier")


class MCPResearchWorkflowResponse(BaseModel):
    """Response from the integrated educational research workflow."""
    model_config = ConfigDict(extra="ignore")

    workflow: str = Field(default="mcp_educational_research")
    status: str = Field(..., description="'completed' or 'failed'")
    student_query: str = Field(..., description="Original student inquiry")
    teacher_explanation: str = Field(..., description="Pedagogical explanation produced by Teacher Agent")
    curated_evidence: Dict[str, Any] = Field(..., description="Evidence compiled by Resource Agent via MCP")
    mcp_tools_used: List[str] = Field(default_factory=list, description="List of MCP tools invoked")
    sources: List[MCPSourceReference] = Field(default_factory=list, description="Verified sources and references")
    correlation_id: str = Field(..., description="Workflow correlation identifier")
    execution_duration_ms: float = Field(..., description="Total workflow duration in milliseconds")
