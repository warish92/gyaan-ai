"""Gyaan AI - Educational Content Moderation Service.

Provides deterministic, explainable pre-execution safeguards for Class 10 CBSE students.
Detects:
1. Abusive language, profanity, and harassment.
2. Hate speech and discriminatory content.
3. Violence, threats, and self-harm keywords.
4. Sexually explicit material inappropriate for school students.

Includes specific domain whitelisting for CBSE Class 10 Science concepts
(e.g., toxic metabolic waste in biology, corrosive acids in chemistry,
reproductive biology in science) to avoid educational false positives.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Optional, Set, Tuple

logger = logging.getLogger("gyaan_ai.security.moderation")

# Standard friendly pedagogical redirection message
DEFAULT_PEDAGOGICAL_REFUSAL = (
    "Let's keep our study session focused on your CBSE Class 10 learning goals. "
    "Please rephrase your question or ask about a science or math topic."
)


@dataclass
class ModerationResult:
    """Represents the structured outcome of a content moderation check."""
    is_safe: bool
    flagged_category: Optional[str] = None
    reason: Optional[str] = None
    pedagogical_guidance: Optional[str] = None

    @property
    def category(self) -> Optional[str]:
        return self.flagged_category

    @property
    def friendly_refusal(self) -> str:
        return self.pedagogical_guidance or DEFAULT_PEDAGOGICAL_REFUSAL


# Explicitly forbidden toxic / abusive words and patterns (word boundaries enforced)
# Uses canonical root stems with regex word boundaries to prevent substring false matches
_ABUSE_PATTERNS = [
    re.compile(r"\b(bastard|bitch|asshole|motherfucker|fucker|dickhead|cunt|slut|whore)\b", re.IGNORECASE),
    re.compile(r"\b(fuck|shit|piss|cock|pussy)\b", re.IGNORECASE),
    re.compile(r"\b(idiot|stupid|moron|retard|loser|dumbass)\b", re.IGNORECASE),
    re.compile(r"\b(shut\s+up|kill\s+yourself|go\s+die|die\s+in\s+a\s+hole)\b", re.IGNORECASE),
]

# Explicit threats and self-harm patterns
_THREAT_PATTERNS = [
    re.compile(r"\b(i\s+will\s+kill\s+you|i\s+will\s+hurt\s+you|gonna\s+murder|bomb\s+the\s+school)\b", re.IGNORECASE),
    re.compile(r"\b(make\s+a\s+bomb|build\s+a\s+bomb|blow\s+up\s+(the\s+)?school|kill\s+everyone|kill\s+people)\b", re.IGNORECASE),
    re.compile(r"\b(i\s+want\s+to\s+kill|want\s+to\s+hurt|i\s+hate\s+you\s+and\s+want\s+to\s+kill)\b", re.IGNORECASE),
    re.compile(r"\b(commit\s+suicide|how\s+to\s+hang\s+myself|cut\s+my\s+wrists|end\s+my\s+life)\b", re.IGNORECASE),
]

# Hate speech and slur patterns
_HATE_PATTERNS = [
    re.compile(r"\b(nigger|faggot|kike|chink|spic)\b", re.IGNORECASE),
    re.compile(r"\b(all\s+(muslims|hindus|christians|jews|blacks|whites)\s+are\s+(evil|terrorists|animals))\b", re.IGNORECASE),
]

# Sexually explicit content (inappropriate for Class 10 school assistant)
_EXPLICIT_PATTERNS = [
    re.compile(r"\b(porn|pornography|blowjob|handjob|gangbang|hardcore\s+sex|nude\s+pics)\b", re.IGNORECASE),
]

# CBSE Class 10 Educational Whitelist Contexts
# Phrases that contain words like 'toxic', 'acid', 'sex', 'kill' in valid scientific/educational context
_EDUCATIONAL_SAFE_TERMS: Set[str] = {
    "toxic metabolic waste",
    "removal of toxic waste",
    "toxic nitrogenous waste",
    "toxic waste in excretion",
    "corrosive acid",
    "corrosive nature of acids",
    "sulphate",
    "copper sulphate",
    "ferrous sulphate",
    "sulphuric acid",
    "sexual reproduction",
    "asexual reproduction",
    "sexual reproduction in flowering plants",
    "human reproductive system",
    "male reproductive system",
    "female reproductive system",
    "killing of microorganisms",
    "kills bacteria in stomach",
    "hydrochloric acid kills bacteria",
}


def check_content_safety(text: str) -> ModerationResult:
    """Inspects text for toxicity, harassment, hate speech, threats, and inappropriate content.

    Returns a ModerationResult indicating whether the text is safe to process.
    If unsafe, provides the category and a friendly pedagogical refusal message.
    """
    if not text or not isinstance(text, str):
        return ModerationResult(is_safe=True)

    clean_text = text.strip()
    if not clean_text:
        return ModerationResult(is_safe=True)

    text_lower = clean_text.lower()

    # 1. Fast check for approved educational contexts (prevents false positives)
    for safe_phrase in _EDUCATIONAL_SAFE_TERMS:
        if safe_phrase in text_lower:
            # Mask the safe educational phrase before evaluating abuse heuristics
            text_lower = text_lower.replace(safe_phrase, "educational_concept")

    # 2. Check for explicit threats and self-harm
    for pattern in _THREAT_PATTERNS:
        if pattern.search(text_lower):
            logger.warning("Content moderation alert: Threat or self-harm pattern detected")
            return ModerationResult(
                is_safe=False,
                flagged_category="THREAT_OR_SELF_HARM",
                reason="Input contains threats of violence or self-harm references.",
                pedagogical_guidance=(
                    "If you are feeling overwhelmed or in crisis, please reach out to a trusted adult, "
                    "teacher, or counselor. In India, you can call the Tele-MANAS helpline at 14416 for free, "
                    "confidential support. Let's focus on your CBSE Class 10 studies whenever you are ready."
                ),
            )

    # 3. Check for hate speech and slurs
    for pattern in _HATE_PATTERNS:
        if pattern.search(text_lower):
            logger.warning("Content moderation alert: Hate speech pattern detected")
            return ModerationResult(
                is_safe=False,
                flagged_category="HATE_SPEECH",
                reason="Input contains derogatory, discriminatory, or hateful language.",
                pedagogical_guidance=DEFAULT_PEDAGOGICAL_REFUSAL,
            )

    # 4. Check for abusive language, profanity, and harassment
    for pattern in _ABUSE_PATTERNS:
        if pattern.search(text_lower):
            logger.warning("Content moderation alert: Abusive language detected")
            return ModerationResult(
                is_safe=False,
                flagged_category="ABUSIVE_LANGUAGE",
                reason="Input contains profanity, insults, or abusive phrasing.",
                pedagogical_guidance=DEFAULT_PEDAGOGICAL_REFUSAL,
            )

    # 5. Check for sexually explicit content
    for pattern in _EXPLICIT_PATTERNS:
        if pattern.search(text_lower):
            logger.warning("Content moderation alert: Inappropriate explicit content detected")
            return ModerationResult(
                is_safe=False,
                flagged_category="EXPLICIT_CONTENT",
                reason="Input contains inappropriate sexually explicit content.",
                pedagogical_guidance=DEFAULT_PEDAGOGICAL_REFUSAL,
            )

    return ModerationResult(is_safe=True)
