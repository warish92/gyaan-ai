"""Gyaan AI - Local Resource Retrieval Service.

Performs deterministic, keyword-indexed text retrieval from local NCERT
educational corpora without requiring external cloud databases.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from backend.db.database import get_document_record
from backend.services.document_service import DocumentService, OwnershipError, DocumentNotFoundError

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


def retrieve_educational_resources(
    subject: str,
    topic: str,
    grade: str = "Class 10",
    student_id: Optional[str] = None,
    document_ids: Optional[List[str]] = None,
    document_service: Optional[Any] = None,
    max_student_chunks: int = 5,
    min_similarity_score: float = 0.35,
) -> Dict[str, Any]:
    """Retrieve verified educational resources combining student documents and NCERT corpus.

    Security & Fallback Rules:
    - If document_ids is specified, authentication is mandatory. Unauthenticated calls raise 401.
    - If document_ids is specified and ownership verification fails, raises OwnershipError (403)
      or DocumentNotFoundError (404). Never falls back silently to NCERT.
    - If student_id is unauthenticated/anonymous and document_ids is None, retrieves only public NCERT.
    - If student_id is authenticated and document_ids is None, searches student documents as
      supplemental context, gracefully falling back to NCERT if 0 matches or if vector store fails.
    - Full 7-field provenance is preserved for all student document chunks.
    """
    clean_sid = student_id.strip() if (student_id and student_id.strip() and student_id != "stu_anonymous") else None
    retrieval_notice: Optional[str] = None
    formatted_student_chunks: List[Dict[str, Any]] = []

    # 1. Enforce strict authentication when targeting specific document IDs
    if document_ids:
        if not clean_sid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access student documents.",
            )

        doc_svc = document_service or DocumentService()
        # Ownership verification occurs inside search_student_documents (raises OwnershipError / DocumentNotFoundError)
        raw_chunks = doc_svc.search_student_documents(
            student_id=clean_sid,
            query=topic,
            document_ids=document_ids,
            max_results=max_student_chunks,
            min_score=min_similarity_score,
        )

        doc_name_cache: Dict[str, str] = {}
        for chunk in raw_chunks:
            doc_id = chunk["document_id"]
            if doc_id not in doc_name_cache:
                rec = get_document_record(
                    doc_id,
                    student_id=clean_sid,
                    custom_path=getattr(doc_svc, "db_path", None),
                )
                doc_name_cache[doc_id] = rec["filename"] if rec and rec.get("filename") else "uploaded_document.pdf"

            formatted_student_chunks.append({
                "document_id": doc_id,
                "filename": doc_name_cache[doc_id],
                "chunk_id": chunk["chunk_id"],
                "page_number": chunk.get("page_number", 1),
                "chunk_index": chunk.get("chunk_index", 0),
                "similarity_score": round(float(chunk.get("similarity_score", 0.0)), 4),
                "text": chunk.get("text", ""),
            })

    elif clean_sid:
        # Authenticated general search across student's documents
        try:
            doc_svc = document_service or DocumentService()
            raw_chunks = doc_svc.search_student_documents(
                student_id=clean_sid,
                query=topic,
                document_ids=None,
                max_results=max_student_chunks,
                min_score=min_similarity_score,
            )

            if raw_chunks:
                doc_name_cache = {}
                for chunk in raw_chunks:
                    doc_id = chunk["document_id"]
                    if doc_id not in doc_name_cache:
                        rec = get_document_record(
                            doc_id,
                            student_id=clean_sid,
                            custom_path=getattr(doc_svc, "db_path", None),
                        )
                        doc_name_cache[doc_id] = rec["filename"] if rec and rec.get("filename") else "uploaded_document.pdf"

                    formatted_student_chunks.append({
                        "document_id": doc_id,
                        "filename": doc_name_cache[doc_id],
                        "chunk_id": chunk["chunk_id"],
                        "page_number": chunk.get("page_number", 1),
                        "chunk_index": chunk.get("chunk_index", 0),
                        "similarity_score": round(float(chunk.get("similarity_score", 0.0)), 4),
                        "text": chunk.get("text", ""),
                    })
            else:
                retrieval_notice = "Notice: No relevant passages found in your uploaded documents matching this topic."
        except Exception as exc:
            logger.warning("Student document retrieval unavailable: %s", exc)
            retrieval_notice = "Notice: Vector retrieval currently unavailable; using verified NCERT curriculum references."

    # 2. Canonical NCERT retrieval
    ncert_data = retrieve_local_resources(
        subject=subject,
        topic=topic,
        grade=grade,
    )

    is_verified = bool(formatted_student_chunks) or ncert_data.get("is_verified", False)
    if formatted_student_chunks and ncert_data.get("is_verified"):
        source_type = "Verified Student Documents & NCERT Corpus"
    elif formatted_student_chunks:
        source_type = "Verified Student Uploaded Documents"
    else:
        source_type = ncert_data.get("source_type", "Provisional Guidelines")

    return {
        "is_verified": is_verified,
        "source_type": source_type,
        "sources": ncert_data.get("sources", []),
        "student_documents": formatted_student_chunks,
        "has_student_docs": bool(formatted_student_chunks),
        "notice": retrieval_notice,
    }
