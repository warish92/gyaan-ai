"""Gyaan AI - A2A Protocol Security, Authentication, and Student Isolation.

Enforces:
1. Internal A2A request authentication (bearer token / secret header).
2. Student session ownership and cross-student isolation validation.
3. Payload size bounds and format validation.
4. Prompt injection detection and payload sanitization.
"""

from __future__ import annotations

import hmac
import logging
import os
import re
from typing import Any, Dict, Optional
from fastapi import HTTPException, Header, Request, status

logger = logging.getLogger("gyaan_ai.a2a.security")

# Environment variable name for internal inter-agent secret (Fail-closed: no hardcoded fallback)
A2A_INTERNAL_SECRET_ENV = "A2A_INTERNAL_SECRET"

# Maximum message payload size in bytes (512 KB)
MAX_A2A_PAYLOAD_BYTES = 512 * 1024


def get_internal_a2a_token() -> str:
    """Returns the expected internal secret token for inter-agent A2A communication.

    Fails closed if the secret environment variable is missing or empty.
    Never falls back to a predictable hardcoded secret.
    """
    token = os.environ.get(A2A_INTERNAL_SECRET_ENV)
    if not token or not token.strip():
        logger.error("A2A_INTERNAL_SECRET is not configured in the environment. Failing closed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A2A service misconfiguration: A2A_INTERNAL_SECRET environment variable is missing.",
        )
    return token.strip()


def verify_a2a_token(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_a2a_token: Optional[str] = Header(None, alias="X-A2A-Internal-Token"),
) -> bool:
    """Verifies that an incoming A2A request carries a valid internal authentication token.

    Accepts either:
    - Authorization: Bearer <token>
    - X-A2A-Internal-Token: <token>

    Uses constant-time comparison (hmac.compare_digest) to prevent timing side-channel attacks.
    Raises HTTPException 401 if missing or invalid.
    """
    expected_token = get_internal_a2a_token()
    provided_token: Optional[str] = None

    if x_a2a_token and isinstance(x_a2a_token, str):
        provided_token = x_a2a_token.strip()
    elif authorization and isinstance(authorization, str):
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided_token = parts[1]
        elif len(parts) == 1:
            provided_token = parts[0]

    if not provided_token or not hmac.compare_digest(provided_token, expected_token):
        logger.warning("Unauthorized A2A request: missing or invalid authentication token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A2A authentication failed: invalid or missing internal authorization token",
        )
    return True


def validate_student_isolation(student_id: str, session_id: str) -> None:
    """Validates student identity format and verifies session binding to prevent cross-student access.

    Raises HTTPException 400 or 403 if invalid or cross-student contamination is detected.
    """
    if not student_id or not isinstance(student_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A2A security validation error: student_id must be a non-empty string",
        )

    clean_student_id = student_id.strip()
    clean_session_id = session_id.strip() if session_id else ""

    if not clean_student_id or len(clean_student_id) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A2A security validation error: invalid student_id length",
        )

    # Validate characters (alphanumeric, underscore, dash)
    if not re.match(r"^[a-zA-Z0-9_\-]+$", clean_student_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A2A security validation error: student_id contains illegal characters",
        )

    # Validate session_id format if provided
    if clean_session_id:
        if len(clean_session_id) > 120 or not re.match(r"^[a-zA-Z0-9_\-:]+$", clean_session_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A2A security validation error: invalid session_id format",
            )

    # Session prefix verification: sessions containing ":" must have prefix matching student_id
    if clean_session_id and ":" in clean_session_id:
        session_owner = clean_session_id.split(":")[0]
        if session_owner != clean_student_id:
            logger.warning(
                "Cross-student session access detected: student %s attempted to use session %s owned by %s",
                clean_student_id,
                clean_session_id,
                session_owner,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-student access forbidden: session does not belong to student {clean_student_id}",
            )

    # Database session ownership verification for non-colon session IDs (UUIDs or standard keys)
    if clean_session_id and ":" not in clean_session_id:
        try:
            from backend.db.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            row = cur.execute(
                "SELECT student_id FROM student_sessions WHERE id = ?",
                (clean_session_id,),
            ).fetchone()
            conn.close()
            if row and row["student_id"] and row["student_id"] != clean_student_id:
                logger.warning(
                    "Cross-student database session access detected: student %s attempted to access session owned by %s",
                    clean_student_id,
                    row["student_id"],
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cross-student access forbidden: session does not belong to student {clean_student_id}",
                )
        except HTTPException:
            raise
        except Exception as db_err:
            logger.debug("Database session ownership check skipped: %s", db_err)

    return clean_student_id


def sanitize_and_check_injection(content: str) -> str:
    """Scans content for prompt injection patterns and returns sanitized text.

    Raises HTTPException 400 if an explicit prompt injection attempt is detected.
    """
    if not content:
        return ""

    from backend.services.prompt_guard import check_prompt_injection

    guard_result = check_prompt_injection(content)
    if not guard_result.is_safe:
        logger.warning("Prompt injection detected in A2A content: %s", guard_result.flagged_pattern)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security violation: {guard_result.reason}",
        )

    return content.strip()
