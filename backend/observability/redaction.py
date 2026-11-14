"""Gyaan AI - Observability Security, Redaction & Data Minimization.

Enforces:
1. Stripping and masking of sensitive credentials (passwords, API keys, tokens, auth headers).
2. Redaction of Personally Identifiable Information (PII) including emails, phone numbers, and IDs.
3. Privacy-preserving pseudonymization of student identifiers via keyed HMAC.
4. Complete redaction and exclusion of private student conversations, prompts, and internal reasoning / chain-of-thought.
5. Bounded payload sizing to prevent memory exhaustion and large log blobs.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from typing import Any, Dict, List, Set, Union

# Regex patterns for sensitive credential key identification
CREDENTIAL_KEY_PATTERNS = [
    re.compile(r"pass(word)?", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"bearer", re.IGNORECASE),
    re.compile(r"auth(orization)?", re.IGNORECASE),
    re.compile(r"private[_-]?key", re.IGNORECASE),
    re.compile(r"jwt", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
]

# Patterns for private internal reasoning, chain-of-thought, or detailed thought steps
REASONING_KEY_PATTERNS = [
    re.compile(r"thought", re.IGNORECASE),
    re.compile(r"reasoning", re.IGNORECASE),
    re.compile(r"chain[_-]?of[_-]?thought", re.IGNORECASE),
    re.compile(r"step_preview", re.IGNORECASE),
    re.compile(r"internal_monologue", re.IGNORECASE),
]

# Patterns for private student conversations, messages, or full user prompts
CONVERSATION_KEY_PATTERNS = [
    re.compile(r"conversation", re.IGNORECASE),
    re.compile(r"chat_history", re.IGNORECASE),
    re.compile(r"user_message", re.IGNORECASE),
    re.compile(r"raw_message", re.IGNORECASE),
    re.compile(r"student_answer", re.IGNORECASE),
    re.compile(r"submitted_answers", re.IGNORECASE),
]

# Patterns for student identification
STUDENT_ID_KEY_PATTERNS = [
    re.compile(r"^student_id$", re.IGNORECASE),
    re.compile(r"^student$", re.IGNORECASE),
    re.compile(r"_student_id$", re.IGNORECASE),
]

STUDENT_NAME_KEY_PATTERNS = [
    re.compile(r"student_name", re.IGNORECASE),
    re.compile(r"display_name", re.IGNORECASE),
    re.compile(r"full_name", re.IGNORECASE),
]

# Regex patterns for PII detection in string values
PII_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PII_PHONE_PATTERN = re.compile(r"(?:\+91[-.\s]?|91[-.\s]?|\b0)?[6-9]\d{9}\b")
PII_AADHAAR_PATTERN = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")

# Maximum string length allowed in telemetry payloads to avoid memory bloat
MAX_TELEMETRY_STRING_LEN = 1000
MAX_RECURSION_DEPTH = 6


def pseudonymize_student_id(student_id: Optional[str]) -> Optional[str]:
    """Generates a privacy-preserving pseudonymous identifier for a student ID via keyed HMAC-SHA256.

    Loads the HMAC secret strictly and exclusively from TELEMETRY_HMAC_SECRET in the environment.
    If the secret is missing, empty, whitespace-only, or unavailable, returns None so that
    student identifiers are completely omitted from telemetry.
    Never falls back to hardcoded salts or unkeyed hashes. Raw student IDs never enter telemetry.
    """
    if not student_id or not isinstance(student_id, str):
        return None

    stripped_id = student_id.strip()
    if not stripped_id:
        return None

    # Load HMAC secret strictly from environment variable
    secret = os.environ.get("TELEMETRY_HMAC_SECRET")
    if not secret or not secret.strip():
        # Secret missing, empty, or whitespace: omit student identifiers entirely
        return None

    # Already pseudonymized
    if stripped_id.startswith("pseudo_"):
        return stripped_id

    try:
        secret_bytes = secret.strip().encode("utf-8")
        digest = hmac.new(secret_bytes, stripped_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        return f"pseudo_{digest}"
    except Exception:
        # On any HMAC failure, omit student identifier entirely
        return None


def is_credential_key(key: str) -> bool:
    """Checks whether a dictionary key name suggests credentials or secrets."""
    if not isinstance(key, str):
        return False
    return any(p.search(key) for p in CREDENTIAL_KEY_PATTERNS)


def is_reasoning_key(key: str) -> bool:
    """Checks whether a dictionary key name suggests private internal reasoning / chain-of-thought."""
    if not isinstance(key, str):
        return False
    return any(p.search(key) for p in REASONING_KEY_PATTERNS)


def is_conversation_key(key: str) -> bool:
    """Checks whether a dictionary key name suggests private student conversation text."""
    if not isinstance(key, str):
        return False
    return any(p.search(key) for p in CONVERSATION_KEY_PATTERNS)


def is_student_id_key(key: str) -> bool:
    """Checks whether a dictionary key name suggests a student ID."""
    if not isinstance(key, str):
        return False
    return any(p.search(key) for p in STUDENT_ID_KEY_PATTERNS)


def is_student_name_key(key: str) -> bool:
    """Checks whether a dictionary key name suggests a student personal name."""
    if not isinstance(key, str):
        return False
    return any(p.search(key) for p in STUDENT_NAME_KEY_PATTERNS)


def redact_string(val: str, max_length: int = MAX_TELEMETRY_STRING_LEN) -> str:
    """Masks PII patterns within a string and bounds its total length."""
    if not isinstance(val, str):
        return str(val)

    # Redact email addresses
    val = PII_EMAIL_PATTERN.sub("[REDACTED_EMAIL]", val)
    # Redact Indian phone numbers
    val = PII_PHONE_PATTERN.sub("[REDACTED_PHONE]", val)
    # Redact Aadhaar/National ID patterns
    val = PII_AADHAAR_PATTERN.sub("[REDACTED_ID]", val)

    # Bounded truncation
    if len(val) > max_length:
        return val[:max_length] + " ... [TRUNCATED_FOR_TELEMETRY]"
    return val


def redact_sensitive_data(obj: Any, depth: int = 0) -> Any:
    """Recursively redacts sensitive keys, student identities, conversations, thoughts,

    and PII patterns from dictionaries, lists, and nested structures.
    Guarantees that no passwords, API keys, tokens, student names, raw student IDs,
    or private conversations enter observability telemetry.
    """
    if depth > MAX_RECURSION_DEPTH:
        return "[MAX_DEPTH_REACHED]"

    # Support Pydantic models (v1 and v2)
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        try:
            return redact_sensitive_data(obj.model_dump(), depth + 1)
        except Exception:
            pass
    elif hasattr(obj, "dict") and callable(obj.dict):
        try:
            return redact_sensitive_data(obj.dict(), depth + 1)
        except Exception:
            pass

    # Support Exception objects
    if isinstance(obj, Exception):
        return f"{type(obj).__name__}: {redact_string(str(obj))}"

    if isinstance(obj, dict):
        sanitized: Dict[str, Any] = {}
        for k, v in obj.items():
            str_key = str(k)
            if is_credential_key(str_key):
                sanitized[str_key] = "[REDACTED_CREDENTIAL]"
            elif is_student_name_key(str_key):
                sanitized[str_key] = "[REDACTED_STUDENT_NAME]"
            elif is_student_id_key(str_key):
                if isinstance(v, str):
                    pseudo = pseudonymize_student_id(v)
                    if pseudo is not None:
                        sanitized[str_key] = pseudo
                elif v is not None:
                    pseudo = pseudonymize_student_id(str(v))
                    if pseudo is not None:
                        sanitized[str_key] = pseudo
                # Note: if pseudo is None (secret missing/empty or invalid ID),
                # the key is omitted completely from sanitized dictionary
            elif is_reasoning_key(str_key):
                sanitized[str_key] = "[REDACTED_INTERNAL_REASONING]"
            elif is_conversation_key(str_key):
                sanitized[str_key] = "[REDACTED_STUDENT_CONVERSATION]"
            else:
                # If a value itself looks like a student ID (e.g. 'student_aarav_01')
                if isinstance(v, str) and v.startswith("student_"):
                    pseudo = pseudonymize_student_id(v)
                    if pseudo is not None:
                        sanitized[str_key] = pseudo
                    # Note: if pseudo is None, key is omitted completely
                else:
                    sanitized[str_key] = redact_sensitive_data(v, depth + 1)
        return sanitized

    elif isinstance(obj, (list, tuple, set)):
        sanitized_list = []
        for item in obj:
            if isinstance(item, str) and item.startswith("student_"):
                pseudo = pseudonymize_student_id(item)
                if pseudo is not None:
                    sanitized_list.append(pseudo)
                # When pseudo is None, item is omitted from the list
            else:
                sanitized_list.append(redact_sensitive_data(item, depth + 1))
        return sanitized_list

    elif isinstance(obj, str):
        if obj.startswith("student_"):
            return pseudonymize_student_id(obj)
        return redact_string(obj)

    elif isinstance(obj, (int, float, bool)) or obj is None:
        return obj

    else:
        # Fallback for complex objects: convert to string and redact
        str_val = str(obj)
        if str_val.startswith("student_"):
            return pseudonymize_student_id(str_val)
        return redact_string(str_val)
