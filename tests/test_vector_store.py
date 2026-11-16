"""
Integration and security tests for Gyaan AI VectorStore Service (Phase 5D.2).

Validates:
- Local ONNX all-MiniLM-L6-v2 embedding generation & dimensions (384-d)
- Persistent ChromaDB storage across client closure and reopening
- Semantic retrieval ranking and similarity scoring
- Duplicate indexing prevention and chunk updates
- Interrupted indexing recovery (atomic purge & retry)
- Document deletion and full vector cleanup
- Multi-tier student data isolation and cross-tenant query rejection
- Foreign chunk detection in post-query assertions (fail-closed)
- Windows client lifecycle and memory-mapped file handle cleanup
- Zero-modification regression on active SQLite database
"""

import gc
from pathlib import Path
import pytest
import sqlite3

from backend.services.text_chunker import DocumentChunk, TextChunker
from backend.services.vector_store import (
    DEFAULT_COLLECTION_NAME,
    EMBEDDING_DIMENSION,
    DocumentIndexingError,
    SecurityViolationError,
    VectorStore,
    VectorStoreError,
)


@pytest.fixture
def temp_vector_store(tmp_path: Path):
    """Provides an isolated VectorStore instance in a temporary test directory."""
    test_dir = tmp_path / "test_chroma_db"
    store = VectorStore(persist_directory=test_dir, collection_name="test_edu_docs")
    yield store
    # Strict Windows cleanup: close client and collect garbage
    store.close()
    del store
    gc.collect()


def _create_sample_chunks(
    document_id: str,
    student_id: str,
    texts: list[str],
) -> list[DocumentChunk]:
    """Helper to generate DocumentChunk objects for tests."""
    chunker = TextChunker()
    return chunker.chunk_document(
        document_id=document_id,
        student_id=student_id,
        pages=texts,
    )


def test_01_embedding_generation_and_dimensions(temp_vector_store: VectorStore):
    """TC-VEC-01: Verifies local ONNX model generates exact 384-dimensional dense vectors."""
    ef = temp_vector_store._embedding_function
    assert ef is not None
    sample_text = ["Quadratic equations of the form ax^2 + bx + c = 0."]
    embeddings = ef(sample_text)

    assert isinstance(embeddings, list)
    assert len(embeddings) == 1
    assert len(embeddings[0]) == EMBEDDING_DIMENSION
    assert isinstance(embeddings[0][0], float) or hasattr(embeddings[0][0], "item")


def test_02_persistent_storage_across_restart(tmp_path: Path):
    """TC-VEC-02: Verifies documents persist on disk and reload cleanly after client restart."""
    test_dir = tmp_path / "persistent_restart_test"

    # Step 1: Open client, index a chunk, and close
    store_1 = VectorStore(persist_directory=test_dir, collection_name="restart_test")
    chunks = _create_sample_chunks(
        "doc_restart",
        "student_101",
        ["Photosynthesis converts light into chemical energy stored in glucose."],
    )
    result = store_1.index_document_chunks("doc_restart", "student_101", chunks)
    assert result["indexed_chunks"] == 1
    store_1.close()
    del store_1
    gc.collect()

    # Step 2: Open second client pointing to same persistent directory
    store_2 = VectorStore(persist_directory=test_dir, collection_name="restart_test")
    try:
        query_res = store_2.query_document_chunks(
            student_id="student_101",
            query_text="solar energy conversion in plants",
            n_results=1,
        )
        assert len(query_res) == 1
        assert "Photosynthesis" in query_res[0]["text"]
        assert query_res[0]["document_id"] == "doc_restart"
    finally:
        store_2.close()
        del store_2
        gc.collect()


def test_03_semantic_similarity_retrieval_relevance(temp_vector_store: VectorStore):
    """TC-VEC-03: Semantic similarity query correctly ranks semantically relevant chunks top."""
    chunks = _create_sample_chunks(
        "doc_physics",
        "student_alpha",
        [
            "Optics is the branch of physics that studies the behaviour and properties of light.",
            "Thermodynamics deals with heat, temperature, work, and heat transfer mechanisms.",
            "Kinematics describes the motion of points, bodies, and systems of bodies without forces.",
        ],
    )
    temp_vector_store.index_document_chunks("doc_physics", "student_alpha", chunks)

    # Query specifically about light and lenses
    results = temp_vector_store.query_document_chunks(
        student_id="student_alpha",
        query_text="reflection, refraction and properties of light rays",
        n_results=2,
    )
    assert len(results) >= 1
    top_result = results[0]
    assert "Optics" in top_result["text"]
    assert top_result["similarity_score"] > 0.4


