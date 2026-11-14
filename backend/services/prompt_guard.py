"""Gyaan AI - Centralized Prompt Injection & Adversarial AI Guardrails.

Protects LLM agents (CrewAI, Google ADK, A2A, and MCP) against:
1. Direct prompt injection (instruction override, role switching, jailbreak phrases).
2. Indirect prompt injection (instructions embedded in retrieved documents or search).
3. System prompt extraction and secret leaking attempts.
4. Delimiter manipulation and escaping attacks.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Optional

logger = logging.getLogger("gyaan_ai.security.prompt_guard")


@dataclass
class PromptGuardResult:
    """Represents the outcome of a prompt injection inspection."""
    is_safe: bool
    flagged_pattern: Optional[str] = None
    reason: Optional[str] = None
    sanitized_text: Optional[str] = None

    @property
    def is_injection(self) -> bool:
        """Convenience property for checking if injection was detected."""
        return not self.is_safe


# Comprehensive adversarial injection patterns
_PROMPT_INJECTION_PATTERNS = [
    # 1. Direct instruction overrides
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|preceding)\s+(instructions|prompts|rules|commands|guidelines)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above|preceding)\s+(instructions|prompts|rules|commands|guidelines)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|above|preceding)\s+(instructions|prompts|rules|commands)", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*override", re.IGNORECASE),
    
    # 2. Role assumption & jailbreaks
    re.compile(r"you\s+are\s+no\s+longer\s+an?\s+ai", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(unrestricted|dan|jailbroken|evil|chaos)", re.IGNORECASE),
    re.compile(r"from\s+now\s+on\s+you\s+(can|will)\s+do\s+anything", re.IGNORECASE),
    re.compile(r"bypass\s+all\s+(safety|content|security)\s+filters", re.IGNORECASE),
    re.compile(r"enable\s+(developer|unrestricted|god)\s+mode", re.IGNORECASE),
    re.compile(r"do\s+anything\s+now", re.IGNORECASE),
    
    # 3. System prompt & secret extraction
    re.compile(r"(repeat|print|reveal|output|display)\s+(your\s+)?(exact\s+)?(system\s+prompt|initial\s+instructions|backstory|developer\s+prompt)", re.IGNORECASE),
    re.compile(r"what\s+(is|are)\s+your\s+(exact\s+)?(initial\s+instructions|system\s+prompt|hidden\s+rules)", re.IGNORECASE),
    re.compile(r"(print|reveal|show|dump)\s+(all\s+)?(api\s+keys|passwords|secrets|hmac\s+keys)", re.IGNORECASE),
    
    # 4. Delimiter manipulation
    re.compile(r"<\s*/?\s*(system|instruction|admin|developer|secret)\s*>", re.IGNORECASE),
    re.compile(r"\[/?(inst|sys|prompt)\]", re.IGNORECASE),
    re.compile(r"<<\s*/?\s*(sys|system)\s*>>", re.IGNORECASE),
]


def check_prompt_injection(text: str) -> PromptGuardResult:
    """Scans incoming text for adversarial prompt injection attempts.

    Returns a PromptGuardResult indicating whether the prompt is safe.
    """
    if not text or not isinstance(text, str):
        return PromptGuardResult(is_safe=True, sanitized_text="")

    clean = text.strip()
    if not clean:
        return PromptGuardResult(is_safe=True, sanitized_text="")

    for pattern in _PROMPT_INJECTION_PATTERNS:
        match = pattern.search(clean)
        if match:
            matched_phrase = match.group(0)
            logger.warning("Prompt injection pattern detected: %s", pattern.pattern)
            return PromptGuardResult(
                is_safe=False,
                flagged_pattern=pattern.pattern,
                reason=f"Input contains an adversarial instruction manipulation pattern: '{matched_phrase}'",
                sanitized_text=None,
            )

    return PromptGuardResult(is_safe=True, sanitized_text=clean)


def wrap_untrusted_content(content: str, source_label: str = "untrusted_input") -> str:
    """Wraps untrusted user or retrieved text in explicit isolation boundary tags.

    Ensures the LLM interprets the text as data/reference rather than executable instructions.
    """
    if not content:
        return ""
    # Strip potential delimiter escapes
    safe_body = content.replace("<system>", "").replace("</system>", "").replace("<instruction>", "").replace("</instruction>", "")
    return f"<{source_label}>\n{safe_body.strip()}\n</{source_label}>"
