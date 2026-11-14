# GYAAN AI — PHASE 5D: FINAL FILE INVENTORY
**Date**: November 14, 2026  
**Target Hardware**: NVIDIA GeForce RTX 2050 (4GB VRAM) | Windows 11  
**Project**: `D:\Gyaan AI` | **Protected Legacy**: `D:\GYAN Ai` (Untouched)  
**Authorization Mode**: Strictly Read-Only Inventory Verification  

---

## 1. Inventory Overview & Ground-Truth Verification

This inventory catalogs every file proposed for creation or modification during Phase 5D. All paths have been cross-referenced and verified against the actual Windows filesystem of `D:\Gyaan AI`.

```
┌─────────────────────────────────────────────────────────────┐
│                 Phase 5D Final File Scope                   │
├────────────────────────────────────────┬────────────────────┤
│ Category                               │ File Count         │
├────────────────────────────────────────┼────────────────────┤
│ 1. New Backend Service Modules         │ 4 files            │
│ 2. Modified Backend Integration Points │ 6 files            │
│ 3. New Frontend Components & Pages     │ 3 files            │
│ 4. Modified Frontend Components        │ 3 files            │
│ 5. New Automated Test Suites           │ 5 files            │
│ 6. Strictly Untouched / Protected      │ Entire Core App    │
└────────────────────────────────────────┴────────────────────┘
```

---

## 2. New Backend Service Modules (To Be Created)

1. **`backend/services/document_parser.py`**
   - **Role**: Validates PDF `%PDF-` magic bytes, enforces $10\text{ MB}$ stream limit, verifies storage path containment using `Path.is_relative_to()`, and executes `pypdf` extraction inside a `ProcessPoolExecutor` with a hard 15-second process timeout.
   - **Dependencies**: `pypdf`, `pathlib`, `uuid`, `concurrent.futures`.

2. **`backend/services/vector_store.py`**
   - **Role**: Manages embedded ChromaDB client at `data/vector_store/`, executes CPU-bound ONNX embeddings via `all-MiniLM-L6-v2` (`DefaultEmbeddingFunction`), performs sliding-window chunking (500 chars, 50 chars overlap), inserts chunk vectors, and queries with mandatory `where={"student_id": student_id}`.
   - **Dependencies**: `chromadb`, `onnxruntime`.

3. **`backend/api/routers/documents.py`**
   - **Role**: Dedicated FastAPI router defining `/api/v1/documents/*` (`upload`, `list`, `details`, `delete`, `search`). Enforces Bearer JWT authentication via `get_current_student` and validates document ownership before all read/delete operations.
   - **Dependencies**: `fastapi`, Pydantic models, `document_parser`, `vector_store`.

4. **`backend/app/schemas_documents.py`**
   - **Role**: Pydantic v2 data models for document upload responses, metadata schemas, semantic search requests, and structured citation objects.

---

## 3. Modified Backend Integration Points (To Be Modified)

1. **`backend/app/main.py`**
   - **Exact Modification**: Register document router:
     ```python
     from backend.api.routers.documents import router as documents_router
     app.include_router(documents_router, prefix="/api/v1/documents", tags=["Documents"])
     ```
   - **Risk**: Very Low. Does not modify existing auth, student, assessment, or mentor endpoints.

2. **`backend/db/database.py`**
   - **Exact Modification**: Add `CREATE TABLE IF NOT EXISTS student_documents (...)` schema and CRUD helpers (`save_student_document`, `get_student_documents`, `get_student_document_by_id`, `delete_student_document`).
   - **Risk**: Zero. `CREATE TABLE IF NOT EXISTS` leaves all 23 existing tables and 793 student records untouched.

3. **`backend/agents/orchestrator.py`**
   - **Exact Modification**: Add intent classification branch for `document_qa` and implement `handle_document_tutoring`.
   - **Risk**: Low. Existing intents (`curriculum_inquiry`, `diagnostic_eval`, `resource_search`) remain untouched.

4. **`backend/agents/crew.py`**
   - **Exact Modification**: Add `create_grounded_teacher_task` to wrap vector chunks in `<student_document_excerpt>` tags and inject into the Teacher Agent prompt.
   - **Risk**: Low. Standard `create_teacher_task` remains untouched for normal tutoring.

5. **`backend/agents/workflow.py`**
   - **Exact Modification**: Upgrade `run_resource_workflow` to accept optional `student_id` to query both NCERT JSON and student ChromaDB vectors.
   - **Risk**: Low. Preserves static NCERT queries when no student documents exist.

6. **`backend/mcp_integration/servers/filesystem_server.py`**
   - **Exact Modification**: Add read-only tool `search_student_documents(student_id, query, top_k)`.
   - **Risk**: Low. Preserves existing curriculum file tools under `data/resources`.

---

## 4. Frontend Files (To Be Created & Modified)

### 4.1 New Frontend Files
1. **`frontend/components/documents/DocumentUploadModal.tsx`**: Drag-and-drop modal with file validation, upload progress, and page count badge.
2. **`frontend/components/documents/DocumentLibrary.tsx`**: Document grid showing page counts, chunk counts, indexing status, and delete confirmation.
3. **`frontend/app/documents/page.tsx`**: Dedicated "My Study Materials" page accessible from sidebar.

### 4.2 Modified Frontend Files
1. **`frontend/app/teacher/page.tsx`**: Add document attachment selector pill in the composer bar.
2. **`frontend/components/ui/FormattedMessage.tsx`**: Add interactive citation badge rendering (`[Doc: Notes.pdf, p. 4]`) with snippet tooltip.
3. **`frontend/lib/api.ts`**: Add document API helper methods (`uploadDocument`, `getDocuments`, `deleteDocument`, `searchDocuments`).

---

## 5. New Test Suites (To Be Created)

1. **`tests/test_document_parser.py`**: Unit tests for magic bytes, 10MB limit, 15s timeout, and scanned PDF rejection.
2. **`tests/test_vector_store.py`**: Unit tests for chunking, embedding generation (384-d), vector search, and chunk deletion.
3. **`tests/test_document_api.py`**: API tests for upload, list, get, delete, 401 unauthenticated block, and IDOR cross-student block.
4. **`tests/test_teacher_rag_grounding.py`**: Integration tests verifying Teacher Agent grounded Socratic answers and prompt injection resistance.
5. **`tests/test_resource_rag_integration.py`**: Integration tests verifying Resource Agent hybrid retrieval.

---

## 6. Strictly Untouched & Protected Files

The following assets are **100% frozen and must NEVER be modified**:
- **Legacy Directory**: `D:\GYAN Ai` (Permanently protected).
- **Canonical Agent Core Definitions**:
  - `backend/agents/teacher.py` (Frozen).
  - `backend/agents/diagnostic.py` (Frozen).
  - `backend/agents/curriculum.py` (Frozen).
  - `backend/agents/resource.py` (Frozen).
  - `backend/agents/assessment.py` (Frozen).
  - `backend/agents/progress.py` (Frozen).
  - `backend/agents/mentor.py` (Frozen).
- **Production Database**: `data/gyaan_ai.db` (Zero records modified).
- **Core Security**: Session token hashing, cookie handling, and `get_current_student` dependency in `backend/app/main.py`.
