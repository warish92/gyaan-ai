"""Gyaan AI - Local Resource Retrieval Service.

Performs deterministic, keyword-indexed text retrieval from local NCERT
educational corpora without requiring external cloud databases.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gyaan_ai.retriever")

RESOURCES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "resources"


def retrieve_local_resources(
    subject: str,
    topic: str,
    grade: str = "Class 10",
    max_results: int = 3,
) -> Dict[str, Any]:
    """Retrieve verified NCERT reference excerpts matching the query.

    Args:
        subject: Target academic subject (e.g. 'Science').
        topic: Concept/topic query (e.g. 'Acids and Bases', 'pH scale').
        grade: Target grade level (default 'Class 10').
        max_results: Maximum excerpts to return.

    Returns:
        Dict[str, Any]: Retrieval result containing metadata, excerpts, and verification flag.
    """
    results: List[Dict[str, Any]] = []
    is_verified = False

    if not RESOURCES_DIR.exists():
        logger.info("Local resources directory %s does not exist.", RESOURCES_DIR)
        return {
            "is_verified": False,
            "source_type": "Provisional Guidelines (No local verified corpus found)",
            "sources": [],
        }

    # Substantive topic query terms (exclude common structural words)
    stop_words = {"and", "the", "for", "with", "from", "class", "chapter", "unit", "part", "ncert"}
    raw_tokens = topic.lower().replace(",", " ").replace("-", " ").replace(":", " ").replace("/", " ").split()
    topic_terms = [t for t in raw_tokens if len(t) >= 3 and t not in stop_words]

    norm_grade = grade.strip().lower()
    norm_subject = subject.strip().lower()

    for json_file in RESOURCES_DIR.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                entries = json.load(f)

            for entry in entries:
                # Check grade and subject match
                entry_grade = entry.get("grade", "").lower()
                entry_subject = entry.get("subject", "").lower()

                if norm_grade not in entry_grade or norm_subject not in entry_subject:
                    continue

                # Match relevance by keywords, title, chapter, or section
                keywords = [k.lower() for k in entry.get("keywords", [])]
                title = entry.get("title", "").lower()
                chapter = entry.get("chapter", "").lower()
                section = entry.get("section", "").lower()
                excerpt = entry.get("excerpt", "").lower()

                match_score = 0
                topic_clean = topic.strip().lower()

                # Direct phrase match gives strong relevance
                if topic_clean and (topic_clean in title or topic_clean in chapter or topic_clean in section):
                    match_score += 10
                elif topic_clean and any(topic_clean in kw for kw in keywords):
                    match_score += 8

                # Individual token matching
                for term in topic_terms:
                    if term in chapter or term in section:
                        match_score += 4
                    elif term in title:
                        if term not in {"science", "physics", "chemistry", "biology", "mathematics"}:
                            match_score += 3
                    if term in keywords:
                        match_score += 3
                    elif term in excerpt:
                        match_score += 1

                # Require substantive topic match (score >= 3) to prevent cross-topic contamination
                if match_score >= 3:
                    results.append((match_score, entry))

        except Exception as exc:
            logger.warning("Error reading resource file %s: %s", json_file, exc)

    if results:
        # Sort by match score descending
        results.sort(key=lambda x: x[0], reverse=True)
        top_entries = [item[1] for item in results[:max_results]]
        is_verified = True
        return {
            "is_verified": True,
            "source_type": "Verified Local NCERT Corpus",
            "sources": top_entries,
        }

    return {
        "is_verified": False,
        "source_type": "Provisional Curriculum Recommendations (No verified local excerpt match)",
        "sources": [],
    }
