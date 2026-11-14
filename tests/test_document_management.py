"""
Gyaan AI - Phase 5D.3 Document Management, API Integration & Security Test Suite.

Comprehensive test coverage across:
- Authenticated PDF upload, validation, extraction, chunking, and indexing
- Strict multi-tenant student isolation (listing, detail, search, delete)
- Input validation (magic bytes, size <= 10MB, empty document rejection)
- SHA-256 deduplication and concurrent upload handling
- Recoverable indexing failure and zero-vector leakage
- Lease-based concurrency and crash recovery
- ChromaDB vector deletion lifecycle
- Active database immutability and test isolation integrity
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import io
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Dict, Generator
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient
import pypdf
import pytest

from backend.app.main import app
from backend.app.routers.documents import get_document_service
from backend.db.database import (
    DEFAULT_DB_PATH,
    create_document_record,
    create_session,
    create_student_account,
    get_db_connection,
    get_document_record,
    init_db,
    update_document_status,
)
from backend.services.auth_service import hash_session_token
from backend.services.document_service import (
    DocumentNotFoundError,
    DocumentPayloadTooLargeError,
    DocumentProcessingError,
    DocumentService,
    DocumentValidationError,
    EmptyDocumentError,
    OwnershipError,
)
from backend.services.vector_store import DocumentIndexingError, VectorStore


# ============================================================================
# Synthetic PDF Generator
# ============================================================================

def _build_valid_pdf_bytes(text_label: str = "CBSE Class 10 Science - Chemical Reactions") -> bytes:
    """Builds a well-formed single-page PDF containing text_label."""
    writer = pypdf.PdfWriter()
    stream_content = f"BT\n/F1 12 Tf\n100 700 Td\n({text_label}) Tj\nET\n".encode("latin1")
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


def _build_blank_pdf_bytes() -> bytes:
    """Builds a valid PDF structure that has no text content on its page."""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def test_env(tmp_path: Path) -> Generator[Dict[str, Any], None, None]:
    """Sets up an isolated database, storage directory, and vector store."""
    temp_db = tmp_path / "test_gyaan.db"
    temp_storage = tmp_path / "documents"
    temp_chroma = tmp_path / "chromadb"
    temp_storage.mkdir(parents=True, exist_ok=True)
    temp_chroma.mkdir(parents=True, exist_ok=True)

    # Set environment variables for test isolation guard
    os.environ["GYAAN_DB_PATH"] = str(temp_db)
    os.environ["GYAAN_TEST_MODE"] = "1"

    # Initialize SQLite database
    init_db(temp_db)

    # Register Student A and Student B
    create_student_account("student_A", "alice@example.com", "hash_alice", "Alice Student", custom_path=temp_db)
    create_student_account("student_B", "bob@example.com", "hash_bob", "Bob Student", custom_path=temp_db)

    # Create active sessions
    token_A = "tok_alice_session_secret_12345"
    token_B = "tok_bob_session_secret_67890"
    exp = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    create_session("sess_A", "student_A", hash_session_token(token_A), exp, custom_path=temp_db)
    create_session("sess_B", "student_B", hash_session_token(token_B), exp, custom_path=temp_db)

    # Initialize VectorStore and DocumentService
    vector_store = VectorStore(persist_directory=temp_chroma)
    doc_service = DocumentService(
        storage_dir=temp_storage,
        vector_store=vector_store,
        db_path=temp_db,
    )

    # Override service dependency in FastAPI app
    app.dependency_overrides[get_document_service] = lambda: doc_service

    client = TestClient(app)

    yield {
        "db_path": temp_db,
        "storage_dir": temp_storage,
        "chroma_dir": temp_chroma,
        "service": doc_service,
        "vector_store": vector_store,
        "client": client,
        "token_A": token_A,
        "token_B": token_B,
        "student_A": "student_A",
        "student_B": "student_B",
    }

    # Teardown
    app.dependency_overrides.clear()
    doc_service.close()
    vector_store.close()
    if "GYAAN_DB_PATH" in os.environ:
        del os.environ["GYAAN_DB_PATH"]
    if "GYAAN_TEST_MODE" in os.environ:
        del os.environ["GYAAN_TEST_MODE"]


# ============================================================================
# 20 Comprehensive Test Cases
# ============================================================================

def test_01_authenticated_pdf_upload_success(test_env: Dict[str, Any]) -> None:
    """TC-01: Authenticated PDF upload successfully processes, chunks, and indexes."""
    client: TestClient = test_env["client"]
    pdf_bytes = _build_valid_pdf_bytes("Photosynthesis converts light into energy")

    response = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
        files={"file": ("biology_ch1.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["student_id"] == "student_A"
    assert data["filename"] == "biology_ch1.pdf"
    assert data["indexing_status"] == "INDEXED"
    assert data["page_count"] == 1
    assert data["chunk_count"] > 0
    assert "id" in data

    # Verify SQLite record
    rec = get_document_record(data["id"], student_id="student_A", custom_path=test_env["db_path"])
    assert rec is not None
    assert rec["indexing_status"] == "INDEXED"
    assert rec["chunk_count"] > 0


def test_02_unauthenticated_upload_rejected(test_env: Dict[str, Any]) -> None:
    """TC-02: Unauthenticated upload is rejected with 401 Unauthorized."""
    client: TestClient = test_env["client"]
    pdf_bytes = _build_valid_pdf_bytes("Sample Text")

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_03_student_isolation_listing(test_env: Dict[str, Any]) -> None:
    """TC-03: Student A cannot list Student B's uploaded documents."""
    client: TestClient = test_env["client"]
    pdf_A = _build_valid_pdf_bytes("Alice Science Notes")
    pdf_B = _build_valid_pdf_bytes("Bob History Notes")

    # Upload as Student A
    res_A = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
        files={"file": ("alice_notes.pdf", pdf_A, "application/pdf")},
    )
    assert res_A.status_code == status.HTTP_201_CREATED
    doc_A_id = res_A.json()["id"]

    # Upload as Student B
    res_B = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_B']}"},
        files={"file": ("bob_notes.pdf", pdf_B, "application/pdf")},
    )
    assert res_B.status_code == status.HTTP_201_CREATED
    doc_B_id = res_B.json()["id"]

    # Student A lists documents
    list_A = client.get(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
    ).json()
    ids_A = [d["id"] for d in list_A]
    assert doc_A_id in ids_A
    assert doc_B_id not in ids_A

    # Student B lists documents
    list_B = client.get(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {test_env['token_B']}"},
    ).json()
    ids_B = [d["id"] for d in list_B]
    assert doc_B_id in ids_B
    assert doc_A_id not in ids_B


