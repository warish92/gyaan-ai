"""Gyaan AI - CrewAI Tool Adapters for Model Context Protocol (MCP).

Provides official CrewAI BaseTool subclasses wrapping Model Context Protocol (MCP)
tools, allowing the Resource Agent, Teacher Agent, and other CrewAI agents to invoke
genuine external MCP tools seamlessly within CrewAI workflows.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field

from crewai.tools import BaseTool
from backend.mcp_integration.client import mcp_manager
from backend.mcp_integration.schemas import MCPToolResponse

logger = logging.getLogger("gyaan_ai.mcp.tools")


# --- Tool 1: MCP Web Search Tool Input Schema ---
class MCPWebSearchInput(BaseModel):
    """Input parameters for MCP Web Search tool."""
    query: str = Field(..., description="Educational concept, keyword, or query to research")
    subject: str = Field(default="Science", description="Academic subject (e.g. Science, Mathematics)")
    grade: str = Field(default="Class 10", description="Grade level (e.g. Class 10)")
    max_results: int = Field(default=3, description="Maximum number of search results to return (1-5)")


class MCPWebSearchTool(BaseTool):
    """CrewAI tool providing external web search capabilities via Model Context Protocol (MCP)."""

    name: str = "mcp_educational_web_search"
    description: str = (
        "Search the web for educational resources, scientific explanations, or curriculum references "
        "relevant to CBSE Class 10 subjects through the Model Context Protocol (MCP). "
        "Returns verified titles, academic snippets, and source URLs."
    )
    args_schema: Type[BaseModel] = MCPWebSearchInput

    def _run(
        self,
        query: str,
        subject: str = "Science",
        grade: str = "Class 10",
        max_results: int = 3,
    ) -> str:
        """Synchronously execute the MCP Web Search tool."""
        logger.info("CrewAI Agent invoked MCPWebSearchTool for query: '%s'", query)
        resp: MCPToolResponse = mcp_manager.execute_tool_sync(
            tool_name="search_educational_web",
            arguments={"query": query, "subject": subject, "grade": grade, "max_results": max_results},
            calling_agent="Resource Agent",
        )

        if resp.execution_status == "failed":
            return f"MCP Web Search error: {resp.error.message if resp.error else 'Tool execution failed'}"

        results = resp.validated_output.get("results", [])
        if not results:
            return f"No external search results found for '{query}'."

        formatted_lines = [
            f"### MCP Educational Web Search Results for '{query}' (Protocol: MCP v{resp.metadata.protocol_version}):",
            f"Execution Duration: {resp.metadata.execution_duration_ms:.2f}ms | Sources Found: {len(results)}\n",
        ]
        for idx, r in enumerate(results, start=1):
            formatted_lines.append(
                f"{idx}. **Title**: {r.get('title')}\n"
                f"   **Source**: {r.get('source_provider', 'Web Search')}\n"
                f"   **URL**: {r.get('url')}\n"
                f"   **Excerpt**: {r.get('snippet')}\n"
            )

        return "\n".join(formatted_lines)


# --- Tool 2: MCP Filesystem Tool Input Schema ---
class MCPFilesystemInput(BaseModel):
    """Input parameters for MCP Filesystem tool."""
    action: str = Field(..., description="Action to perform: 'list' (list available materials) or 'read' (read document)")
    file_name: Optional[str] = Field(None, description="Name of the file to read (required if action='read')")
    sub_directory: Optional[str] = Field(default="", description="Optional sub-directory within approved repository")


class MCPFilesystemTool(BaseTool):
    """CrewAI tool providing sandboxed access to approved educational materials via Model Context Protocol (MCP)."""

    name: str = "mcp_educational_filesystem"
    description: str = (
        "Inspect and read approved CBSE Class 10 educational textbooks, JSON corpora, and study documents "
        "stored in the sandboxed educational repository via the Model Context Protocol (MCP). "
        "Strictly read-only and protected against directory traversal."
    )
    args_schema: Type[BaseModel] = MCPFilesystemInput

    def _run(
        self,
        action: str,
        file_name: Optional[str] = None,
        sub_directory: Optional[str] = "",
    ) -> str:
        """Synchronously execute the MCP Filesystem tool."""
        logger.info("CrewAI Agent invoked MCPFilesystemTool (action=%s, file=%s)", action, file_name)

        if action.lower() == "list":
            resp = mcp_manager.execute_tool_sync(
                tool_name="list_educational_resources",
                arguments={"sub_directory": sub_directory or ""},
                calling_agent="Resource Agent",
            )
            if resp.execution_status == "failed" or resp.validated_output.get("status") == "error":
                return f"MCP Filesystem error: {resp.validated_output.get('message', 'Failed to list resources')}"

            files = resp.validated_output.get("files", [])
            lines = [
                f"### Approved Educational Resources (MCP Filesystem, duration={resp.metadata.execution_duration_ms:.2f}ms):",
                f"Total Available Documents: {len(files)}\n",
            ]
            for f in files:
                lines.append(f"- **{f.get('file_name')}** ({f.get('size_bytes')} bytes, format: {f.get('extension')})")
            return "\n".join(lines)

        elif action.lower() == "read":
            if not file_name:
                return "Error: 'file_name' is required when action='read'."

            resp = mcp_manager.execute_tool_sync(
                tool_name="read_educational_resource",
                arguments={"file_name": file_name},
                calling_agent="Resource Agent",
            )
            if resp.execution_status == "failed" or resp.validated_output.get("status") == "error":
                return f"MCP Filesystem error: {resp.validated_output.get('message', 'Failed to read resource')}"

            content = resp.validated_output.get("content")
            size = resp.validated_output.get("size_bytes", 0)
            provenance = resp.validated_output.get("provenance", "NCERT Repository")

            content_str = json.dumps(content, indent=2) if isinstance(content, (dict, list)) else str(content)
            # Truncate preview if very large for agent context window
            if len(content_str) > 4000:
                content_str = content_str[:4000] + "\n... [Content truncated for pedagogical focus]"

            return (
                f"### MCP Retrieved Educational Resource: '{file_name}' ({size} bytes):\n"
                f"Provenance: {provenance} | Duration: {resp.metadata.execution_duration_ms:.2f}ms\n\n"
                f"```json\n{content_str}\n```"
            )

        else:
            return f"Error: Unsupported action '{action}'. Valid actions are 'list' or 'read'."
