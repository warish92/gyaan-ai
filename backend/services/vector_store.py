"""
Gyaan AI - Persistent Vector Storage & Retrieval Service (Phase 5D.2).

Provides student-isolated semantic vector retrieval over educational document chunks
using ChromaDB and local ONNX all-MiniLM-L6-v2 embeddings. Enforces a multi-tier
security boundary, atomic recoverable indexing, and Windows-safe resource lifecycle
disposal to eliminate [WinError 32] file sharing violations.
"""

from __future__ import annotations

import gc
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

from backend.services.text_chunker import DocumentChunk

logger = logging.getLogger("gyaan_ai.vector_store")

# Default persistence location inside project root (gitignored)
DEFAULT_CHROMA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "chromadb"
DEFAULT_COLLECTION_NAME = "educational_documents"
EMBEDDING_DIMENSION = 384


# ============================================================================
# 1. Custom Structured Exceptions
# ============================================================================

class VectorStoreError(Exception):
    """Base exception for all vector store failures."""
    pass


class SecurityViolationError(VectorStoreError):
    """Raised when cross-tenant data access or isolation breach is detected."""
    pass


class EmbeddingGenerationError(VectorStoreError):
    """Raised when local embedding generation fails."""
    pass


class DocumentIndexingError(VectorStoreError):
    """Raised when document ingestion or chunk indexing fails."""
    pass


# ============================================================================
# 2. VectorStore Implementation
# ============================================================================