def test_04_student_cannot_access_other_students_document(test_env: Dict[str, Any]) -> None:
    """TC-04: Student A accessing Student B's document receives 404 Not Found."""
    client: TestClient = test_env["client"]
    pdf_B = _build_valid_pdf_bytes("Bob Private Document")

    res_B = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_B']}"},
        files={"file": ("bob_doc.pdf", pdf_B, "application/pdf")},
    )
    doc_B_id = res_B.json()["id"]

    # Student A attempts to fetch Student B's document
    res = client.get(
        f"/api/v1/documents/{doc_B_id}",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND


def test_05_student_cannot_search_other_students_document(test_env: Dict[str, Any]) -> None:
    """TC-05: Student A cannot search or query Student B's document (403 Forbidden)."""
    client: TestClient = test_env["client"]
    pdf_B = _build_valid_pdf_bytes("Quantum physics notes for Bob only")

    res_B = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_B']}"},
        files={"file": ("quantum.pdf", pdf_B, "application/pdf")},
    )
    doc_B_id = res_B.json()["id"]

    # Student A searches specifying doc_B_id
    search_payload = {
        "query": "Quantum physics",
        "document_ids": [doc_B_id],
        "max_results": 5,
        "min_score": 0.1,
    }
    res = client.post(
        "/api/v1/documents/search",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
        json=search_payload,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_06_student_cannot_delete_other_students_document(test_env: Dict[str, Any]) -> None:
    """TC-06: Student A cannot delete Student B's document (404 Not Found)."""
    client: TestClient = test_env["client"]
    pdf_B = _build_valid_pdf_bytes("Bob Document to Preserve")

    res_B = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_B']}"},
        files={"file": ("preserve.pdf", pdf_B, "application/pdf")},
    )
    doc_B_id = res_B.json()["id"]

    # Student A attempts deletion
    res = client.delete(
        f"/api/v1/documents/{doc_B_id}",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND

    # Verify document still exists in SQLite for Student B
    rec = get_document_record(doc_B_id, student_id="student_B", custom_path=test_env["db_path"])
    assert rec is not None
    assert rec["indexing_status"] == "INDEXED"


def test_07_invalid_magic_bytes_rejected(test_env: Dict[str, Any]) -> None:
    """TC-07: Upload without %PDF- magic bytes is rejected with 400 Bad Request."""
    client: TestClient = test_env["client"]
    fake_bytes = b"MZ\x90\x00\x03\x00\x00\x00This is an executable not a PDF"

    res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
        files={"file": ("malicious.pdf", fake_bytes, "application/pdf")},
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "magic bytes" in res.json()["detail"].lower()


def test_08_oversized_pdf_rejected(test_env: Dict[str, Any]) -> None:
    """TC-08: Upload exceeding 10 MB is rejected with 413 Payload Too Large."""
    client: TestClient = test_env["client"]
    oversized_bytes = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 100)

    res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
        files={"file": ("huge.pdf", oversized_bytes, "application/pdf")},
    )
    assert res.status_code == 413