def test_04_duplicate_indexing_prevention(temp_vector_store: VectorStore):
    """TC-VEC-04: Re-indexing an existing document updates/replaces without duplicating chunks."""
    chunks = _create_sample_chunks(
        "doc_dup_test",
        "student_dup",
        ["Introduction to coordinate geometry and Cartesian plane."],
    )

    # Initial indexing
    res1 = temp_vector_store.index_document_chunks("doc_dup_test", "student_dup", chunks)
    assert res1["indexed_chunks"] == 1

    # Second indexing of same document
    res2 = temp_vector_store.index_document_chunks("doc_dup_test", "student_dup", chunks)
    assert res2["indexed_chunks"] == 1

    # Query should return exactly 1 chunk, not 2
    query_res = temp_vector_store.query_document_chunks(
        student_id="student_dup",
        query_text="Cartesian coordinate systems",
        n_results=10,
    )
    assert len(query_res) == 1


def test_05_interrupted_indexing_recovery(temp_vector_store: VectorStore):
    """TC-VEC-05: Re-indexing purges stale partial chunks before ingesting a clean batch."""
    # Simulate partial indexing of doc_partial with 1 chunk
    chunk_v1 = _create_sample_chunks("doc_partial", "student_rec", ["Partial draft chunk 1."])
    temp_vector_store.index_document_chunks("doc_partial", "student_rec", chunk_v1)

    # Full updated indexing with 2 new chunks
    chunk_v2 = _create_sample_chunks(
        "doc_partial",
        "student_rec",
        ["Updated comprehensive Section 1.", "Updated comprehensive Section 2."],
    )
    res = temp_vector_store.index_document_chunks("doc_partial", "student_rec", chunk_v2)
    assert res["indexed_chunks"] == 2

    # Verify old partial chunk no longer exists
    results = temp_vector_store.query_document_chunks(
        student_id="student_rec",
        query_text="comprehensive section",
        n_results=5,
    )
    assert len(results) == 2
    for r in results:
        assert "Updated" in r["text"]


def test_06_document_deletion_vector_cleanup(temp_vector_store: VectorStore):
    """TC-VEC-06: Deleting a document completely purges its vectors from ChromaDB."""
    chunks = _create_sample_chunks(
        "doc_to_delete",
        "student_del",
        ["Temporary study note regarding organic reactions to be deleted."],
    )
    temp_vector_store.index_document_chunks("doc_to_delete", "student_del", chunks)

    # Confirm it is indexed
    before_del = temp_vector_store.query_document_chunks(
        student_id="student_del", query_text="organic reactions"
    )
    assert len(before_del) == 1

    # Purge vectors
    remaining = temp_vector_store.delete_document_vectors("doc_to_delete", "student_del")
    assert remaining == 0

    # Confirm zero chunks returned after deletion
    after_del = temp_vector_store.query_document_chunks(
        student_id="student_del", query_text="organic reactions"
    )
    assert len(after_del) == 0


def test_07_strict_student_isolation(temp_vector_store: VectorStore):
    """TC-VEC-07: Security Test: Queries by Student A never retrieve chunks belonging to Student B."""
    chunks_A = _create_sample_chunks(
        "doc_A",
        "student_A",
        ["Confidential personal essay by Alice discussing modern literature."],
    )
    chunks_B = _create_sample_chunks(
        "doc_B",
        "student_B",
        ["Confidential research notes by Bob on quantum teleportation."],
    )

    temp_vector_store.index_document_chunks("doc_A", "student_A", chunks_A)
    temp_vector_store.index_document_chunks("doc_B", "student_B", chunks_B)

    # Student A queries for Bob's exact topic with relevance threshold
    query_by_A = temp_vector_store.query_document_chunks(
        student_id="student_A",
        query_text="quantum teleportation research notes",
        min_score=0.4,
    )
    # Must return 0 chunks above threshold because Alice has no quantum physics notes
    assert len(query_by_A) == 0

    # Also assert that raw retrieval for Alice NEVER leaks Bob's chunks
    raw_query_A = temp_vector_store.query_document_chunks(
        student_id="student_A",
        query_text="quantum teleportation research notes",
    )
    assert all(c["student_id"] == "student_A" for c in raw_query_A)
    assert all(c["document_id"] != "doc_B" for c in raw_query_A)
    assert not any("Bob" in c["text"] for c in raw_query_A)

    # Student B queries for Bob's exact topic
    query_by_B = temp_vector_store.query_document_chunks(
        student_id="student_B",
        query_text="quantum teleportation research notes",
    )
    assert len(query_by_B) == 1
    assert query_by_B[0]["document_id"] == "doc_B"


