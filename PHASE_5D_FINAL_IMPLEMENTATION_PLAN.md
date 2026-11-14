# GYAAN AI — PHASE 5D: FINAL IMPLEMENTATION PLAN
**Date**: November 14, 2026  
**Target Hardware**: NVIDIA GeForce RTX 2050 (4GB VRAM) | Windows 11  
**Project**: `D:\Gyaan AI` | **Protected Legacy**: `D:\GYAN Ai` (Untouched)  
**Authorization Mode**: Strictly Read-Only Implementation Planning  

---

## 1. Controlled Substage Implementation Roadmap

To eliminate regression risks and protect existing functionality, Phase 5D is divided into seven self-contained, sequentially gated substages. **Each substage requires separate explicit user authorization before execution.**

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Phase 5D Substage Gated Sequence                     │
├─────────┬──────────────────────────────────┬───────────────────────────┤
│ Stage   │ Substage Title                   │ Primary Output / Boundary │
├─────────┼──────────────────────────────────┼───────────────────────────┤
│ 5D.1    │ Document Storage & PDF Extractor │ Core file parsing service │
│ 5D.2    │ Embedding & Vector Indexing      │ ChromaDB & ONNX pipeline  │
│ 5D.3    │ Document API & Security Guards   │ FastAPI /api/v1/documents │
│ 5D.4    │ Resource Agent Integration       │ Hybrid NCERT/doc workflow │
│ 5D.5    │ Teacher Agent Grounded Tutoring  │ Contextual Socratic tasks │
│ 5D.6    │ Frontend Document Library        │ Next.js upload & manage UI│
│ 5D.7    │ End-to-End Regression Audit      │ Full suite verification   │
└─────────┴──────────────────────────────────┴───────────────────────────┘
```

---

## 2. Detailed Substage Specifications

### Substage 5D.1: Document Storage & PDF Extraction
- **Objective**: Implement robust, process-isolated PDF validation, disk storage, and text extraction.
- **Files to Create**:
  - `backend/services/document_parser.py`: Implements `%PDF-` magic-byte inspection, file size validation ($\le 10\text{MB}$), path resolution with `Path.is_relative_to()`, and process-isolated `pypdf` extraction with a hard 15-second timeout.
  - `tests/test_document_parser.py`: Unit tests for valid PDFs, encrypted PDFs, corrupted streams, scanned PDFs (empty text refusal), and path traversal attempts.
- **Existing Files to Modify**: None.
- **Database Changes**: None.
- **Security Requirements**: Magic-byte verification, strict 10MB limit, random UUID storage names, path traversal rejection.
- **Tests to Execute**: `pytest tests/test_document_parser.py`.
- **Acceptance Criteria**: 100% test pass; process kills hung extractions cleanly within 15 seconds; 0 MB GPU VRAM allocated.
- **Rollback Strategy**: Delete `backend/services/document_parser.py` and `tests/test_document_parser.py`.

---

### Substage 5D.2: Embedding & Vector Indexing
- **Objective**: Implement sliding-window text chunking and persistent ChromaDB vector storage using CPU ONNX embeddings.
- **Files to Create**:
  - `backend/services/vector_store.py`: Initializes `chromadb.PersistentClient(path="data/vector_store")`, configures `DefaultEmbeddingFunction()`, implements sliding chunker (500 chars, 50 chars overlap), metadata tagging, query vectorization, and multi-tenant collection filtering.
  - `tests/test_vector_store.py`: Unit tests for chunk generation, embedding dimension (384), cosine similarity retrieval, and chunk purging.
- **Existing Files to Modify**: None.
- **Database Changes**: None.
- **Security Requirements**: Mandatory `student_id` metadata tag on every chunk; query requires `where={"student_id": student_id}`.
- **Tests to Execute**: `pytest tests/test_vector_store.py`.
- **Acceptance Criteria**: 100% test pass; vector search executes in $< 15\text{ms}$; zero GPU memory allocated.
- **Rollback Strategy**: Delete `backend/services/vector_store.py`, `tests/test_vector_store.py`, and purge `data/vector_store`.

---

### Substage 5D.3: Document API & Security Guards
- **Objective**: Expose authenticated FastAPI endpoints for document upload, listing, details, and deletion with SQLite metadata persistence.
- **Files to Create**:
  - `backend/api/routers/documents.py`: FastAPI router implementing `POST /upload`, `GET /`, `GET /{id}`, `DELETE /{id}`, and `POST /search`.
  - `backend/app/schemas_documents.py`: Pydantic models for document requests and responses.
  - `tests/test_document_api.py`: API tests verifying authentication enforcement, IDOR rejection, and complete deletion lifecycle.
- **Existing Files to Modify**:
  - `backend/app/main.py`: Register router: `app.include_router(documents_router, prefix="/api/v1/documents", tags=["Documents"])`.
  - `backend/db/database.py`: Add `CREATE TABLE IF NOT EXISTS student_documents (...)` and 4 CRUD functions (`save_student_document`, `get_student_documents`, `get_student_document_by_id`, `delete_student_document`).
- **Database Changes**: Add standalone `student_documents` table and `idx_student_documents_student_id` index. Zero existing tables or records touched.
- **Security Requirements**: Reuse `get_current_student` dependency; strict IDOR verification against SQLite and ChromaDB.
- **Tests to Execute**: `pytest tests/test_document_api.py tests/test_phase5b_security_verification.py`.
- **Acceptance Criteria**: 100% test pass; unauthenticated access returns 401; cross-student access returns 404.
- **Rollback Strategy**: Unregister router in `main.py`, drop `student_documents` table in SQLite, delete new files.

---

### Substage 5D.4: Resource Agent Integration
- **Objective**: Enable the Resource Agent to cross-reference student study notes with the verified NCERT curriculum corpus.
- **Files to Create**:
  - `tests/test_resource_rag_integration.py`: Unit tests verifying hybrid resource retrieval and NCERT gap analysis.
- **Existing Files to Modify**:
  - `backend/agents/workflow.py`: Upgrade `run_resource_workflow` to accept an optional `student_id` parameter, querying both static NCERT JSON and student ChromaDB vectors.
  - `backend/mcp_integration/servers/filesystem_server.py`: Add safe, read-only MCP tool `search_student_documents(student_id, query)`.
- **Database Changes**: None.
- **Security Requirements**: MCP tool validates student identity; Resource Agent operates in read-only analysis mode.
- **Tests to Execute**: `pytest tests/test_resource_rag_integration.py tests/test_specialist_agent_independence.py`.
- **Acceptance Criteria**: 100% test pass; canonical Resource Agent role and prompt remain unaltered; non-RAG resource searches continue unaffected.
- **Rollback Strategy**: Revert changes in `workflow.py` and `filesystem_server.py`.

---

### Substage 5D.5: Teacher Agent Grounded Tutoring
- **Objective**: Connect document retrieval to the Teacher Agent tutoring workflow with Socratic prompt framing and verified citations.
- **Files to Create**:
  - `tests/test_teacher_rag_grounding.py`: Unit tests verifying grounded tutoring, prompt injection resistance, and citation accuracy.
- **Existing Files to Modify**:
  - `backend/agents/orchestrator.py`: Add `document_qa` intent routing branch in `classify_educational_intent` and implement `handle_document_tutoring`.
  - `backend/agents/crew.py`: Add `create_grounded_teacher_task` wrapping retrieved chunks in `<student_document_excerpt>` tags.
- **Database Changes**: None (normal `learning_sessions` entry logged via existing function).
- **Security Requirements**: Prompt injection delimiters; Teacher Agent denied write tools; citation metadata sourced strictly from chunk attributes.
- **Tests to Execute**: `pytest tests/test_teacher_rag_grounding.py tests/test_teacher_crew.py tests/test_verify_8_intent_routes.py`.
- **Acceptance Criteria**: 100% test pass; regular tutoring questions without documents execute standard `handle_teacher_answer` without change.
- **Rollback Strategy**: Revert changes in `orchestrator.py` and `crew.py`.

---

### Substage 5D.6: Frontend Document Library & Teacher Studio Integration
- **Objective**: Provide intuitive UI for student document management and citation rendering.
- **Files to Create**:
  - `frontend/components/documents/DocumentUploadModal.tsx`: Drag-and-drop PDF uploader with progress and validation feedback.
  - `frontend/components/documents/DocumentLibrary.tsx`: Card grid displaying uploaded documents, chunk counts, and delete actions.
  - `frontend/app/documents/page.tsx`: "My Study Materials" page accessible from sidebar.
- **Existing Files to Modify**:
  - `frontend/app/teacher/page.tsx`: Add document attachment selector pill in the composer bar.
  - `frontend/components/ui/FormattedMessage.tsx`: Add interactive citation badge rendering.
  - `frontend/lib/api.ts`: Add `uploadDocument`, `getDocuments`, `deleteDocument`, `searchDocuments` methods.
- **Database Changes**: None.
- **Security Requirements**: Client-side MIME checks; auth token attached automatically via `api.ts`.
- **Tests to Execute**: `npm run build` in `frontend/`.
- **Acceptance Criteria**: 16/16 routes compile successfully; zero TypeScript or linting errors; responsive on desktop and mobile.
- **Rollback Strategy**: Revert modified frontend files and delete new components.

---

### Substage 5D.7: Complete End-to-End Regression Verification
- **Objective**: Comprehensive test battery across all existing and new features.
- **Scope**:
  - Run full backend unit suite (248 tests).
  - Run security and isolation suite (26 tests).
  - Run live integration test suite with Ollama (9 tests).
  - Run Next.js production build (`npm run build`).
  - Verify SQLite database integrity and student record preservation (793 students intact).
  - Verify `D:\GYAN Ai` remains untouched.