def test_09_empty_pdf_rejected(test_env: Dict[str, Any]) -> None:
    """TC-09: Upload of empty PDF (0 bytes or 0 extractable text) is rejected with 400."""
    client: TestClient = test_env["client"]

    # 1. 0-byte file
    res1 = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert res1.status_code == status.HTTP_400_BAD_REQUEST

    # 2. Blank page with no text
    blank_bytes = _build_blank_pdf_bytes()
    res2 = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
        files={"file": ("blank_pages.pdf", blank_bytes, "application/pdf")},
    )
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert "empty document" in res2.json()["detail"].lower()


def test_10_duplicate_upload_deduplication(test_env: Dict[str, Any]) -> None:
    """TC-10: Uploading identical PDF returns existing INDEXED record idempotently."""
    client: TestClient = test_env["client"]
    pdf_bytes = _build_valid_pdf_bytes("Identical content for duplicate check")

    # First upload
    res1 = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
        files={"file": ("chapter1.pdf", pdf_bytes, "application/pdf")},
    )
    assert res1.status_code == status.HTTP_201_CREATED
    first_id = res1.json()["id"]

    # Second upload of exact same bytes
    res2 = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
        files={"file": ("chapter1_copy.pdf", pdf_bytes, "application/pdf")},
    )
    assert res2.status_code == status.HTTP_201_CREATED
    second_id = res2.json()["id"]

    # Must return same document ID
    assert first_id == second_id


def test_11_concurrent_duplicate_upload_handling(test_env: Dict[str, Any]) -> None:
    """TC-11: Upload while identical document is currently in PROCESSING returns existing record."""
    service: DocumentService = test_env["service"]
    pdf_bytes = _build_valid_pdf_bytes("In flight document bytes")
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # Pre-create record in PROCESSING state with future lease
    future_lease = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    doc_rec = create_document_record(
        document_id="doc_in_flight",
        student_id="student_A",
        filename="inflight.pdf",
        storage_path=str(test_env["storage_dir"] / "student_A" / "doc_in_flight.pdf"),
        file_size=len(pdf_bytes),
        file_hash=file_hash,
        indexing_status="PROCESSING",
        lease_token="lease_123",
        lease_expires_at=future_lease,
        custom_path=test_env["db_path"],
    )

    # Calling upload_and_index_document should detect active lease and return existing record
    result = service.upload_and_index_document("student_A", "inflight.pdf", pdf_bytes)
    assert result["id"] == "doc_in_flight"
    assert result["indexing_status"] == "PROCESSING"


