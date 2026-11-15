"""
Gyaan AI - Phase 5D.6 Frontend Document Library & Teacher RAG Integration Tests.

Comprehensive integration test suite verifying the end-to-end contract between
the frontend Document Library & Teacher Studio and the FastAPI backend:
1. Document upload success (multipart PDF <= 10MB) returning valid DocumentMetadataResponse.
2. Oversized PDF rejection (> 10MB -> HTTP 413 Payload Too Large).
3. Non-PDF file rejection (HTTP 400 Bad Request).
4. Unauthenticated upload rejection (HTTP 401 Unauthorized).
5. Document listing strictly scoped to authenticated student (multi-tenant isolation).
6. Single document metadata retrieval (200 for owner, 404 for foreign/missing).
7. Semantic search with relevance scores and page citations.
8. Foreign document search rejection (HTTP 403 Forbidden).
9. Missing document search rejection (HTTP 404 Not Found).
10. Document deletion and vector store chunk purging.
11. Foreign document delete rejection (HTTP 404 Not Found).
12. Teacher Agent /api/v1/ask with document_ids returning 7-field provenance.
13. Teacher Agent anonymous request with document_ids rejected (HTTP 401).
14. Teacher Agent public NCERT inquiry without documents (unauthenticated allowed).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import os
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient
import pypdf
import pytest

from backend.app.main import app
from backend.app.routers.documents import get_document_service
from backend.db.database import (
    create_session,
    create_student_account,
    get_document_record,
    init_db,
)
from backend.services.auth_service import hash_session_token
from backend.services.document_service import DocumentService
from backend.services.vector_store import VectorStore


# ============================================================================
# Synthetic PDF Generator Helper
# ============================================================================

def _generate_valid_pdf_bytes(text_content: str = "CBSE Class 10 Science - Ohm's Law and Resistance") -> bytes:
    """Generates a valid single-page PDF containing text_content."""
    writer = pypdf.PdfWriter()
    stream_content = f"BT\n/F1 12 Tf\n100 700 Td\n({text_content}) Tj\nET\n".encode("latin1")
    stream_len = len(stream_content)

    parts = [
        b"%PDF-1.4\n",
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("latin1"),
        stream_content,
        b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        b"xref\n0 6\n",
        b"0000000000 65535 f \n",
        b"0000000009 00000 n \n",
        b"0000000058 00000 n \n",
        b"0000000115 00000 n \n",
        b"0000000244 00000 n \n",
        b"0000000350 00000 n \n",
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n",
        b"startxref\n432\n%%EOF\n",
    ]
    return b"".join(parts)


# ============================================================================
# Test Environment Fixture
# ============================================================================

@pytest.fixture
def doc_test_env(tmp_path: Path) -> Generator[Dict[str, Any], None, None]:
    """Isolated test environment with dedicated SQLite DB and ChromaDB vector store."""
    temp_db = tmp_path / "test_frontend_docs.db"
    temp_storage = tmp_path / "storage"
    temp_chroma = tmp_path / "chromadb"
    temp_storage.mkdir(parents=True, exist_ok=True)
    temp_chroma.mkdir(parents=True, exist_ok=True)

    # Set environment variables for test isolation guard
    os.environ["GYAAN_DB_PATH"] = str(temp_db)
    os.environ["GYAAN_TEST_MODE"] = "1"

    init_db(temp_db)

    # Register Student A (Alice) and Student B (Bob)
    student_a = create_student_account(
        "stu_alice_frontend",
        "alice@gyaan.ai",
        "hash_alice",
        "Alice Frontend",
        custom_path=temp_db,
    )
    student_b = create_student_account(
        "stu_bob_frontend",
        "bob@gyaan.ai",
        "hash_bob",
        "Bob Frontend",
        custom_path=temp_db,
    )

    # Create active sessions
    token_a = "tok_alice_session_frontend_test_12345"
    token_b = "tok_bob_session_frontend_test_67890"
    exp = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    create_session("sess_alice", student_a["id"], hash_session_token(token_a), exp, custom_path=temp_db)
    create_session("sess_bob", student_b["id"], hash_session_token(token_b), exp, custom_path=temp_db)

    # Initialize isolated VectorStore and DocumentService
    vector_store = VectorStore(persist_directory=temp_chroma)
    doc_service = DocumentService(
        storage_dir=temp_storage,
        vector_store=vector_store,
        db_path=temp_db,
    )

    # Override document service dependency in FastAPI app
    app.dependency_overrides[get_document_service] = lambda: doc_service

    client = TestClient(app)

    yield {
        "db_path": temp_db,
        "storage_dir": temp_storage,
        "chroma_dir": temp_chroma,
        "service": doc_service,
        "vector_store": vector_store,
        "client": client,
        "student_a": student_a["id"],
        "token_a": token_a,
        "student_b": student_b["id"],
        "token_b": token_b,
    }

    # Teardown
    app.dependency_overrides.clear()
    doc_service.close()
    vector_store.close()
    if "GYAAN_DB_PATH" in os.environ:
        del os.environ["GYAAN_DB_PATH"]


# ============================================================================
# 1. Document Upload Success (Multipart PDF <= 10MB)
# ============================================================================

def test_01_document_upload_success_multipart_pdf(doc_test_env):
    """Verify authenticated multipart PDF upload creates document record and returns 201."""
    client: TestClient = doc_test_env["client"]
    token: str = doc_test_env["token_a"]

    pdf_bytes = _generate_valid_pdf_bytes("Ohm's Law: V = IR. Resistance depends on length and area.")
    files = {"file": ("class10_science_notes.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/api/v1/documents/upload", files=files, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert "id" in data
    assert data["student_id"] == doc_test_env["student_a"]
    assert data["filename"] == "class10_science_notes.pdf"
    assert data["file_size"] == len(pdf_bytes)
    assert data["content_type"] == "application/pdf"
    assert data["page_count"] == 1
    assert data["chunk_count"] >= 1
    assert data["indexing_status"] == "INDEXED"
    assert data["error_message"] is None


# ============================================================================
# 2. Oversized PDF Rejection (> 10MB -> HTTP 413)
# ============================================================================

def test_02_oversized_pdf_rejection_http_413(doc_test_env):
    """Verify upload exceeding 10 MB limit is rejected with HTTP 413."""
    client: TestClient = doc_test_env["client"]
    token: str = doc_test_env["token_a"]

    # 10 MB + 1 KB oversized payload
    oversized_bytes = b"%PDF-1.4\n" + b"A" * (10 * 1024 * 1024 + 1024)
    files = {"file": ("huge_textbook.pdf", io.BytesIO(oversized_bytes), "application/pdf")}
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/api/v1/documents/upload", files=files, headers=headers)
    assert response.status_code == 413
    assert "exceeds" in response.json().get("detail", "").lower()


# ============================================================================
# 3. Non-PDF File Rejection (HTTP 400)
# ============================================================================

def test_03_non_pdf_file_rejection_http_400(doc_test_env):
    """Verify non-PDF file upload is rejected with HTTP 400."""
    client: TestClient = doc_test_env["client"]
    token: str = doc_test_env["token_a"]

    text_bytes = b"This is a plain text file, not a valid PDF document."
    files = {"file": ("notes.txt", io.BytesIO(text_bytes), "text/plain")}
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/api/v1/documents/upload", files=files, headers=headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "pdf" in response.json().get("detail", "").lower()


# ============================================================================
# 4. Unauthenticated Upload Rejection (HTTP 401)
# ============================================================================

def test_04_unauthenticated_upload_rejection_http_401(doc_test_env):
    """Verify upload without valid authentication token is rejected with HTTP 401."""
    client: TestClient = doc_test_env["client"]

    pdf_bytes = _generate_valid_pdf_bytes("Sample notes content")
    files = {"file": ("sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    # No Authorization header
    response = client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # Invalid token
    response_invalid = client.post(
        "/api/v1/documents/upload",
        files=files,
        headers={"Authorization": "Bearer invalid_nonexistent_token"},
    )
    assert response_invalid.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# 5. Document Listing Scoped to Student (Multi-Tenant Isolation)
# ============================================================================

def test_05_document_listing_scoped_to_student(doc_test_env):
    """Verify student A only lists student A's documents, and student B only lists student B's."""
    client: TestClient = doc_test_env["client"]
    token_a: str = doc_test_env["token_a"]
    token_b: str = doc_test_env["token_b"]

    # Student A uploads document
    pdf_a = _generate_valid_pdf_bytes("Alice's private biology notes on photosynthesis")
    client.post(
        "/api/v1/documents/upload",
        files={"file": ("alice_bio.pdf", io.BytesIO(pdf_a), "application/pdf")},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # Student B uploads document
    pdf_b = _generate_valid_pdf_bytes("Bob's private chemistry notes on acids and bases")
    client.post(
        "/api/v1/documents/upload",
        files={"file": ("bob_chem.pdf", io.BytesIO(pdf_b), "application/pdf")},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    # List as Student A
    resp_a = client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == status.HTTP_200_OK
    docs_a = resp_a.json()
    assert len(docs_a) == 1
    assert docs_a[0]["filename"] == "alice_bio.pdf"
    assert docs_a[0]["student_id"] == doc_test_env["student_a"]

    # List as Student B
    resp_b = client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == status.HTTP_200_OK
    docs_b = resp_b.json()
    assert len(docs_b) == 1
    assert docs_b[0]["filename"] == "bob_chem.pdf"
    assert docs_b[0]["student_id"] == doc_test_env["student_b"]


# ============================================================================
# 6. Single Document Metadata Retrieval
# ============================================================================

def test_06_single_document_metadata_retrieval(doc_test_env):
    """Verify owner retrieves metadata (200), foreign student gets 404, unknown ID gets 404."""
    client: TestClient = doc_test_env["client"]
    token_a: str = doc_test_env["token_a"]
    token_b: str = doc_test_env["token_b"]

    # Alice uploads a document
    pdf_bytes = _generate_valid_pdf_bytes("Light reflection and refraction laws")
    upload_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("physics_light.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc_id = upload_res.json()["id"]

    # Alice gets her own document
    get_res = client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["id"] == doc_id
    assert get_res.json()["filename"] == "physics_light.pdf"

    # Bob tries to access Alice's document -> 404 (prevents document existence leakage)
    foreign_res = client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert foreign_res.status_code == status.HTTP_404_NOT_FOUND

    # Alice accesses non-existent document -> 404
    missing_res = client.get("/api/v1/documents/doc_does_not_exist_999", headers={"Authorization": f"Bearer {token_a}"})
    assert missing_res.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# 7. Semantic Search with Relevance Scores and Page Citations
# ============================================================================

def test_07_semantic_search_with_relevance_scores_and_page_citations(doc_test_env):
    """Verify semantic search returns relevant chunk excerpts with page numbers and scores."""
    client: TestClient = doc_test_env["client"]
    token_a: str = doc_test_env["token_a"]

    pdf_bytes = _generate_valid_pdf_bytes(
        "Ohm's Law states that potential difference V across ends of conductor is proportional to current I. V = I * R."
    )
    client.post(
        "/api/v1/documents/upload",
        files={"file": ("electricity_notes.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    search_payload = {
        "query": "What is the formula for Ohm's law?",
        "max_results": 3,
        "min_score": 0.0,
    }
    search_res = client.post(
        "/api/v1/documents/search",
        json=search_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert search_res.status_code == status.HTTP_200_OK
    data = search_res.json()
    assert data["query"] == search_payload["query"]
    assert data["results_count"] >= 1
    first_result = data["results"][0]
    assert "chunk_id" in first_result
    assert first_result["page_number"] == 1
    assert "similarity_score" in first_result
    assert first_result["similarity_score"] >= 0.0
    assert "text" in first_result
    assert "Ohm" in first_result["text"]


# ============================================================================
# 8. Foreign Document Search Rejection (HTTP 403)
# ============================================================================

def test_08_foreign_document_search_rejection_http_403(doc_test_env):
    """Verify querying another student's document ID in search raises HTTP 403."""
    client: TestClient = doc_test_env["client"]
    token_a: str = doc_test_env["token_a"]
    token_b: str = doc_test_env["token_b"]

    # Bob uploads a document
    pdf_b = _generate_valid_pdf_bytes("Bob's secret formula book")
    upload_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("bobs_formulas.pdf", io.BytesIO(pdf_b), "application/pdf")},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    bob_doc_id = upload_res.json()["id"]

    # Alice explicitly searches Bob's document ID
    search_payload = {
        "query": "formula",
        "document_ids": [bob_doc_id],
    }
    search_res = client.post(
        "/api/v1/documents/search",
        json=search_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert search_res.status_code == status.HTTP_403_FORBIDDEN
    assert "belong" in search_res.json().get("detail", "").lower() or "not authorized" in search_res.json().get("detail", "").lower()


# ============================================================================
# 9. Missing Document Search Rejection (HTTP 404)
# ============================================================================

def test_09_missing_document_search_rejection_http_404(doc_test_env):
    """Verify querying non-existent document ID raises HTTP 404."""
    client: TestClient = doc_test_env["client"]
    token_a: str = doc_test_env["token_a"]

    search_payload = {
        "query": "any query",
        "document_ids": ["doc_phantom_12345"],
    }
    search_res = client.post(
        "/api/v1/documents/search",
        json=search_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert search_res.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in search_res.json().get("detail", "").lower()


# ============================================================================
# 10. Document Deletion and Vector Store Purge
# ============================================================================

def test_10_document_deletion_and_vector_store_purge(doc_test_env):
    """Verify document deletion removes SQLite record and purges vector store embeddings."""
    client: TestClient = doc_test_env["client"]
    token_a: str = doc_test_env["token_a"]
    vs: VectorStore = doc_test_env["vector_store"]

    pdf_bytes = _generate_valid_pdf_bytes("Digestive system and gastric enzymes")
    upload_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("digestion.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc_id = upload_res.json()["id"]

    # Verify chunks exist in vector store
    chunks_before = vs.collection.get(where={"document_id": {"$eq": doc_id}})["ids"]
    assert len(chunks_before) >= 1

    # Delete the document
    del_res = client.delete(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert del_res.status_code == status.HTTP_200_OK
    del_data = del_res.json()
    assert del_data["success"] is True
    assert del_data["document_id"] == doc_id

    # Verify document no longer retrieved from API
    get_res = client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert get_res.status_code == status.HTTP_404_NOT_FOUND

    # Verify vector store chunks are purged
    chunks_after = vs.collection.get(where={"document_id": {"$eq": doc_id}})["ids"]
    assert len(chunks_after) == 0


# ============================================================================
# 11. Foreign Document Delete Rejection (HTTP 404)
# ============================================================================

def test_11_foreign_document_delete_rejection_http_404(doc_test_env):
    """Verify attempting to delete another student's document returns HTTP 404."""
    client: TestClient = doc_test_env["client"]
    token_a: str = doc_test_env["token_a"]
    token_b: str = doc_test_env["token_b"]

    # Bob uploads a document
    pdf_b = _generate_valid_pdf_bytes("Bob's physics revision notes")
    upload_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("bobs_notes.pdf", io.BytesIO(pdf_b), "application/pdf")},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    bob_doc_id = upload_res.json()["id"]

    # Alice tries to delete Bob's document
    del_res = client.delete(f"/api/v1/documents/{bob_doc_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert del_res.status_code == status.HTTP_404_NOT_FOUND

    # Verify Bob's document is still intact
    get_res = client.get(f"/api/v1/documents/{bob_doc_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert get_res.status_code == status.HTTP_200_OK


# ============================================================================
# 12. Teacher Agent /api/v1/ask with document_ids Returns 7-Field Provenance
# ============================================================================

def test_12_teacher_agent_ask_with_document_ids_returns_provenance(doc_test_env):
    """Verify /api/v1/ask grounds response using student notes and returns full 7-field provenance."""
    client: TestClient = doc_test_env["client"]
    token_a: str = doc_test_env["token_a"]

    pdf_bytes = _generate_valid_pdf_bytes(
        "Electric current I = Q/t where Q is charge in coulombs and t is time in seconds. 1 Ampere = 1 Coulomb/sec."
    )
    upload_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("current_definition.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc_id = upload_res.json()["id"]

    mock_result = MagicMock()
    mock_result.raw = "Electric current is the rate of flow of electric charge through a conductor (I = Q/t)."

    doc_svc = doc_test_env["service"]
    with patch("backend.services.resource_retriever.DocumentService", return_value=doc_svc), \
         patch("backend.app.main.build_teacher_crew") as mock_builder:
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_result
        mock_builder.return_value = mock_crew

        ask_payload = {
            "question": "What is electric current and how is it defined in my notes?",
            "grade": "Class 10",
            "subject": "Science",
            "topic": "Electric current and charge definition",
            "document_ids": [doc_id],
        }
        ask_res = client.post(
            "/api/v1/ask",
            json=ask_payload,
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert ask_res.status_code == status.HTTP_200_OK
        data = ask_res.json()
        assert data["status"] == "success"
        assert "student_documents" in data
        assert data["student_documents"] is not None
        assert len(data["student_documents"]) >= 1

        first_doc = data["student_documents"][0]
        # Verify all 7 provenance fields
        assert "document_id" in first_doc and first_doc["document_id"] == doc_id
        assert "filename" in first_doc and first_doc["filename"] == "current_definition.pdf"
        assert "chunk_id" in first_doc
        assert "page_number" in first_doc and first_doc["page_number"] == 1
        assert "chunk_index" in first_doc
        assert "similarity_score" in first_doc and first_doc["similarity_score"] >= 0.0
        assert "text" in first_doc and "Electric current" in first_doc["text"]


# ============================================================================
# 13. Teacher Agent Anonymous Request with document_ids Rejected (HTTP 401)
# ============================================================================

def test_13_teacher_agent_anonymous_request_with_document_ids_rejected_401(doc_test_env):
    """Verify /api/v1/ask with document_ids but without auth token is rejected with HTTP 401."""
    client: TestClient = doc_test_env["client"]

    ask_payload = {
        "question": "Explain Ohm's Law from my notes",
        "grade": "Class 10",
        "subject": "Science",
        "document_ids": ["doc_any_id_123"],
    }
    # No Authorization header
    ask_res = client.post("/api/v1/ask", json=ask_payload)
    assert ask_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "authentication required" in ask_res.json().get("detail", "").lower()


# ============================================================================
# 14. Teacher Agent Public NCERT Inquiry Without Documents
# ============================================================================

def test_14_teacher_agent_public_ncert_inquiry_without_documents(doc_test_env):
    """Verify /api/v1/ask without document_ids operates normally without authentication."""
    client: TestClient = doc_test_env["client"]

    mock_result = MagicMock()
    mock_result.raw = "Photosynthesis is the process by which green plants make food from CO2 and water."

    with patch("backend.app.main.build_teacher_crew") as mock_builder:
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_result
        mock_builder.return_value = mock_crew

        ask_payload = {
            "question": "What is photosynthesis?",
            "grade": "Class 10",
            "subject": "Science",
            "chapter": "Life Processes",
        }
        # No Authorization header and no document_ids
        ask_res = client.post("/api/v1/ask", json=ask_payload)
        assert ask_res.status_code == status.HTTP_200_OK
        data = ask_res.json()
        assert data["status"] == "success"
        assert data["student_documents"] is None
        assert "Photosynthesis" in data["answer"]