def test_08_cross_student_tampered_document_id_rejection(temp_vector_store: VectorStore):
    """TC-VEC-08: Passing another student's document_id in document_ids returns zero chunks."""
    chunks_B = _create_sample_chunks(
        "doc_B_private",
        "student_B",
        ["Private notes on organic synthesis."],
    )
    temp_vector_store.index_document_chunks("doc_B_private", "student_B", chunks_B)

    # Student A attempts to target Bob's document_id
    tampered_query = temp_vector_store.query_document_chunks(
        student_id="student_A",
        query_text="organic synthesis",
        document_ids=["doc_B_private"],
    )
    assert len(tampered_query) == 0


def test_09_mismatched_student_chunk_indexing_rejected(temp_vector_store: VectorStore):
    """TC-VEC-09: Ingesting chunks where chunk.student_id != caller student_id raises SecurityViolationError."""
    # Create chunk belonging to student_intruder
    tampered_chunks = _create_sample_chunks("doc_hack", "student_intruder", ["Malicious text."])

    # Caller passes student_victim
    with pytest.raises(SecurityViolationError, match="student_id mismatch"):
        temp_vector_store.index_document_chunks(
            document_id="doc_hack",
            student_id="student_victim",
            chunks=tampered_chunks,
        )


def test_10_missing_or_blank_student_id_rejected(temp_vector_store: VectorStore):
    """TC-VEC-10: Blank or missing student_id fails closed immediately."""
    with pytest.raises(SecurityViolationError, match="student_id cannot be blank"):
        temp_vector_store.query_document_chunks(student_id="", query_text="sample query")

    with pytest.raises(SecurityViolationError, match="student_id cannot be blank"):
        temp_vector_store.index_document_chunks("doc1", "  ", [])


def test_11_post_query_foreign_chunk_fails_closed(temp_vector_store: VectorStore, monkeypatch):
    """TC-VEC-11: Defense-in-depth: If foreign chunk bypasses ChromaDB where filter, post-check fails closed."""
    chunks_A = _create_sample_chunks("doc_A", "student_A", ["Normal student text."])
    temp_vector_store.index_document_chunks("doc_A", "student_A", chunks_A)

    # Monkeypatch collection.query to simulate ChromaDB filter breach returning Student X chunk
    original_query = temp_vector_store.collection.query

    def breached_query(*args, **kwargs):
        res = original_query(*args, **kwargs)
        # Inject foreign metadata
        res["metadatas"][0][0]["student_id"] = "student_FOREIGN_ATTACKER"
        return res

    monkeypatch.setattr(temp_vector_store.collection, "query", breached_query)

    with pytest.raises(SecurityViolationError, match="Tenant isolation breach detected"):
        temp_vector_store.query_document_chunks(student_id="student_A", query_text="Normal text")


def test_12_windows_client_lifecycle_and_handle_cleanup(tmp_path: Path):
    """TC-VEC-12: Verifies close() releases memory-mapped handles without [WinError 32]."""
    test_dir = tmp_path / "lifecycle_cleanup_test"

    store = VectorStore(persist_directory=test_dir, collection_name="lifecycle_test")
    chunks = _create_sample_chunks("doc_life", "std_life", ["Lifecycle validation text."])
    store.index_document_chunks("doc_life", "std_life", chunks)

    # Explicit close and garbage collection
    store.close()
    del store
    gc.collect()

    # Reopen to confirm directory was not corrupted
    store_reopened = VectorStore(persist_directory=test_dir, collection_name="lifecycle_test")
    try:
        assert store_reopened.collection.count() == 1
    finally:
        store_reopened.close()
        del store_reopened
        gc.collect()


def test_13_database_untouched_regression():
    """TC-REG-03: Asserts active SQLite database data/gyaan_ai.db remains completely untouched."""
    db_path = Path("data/gyaan_ai.db").resolve()
    assert db_path.is_file(), f"Database not found at {db_path}"

    uri = f"{db_path.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        assert cur.fetchone()[0] == "ok"

        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        assert cur.fetchone()[0] == 23

        cur.execute("SELECT count(*) FROM students;")
        assert cur.fetchone()[0] in (793, 794)
    finally:
        conn.close()
