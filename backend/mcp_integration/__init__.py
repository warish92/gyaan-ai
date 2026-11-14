"""Gyaan AI - Model Context Protocol (MCP) Package.

Exports schemas, client manager, CrewAI tool adapters, security utilities,
and FastAPI router for Model Context Protocol (MCP) integration.
"""

from backend.mcp_integration.client import MCPClient, MCPClientManager, mcp_manager
from backend.mcp_integration.schemas import (
    MCPExecutionError,
    MCPExecutionMetadata,
    MCPResearchWorkflowRequest,
    MCPResearchWorkflowResponse,
    MCPSourceReference,
    MCPToolRequest,
    MCPToolResponse,
)
from backend.mcp_integration.security import (
    APPROVED_MCP_TOOLS,
    APPROVED_RESOURCES_DIR,
    MCPSecurityError,
    sanitize_and_check_injection,
    validate_and_resolve_resource_path,
    validate_tool_name,
)
from backend.mcp_integration.service import mcp_router
from backend.mcp_integration.tools import MCPFilesystemTool, MCPWebSearchTool

__all__ = [
    "MCPClientManager",
    "mcp_manager",
    "MCPToolRequest",
    "MCPToolResponse",
    "MCPExecutionMetadata",
    "MCPSourceReference",
    "MCPExecutionError",
    "MCPResearchWorkflowRequest",
    "MCPResearchWorkflowResponse",
    "MCPWebSearchTool",
    "MCPFilesystemTool",
    "mcp_router",
    "MCPSecurityError",
    "validate_tool_name",
    "validate_and_resolve_resource_path",
    "sanitize_and_check_injection",
    "APPROVED_MCP_TOOLS",
    "APPROVED_RESOURCES_DIR",
]
