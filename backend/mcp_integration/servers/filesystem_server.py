"""Gyaan AI - Educational Filesystem FastMCP Server.

Provides a genuine Model Context Protocol (MCP) server exposing sandboxed,
read-only access to approved CBSE/NCERT educational materials.
Prevents directory traversal, blocks unauthorized writes, and strictly confines
access to the approved educational corpus directory (data/resources).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

# Ensure project root is accessible
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.mcp_integration.security import (
    APPROVED_RESOURCES_DIR,
    MAX_FILE_READ_BYTES,
    MCPSecurityError,
    sanitize_and_check_injection,
    validate_and_resolve_resource_path,
)

logger = logging.getLogger("gyaan_ai.mcp.filesystem")

# Initialize FastMCP server
mcp = FastMCP(
    name="gyaan_educational_filesystem",
    instructions="Gyaan AI Educational Filesystem Server: provides read-only access to approved CBSE educational resources.",
)


@mcp.tool(
    name="list_educational_resources",
    description=(
        "List all approved educational materials, NCERT textbook corpora, and curriculum references "
        "stored in the sandboxed resources directory. Returns file names, sizes, and formats."
    ),
)
def list_educational_resources(
    sub_directory: str = "",
    trace_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """List available educational resource files within the approved directory.

    Args:
        sub_directory: Optional sub-folder within approved resources directory (default '').

    Returns:
        Dict[str, Any]: Directory listing with file metadata.
    """
    try:
        target_dir = validate_and_resolve_resource_path(sub_directory)
    except MCPSecurityError as err:
        logger.warning("Security violation in list_educational_resources: %s", err)
        return {
            "status": "error",
            "error_code": err.code,
            "message": str(err),
            "files": [],
        }

    if not target_dir.exists() or not target_dir.is_dir():
        return {
            "status": "error",
            "error_code": "DIRECTORY_NOT_FOUND",
            "message": f"Approved resources sub-directory does not exist: {sub_directory}",
            "files": [],
        }

    files_list: List[Dict[str, Any]] = []
    for item in target_dir.iterdir():
        if item.is_file():
            stat = item.stat()
            files_list.append({
                "file_name": item.name,
                "relative_path": str(item.relative_to(APPROVED_RESOURCES_DIR)).replace("\\", "/"),
                "size_bytes": stat.st_size,
                "extension": item.suffix.lower(),
                "is_approved_corpus": True,
            })

    tc = trace_context or {}
    resolved_trace_id = tc.get("trace_id") or os.environ.get("GYAAN_TRACE_ID")
    resolved_span_id = tc.get("parent_span_id") or os.environ.get("GYAAN_PARENT_SPAN_ID")
    resolved_corr_id = tc.get("correlation_id") or os.environ.get("GYAAN_CORRELATION_ID")

    if resolved_trace_id:
        try:
            from backend.observability import log_observability_event
            log_observability_event(
                event_type="mcp_server_exec",
                message="MCP server executed tool: 'list_educational_resources'",
                trace_id=resolved_trace_id,
                span_id=resolved_span_id,
                component="mcp_server",
                status="completed",
                details={"tool": "list_educational_resources", "correlation_id": resolved_corr_id},
            )
        except Exception:
            pass

    return {
        "status": "success",
        "base_directory": "data/resources",
        "total_files": len(files_list),
        "files": files_list,
        "trace_id": resolved_trace_id,
        "correlation_id": resolved_corr_id,
    }


@mcp.tool(
    name="read_educational_resource",
    description=(
        "Read the contents of an approved educational document or NCERT textbook JSON corpus. "
        "Strictly sandboxed to the educational resources repository with directory traversal protection."
    ),
)
def read_educational_resource(
    file_name: str,
    max_entries: Optional[int] = 10,
    trace_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read an approved educational resource file.

    Args:
        file_name: Name or relative path of the approved file (e.g. 'ncert_class10_science.json').
        max_entries: If the file is a JSON list, maximum entries to return (default 10).

    Returns:
        Dict[str, Any]: File content, structure, and provenance metadata.
    """
    # 1. Path validation & traversal prevention
    try:
        resolved_file = validate_and_resolve_resource_path(file_name)
    except MCPSecurityError as err:
        logger.warning("Security violation in read_educational_resource: %s", err)
        return {
            "status": "error",
            "error_code": err.code,
            "message": str(err),
            "file_name": file_name,
        }

    if not resolved_file.exists() or not resolved_file.is_file():
        return {
            "status": "error",
            "error_code": "FILE_NOT_FOUND",
            "message": f"Resource file '{file_name}' does not exist in approved educational repository",
            "file_name": file_name,
        }

    # 2. File size bound check
    stat = resolved_file.stat()
    if stat.st_size > MAX_FILE_READ_BYTES:
        return {
            "status": "error",
            "error_code": "FILE_TOO_LARGE",
            "message": f"File size ({stat.st_size} bytes) exceeds maximum permitted limit ({MAX_FILE_READ_BYTES} bytes)",
            "file_name": file_name,
        }

    # 3. Read content securely
    try:
        with open(resolved_file, "r", encoding="utf-8") as f:
            raw_content = f.read()

        parsed_content: Any = None
        is_json = False
        if resolved_file.suffix.lower() == ".json":
            try:
                parsed_content = json.loads(raw_content)
                is_json = True
                if isinstance(parsed_content, list) and max_entries:
                    parsed_content = parsed_content[:max_entries]
            except Exception:
                parsed_content = raw_content
        else:
            parsed_content = raw_content

        logger.info("Successfully read approved educational resource: %s (%d bytes)", resolved_file.name, stat.st_size)

        tc = trace_context or {}
        resolved_trace_id = tc.get("trace_id") or os.environ.get("GYAAN_TRACE_ID")
        resolved_span_id = tc.get("parent_span_id") or os.environ.get("GYAAN_PARENT_SPAN_ID")
        resolved_corr_id = tc.get("correlation_id") or os.environ.get("GYAAN_CORRELATION_ID")

        if resolved_trace_id:
            try:
                from backend.observability import log_observability_event
                log_observability_event(
                    event_type="mcp_server_exec",
                    message="MCP server executed tool: 'read_educational_resource'",
                    trace_id=resolved_trace_id,
                    span_id=resolved_span_id,
                    component="mcp_server",
                    status="completed",
                    details={"tool": "read_educational_resource", "file": resolved_file.name, "correlation_id": resolved_corr_id},
                )
            except Exception:
                pass

        return {
            "status": "success",
            "file_name": resolved_file.name,
            "relative_path": str(resolved_file.relative_to(APPROVED_RESOURCES_DIR)).replace("\\", "/"),
            "size_bytes": stat.st_size,
            "format": "json" if is_json else "text",
            "content": parsed_content,
            "provenance": "Verified NCERT Educational Repository",
            "trace_id": resolved_trace_id,
            "correlation_id": resolved_corr_id,
        }

    except Exception as exc:
        logger.error("Error reading educational resource '%s': %s", file_name, exc)
        return {
            "status": "error",
            "error_code": "READ_ERROR",
            "message": f"Failed to read resource file: {str(exc)}",
            "file_name": file_name,
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")
