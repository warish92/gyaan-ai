"""
Gyaan AI - Document Management and Indexing Service (Phase 5D.3).

Orchestrates the lifecycle of student-uploaded educational documents:
- Secure multi-tenant file storage and directory confinement
- Magic-byte, MIME, and size validation
- SHA-256 deduplication
- Process-isolated extraction (via pdf_parser)
- Structure-preserving chunking (via text_chunker)
- Multi-tier isolated vector storage (via vector_store)
- Lease-based concurrency and crash reconciliation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from backend.db.database import (
    create_document_record,
    delete_document_record,
    find_document_by_hash,
    get_document_record,
    list_student_documents,
    reconcile_stale_documents,
    update_document_status,
)
from backend.services.pdf_parser import (
    PDFEncryptedError,
    PDFExtractionResult,
    PDFMalformedError,
    PDFParserError,
    PDFSecurityError,
    PDFTimeoutError,
    PDFValidationError,
    PDFWorkerCrashError,
    extract_pdf_text_isolated,
)
from backend.services.text_chunker import TextChunker
from backend.services.vector_store import (
    DocumentIndexingError,
    SecurityViolationError,
    VectorStore,
    VectorStoreError,
)

logger = logging.getLogger("gyaan_ai.document_service")

# Storage directory under project data root
DEFAULT_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "documents"
MAX_PDF_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB limit
DEFAULT_LEASE_TIMEOUT_SECONDS: int = 300     # 5-minute processing lease


# ============================================================================
# 1. Custom Exceptions
# ============================================================================

class DocumentServiceError(Exception):
    """Base exception for all document management operations."""
    pass


class DocumentValidationError(DocumentServiceError):
    """Raised when document fails validation (format, size, magic bytes)."""
    pass


class DocumentPayloadTooLargeError(DocumentValidationError):
    """Raised when document size exceeds 10 MB limit."""
    pass


class EmptyDocumentError(DocumentValidationError):
    """Raised when document has no extractable text or produces 0 chunks."""
    pass


class OwnershipError(DocumentServiceError):
    """Raised when an operation violates student document ownership."""
    pass


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a document cannot be found."""
    pass


class DocumentProcessingError(DocumentServiceError):
    """Raised when parsing, chunking, or indexing fails."""
    pass


# ============================================================================
# 2. Document Service Implementation
# ============================================================================

