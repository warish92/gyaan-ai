"""Gyaan AI - MCP Client & Session Manager.

Manages connections, tool discovery, and execution lifecycles for Model Context
Protocol (MCP) servers using the official Python MCP SDK over cross-process stdio.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional
import uuid

from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.types import Tool

from backend.mcp_integration.schemas import (
    MCPExecutionError,
    MCPExecutionMetadata,
    MCPSourceReference,
    MCPToolRequest,
    MCPToolResponse,
)
from backend.mcp_integration.security import (
    MCPSecurityError,
    sanitize_and_check_injection,
    validate_tool_name,
)

logger = logging.getLogger("gyaan_ai.mcp.client")

# Paths to the two genuine MCP servers
SERVERS_DIR = Path(__file__).resolve().parent / "servers"
WEB_SEARCH_SERVER_SCRIPT = str(SERVERS_DIR / "web_search_server.py")
FILESYSTEM_SERVER_SCRIPT = str(SERVERS_DIR / "filesystem_server.py")


class MCPClientManager:
    """Manages official MCP client sessions and tool execution across MCP servers."""

    def __init__(self, default_timeout: float = 30.0, max_retries: int = 1) -> None:
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.server_registry = {
            "web_search": WEB_SEARCH_SERVER_SCRIPT,
            "filesystem": FILESYSTEM_SERVER_SCRIPT,
        }
        self.tool_to_server = {
            "search_educational_web": "web_search",
            "list_educational_resources": "filesystem",
            "read_educational_resource": "filesystem",
        }

    def _get_server_params(
        self,
        server_name: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> StdioServerParameters:
        """Constructs StdioServerParameters for launching the specified MCP server."""
        script_path = self.server_registry.get(server_name)
        if not script_path or not os.path.exists(script_path):
            raise FileNotFoundError(f"MCP server script for '{server_name}' not found: {script_path}")

        env = os.environ.copy()
        # Ensure PYTHONPATH includes project root
        project_root = str(Path(__file__).resolve().parent.parent.parent)
        pythonpath = env.get("PYTHONPATH", "")
        if project_root not in pythonpath:
            env["PYTHONPATH"] = f"{project_root};{pythonpath}" if pythonpath else project_root

        # Subprocess distributed trace propagation
        if trace_id:
            env["GYAAN_TRACE_ID"] = trace_id
        if span_id:
            env["GYAAN_PARENT_SPAN_ID"] = span_id
        if correlation_id:
            env["GYAAN_CORRELATION_ID"] = correlation_id

        return StdioServerParameters(
            command=sys.executable,
            args=[script_path],
            env=env,
        )

    async def discover_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Connects to an MCP server, performs protocol initialization, and lists tools."""
        server_params = self._get_server_params(server_name)
        logger.info("Connecting to MCP server '%s' for tool discovery...", server_name)

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                logger.info(
                    "MCP Server '%s' initialized (name=%s, version=%s, protocol=%s)",
                    server_name,
                    init_result.serverInfo.name,
                    init_result.serverInfo.version,
                    getattr(init_result, "protocolVersion", "2025-11-25"),
                )

                tools_response = await session.list_tools()
                discovered: List[Dict[str, Any]] = []
                for tool in tools_response.tools:
                    discovered.append({
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
                        "server_name": server_name,
                    })

                logger.info("Discovered %d tools on MCP server '%s': %s", len(discovered), server_name, [d["name"] for d in discovered])
                return discovered

    async def discover_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Discovers tools across all registered MCP servers."""
        all_tools: Dict[str, List[Dict[str, Any]]] = {}
        for server_name in self.server_registry:
            try:
                all_tools[server_name] = await self.discover_tools(server_name)
            except Exception as exc:
                logger.error("Failed to discover tools from MCP server '%s': %s", server_name, exc)
                all_tools[server_name] = []
        return all_tools

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        server_name: Optional[str] = None,
        calling_agent: str = "Resource Agent",
        correlation_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> MCPToolResponse:
        """Executes an MCP tool via the official MCP client interface over stdio."""
        start_time = time.perf_counter()
        req_id = f"mcp_req_{uuid.uuid4().hex[:10]}"
        corr_id = correlation_id or f"corr_mcp_{uuid.uuid4().hex[:8]}"
        exec_timeout = timeout or self.default_timeout

        # 1. Resolve server name
        resolved_server = server_name or self.tool_to_server.get(tool_name)
        if not resolved_server:
            raise ValueError(f"Unknown MCP tool '{tool_name}': cannot resolve target server")

        # 2. Security validation
        validate_tool_name(tool_name)

        from backend.observability import trace_scope
        with trace_scope(
            name=f"mcp_tool:{tool_name}",
            span_type="mcp",
            agent_name=calling_agent,
            input_data=arguments,
            metadata={"server": resolved_server, "correlation_id": corr_id},
        ) as mcp_span:
            # Propagate trace context to subprocess environment and tool arguments
            server_params = self._get_server_params(
                resolved_server,
                trace_id=mcp_span.trace_id,
                span_id=mcp_span.span_id,
                correlation_id=corr_id,
            )
            tool_args = dict(arguments)
            tool_args["trace_context"] = {
                "trace_id": mcp_span.trace_id,
                "parent_span_id": mcp_span.span_id,
                "correlation_id": corr_id,
            }

            for attempt in range(self.max_retries + 1):
                try:
                    logger.info(
                        "Executing MCP tool '%s' on server '%s' (attempt %d/%d, correlation=%s)",
                        tool_name,
                        resolved_server,
                        attempt + 1,
                        self.max_retries + 1,
                        corr_id,
                    )

                    async with stdio_client(server_params) as (read_stream, write_stream):
                        async with ClientSession(read_stream, write_stream) as session:
                            await session.initialize()

                            # Execute tool with bounded timeout
                            call_result = await asyncio.wait_for(
                                session.call_tool(tool_name, arguments=tool_args),
                                timeout=exec_timeout,
                            )

                            duration_ms = (time.perf_counter() - start_time) * 1000.0

                            # Parse content blocks from CallToolResult
                            parsed_output: Dict[str, Any] = {}
                            sources: List[MCPSourceReference] = []

                            for content_block in call_result.content:
                                if hasattr(content_block, "text") and content_block.text:
                                    text_data = content_block.text
                                    try:
                                        json_data = json.loads(text_data)
                                        if isinstance(json_data, dict):
                                            parsed_output.update(json_data)
                                        elif isinstance(json_data, list):
                                            parsed_output["data"] = json_data
                                        else:
                                            parsed_output["text"] = str(json_data)
                                    except Exception:
                                        parsed_output["raw_text"] = text_data

                            # Extract sources if present
                            if "results" in parsed_output and isinstance(parsed_output["results"], list):
                                for idx, item in enumerate(parsed_output["results"]):
                                    sources.append(
                                        MCPSourceReference(
                                            source_id=f"src_web_{idx+1}",
                                            title=item.get("title", f"Web Search Result {idx+1}"),
                                            url=item.get("url"),
                                            publisher_or_corpus=item.get("source_provider", "Web Search Index"),
                                            snippet=item.get("snippet", ""),
                                            relevance_score=0.90,
                                        )
                                    )
                            elif "file_name" in parsed_output:
                                sources.append(
                                    MCPSourceReference(
                                        source_id=f"src_fs_01",
                                        title=parsed_output.get("file_name", "Educational Resource"),
                                        file_path=parsed_output.get("relative_path"),
                                        publisher_or_corpus=parsed_output.get("provenance", "NCERT Resource Repository"),
                                        snippet=f"Local document: {parsed_output.get('file_name')} ({parsed_output.get('size_bytes', 0)} bytes)",
                                        relevance_score=1.0,
                                    )
                                )

                            status_str = "failed" if call_result.isError else "success"
                            error_obj = None
                            if call_result.isError:
                                error_obj = MCPExecutionError(
                                    error_code="TOOL_REPORTED_ERROR",
                                    message=str(parsed_output.get("message", "Tool execution failed")),
                                    tool_name=tool_name,
                                    server_name=resolved_server,
                                )

                            meta = MCPExecutionMetadata(
                                tool_name=tool_name,
                                server_name=resolved_server,
                                calling_agent=calling_agent,
                                correlation_id=corr_id,
                                execution_duration_ms=duration_ms,
                                protocol_version="2025-11-25",
                                transport="stdio",
                            )

                            logger.info(
                                "MCP Tool '%s' executed successfully in %.2fms (sources=%d)",
                                tool_name,
                                duration_ms,
                                len(sources),
                            )

                            mcp_span.output_data = {
                                "status": status_str,
                                "duration_ms": duration_ms,
                                "sources_count": len(sources),
                                "server_correlation_id": parsed_output.get("correlation_id"),
                                "server_trace_id": parsed_output.get("trace_id"),
                            }
                            if call_result.isError:
                                mcp_span.status = "failed"
                                mcp_span.error = str(parsed_output.get("message"))

                            return MCPToolResponse(
                                request_id=req_id,
                                correlation_id=corr_id,
                                execution_status=status_str,
                                validated_output=parsed_output,
                                sources=sources,
                                metadata=meta,
                                error=error_obj,
                            )

                except (asyncio.TimeoutError, TimeoutError):
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    err_msg = f"MCP tool execution timed out after {exec_timeout} seconds"
                    logger.warning(err_msg)
                    last_error = asyncio.TimeoutError(err_msg)
                except Exception as exc:
                    elapsed = time.perf_counter() - start_time
                    duration_ms = elapsed * 1000.0
                    sub_exceptions = getattr(exc, "exceptions", [])
                    is_timeout = (
                        elapsed >= exec_timeout
                        or "timeout" in str(exc).lower()
                        or any(
                            "timeout" in str(e).lower()
                            or "brokenresource" in type(e).__name__.lower()
                            or isinstance(e, (asyncio.TimeoutError, TimeoutError, asyncio.CancelledError))
                            for e in sub_exceptions
                        )
                    )
                    if is_timeout:
                        err_msg = f"MCP tool execution timed out after {exec_timeout} seconds"
                        logger.warning(err_msg)
                        last_error = asyncio.TimeoutError(err_msg)
                    else:
                        logger.warning("MCP tool execution attempt %d error: %s", attempt + 1, exc)
                        last_error = exc

                if attempt < self.max_retries:
                    await asyncio.sleep(0.5)

            # Retries exhausted
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            meta = MCPExecutionMetadata(
                tool_name=tool_name,
                server_name=resolved_server,
                calling_agent=calling_agent,
                correlation_id=corr_id,
                execution_duration_ms=duration_ms,
            )
            is_timeout_err = isinstance(last_error, (asyncio.TimeoutError, TimeoutError)) or "timeout" in str(last_error).lower()
            error_code = "TIMEOUT" if is_timeout_err else "EXECUTION_FAILED"
            error_msg = f"MCP tool execution timed out after {exec_timeout} seconds" if is_timeout_err else str(last_error)

            mcp_span.status = "failed"
            mcp_span.error = error_msg
            mcp_span.output_data = {"error": error_msg}

            return MCPToolResponse(
                request_id=req_id,
                correlation_id=corr_id,
                execution_status="failed",
                validated_output={"error": error_msg},
                sources=[],
                metadata=meta,
                error=MCPExecutionError(
                    error_code=error_code,
                    message=error_msg,
                    tool_name=tool_name,
                    server_name=resolved_server,
                    retryable=False,
                ),
            )

    def execute_tool_sync(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        server_name: Optional[str] = None,
        calling_agent: str = "Resource Agent",
        correlation_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> MCPToolResponse:
        """Synchronous helper for CrewAI tool invocation contexts."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    self.execute_tool(
                        tool_name=tool_name,
                        arguments=arguments,
                        server_name=server_name,
                        calling_agent=calling_agent,
                        correlation_id=correlation_id,
                        timeout=timeout,
                    ),
                ).result()
        else:
            return loop.run_until_complete(
                self.execute_tool(
                    tool_name=tool_name,
                    arguments=arguments,
                    server_name=server_name,
                    calling_agent=calling_agent,
                    correlation_id=correlation_id,
                    timeout=timeout,
                )
            )


# Global singleton instance and alias
mcp_manager = MCPClientManager()
MCPClient = MCPClientManager
