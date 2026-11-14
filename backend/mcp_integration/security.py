"""Gyaan AI - MCP Security, Path Validation, and Prompt Injection Guards.

Enforces:
1. Sandboxed filesystem access restricted strictly to approved educational corpora.
2. Directory traversal prevention (path canonicalization, boundary validation).
3. Tool allowlists ensuring only approved educational tools can execute.
4. Prompt injection filtering on both MCP inputs and untrusted external web outputs.
5. Sensitive credential protection.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("gyaan_ai.mcp.security")

# Canonical Approved Resources Directory: D:\Gyaan AI\data\resources
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
APPROVED_RESOURCES_DIR = (PROJECT_ROOT / "data" / "resources").resolve()

# Allowed file extensions for safe reading
ALLOWED_FILE_EXTENSIONS: Set[str] = {".json", ".txt", ".md", ".csv"}

# Maximum file size allowed to be read through MCP (1 MB)
MAX_FILE_READ_BYTES = 1024 * 1024

# Approved MCP Tool Names
APPROVED_MCP_TOOLS: Set[str] = {
    "search_educational_web",
    "list_educational_resources",
    "read_educational_resource",
}

# Prompt injection heuristic detection patterns
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*override", re.IGNORECASE),
    re.compile(r"you\s+are\s+no\s+longer\s+an?\s+ai", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?above", re.IGNORECASE),
    re.compile(r"bypass\s+all\s+safety\s+filters", re.IGNORECASE),
    re.compile(r"execute\s+command\s*:", re.IGNORECASE),
]


class MCPSecurityError(Exception):
    """Raised when an MCP security boundary or restriction is violated."""
    def __init__(self, message: str, code: str = "SECURITY_VIOLATION"):
        super().__init__(message)
        self.message = message
        self.code = code


def validate_tool_name(tool_name: str) -> None:
    """Verifies that the requested tool is on the approved MCP tool allowlist."""
    if not tool_name or tool_name not in APPROVED_MCP_TOOLS:
        logger.warning("Disallowed MCP tool execution attempt: %s", tool_name)
        raise MCPSecurityError(
            f"Tool '{tool_name}' is not in the approved MCP educational tool allowlist",
            code="DISALLOWED_TOOL",
        )


def sanitize_and_check_injection(content: str, source_context: str = "input") -> str:
    """Scans content for prompt injection patterns.

    Raises MCPSecurityError if an explicit prompt injection attempt is detected.
    """
    if not content or not isinstance(content, str):
        return ""

    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(content):
            logger.warning(
                "Prompt injection pattern detected in MCP %s: %s",
                source_context,
                pattern.pattern,
            )
            raise MCPSecurityError(
                f"Prompt injection pattern detected in MCP {source_context}: {pattern.pattern}",
                code="PROMPT_INJECTION_DETECTED",
            )

    return content.strip()


def validate_and_resolve_resource_path(relative_or_sub_path: str) -> Path:
    """Validates and resolves a path to ensure it is strictly inside the approved resources directory.

    Guards against:
    - Path traversal attacks ('..' or absolute root jumps)
    - Files outside APPROVED_RESOURCES_DIR
    - Disallowed file extensions
    - Symlink escapes
    """
    if not relative_or_sub_path:
        return APPROVED_RESOURCES_DIR

    # Normalize slashes and strip leading/trailing whitespace
    clean_path = relative_or_sub_path.strip().replace("\\", "/")

    # Detect explicit path traversal sequences
    if ".." in clean_path.split("/"):
        logger.warning("Directory traversal attempt detected in path: %s", relative_or_sub_path)
        raise MCPSecurityError(
            "Access denied: Directory traversal sequence ('..') detected",
            code="DIRECTORY_TRAVERSAL_DENIED",
        )

    # Disallow absolute drive roots or leading root slashes
    if os.path.isabs(clean_path) or (len(clean_path) > 1 and clean_path[1] == ":"):
        resolved_candidate = Path(clean_path).resolve()
    else:
        resolved_candidate = (APPROVED_RESOURCES_DIR / clean_path).resolve()

    # Ensure resolved path is strictly within APPROVED_RESOURCES_DIR
    try:
        resolved_candidate.relative_to(APPROVED_RESOURCES_DIR)
    except ValueError:
        logger.warning(
            "Path escape violation: %s resolved outside %s",
            resolved_candidate,
            APPROVED_RESOURCES_DIR,
        )
        raise MCPSecurityError(
            f"Access denied: Path '{relative_or_sub_path}' escapes approved educational directory",
            code="PATH_ESCAPE_DENIED",
        )

    # If candidate has a file extension or is a file, validate extension
    suffix = resolved_candidate.suffix.lower()
    if suffix and suffix not in ALLOWED_FILE_EXTENSIONS:
        raise MCPSecurityError(
            f"Access denied: File extension '{suffix}' is not permitted. Allowed: {sorted(ALLOWED_FILE_EXTENSIONS)}",
            code="DISALLOWED_EXTENSION",
        )

    return resolved_candidate


def wrap_untrusted_web_content(raw_text: str, source_url: Optional[str] = None) -> str:
    """Wraps retrieved web search content in an explicit untrusted container tag.

    This ensures LLMs process external information as reference data rather than instructions.
    """
    sanitized = raw_text.replace("<system>", "").replace("</system>", "")
    url_attr = f' source="{source_url}"' if source_url else ""
    return f'<external_untrusted_reference{url_attr}>\n{sanitized}\n</external_untrusted_reference>'
