"""
Gyaan AI - Text Chunker Service for Educational Documents (Phase 5D.2).

Provides sentence-aware, paragraph-aware recursive text chunking tailored for
educational PDF textbooks and reference corpora. Preserves structural page numbers,
character offsets, token estimates, and deterministic content hashes while preventing
duplicate boilerplate chunks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Union

logger = logging.getLogger("gyaan_ai.text_chunker")

# Sensible default parameters for educational texts
DEFAULT_CHUNK_SIZE: int = 500       # ~100-120 words, optimal for conceptual definitions
DEFAULT_CHUNK_OVERLAP: int = 100    # ~20 words, preserves context across boundaries
MIN_CHUNK_SIZE: int = 1             # Do not discard meaningful short sentences or formulas


@dataclass(frozen=True)
class DocumentChunk:
    """
    Represents an isolated, self-contained educational text chunk with provenance metadata.
    """
    chunk_id: str
    document_id: str
    student_id: str
    page_number: int
    chunk_index: int
    text: str
    character_start: int
    character_end: int
    content_hash: str
    token_estimate: int

    def to_metadata(self) -> Dict[str, Union[str, int, float, bool]]:
        """
        Converts provenance fields into ChromaDB-compatible metadata dictionary.
        (ChromaDB metadata values must be primitive str, int, float, or bool).
        """
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "student_id": self.student_id,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "character_start": self.character_start,
            "character_end": self.character_end,
            "content_hash": self.content_hash,
            "token_estimate": self.token_estimate,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Returns full chunk dictionary including text content."""
        return asdict(self)


class TextChunker:
    """
    Sentence- and paragraph-aware recursive text chunker.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        min_chunk_size: int = MIN_CHUNK_SIZE,
        separators: Optional[Sequence[str]] = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap cannot be negative, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        # Recursive boundary preference: Paragraphs -> Newlines -> Sentences -> Words -> Characters
        self.separators = list(separators) if separators else [
            "\n\n",
            "\r\n\r\n",
            "\n",
            "\r\n",
            ". ",
            "? ",
            "! ",
            "; ",
            " ",
            "",
        ]

    def _compute_hash(self, text: str) -> str:
        """Computes deterministic SHA-256 hash of normalized text."""
        normalized = " ".join(text.strip().lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _split_text_recursive(self, text: str, separators: List[str]) -> List[str]:
        """
        Recursively splits text using the highest-priority separator that divides the content.
        """
        final_chunks: List[str] = []
        if not text:
            return final_chunks

        # If text is already within target budget, return as is
        if len(text) <= self.chunk_size:
            return [text]

        # Determine best separator
        separator = ""
        new_separators: List[str] = []
        for i, sep in enumerate(separators):
            if sep == "":
                separator = ""
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1:]
                break

        # Split text by current separator
        if separator != "":
            splits = text.split(separator)
        else:
            # Character-level fallback for giant uninterrupted strings
            splits = list(text)

        # Re-pack splits respecting chunk_size and chunk_overlap
        good_splits: List[str] = []
        for s in splits:
            if s != "":
                good_splits.append(s)

        merged_chunks: List[str] = []
        current_doc: List[str] = []
        current_len = 0

        for piece in good_splits:
            piece_len = len(piece) + (len(separator) if current_doc else 0)
            if current_len + piece_len > self.chunk_size:
                if current_doc:
                    doc_text = separator.join(current_doc)
                    if len(doc_text) > self.chunk_size and new_separators:
                        # Sub-split oversized chunk with next separator
                        sub_chunks = self._split_text_recursive(doc_text, new_separators)
                        merged_chunks.extend(sub_chunks)
                    else:
                        merged_chunks.append(doc_text)

                    # Build overlap window from tail of current_doc
                    while current_doc and current_len > self.chunk_overlap:
                        popped = current_doc.pop(0)
                        current_len -= len(popped) + (len(separator) if current_doc else 0)

                    # If popped pieces emptied current_doc, extract clean trailing word overlap
                    if not current_doc and doc_text and self.chunk_overlap > 0:
                        tail = doc_text[-self.chunk_overlap:]
                        space_idx = tail.find(" ")
                        clean_tail = tail[space_idx + 1:] if (space_idx != -1 and space_idx < len(tail) - 1) else tail
                        if clean_tail.strip():
                            current_doc.append(clean_tail.strip())
                            current_len = len(clean_tail.strip())

                current_doc.append(piece)
                current_len = sum(len(p) for p in current_doc) + (len(separator) * (len(current_doc) - 1))
            else:
                current_doc.append(piece)
                current_len += piece_len

        if current_doc:
            doc_text = separator.join(current_doc)
            if len(doc_text) > self.chunk_size and new_separators:
                sub_chunks = self._split_text_recursive(doc_text, new_separators)
                merged_chunks.extend(sub_chunks)
            else:
                merged_chunks.append(doc_text)

        return merged_chunks

    def chunk_document(
        self,
        document_id: str,
        student_id: str,
        pages: Sequence[str] | Dict[int, str],
        deduplicate: bool = True,
    ) -> List[DocumentChunk]:
        """
        Chunks an entire document across pages, preserving page provenance and discarding duplicates.

        Args:
            document_id: Unique identifier of target document.
            student_id: Authenticated owner student ID.
            pages: Sequence of page text strings or dict mapping {page_number: text}.
            deduplicate: If True, skips identical chunks (e.g. repeated headers/footers).

        Returns:
            List of DocumentChunk objects with deterministic IDs and metadata.
        """
        if not document_id or not document_id.strip():
            raise ValueError("document_id cannot be blank")
        if not student_id or not student_id.strip():
            raise ValueError("student_id cannot be blank")

        page_items: List[tuple[int, str]] = []
        if isinstance(pages, dict):
            for p_num, p_text in sorted(pages.items()):
                page_items.append((p_num, p_text))
        else:
            for idx, p_text in enumerate(pages, 1):
                page_items.append((idx, p_text))

        all_chunks: List[DocumentChunk] = []
        seen_hashes: set[str] = set()
        global_chunk_idx = 0

        for page_num, raw_text in page_items:
            if not raw_text or not raw_text.strip():
                # Skip blank or whitespace-only pages
                continue

            cleaned_text = raw_text.strip()
            # Preserve character offsets relative to page text
            raw_splits = self._split_text_recursive(cleaned_text, self.separators)

            last_find_idx = 0
            for split_text in raw_splits:
                stripped_split = split_text.strip()
                if len(stripped_split) < self.min_chunk_size:
                    # Drop minuscule fragments (e.g. solitary punctuation or isolated numbers)
                    continue

                content_hash = self._compute_hash(stripped_split)
                if deduplicate and content_hash in seen_hashes:
                    logger.debug(
                        f"Skipping duplicate chunk on page {page_num} for doc {document_id}"
                    )
                    continue

                # Locate approximate character offsets in source page text
                char_start = cleaned_text.find(stripped_split, last_find_idx)
                if char_start == -1:
                    char_start = last_find_idx
                char_end = char_start + len(stripped_split)
                last_find_idx = max(0, char_end - self.chunk_overlap)

                chunk_id = f"{document_id}_p{page_num}_c{global_chunk_idx}_{content_hash[:8]}"
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    student_id=student_id,
                    page_number=page_num,
                    chunk_index=global_chunk_idx,
                    text=stripped_split,
                    character_start=char_start,
                    character_end=char_end,
                    content_hash=content_hash,
                    token_estimate=max(1, len(stripped_split) // 4),
                )

                all_chunks.append(chunk)
                seen_hashes.add(content_hash)
                global_chunk_idx += 1

        return all_chunks
