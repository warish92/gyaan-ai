# GYAAN AI — PHASE 5D: REGRESSION RISK REPORT & MITIGATION PLAN
**Date**: November 14, 2026  
**Target Hardware**: NVIDIA GeForce RTX 2050 (4GB VRAM) | Windows 11  
**Project**: `D:\Gyaan AI` | **Protected Legacy**: `D:\GYAN Ai` (Untouched)  
**Investigation Mode**: Strictly Read-Only Architecture Design  

---

## 1. Regression Risk Matrix

Phase 5D introduces document intelligence and semantic retrieval to Gyaan AI. To ensure that existing core capabilities (tutoring, assessment, mentoring, diagnostics, progress tracking) remain completely undisturbed, every subsystem is evaluated across probability, severity, and defense-in-depth mitigations.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Subsystem Risk Evaluation                         │
├─────────────────────────┬─────────────┬───────────┬────────────────────┤
│ Subsystem / Area        │ Probability │ Severity  │ Overall Risk Level │
├─────────────────────────┼─────────────┼───────────┼────────────────────┤
│ 1. 8 Canonical Agents   │ LOW         │ HIGH      │ LOW                │
│ 2. GPU VRAM (RTX 2050)  │ MEDIUM      │ CRITICAL  │ CONTROLLED         │
│ 3. Database Integrity   │ VERY LOW    │ CRITICAL  │ VERY LOW           │
│ 4. Authentication/IDOR  │ LOW         │ HIGH      │ VERY LOW           │
│ 5. Frontend Build / SSR │ LOW         │ MEDIUM    │ LOW                │
└─────────────────────────┴─────────────┴───────────┴────────────────────┘
```

---

## 2. Detailed Subsystem Risk Analysis & Mitigations

### 2.1 Canonical Agent Functionality (Zero Alteration Guarantee)
- **Specific Risk**: Introducing document context might alter the Teacher Agent's Socratic pedagogy, leading to direct answer-dumping or breaking other agent interactions (e.g. Assessment Agent quiz generation or Mentor Agent guidance).
- **Technical Root Cause**: Overriding system prompts or altering base agent configurations.
- **Mitigation Strategy**:
  1. Base agent definitions in `backend/agents/*.py` remain **100% frozen**.
  2. Document context is passed **only** when explicitly requested via the new `document_qa` intent or explicit `document_id`.
  3. Standard tutoring queries continue to execute the unchanged `handle_teacher_answer` function.
  4. The task description provides clear Socratic boundaries: *"Maintain your supportive Socratic teaching style; explain using an intuitive analogy and pose a follow-up question."*

### 2.2 Hardware & VRAM Management (RTX 2050 4GB Headroom)
- **Specific Risk**: Attempting to load secondary neural models or embedding transformers onto the GPU alongside Ollama `qwen2.5:3b` triggers CUDA Out-Of-Memory (OOM) or system crash (Exit Code `0xC0000409`).
- **Technical Root Cause**: RTX 2050 has only 4,096 MB VRAM. `qwen2.5:3b` occupies $\sim 2,250\text{ MB}$, and KV cache consumes $\sim 450\text{ MB}$, leaving $\sim 1\text{ GB}$ total safety margin.
- **Mitigation Strategy**:
  1. **Strict 0 MB GPU VRAM Embedding Path**: Use CPU-bound `onnxruntime` (`all-MiniLM-L6-v2`), which runs on host CPU threads with zero GPU memory allocation.
  2. **Alternative Zero-Allocation Path**: Utilize Ollama's already-resident model memory via `POST http://127.0.0.1:11434/api/embeddings` (`model="qwen2.5:3b"`), creating zero new GPU allocations.
  3. Retrieval context is strictly capped at $k=4$ chunks ($\le 2,000$ characters), preventing context window blowup.

### 2.3 SQLite Production Database Integrity
- **Specific Risk**: Schema corruption, table locks, or accidental data loss in `data/gyaan_ai.db` (which contains 793 registered students, 440 sessions, 253 quizzes, and 150 diagnostics).
- **Technical Root Cause**: Running destructive `DROP TABLE`, table restructuring, or failing migration scripts.
- **Mitigation Strategy**:
  1. Zero modifications to any existing table schemas.
  2. Document metadata is isolated entirely in a new, independent table: `CREATE TABLE IF NOT EXISTS student_documents (...)`.
  3. All unit and integration tests are executed against isolated in-memory (`:memory:`) or temporary file databases.

### 2.4 Authentication, Session Security & IDOR Defense
- **Specific Risk**: New document endpoints could allow unauthenticated users or malicious students to inspect or delete documents belonging to other students.
- **Technical Root Cause**: Missing auth dependencies or relying on unverified client-provided IDs.
- **Mitigation Strategy**:
  1. Every single endpoint under `/api/v1/documents/*` depends on `get_current_student` from `backend/app/main.py`.
  2. All ChromaDB vector queries mandate the filter `where={"student_id": current_student["id"]}`.
  3. Every document read or delete operation performs explicit ownership verification against SQLite before proceeding.

### 2.5 Frontend Build & Next.js Hydration Stability
- **Specific Risk**: Introducing new components or document upload forms causing hydration mismatch or TypeScript compilation errors in Next.js.
- **Technical Root Cause**: Improper client-side React hooks (`useState`, `useEffect`, `sessionStorage`) in Server Components.
- **Mitigation Strategy**:
  1. All new interactive components (`DocumentUploadModal`, `DocumentLibrary`, `/documents` page) strictly declare `"use client";`.
  2. Full Next.js production build (`npm run build`) is executed and validated before declaring implementation complete.

---

## 3. Comprehensive Verification & Testing Protocol

Before any code in Phase 5D is merged, the following test battery must pass with 100% success:

1. **Unit Test Suite**:
   - `test_document_service.py`: Magic byte detection, 10MB file limit, text extraction, sliding chunker.
   - `test_vector_store.py`: Embedding generation, cosine similarity search, chunk deletion.
   - Existing unit test suite (all 248 tests in `tests/unit/`) must pass without regressions.
2. **Integration Test Suite**:
   - `test_document_api.py`: Upload, list, metadata retrieval, deletion, and search.
   - Cross-student IDOR access test: Student B cannot view or search Student A's documents.
   - Existing integration test suite (9/9 passed in `tests/integration/test_phase4_integration.py`).
3. **Live End-to-End Test**:
   - Upload sample CBSE Science PDF.
   - Query AI Teacher: *"Explain Chapter 2 according to my uploaded document."*
   - Verify grounded Socratic response with page citation `[Source: ..., Page X]`.
4. **Hardware VRAM Check**:
   - `nvidia-smi` check verifying VRAM utilization remains under $3.2\text{ GB} / 4.0\text{ GB}$.

---

## 4. Rollback Plan

If any critical issue or regression occurs during Phase 5D implementation, the following rollback steps will instantly restore the application to its current clean state:

```
Step 1: Unregister Documents Router
  In backend/app/main.py, remove:
  app.include_router(documents_router, prefix="/api/v1/documents")

Step 2: Remove New Standalone Modules
  Delete backend/services/document_service.py
  Delete backend/services/vector_store.py
  Delete backend/api/routers/documents.py
  Delete backend/app/schemas_documents.py

Step 3: Revert Orchestrator Intent Hook
  Remove document_qa branch from backend/agents/orchestrator.py

Step 4: Clean Up File Storage
  Purge data/uploads/ and data/vector_store/

Step 5: Database Schema Cleanliness
  DROP TABLE IF EXISTS student_documents;
  (All 23 existing tables, 793 students, and historical sessions remain completely intact).
```
