# GYAAN AI — PHASE 5D: AFFECTED FILES INVENTORY
**Date**: November 14, 2026  
**Target Hardware**: NVIDIA GeForce RTX 2050 (4GB VRAM) | Windows 11  
**Project**: `D:\Gyaan AI` | **Protected Legacy**: `D:\GYAN Ai` (Untouched)  
**Investigation Mode**: Strictly Read-Only Architecture Design  

---

## 1. Inventory Summary

This inventory catalogs every file planned for creation or modification during Phase 5D (Document Intelligence & RAG implementation). The implementation follows an **additive-first** architecture: new functionality is encapsulated in standalone modules, while existing endpoints and agent workflows receive minimal, non-breaking integration hooks.

```
┌─────────────────────────────────────────────────────────────┐
│                 Phase 5D Affected Files Scope               │
├────────────────────────────────────────┬────────────────────┤
│ Category                               │ File Count         │
├────────────────────────────────────────┼────────────────────┤
│ 1. New Backend Modules                 │ 4 files            │
│ 2. Modified Backend Integration Points │ 5 files            │
│ 3. New Frontend Components & Pages     │ 3 files            │
│ 4. Modified Frontend Components        │ 2 files            │
│ 5. Test Suite Additions                │ 3 files            │
│ 6. Strictly Protected / Untouched      │ Complete Core App  │
└────────────────────────────────────────┴────────────────────┘
```

---

## 2. New Backend Modules (Additive Services)

These files encapsulate all PDF processing, vector indexing, and document endpoints:

1. **`backend/services/document_service.py`**
   - **Role**: Handles binary upload stream verification (`%PDF-` magic bytes, 10MB limit), cryptographic random ID generation, disk storage under `data/uploads/{student_id}/{doc_id}.pdf`, text extraction via `pypdf`/`pdfplumber`, sliding-window text chunking (500 chars, 50 chars overlap), and document lifecycle deletion.
   - **Dependencies**: `pypdf`, `pdfplumber`, `pathlib`, `uuid`.

2. **`backend/services/vector_store.py`**
   - **Role**: Manages embedded ChromaDB client (`chromadb.PersistentClient(path="data/vector_store")`). Generates embeddings via CPU-bound `onnxruntime` (`all-MiniLM-L6-v2`) or local Ollama embeddings (`POST /api/embeddings`). Executes metadata-isolated similarity queries (`where={"student_id": student_id}`).
   - **Dependencies**: `chromadb`, `onnxruntime` (or `requests` to Ollama).

3. **`backend/api/routers/documents.py`**
   - **Role**: Dedicated FastAPI router exposing `/api/v1/documents/*` (`upload`, `list`, `details`, `delete`, `search`). Enforces Bearer JWT authentication via `get_current_student` and strict IDOR student ownership checks.
   - **Dependencies**: `fastapi`, Pydantic schemas, `document_service`, `vector_store`.

4. **`backend/app/schemas_documents.py`**
   - **Role**: Pydantic v2 data models for document uploads, metadata responses, search requests, search results, and citation structures.

---

## 3. Modified Backend Files (Minimal Integration Points)

Existing files receiving strictly non-breaking, additive extensions:

1. **`backend/app/main.py`**
   - **Modification**: Include documents router:
     `app.include_router(documents_router, prefix="/api/v1/documents", tags=["Documents"])`.
   - **Risk**: Minimal. Zero changes to existing auth, assessment, or student routes.

2. **`backend/db/database.py`**
   - **Modification**: Add `CREATE TABLE IF NOT EXISTS student_documents (...)` schema and 4 CRUD functions (`save_student_document`, `get_student_documents`, `get_student_document_by_id`, `delete_student_document`).
   - **Risk**: None. New table creation with `IF NOT EXISTS` leaves all 23 existing tables untouched.

3. **`backend/agents/orchestrator.py`**
   - **Modification**: Add `document_qa` intent routing branch in `classify_educational_intent` and implement `handle_document_tutoring`.
   - **Risk**: Low. Existing intents (`curriculum_inquiry`, `diagnostic_eval`, etc.) remain identical.

4. **`backend/agents/workflow.py`**
   - **Modification**: Add `build_grounded_teacher_crew` and enhance `run_resource_workflow` to support optional student document vector retrieval alongside static NCERT data.
   - **Risk**: Low. Purely additive functions.

5. **`backend/mcp/filesystem_server.py`**
   - **Modification**: Register two read-only tools: `search_student_documents` and `get_document_page`.
   - **Risk**: Low. Preserves existing curriculum file tools.

---

## 4. Frontend Files Inventory

### 4.1 New Frontend Files
1. **`frontend/components/documents/DocumentUploadModal.tsx`**:
   - Drag-and-drop PDF upload UI with client-side file size and MIME checks, upload progress bar, and page count badge.
2. **`frontend/components/documents/DocumentLibrary.tsx`**:
   - Card/list view of uploaded documents with indexed chunk counts, upload date, delete confirmation dialog, and selection toggle.
3. **`frontend/app/documents/page.tsx`**:
   - Dedicated "My Study Materials" page accessible from the sidebar.

### 4.2 Modified Frontend Files
1. **`frontend/app/teacher/page.tsx`**:
   - Add a document attachment toggle in the chat composer bar allowing students to select an uploaded document for grounded tutoring.
2. **`frontend/components/teacher/FormattedMessage.tsx`**:
   - Render interactive citation badges (e.g. `[Doc: Science_Notes.pdf, p. 4]`) with a popup preview tooltip showing snippet text.

---

## 5. Test Suite Inventory (New Verification Tests)

1. **`tests/test_document_service.py`**:
   - Unit tests for magic byte validation, 10MB limit rejection, pypdf text extraction, and chunk generation.
2. **`tests/test_vector_store.py`**:
   - Unit tests for ChromaDB client persistence, CPU ONNX embeddings, multi-tenant isolation, and document deletion cascades.
3. **`tests/test_document_api.py`**:
   - Integration tests verifying `POST /upload`, `GET /documents`, IDOR security rejection for cross-student access, and unauthenticated request blocks.

---

## 6. Strictly Untouched & Protected Files

The following assets are **100% protected and must NEVER be modified** during Phase 5D:

- **Legacy Project**: `D:\GYAN Ai` (Permanently untouchable).
- **Canonical Agent Core Definitions**:
  - `backend/agents/teacher.py` (Core prompt, backstory, role unchanged).
  - `backend/agents/diagnostic.py` (Core prompt, backstory, role unchanged).
  - `backend/agents/curriculum.py` (Core prompt, backstory, role unchanged).
  - `backend/agents/resource.py` (Core prompt, backstory, role unchanged).
  - `backend/agents/assessment.py` (Core prompt, backstory, role unchanged).
  - `backend/agents/progress.py` (Core prompt, backstory, role unchanged).
  - `backend/agents/mentor.py` (Core prompt, backstory, role unchanged).
- **Production Database**: `data/gyaan_ai.db` (Zero record modifications, zero column alterations on existing tables).
- **Core Security**: `get_current_student` authentication logic and password hashing.