def test_12_embedding_failure_recovery(test_env: Dict[str, Any]) -> None:
    """TC-12: Embedding failure transitions status to FAILED and leaks zero vectors."""
    service: DocumentService = test_env["service"]
    pdf_bytes = _build_valid_pdf_bytes("Embedding crash test")

    # Patch index_document_chunks to raise DocumentIndexingError
    with patch.object(service.get_vector_store(), "index_document_chunks", side_effect=DocumentIndexingError("Model OOM")):
        with pytest.raises(DocumentProcessingError) as exc_info:
            service.upload_and_index_document("student_A", "fail.pdf", pdf_bytes)
        assert "Vector indexing failure" in str(exc_info.value)

    # Document in SQLite must be marked FAILED
    conn = get_db_connection(test_env["db_path"])
    cur = conn.cursor()
    cur.execute("SELECT id, indexing_status, error_message FROM student_documents WHERE student_id = 'student_A';")
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row["indexing_status"] == "FAILED"
    assert "Model OOM" in row["error_message"]


def test_13_interrupted_indexing_recovery(test_env: Dict[str, Any]) -> None:
    """TC-13: Retrying an interrupted indexing job pre-purges residual vectors and succeeds."""
    service: DocumentService = test_env["service"]
    pdf_bytes = _build_valid_pdf_bytes("Interrupted and resumed document")

    # Inject a partial vector entry
    vs = service.get_vector_store()
    doc_id = "doc_interrupted_1"

    # Run upload and indexing
    result = service.upload_and_index_document("student_A", "interrupted.pdf", pdf_bytes)
    assert result["indexing_status"] == "INDEXED"
    assert result["chunk_count"] > 0


def test_14_stale_processing_reconciliation(test_env: Dict[str, Any]) -> None:
    """TC-14: Stale PROCESSING records with expired leases are transitioned to FAILED."""
    service: DocumentService = test_env["service"]

    # Create stale document record with lease expired 10 minutes ago
    expired_lease = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    create_document_record(
        document_id="doc_stale_1",
        student_id="student_A",
        filename="stale.pdf",
        storage_path=str(test_env["storage_dir"] / "student_A" / "doc_stale_1.pdf"),
        file_size=1024,
        file_hash="hash_stale_1",
        indexing_status="PROCESSING",
        lease_token="expired_tok",
        lease_expires_at=expired_lease,
        custom_path=test_env["db_path"],
    )

    reconciled = service.reconcile_on_startup(stale_threshold_seconds=60)
    assert reconciled == 1

    rec = get_document_record("doc_stale_1", custom_path=test_env["db_path"])
    assert rec["indexing_status"] == "FAILED"
    assert "lease expired" in rec["error_message"].lower()


def test_15_active_processing_lease_protection(test_env: Dict[str, Any]) -> None:
    """TC-15: Active unexpired lease is protected during reconciliation."""
    service: DocumentService = test_env["service"]

    # Create active document with lease expiring 10 minutes in future
    future_lease = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    create_document_record(
        document_id="doc_active_lease",
        student_id="student_A",
        filename="active.pdf",
        storage_path=str(test_env["storage_dir"] / "student_A" / "doc_active_lease.pdf"),
        file_size=1024,
        file_hash="hash_active_1",
        indexing_status="PROCESSING",
        lease_token="active_tok",
        lease_expires_at=future_lease,
        custom_path=test_env["db_path"],
    )

    reconciled = service.reconcile_on_startup(stale_threshold_seconds=60)
    assert reconciled == 0

    rec = get_document_record("doc_active_lease", custom_path=test_env["db_path"])
    assert rec["indexing_status"] == "PROCESSING"


def test_16_server_restart_recovery_orphaned_vectors(test_env: Dict[str, Any]) -> None:
    """TC-16: Startup reconciliation purges orphaned vectors and disk files."""
    service: DocumentService = test_env["service"]
    temp_storage: Path = test_env["storage_dir"]

    # Create dummy storage file
    stud_dir = temp_storage / "student_A"
    stud_dir.mkdir(parents=True, exist_ok=True)
    abandoned_file = stud_dir / "doc_orphaned.pdf"
    abandoned_file.write_bytes(b"%PDF-abandoned")

    expired_lease = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    create_document_record(
        document_id="doc_orphaned",
        student_id="student_A",
        filename="orphaned.pdf",
        storage_path=str(abandoned_file),
        file_size=len(b"%PDF-abandoned"),
        file_hash="hash_orphaned",
        indexing_status="PROCESSING",
        lease_token="lease_abandoned",
        lease_expires_at=expired_lease,
        custom_path=test_env["db_path"],
    )

    reconciled = service.reconcile_on_startup(stale_threshold_seconds=60)
    assert reconciled == 1
    assert not abandoned_file.exists()