class VectorStore:
    """
    Manages persistent ChromaDB vector storage with strict student-level isolation.
    """

    def __init__(
        self,
        persist_directory: Optional[Union[Path, str]] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ) -> None:
        self.persist_path = Path(persist_directory) if persist_directory else DEFAULT_CHROMA_PATH
        self.collection_name = collection_name
        self._client: Optional[ClientAPI] = None
        self._collection: Optional[Collection] = None
        self._embedding_function: Optional[ONNXMiniLM_L6_V2] = None

        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initializes the persistent ChromaDB client and local ONNX embedding engine."""
        try:
            self.persist_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.persist_path))

            # Initialize local ONNX model (uses cached all-MiniLM-L6-v2 weights)
            self._embedding_function = ONNXMiniLM_L6_V2()

            # Retrieve or create student educational documents collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"ChromaDB initialized at '{self.persist_path}', collection='{self.collection_name}'"
            )
        except Exception as exc:
            self.close()
            raise VectorStoreError(f"Failed to initialize ChromaDB persistent client: {exc}") from exc

    @property
    def collection(self) -> Collection:
        """Returns active collection or raises if closed."""
        if self._collection is None:
            raise VectorStoreError("VectorStore client has been closed or uninitialized.")
        return self._collection

    # ------------------------------------------------------------------------
    # Indexing & Atomicity / Recovery
    # ------------------------------------------------------------------------

    def index_document_chunks(
        self,
        document_id: str,
        student_id: str,
        chunks: Sequence[DocumentChunk],
        batch_size: int = 64,
    ) -> Dict[str, Any]:
        """
        Atomically indexes a document's chunks with tenant ownership verification.

        If any previous partial chunks exist for this document, they are purged before
        indexing to guarantee that interrupted jobs cannot leave duplicate or stale state.

        Args:
            document_id: Identifier of target document.
            student_id: Authenticated owner student ID.
            chunks: Sequence of DocumentChunk objects.
            batch_size: Maximum chunks per ingestion batch.

        Returns:
            Dict containing indexed_chunks count and document_id.
        """
        if not document_id or not document_id.strip():
            raise DocumentIndexingError("document_id cannot be blank.")
        if not student_id or not student_id.strip():
            raise SecurityViolationError("student_id cannot be blank.")

        if not chunks:
            raise DocumentIndexingError(
                f"Document '{document_id}' contains no extractable chunks; empty documents cannot be indexed."
            )

        # 1. Pre-validation: Verify that EVERY chunk belongs to the authenticated student
        for idx, chunk in enumerate(chunks):
            if chunk.student_id != student_id:
                raise SecurityViolationError(
                    f"Chunk {chunk.chunk_id} (index {idx}) student_id mismatch: "
                    f"expected '{student_id}', found '{chunk.student_id}'"
                )
            if chunk.document_id != document_id:
                raise DocumentIndexingError(
                    f"Chunk {chunk.chunk_id} document_id mismatch: "
                    f"expected '{document_id}', found '{chunk.document_id}'"
                )

        coll = self.collection

        # 2. Interrupted Indexing Recovery: Purge any existing/partial chunks for this doc
        try:
            coll.delete(
                where={
                    "$and": [
                        {"document_id": {"$eq": document_id}},
                        {"student_id": {"$eq": student_id}},
                    ]
                }
            )
        except Exception as del_err:
            logger.debug(f"Pre-indexing purge notice for {document_id}: {del_err}")

        # 3. Batch Ingestion
        total_indexed = 0
        try:
            for b_start in range(0, len(chunks), batch_size):
                b_chunks = chunks[b_start : b_start + batch_size]
                ids = [c.chunk_id for c in b_chunks]
                documents = [c.text for c in b_chunks]
                metadatas = [c.to_metadata() for c in b_chunks]

                coll.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )
                total_indexed += len(b_chunks)

        except Exception as exc:
            # On failure, roll back all ingested chunks for this document (fail-closed)
            try:
                coll.delete(
                    where={
                        "$and": [
                            {"document_id": {"$eq": document_id}},
                            {"student_id": {"$eq": student_id}},
                        ]
                    }
                )
            except Exception:
                pass
            raise DocumentIndexingError(
                f"Failed to index chunks for document '{document_id}': {exc}"
            ) from exc

        return {
            "document_id": document_id,
            "student_id": student_id,
            "indexed_chunks": total_indexed,
        }

    # ------------------------------------------------------------------------
    # Student-Isolated Semantic Retrieval
    # ------------------------------------------------------------------------

    def query_document_chunks(
        self,
        student_id: str,
        query_text: str,
        document_ids: Optional[List[str]] = None,
        n_results: int = 5,
        min_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic similarity retrieval strictly confined to the authenticated student.

        Enforces:
        - Mandatory student_id metadata filtering
        - Optional document_id constraint
        - Post-query ownership assertion on every returned chunk
        - Conversion of cosine distance to similarity score: score = 1.0 - distance

        Args:
            student_id: Authenticated caller student ID.
            query_text: Search query string.
            document_ids: Optional list of document IDs to restrict search within.
            n_results: Maximum matching chunks to return.
            min_score: Optional minimum similarity score threshold (0.0 to 1.0).

        Returns:
            List of chunk records with text, metadata, distance, and similarity score.
        """
        if not student_id or not student_id.strip():
            raise SecurityViolationError("Authentication required: student_id cannot be blank.")
        if not query_text or not query_text.strip():
            return []

        clean_student_id = student_id.strip()
        clean_query = query_text.strip()

        # 1. Construct mandatory student isolation filter
        if document_ids:
            clean_doc_ids = [d.strip() for d in document_ids if d and d.strip()]
            if len(clean_doc_ids) == 1:
                where_filter = {
                    "$and": [
                        {"student_id": {"$eq": clean_student_id}},
                        {"document_id": {"$eq": clean_doc_ids[0]}},
                    ]
                }
            else:
                where_filter = {
                    "$and": [
                        {"student_id": {"$eq": clean_student_id}},
                        {"document_id": {"$in": clean_doc_ids}},
                    ]
                }
        else:
            where_filter = {"student_id": {"$eq": clean_student_id}}

        coll = self.collection

        try:
            results = coll.query(
                query_texts=[clean_query],
                n_results=max(1, n_results),
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise VectorStoreError(f"ChromaDB similarity query failed: {exc}") from exc

        retrieved: List[Dict[str, Any]] = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return retrieved

        ids_list = results["ids"][0]
        docs_list = results["documents"][0] if results.get("documents") else []
        meta_list = results["metadatas"][0] if results.get("metadatas") else []
        dist_list = results["distances"][0] if results.get("distances") else []

        for idx, chunk_id in enumerate(ids_list):
            meta = meta_list[idx] if idx < len(meta_list) else {}
            doc_text = docs_list[idx] if idx < len(docs_list) else ""
            dist = dist_list[idx] if idx < len(dist_list) else 0.0

            # 2. Strict Post-Query Ownership Assertion (Defense-in-Depth)
            chunk_owner = meta.get("student_id")
            if chunk_owner != clean_student_id:
                logger.critical(
                    f"CRITICAL ISOLATION BREACH: Foreign chunk '{chunk_id}' owned by "
                    f"'{chunk_owner}' retrieved for student '{clean_student_id}'! Aborting."
                )
                raise SecurityViolationError(
                    "Tenant isolation breach detected: foreign document chunk encountered."
                )

            # Cosine distance to similarity score
            score = max(0.0, min(1.0, 1.0 - dist))
            if min_score is not None and score < min_score:
                continue

            retrieved.append({
                "chunk_id": chunk_id,
                "text": doc_text,
                "document_id": meta.get("document_id"),
                "student_id": clean_student_id,
                "page_number": meta.get("page_number"),
                "chunk_index": meta.get("chunk_index"),
                "similarity_score": round(score, 4),
                "distance": round(dist, 4),
                "metadata": meta,
            })

        return retrieved

    # ------------------------------------------------------------------------
    # Document Purge / Deletion
    # ------------------------------------------------------------------------

    def delete_document_vectors(self, document_id: str, student_id: str) -> int:
        """
        Deletes all vector chunks associated with a document, strictly verified by student_id.

        Args:
            document_id: Document ID to purge.
            student_id: Authenticated owner student ID.

        Returns:
            Number of chunks remaining (must be 0 on success).
        """
        if not document_id or not document_id.strip():
            raise DocumentIndexingError("document_id cannot be blank.")
        if not student_id or not student_id.strip():
            raise SecurityViolationError("student_id cannot be blank.")

        coll = self.collection

        try:
            coll.delete(
                where={
                    "$and": [
                        {"document_id": {"$eq": document_id}},
                        {"student_id": {"$eq": student_id}},
                    ]
                }
            )

            # Verify deletion post-condition
            check = coll.get(
                where={
                    "$and": [
                        {"document_id": {"$eq": document_id}},
                        {"student_id": {"$eq": student_id}},
                    ]
                }
            )
            remaining = len(check.get("ids", []))
            if remaining > 0:
                raise DocumentIndexingError(
                    f"Incomplete deletion: {remaining} chunks remained for doc {document_id}"
                )
            return remaining

        except Exception as exc:
            if isinstance(exc, (VectorStoreError, SecurityViolationError)):
                raise
            raise VectorStoreError(f"Failed to delete document vectors: {exc}") from exc

    # ------------------------------------------------------------------------
    # Windows Lifecycle & File Handle Cleanup
    # ------------------------------------------------------------------------

    def close(self) -> None:
        """
        Explicitly releases ChromaDB client instances, collection references,
        and forces garbage collection to release Windows memory-mapped handles.
        """
        if self._client is not None and hasattr(self._client, "close"):
            try:
                self._client.close()
            except Exception as exc:
                logger.debug(f"ChromaDB client close notice: {exc}")
        self._collection = None
        self._embedding_function = None
        self._client = None
        gc.collect()

    def __enter__(self) -> "VectorStore":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