class DocumentService:
    """
    Manages document upload, extraction, indexing, querying, deletion,
    and crash recovery with strict student isolation.
    """

    def __init__(
        self,
        storage_dir: Optional[Path | str] = None,
        vector_store: Optional[VectorStore] = None,
        db_path: Optional[Path | str] = None,
        lease_timeout_seconds: int = DEFAULT_LEASE_TIMEOUT_SECONDS,
        max_file_size: int = MAX_PDF_SIZE_BYTES,
    ) -> None:
        if storage_dir is not None:
            self.storage_dir = Path(storage_dir).resolve()
        else:
            self.storage_dir = DEFAULT_STORAGE_DIR.resolve()

        self.db_path = db_path
        self.lease_timeout_seconds = lease_timeout_seconds
        self.max_file_size = max_file_size

        self._vector_store = vector_store
        self._owns_vector_store = vector_store is None
        self._chunker = TextChunker()

    def get_vector_store(self) -> VectorStore:
        """Lazily initialize or return the injected VectorStore."""
        if self._vector_store is None:
            self._vector_store = VectorStore()
            self._owns_vector_store = True
        return self._vector_store

    def _get_student_dir(self, student_id: str) -> Path:
        """Resolve and confine student storage directory to prevent path traversal."""
        clean_id = student_id.strip()
        if not clean_id or ".." in clean_id or "/" in clean_id or "\\" in clean_id:
            raise OwnershipError("Invalid student identifier format.")
        student_dir = (self.storage_dir / clean_id).resolve()
        if not student_dir.is_relative_to(self.storage_dir):
            raise OwnershipError("Student storage directory escapes base storage root.")
        student_dir.mkdir(parents=True, exist_ok=True)
        return student_dir

    # ------------------------------------------------------------------------
    # Upload and Indexing Pipeline
    # ------------------------------------------------------------------------

    def upload_and_index_document(
        self,
        student_id: str,
        filename: str,
        file_bytes: bytes,
    ) -> Dict[str, Any]:
        """
        Validates, persists, extracts, chunks, and indexes a PDF document.

        Guarantees:
        - Strict file validation (magic bytes, size <= 10MB)
        - Deduplication check (existing INDEXED returns immediately)
        - Processing lease to protect concurrent operations
        - Isolated process extraction
        - Rejection of empty documents with explicit error
        - Automatic compensating cleanup on any failure
        """
        if not student_id or not student_id.strip():
            raise OwnershipError("Authentication required: student_id cannot be blank.")
        clean_student_id = student_id.strip()

        # 1. Sanitize filename
        safe_filename = Path(filename).name.strip()
        if not safe_filename or safe_filename in (".", ".."):
            safe_filename = "document.pdf"

        # 2. File size validation
        file_size = len(file_bytes)
        if file_size == 0:
            raise DocumentValidationError("Upload rejected: file is empty (0 bytes).")
        if file_size > self.max_file_size:
            raise DocumentPayloadTooLargeError(
                f"Upload rejected: file size ({file_size:,} bytes) exceeds {self.max_file_size:,} byte limit."
            )

        # 3. Magic bytes validation (%PDF-)
        if not file_bytes.startswith(b"%PDF-"):
            raise DocumentValidationError(
                "Upload rejected: invalid file format. File does not start with valid PDF magic bytes (%PDF-)."
            )

        # 4. SHA-256 Content Hash & Deduplication Check
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        existing = find_document_by_hash(clean_student_id, file_hash, custom_path=self.db_path)
        if existing:
            if existing["indexing_status"] == "INDEXED":
                logger.info(
                    f"Duplicate document detected for student {clean_student_id} (hash {file_hash[:8]}). Returning existing {existing['id']}."
                )
                return existing
            elif existing["indexing_status"] == "PROCESSING":
                # Check if lease is active
                lease_exp = existing.get("lease_expires_at")
                if lease_exp:
                    try:
                        exp_dt = datetime.fromisoformat(lease_exp)
                        if exp_dt > datetime.now(timezone.utc):
                            logger.info(
                                f"Document {existing['id']} is currently being processed under an active lease."
                            )
                            return existing
                    except Exception:
                        pass

        # 5. Initialize Document Record with Lease
        document_id = f"doc_{uuid.uuid4().hex[:16]}"
        lease_token = uuid.uuid4().hex
        lease_expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=self.lease_timeout_seconds)
        ).isoformat()

        student_dir = self._get_student_dir(clean_student_id)
        storage_file_path = student_dir / f"{document_id}.pdf"

        # Create record in PROCESSING state
        doc_record = create_document_record(
            document_id=document_id,
            student_id=clean_student_id,
            filename=safe_filename,
            storage_path=str(storage_file_path),
            file_size=file_size,
            file_hash=file_hash,
            content_type="application/pdf",
            indexing_status="PROCESSING",
            lease_token=lease_token,
            lease_expires_at=lease_expires_at,
            custom_path=self.db_path,
        )

        # 6. Write file to disk securely
        try:
            with open(storage_file_path, "wb") as f:
                f.write(file_bytes)
        except Exception as exc:
            update_document_status(
                document_id,
                "FAILED",
                error_message=f"Disk I/O failure: {exc}",
                clear_lease=True,
                custom_path=self.db_path,
            )
            raise DocumentProcessingError(f"Failed to persist document to disk: {exc}") from exc

        # 7. Process-Isolated Extraction
        try:
            extraction_result: PDFExtractionResult = extract_pdf_text_isolated(
                file_path=storage_file_path,
                allowed_dir=student_dir,
                timeout=15.0,
                max_bytes=self.max_file_size,
            )
        except (PDFValidationError, PDFEncryptedError, PDFMalformedError, PDFTimeoutError, PDFWorkerCrashError, PDFSecurityError, PDFParserError) as exc:
            self._cleanup_failed_indexing(document_id, clean_student_id, storage_file_path)
            error_msg = f"PDF extraction failed: {exc}"
            update_document_status(
                document_id,
                "FAILED",
                error_message=error_msg,
                clear_lease=True,
                custom_path=self.db_path,
            )
            if isinstance(exc, PDFValidationError):
                raise DocumentValidationError(error_msg) from exc
            if isinstance(exc, (PDFMalformedError, PDFEncryptedError)):
                if "no readable text" in str(exc).lower():
                    raise EmptyDocumentError(f"Empty document: {exc}") from exc
                raise DocumentValidationError(error_msg) from exc
            raise DocumentProcessingError(error_msg) from exc
        except Exception as exc:
            self._cleanup_failed_indexing(document_id, clean_student_id, storage_file_path)
            error_msg = f"Unexpected extraction error: {exc}"
            update_document_status(
                document_id,
                "FAILED",
                error_message=error_msg,
                clear_lease=True,
                custom_path=self.db_path,
            )
            raise DocumentProcessingError(error_msg) from exc

        # 8. Empty Document Validation
        extracted_text = extraction_result.text.strip()
        if not extracted_text:
            self._cleanup_failed_indexing(document_id, clean_student_id, storage_file_path)
            error_msg = "Empty document: no extractable text found in PDF."
            update_document_status(
                document_id,
                "FAILED",
                error_message=error_msg,
                clear_lease=True,
                custom_path=self.db_path,
            )
            raise EmptyDocumentError(error_msg)

        # 9. Text Chunking
        try:
            chunks = self._chunker.chunk_document(
                document_id=document_id,
                student_id=clean_student_id,
                pages=[extracted_text],
            )
        except Exception as exc:
            self._cleanup_failed_indexing(document_id, clean_student_id, storage_file_path)
            error_msg = f"Chunking error: {exc}"
            update_document_status(
                document_id,
                "FAILED",
                error_message=error_msg,
                clear_lease=True,
                custom_path=self.db_path,
            )
            raise DocumentProcessingError(error_msg) from exc

        if not chunks:
            self._cleanup_failed_indexing(document_id, clean_student_id, storage_file_path)
            error_msg = "Empty document: text produced zero indexing chunks."
            update_document_status(
                document_id,
                "FAILED",
                error_message=error_msg,
                clear_lease=True,
                custom_path=self.db_path,
            )
            raise EmptyDocumentError(error_msg)

        # 10. Vector Indexing
        vs = self.get_vector_store()
        try:
            # Pre-purge in case of retry/interrupted prior indexing
            try:
                vs.delete_document_vectors(document_id=document_id, student_id=clean_student_id)
            except Exception:
                pass

            vs.index_document_chunks(
                document_id=document_id,
                student_id=clean_student_id,
                chunks=chunks,
            )
        except Exception as exc:
            # Compensating rollback: delete any partial vectors & file
            self._cleanup_failed_indexing(document_id, clean_student_id, storage_file_path)
            error_msg = f"Vector indexing failure: {exc}"
            update_document_status(
                document_id,
                "FAILED",
                error_message=error_msg,
                clear_lease=True,
                custom_path=self.db_path,
            )
            raise DocumentProcessingError(error_msg) from exc

        # 11. Finalize Document Status to INDEXED
        update_document_status(
            document_id=document_id,
            status="INDEXED",
            page_count=extraction_result.page_count,
            chunk_count=len(chunks),
            clear_lease=True,
            custom_path=self.db_path,
        )

        final_record = get_document_record(document_id, student_id=clean_student_id, custom_path=self.db_path)
        if final_record is None:
            raise DocumentProcessingError(f"Failed to load indexed record for {document_id}")
        return final_record

    def _cleanup_failed_indexing(
        self,
        document_id: str,
        student_id: str,
        storage_file_path: Path,
    ) -> None:
        """Compensating action: purges partial vectors and removes failed file from disk."""
        try:
            if self._vector_store is not None:
                self._vector_store.delete_document_vectors(
                    document_id=document_id, student_id=student_id
                )
        except Exception as exc:
            logger.warning(f"Vector cleanup notice during failure recovery for {document_id}: {exc}")

        try:
            if storage_file_path.exists():
                storage_file_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning(f"File cleanup notice for {storage_file_path}: {exc}")

    # ------------------------------------------------------------------------
    # Document Search & Retrieval
    # ------------------------------------------------------------------------

    def search_student_documents(
        self,
        student_id: str,
        query: str,
        document_ids: Optional[List[str]] = None,
        max_results: int = 5,
        min_score: float = 0.4,
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic search strictly bounded by student ownership.

        Enforces:
        - Relational SQL ownership verification on all supplied document_ids
        - Raising OwnershipError on any foreign document requested
        - ChromaDB tenant isolation
        - Cosine similarity threshold filtering
        """
        if not student_id or not student_id.strip():
            raise OwnershipError("Authentication required: student_id cannot be blank.")
        clean_student_id = student_id.strip()

        if not query or not query.strip():
            return []

        # Validate requested document_ids in SQLite
        if document_ids:
            for doc_id in document_ids:
                doc_record = get_document_record(doc_id, custom_path=self.db_path)
                if doc_record is None:
                    raise DocumentNotFoundError(f"Document '{doc_id}' not found.")
                if doc_record["student_id"] != clean_student_id:
                    raise OwnershipError(
                        f"Access denied: Document '{doc_id}' does not belong to student '{clean_student_id}'."
                    )

        vs = self.get_vector_store()
        return vs.query_document_chunks(
            student_id=clean_student_id,
            query_text=query,
            document_ids=document_ids,
            n_results=max_results,
            min_score=min_score,
        )

    # ------------------------------------------------------------------------
    # Document Management & Deletion
    # ------------------------------------------------------------------------

    def get_document(
        self,
        document_id: str,
        student_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve document record, verifying ownership."""
        if not student_id or not student_id.strip():
            raise OwnershipError("Authentication required: student_id cannot be blank.")
        clean_student_id = student_id.strip()

        record = get_document_record(document_id, custom_path=self.db_path)
        if record is None:
            return None
        if record["student_id"] != clean_student_id:
            raise OwnershipError(
                f"Access denied: Document '{document_id}' belongs to another student."
            )
        return record

    def list_documents(
        self,
        student_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List documents owned by the student with pagination."""
        if not student_id or not student_id.strip():
            raise OwnershipError("Authentication required: student_id cannot be blank.")
        return list_student_documents(
            student_id=student_id.strip(),
            status=status,
            limit=limit,
            offset=offset,
            custom_path=self.db_path,
        )

    def delete_document(
        self,
        document_id: str,
        student_id: str,
    ) -> bool:
        """
        Safely deletes a document:
        1. Verifies ownership in SQLite
        2. Sets status to DELETING
        3. Purges ChromaDB vectors
        4. Unlinks PDF file from disk
        5. Deletes SQLite record
        """
        if not student_id or not student_id.strip():
            raise OwnershipError("Authentication required: student_id cannot be blank.")
        clean_student_id = student_id.strip()

        # 1. Ownership check
        doc_record = get_document_record(document_id, custom_path=self.db_path)
        if doc_record is None:
            raise DocumentNotFoundError(f"Document '{document_id}' not found.")
        if doc_record["student_id"] != clean_student_id:
            raise OwnershipError(
                f"Access denied: Document '{document_id}' belongs to another student."
            )

        # 2. Transition to DELETING
        update_document_status(
            document_id=document_id,
            status="DELETING",
            clear_lease=True,
            custom_path=self.db_path,
        )

        # 3. Purge ChromaDB vectors
        vs = self.get_vector_store()
        try:
            vs.delete_document_vectors(document_id=document_id, student_id=clean_student_id)
        except Exception as exc:
            logger.warning(f"Notice purging vectors for {document_id}: {exc}")

        # 4. Unlink file from storage
        storage_path = Path(doc_record["storage_path"])
        try:
            if storage_path.exists():
                storage_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning(f"Notice unlinking file {storage_path}: {exc}")

        # 5. Delete SQLite record
        return delete_document_record(
            document_id=document_id,
            student_id=clean_student_id,
            custom_path=self.db_path,
        )

    # ------------------------------------------------------------------------
    # Startup & Crash Reconciliation
    # ------------------------------------------------------------------------

    def reconcile_on_startup(self, stale_threshold_seconds: int = DEFAULT_LEASE_TIMEOUT_SECONDS) -> int:
        """
        Recovers from unexpected server termination or crashes:
        - Finds documents in PROCESSING whose lease has expired
        - Cleans up partial vectors and files
        - Marks records as FAILED
        - Completes interrupted DELETING operations
        """
        stale_records = reconcile_stale_documents(
            stale_threshold_seconds=stale_threshold_seconds,
            custom_path=self.db_path,
        )
        if not stale_records:
            return 0

        vs = self.get_vector_store()
        for rec in stale_records:
            doc_id = rec["id"]
            stud_id = rec["student_id"]
            storage_path = Path(rec["storage_path"])

            # Clean vectors
            try:
                vs.delete_document_vectors(doc_id, stud_id)
            except Exception as exc:
                logger.warning(f"Reconciliation vector cleanup notice for {doc_id}: {exc}")

            # Clean file
            try:
                if storage_path.exists():
                    storage_path.unlink(missing_ok=True)
            except Exception as exc:
                logger.warning(f"Reconciliation file cleanup notice for {storage_path}: {exc}")

            # If it was DELETING, finalize record deletion
            if rec.get("indexing_status") == "DELETING":
                try:
                    delete_document_record(doc_id, stud_id, custom_path=self.db_path)
                except Exception as exc:
                    logger.warning(f"Reconciliation delete record notice for {doc_id}: {exc}")

        logger.info(f"Startup reconciliation resolved {len(stale_records)} abandoned documents.")
        return len(stale_records)

    # ------------------------------------------------------------------------
    # Resource Lifecycle Cleanup
    # ------------------------------------------------------------------------

    def close(self) -> None:
        """Releases underlying VectorStore and handles."""
        if self._vector_store is not None and self._owns_vector_store:
            try:
                self._vector_store.close()
            except Exception as exc:
                logger.debug(f"VectorStore close notice in DocumentService: {exc}")
            self._vector_store = None

    def __enter__(self) -> "DocumentService":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
