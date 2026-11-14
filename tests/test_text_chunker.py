"""
Unit tests for Gyaan AI Text Chunker Service (Phase 5D.2).

Validates:
- Empty and blank input handling
- Single and multi-paragraph splitting
- Long paragraph handling without truncation
- Sentence and punctuation boundary preference
- Chunk overlap and semantic continuity
- Page-number preservation across multiple pages
- Deterministic chunk IDs and content hashing
- Duplicate chunk rejection across repeated headers/footers
- Metadata dictionary integrity
"""

import pytest

from backend.services.text_chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DocumentChunk,
    TextChunker,
)


def test_01_empty_text_returns_empty_list():
    """TC-CHK-01: Empty or whitespace-only documents return an empty chunk list."""
    chunker = TextChunker()
    assert chunker.chunk_document("doc_empty", "std_1", []) == []
    assert chunker.chunk_document("doc_empty", "std_1", ["", "   \n\t  "]) == []


def test_02_single_short_paragraph_creates_single_chunk():
    """TC-CHK-02: A single paragraph smaller than chunk_size produces exactly one chunk."""
    chunker = TextChunker(chunk_size=500, chunk_overlap=100)
    text = "Photosynthesis is the process by which green plants transform light energy into chemical energy."
    chunks = chunker.chunk_document("doc_bio", "std_1", [text])

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.document_id == "doc_bio"
    assert chunk.student_id == "std_1"
    assert chunk.page_number == 1
    assert chunk.chunk_index == 0
    assert chunk.text == text
    assert chunk.character_start == 0
    assert chunk.character_end == len(text)
    assert chunk.token_estimate == len(text) // 4


def test_03_multiple_paragraphs_respect_natural_boundaries():
    """TC-CHK-03: Splits across natural paragraph breaks (\\n\\n) before dividing sentences."""
    chunker = TextChunker(chunk_size=120, chunk_overlap=20)
    p1 = "First educational paragraph discussing basic algebra and linear equations."
    p2 = "Second educational paragraph discussing quadratic formulas and parabolas."
    text = f"{p1}\n\n{p2}"

    chunks = chunker.chunk_document("doc_math", "std_1", [text])
    assert len(chunks) >= 2
    assert p1 in chunks[0].text
    assert p2 in chunks[1].text


def test_04_long_paragraph_splits_on_sentence_boundaries():
    """TC-CHK-04: Giant paragraph is divided at sentence boundaries (. ?) rather than arbitrary words."""
    chunker = TextChunker(chunk_size=150, chunk_overlap=30)
    sentence_1 = "Newton's first law states an object remains at rest unless acted upon by a net external force."
    sentence_2 = "Newton's second law defines the relationship between force, mass, and acceleration as F equals ma."
    sentence_3 = "Newton's third law states that for every action there is an equal and opposite reaction."
    long_para = f"{sentence_1} {sentence_2} {sentence_3}"

    chunks = chunker.chunk_document("doc_phys", "std_1", [long_para])
    assert len(chunks) >= 2
    # Ensure splits don't cut words in half
    for c in chunks:
        assert not c.text.endswith(" ")
        assert len(c.text) <= 180  # Allows slight boundary buffer


def test_05_chunk_overlap_preserves_context():
    """TC-CHK-05: Consecutive chunks share overlap characters for semantic continuity."""
    chunker = TextChunker(chunk_size=100, chunk_overlap=30)
    text = (
        "Cellular respiration is a metabolic pathway that breaks down glucose and produces ATP. "
        "The stages of cellular respiration include glycolysis, pyruvate oxidation, the citric acid cycle, "
        "and oxidative phosphorylation."
    )
    chunks = chunker.chunk_document("doc_cell", "std_1", [text])
    assert len(chunks) >= 2

    # Verify that the end of chunk 0 appears in chunk 1
    tail_chunk_0 = chunks[0].text[-25:]
    assert any(tail_chunk_0 in c.text for c in chunks[1:])


