"""
Gyaan AI - Document Management API Router (Phase 5D.3).

Provides authenticated REST endpoints for:
- PDF document upload, validation, and isolated indexing
- Student-isolated semantic document search
- Document listing and metadata retrieval
- Document deletion and vector purging
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend.db.database import (
    get_session_by_token_hash,
    get_student_by_id,
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

logger = logging.getLogger("gyaan_ai.routers.documents")

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])
security_scheme = HTTPBearer(auto_error=False)

# Rate limiting storage: { "student_id:action": [timestamp, ...] }
_rate_limit_state: Dict[str, List[float]] = {}


# ============================================================================
# 1. Rate Limiting Helper
# ============================================================================

def enforce_rate_limit(
    student_id: str,
    action: str,
    max_requests: int,
    window_seconds: float = 60.0,
) -> None:
    """Enforces in-memory sliding window rate limits per student."""
    now = time.monotonic()
    key = f"{student_id}:{action}"
    history = _rate_limit_state.setdefault(key, [])
    # Prune outdated timestamps
    history[:] = [t for t in history if now - t < window_seconds]
    if len(history) >= max_requests:
        logger.warning(
            f"Rate limit exceeded for student {student_id} on action {action} "
            f"({len(history)}/{max_requests} in {window_seconds}s)"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for document {action}. Maximum {max_requests} requests per minute.",
        )
    history.append(now)


# ============================================================================
# 2. Authentication Dependency
# ============================================================================

async def get_current_student(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Dict[str, Any]:
    """Authenticates request via Bearer token or HttpOnly session cookie."""
    raw_token = None
    if creds and creds.credentials:
        raw_token = creds.credentials
    elif request.cookies.get("gyaan_auth_token"):
        raw_token = request.cookies.get("gyaan_auth_token")

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token or session cookie.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token_hash = hash_session_token(raw_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token format.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session = get_session_by_token_hash(token_hash)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        expires_at_dt = datetime.fromisoformat(session["expires_at"])
        if expires_at_dt < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session token has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token validation error.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    student = get_student_by_id(session["student_id"])
    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Student account not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return student


# ============================================================================
# 3. Pydantic Schemas
# ============================================================================

class DocumentMetadataResponse(BaseModel):
    id: str
    student_id: str
    filename: str
    file_size: int
    content_type: str
    page_count: int
    chunk_count: int
    indexing_status: str
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    document_ids: Optional[List[str]] = None
    max_results: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.4, ge=0.0, le=1.0)


class DocumentSearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    student_id: str
    page_number: int
    chunk_index: int
    text: str
    similarity_score: float


class DocumentSearchResponse(BaseModel):
    query: str
    results_count: int
    results: List[DocumentSearchResultItem]


class DocumentDeleteResponse(BaseModel):
    success: bool
    message: str
    document_id: str


# ============================================================================
# 4. Dependency Provider
# ============================================================================

def get_document_service() -> DocumentService:
    """Dependency injection provider for DocumentService."""
    return DocumentService()


# ============================================================================
# 5. Route Handlers
# ============================================================================

@router.post(
    "/upload",
    response_model=DocumentMetadataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and Index PDF Document",
)
async def upload_document(
    file: UploadFile = File(...),
    current_student: Dict[str, Any] = Depends(get_current_student),
    service: DocumentService = Depends(get_document_service),
) -> Dict[str, Any]:
    """Uploads a PDF document, validates size & magic bytes, and indexes text into isolated vector store."""
    student_id = current_student["id"]

    # Rate limiting: 10 uploads/min
    enforce_rate_limit(student_id, "upload", max_requests=10, window_seconds=60.0)

    # Read uploaded bytes
    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        )

    # Validate size upfront
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Upload rejected: file size ({len(file_bytes):,} bytes) exceeds 10 MB limit.",
        )

    try:
        record = service.upload_and_index_document(
            student_id=student_id,
            filename=file.filename or "document.pdf",
            file_bytes=file_bytes,
        )
        return record
    except DocumentPayloadTooLargeError as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        )
    except (DocumentValidationError, EmptyDocumentError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document indexing failed: {exc}",
        )
    except Exception as exc:
        logger.error(f"Unhandled upload exception for student {student_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal document processing error.",
        )


@router.post(
    "/search",
    response_model=DocumentSearchResponse,
    summary="Semantic Search across Student Documents",
)
async def search_documents(
    req: DocumentSearchRequest,
    current_student: Dict[str, Any] = Depends(get_current_student),
    service: DocumentService = Depends(get_document_service),
) -> Dict[str, Any]:
    """Performs semantic retrieval strictly confined to the caller's documents."""
    student_id = current_student["id"]

    # Rate limiting: 30 searches/min
    enforce_rate_limit(student_id, "search", max_requests=30, window_seconds=60.0)

    try:
        retrieved_chunks = service.search_student_documents(
            student_id=student_id,
            query=req.query,
            document_ids=req.document_ids,
            max_results=req.max_results,
            min_score=req.min_score,
        )
        return {
            "query": req.query,
            "results_count": len(retrieved_chunks),
            "results": [
                {
                    "chunk_id": c["chunk_id"],
                    "document_id": c["document_id"],
                    "student_id": c["student_id"],
                    "page_number": c["page_number"],
                    "chunk_index": c["chunk_index"],
                    "text": c["text"],
                    "similarity_score": c["similarity_score"],
                }
                for c in retrieved_chunks
            ],
        }
    except OwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Search exception for student {student_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document search error.",
        )


@router.get(
    "/",
    response_model=List[DocumentMetadataResponse],
    summary="List Student Documents",
)
async def list_documents(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_student: Dict[str, Any] = Depends(get_current_student),
    service: DocumentService = Depends(get_document_service),
) -> List[Dict[str, Any]]:
    """List all documents belonging to the authenticated student."""
    student_id = current_student["id"]
    return service.list_documents(
        student_id=student_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentMetadataResponse,
    summary="Get Document Metadata",
)
async def get_document(
    document_id: str,
    current_student: Dict[str, Any] = Depends(get_current_student),
    service: DocumentService = Depends(get_document_service),
) -> Dict[str, Any]:
    """Retrieves document metadata by ID, returning 404 if not found or unowned."""
    student_id = current_student["id"]
    try:
        record = service.get_document(document_id=document_id, student_id=student_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found.",
            )
        return record
    except OwnershipError:
        # Defense-in-depth: do not reveal existence of other tenants' documents
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete Document and Associated Vectors",
)
async def delete_document(
    document_id: str,
    current_student: Dict[str, Any] = Depends(get_current_student),
    service: DocumentService = Depends(get_document_service),
) -> Dict[str, Any]:
    """Deletes a document from SQLite, unlinks from disk, and purges all associated vector embeddings."""
    student_id = current_student["id"]
    try:
        service.delete_document(document_id=document_id, student_id=student_id)
        return {
            "success": True,
            "message": f"Document '{document_id}' and all associated vectors deleted successfully.",
            "document_id": document_id,
        }
    except (DocumentNotFoundError, OwnershipError):
        # Defense-in-depth: return 404 for unowned or missing documents
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    except Exception as exc:
        logger.error(f"Delete exception for document {document_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document deletion failure.",
        )