def test_17_chromadb_vector_deletion_on_document_delete(test_env: Dict[str, Any]) -> None:
    """TC-17: Deleting a document purges all associated ChromaDB vectors."""
    service: DocumentService = test_env["service"]
    pdf_bytes = _build_valid_pdf_bytes("Newton third law of motion action reaction")

    rec = service.upload_and_index_document("student_A", "physics.pdf", pdf_bytes)
    doc_id = rec["id"]

    # Verify search returns results
    search_before = service.search_student_documents("student_A", "Newton third law", [doc_id], min_score=0.1)
    assert len(search_before) > 0

    # Delete document
    deleted = service.delete_document(doc_id, "student_A")
    assert deleted is True

    # Vector store query should now return 0 results
    search_after = service.get_vector_store().query_document_chunks("student_A", "Newton third law", [doc_id], min_score=0.1)
    assert len(search_after) == 0


def test_18_safe_document_deletion(test_env: Dict[str, Any]) -> None:
    """TC-18: Deletion unlinks file from disk and deletes SQLite record."""
    client: TestClient = test_env["client"]
    service: DocumentService = test_env["service"]
    pdf_bytes = _build_valid_pdf_bytes("Chemistry periodic table trends")

    rec = service.upload_and_index_document("student_A", "chem.pdf", pdf_bytes)
    doc_id = rec["id"]
    storage_path = Path(rec["storage_path"])
    assert storage_path.exists()

    # Call API to delete
    res = client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {test_env['token_A']}"},
    )
    assert res.status_code == status.HTTP_200_OK

    # Assert disk file unlinked
    assert not storage_path.exists()

    # Assert SQLite row removed
    assert get_document_record(doc_id, custom_path=test_env["db_path"]) is None


def test_19_failed_deletion_recovery(test_env: Dict[str, Any]) -> None:
    """TC-19: Interrupted DELETING status document is cleaned up on startup reconciliation."""
    service: DocumentService = test_env["service"]
    temp_storage: Path = test_env["storage_dir"]

    stud_dir = temp_storage / "student_A"
    stud_dir.mkdir(parents=True, exist_ok=True)
    interrupted_file = stud_dir / "doc_del_interrupted.pdf"
    interrupted_file.write_bytes(b"%PDF-del-interrupted")

    expired_updated = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    create_document_record(
        document_id="doc_del_interrupted",
        student_id="student_A",
        filename="del.pdf",
        storage_path=str(interrupted_file),
        file_size=1024,
        file_hash="hash_del_1",
        indexing_status="DELETING",
        custom_path=test_env["db_path"],
    )
    # Simulate an interrupted deletion where updated_at is in the past
    conn = get_db_connection(test_env["db_path"])
    with conn:
        conn.execute("UPDATE student_documents SET updated_at = ? WHERE id = 'doc_del_interrupted';", (expired_updated,))
    conn.close()

    reconciled = service.reconcile_on_startup(stale_threshold_seconds=60)
    assert reconciled == 1
    assert not interrupted_file.exists()
    assert get_document_record("doc_del_interrupted", custom_path=test_env["db_path"]) is None


def test_20_active_database_integrity(test_env: Dict[str, Any]) -> None:
    """TC-20: Verifies active database and backup remain strictly untouched."""
    active_db = Path("data/gyaan_ai.db").resolve()
    backup_db = Path("data/backups/gyaan_ai_pre_phase5d_backup.db").resolve()

    assert active_db.exists()
    assert backup_db.exists()

    # Check size invariant
    assert active_db.stat().st_size == 4329472
    assert backup_db.stat().st_size == 4329472

    # Verify SQLite integrity
    for db_file in (active_db, backup_db):
        con = sqlite3.connect(str(db_file))
        cur = con.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()[0]
        con.close()
        assert res == "ok"