def test_06_page_number_preservation_across_multipage():
    """TC-CHK-06: Chunks maintain strictly accurate page numbers across a multipage input."""
    chunker = TextChunker(chunk_size=300)
    pages = {
        1: "Page 1 Content: Introduction to Organic Chemistry and Carbon Compounds.",
        2: "Page 2 Content: Saturated Hydrocarbons, Alkanes, and Single Covalent Bonds.",
        3: "Page 3 Content: Unsaturated Hydrocarbons, Alkenes, Alkynes, and Multiple Bonds.",
    }
    chunks = chunker.chunk_document("doc_chem", "std_1", pages)
    assert len(chunks) == 3
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2
    assert chunks[2].page_number == 3


def test_07_deterministic_chunk_ids_and_hashing():
    """TC-CHK-07: Chunk IDs are fully deterministic across repeated runs with identical text."""
    chunker = TextChunker(chunk_size=200)
    text = "Thermodynamics is the branch of physics dealing with heat, work, and temperature."

    run_1 = chunker.chunk_document("doc_det", "std_1", [text])
    run_2 = chunker.chunk_document("doc_det", "std_1", [text])

    assert len(run_1) == len(run_2) == 1
    assert run_1[0].chunk_id == run_2[0].chunk_id
    assert run_1[0].content_hash == run_2[0].content_hash


def test_08_duplicate_chunk_prevention():
    """TC-CHK-08: Identical repeated boilerplate (e.g. headers/footers) is filtered when deduplicate=True."""
    chunker = TextChunker(chunk_size=200)
    header = "NCERT Class 10 Science - Official Chapter 1 Reference Material."
    page_1 = f"{header}\n\nChemical Reactions and Equations: Chemical changes in daily life."
    page_2 = f"{header}\n\nBalancing Chemical Equations: Conservation of mass in reactions."

    chunks = chunker.chunk_document("doc_dup", "std_1", [page_1, page_2], deduplicate=True)
    # Header should only appear as a separate chunk once if isolated, or not duplicate
    hashes = [c.content_hash for c in chunks]
    assert len(hashes) == len(set(hashes)), "Duplicate chunk content hashes detected!"


def test_09_metadata_integrity_and_serialization():
    """TC-CHK-09: DocumentChunk converts to ChromaDB-compliant primitive metadata dict."""
    chunk = DocumentChunk(
        chunk_id="doc1_p1_c0_a1b2c3d4",
        document_id="doc1",
        student_id="std_99",
        page_number=1,
        chunk_index=0,
        text="Sample text for metadata validation.",
        character_start=0,
        character_end=36,
        content_hash="a1b2c3d4e5f60718",
        token_estimate=9,
    )
    meta = chunk.to_metadata()
    # ChromaDB metadata must only have primitive types
    for key, val in meta.items():
        assert isinstance(val, (str, int, float, bool)), f"Non-primitive metadata key '{key}': {type(val)}"

    assert meta["chunk_id"] == "doc1_p1_c0_a1b2c3d4"
    assert meta["student_id"] == "std_99"
    assert meta["page_number"] == 1


def test_10_invalid_parameters_raise_validation_errors():
    """TC-CHK-10: Out-of-bounds parameters raise explicit ValueError."""
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        TextChunker(chunk_size=0)

    with pytest.raises(ValueError, match="chunk_overlap cannot be negative"):
        TextChunker(chunk_size=500, chunk_overlap=-10)

    with pytest.raises(ValueError, match="must be strictly less than chunk_size"):
        TextChunker(chunk_size=200, chunk_overlap=200)

    chunker = TextChunker()
    with pytest.raises(ValueError, match="document_id cannot be blank"):
        chunker.chunk_document("", "std_1", ["valid text"])

    with pytest.raises(ValueError, match="student_id cannot be blank"):
        chunker.chunk_document("doc_1", "", ["valid text"])
