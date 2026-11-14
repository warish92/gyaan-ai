# GYAAN AI — PHASE 5D: FINAL TESTING PLAN & REGRESSION VERIFICATION
**Date**: November 14, 2026  
**Target Hardware**: NVIDIA GeForce RTX 2050 (4GB VRAM) | Windows 11  
**Project**: `D:\Gyaan AI` | **Protected Legacy**: `D:\GYAN Ai` (Untouched)  
**Authorization Mode**: Strictly Read-Only Test Protocol Design  

---

## 1. Regression Verification Strategy

To guarantee that adding Document Intelligence and RAG causes zero regression to existing tutoring, assessment, diagnostic, mentoring, and security workflows, testing is divided into three distinct batteries:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Phase 5D Three-Tier Testing Matrix                   │
├─────────────────────────┬──────────────┬───────────────┬───────────────┤
│ Tier                    │ Test Count   │ Environment   │ Target Area   │
├─────────────────────────┼──────────────┼───────────────┼───────────────┤
│ Tier 1: Existing Suites │ 248 tests    │ Isolated Mock │ Core App Flow │
│ Tier 2: Existing Sec.   │ 26 tests     │ Isolated DB   │ SEC-01 to 14  │
│ Tier 3: New RAG Battery │ 28 tests     │ Temp Test Dir │ RAG Endpoints │
│ Live: Ollama Integ.     │ 9 tests      │ Local GPU     │ Real LLM Loop │
│ Frontend Build Check    │ 16/16 routes │ Node/Webpack  │ Next.js Prod  │
└─────────────────────────┴──────────────┴───────────────┴───────────────┘
```

---

## 2. Tier 1 & Tier 2: Existing Application Protection

All existing tests in `tests/` must execute with **100% PASS** before and after each Phase 5D substage:

- **Authentication & Persistence (`test_auth_and_persistence.py`)**: 12 tests.
- **Security & Authorization (`test_phase5b_security_verification.py`)**: 26 tests.
- **Agent Independence (`test_specialist_agent_independence.py`, `test_specialist_isolation_and_independence.py`)**: 21 tests.
- **Teacher & Orchestrator Workflows (`test_teacher_crew.py`, `test_orchestrator_unit.py`, `test_verify_8_intent_routes.py`)**: 40 tests.
- **Database & Session Isolation (`test_database.py`, `test_database_isolation.py`)**: 24 tests.
- **ADK, A2A & MCP Integration (`test_adk_foundation.py`, `test_a2a_interoperability.py`, `test_mcp_integration.py`)**: 32 tests.
- **Progress & Mentor Workflows (`test_progress_mentor_unit.py`, `test_phase6_integration.py`)**: 18 tests.

> [!IMPORTANT]
> All tests must use isolated in-memory (`:memory:`) or temporary pytest databases. **No test shall ever execute writes against production `data/gyaan_ai.db`.**

---

## 3. Tier 3: New Phase 5D RAG Test Battery (28 Test Cases)

### 3.1 Document Parsing & Ingestion Unit Tests (`tests/test_document_parser.py`)
1. `test_valid_pdf_magic_bytes_accepted`: `%PDF-` header passes.
2. `test_invalid_file_extension_and_header_rejected`: Text/binary file without `%PDF-` rejected with HTTP 400.
3. `test_oversized_pdf_stream_rejected`: File exceeding $10\text{ MB}$ rejected with HTTP 413.
4. `test_path_traversal_in_filename_blocked`: Filename containing `../../` sanitized; storage path stays within `data/uploads/{student_id}`.
5. `test_process_isolation_timeout_kills_hung_worker`: Synthetic hanging extractor killed cleanly at 15s.
6. `test_scanned_pdf_zero_characters_rejected`: PDF with raster images only returns graceful refusal message.
7. `test_corrupted_pdf_stream_fails_gracefully`: Malformed PDF returns clean error without crashing process.

### 3.2 Vector Store & Embedding Unit Tests (`tests/test_vector_store.py`)
8. `test_sliding_window_chunk_geometry`: 500-char chunks with 50-char overlap produced correctly.
9. `test_chunk_metadata_completeness`: Every chunk retains `student_id`, `document_id`, `page_number`, `chunk_index`.
10. `test_onnx_minilm_embedding_dimension`: Outputs exact 384-dimensional vector using CPU threads.
11. `test_vector_similarity_ranking`: Returns relevant chunk as top-1 result (cosine similarity $> 0.80$).
12. `test_multitenant_vector_isolation`: Chunks for Student A never return in query for Student B (`where={"student_id": "B"}`).
13. `test_chunk_deletion_purges_vectors`: Deleting document removes 100% of its chunks from ChromaDB.

### 3.3 Document API & Security Tests (`tests/test_document_api.py`)
14. `test_upload_endpoint_requires_auth`: Unauthenticated `POST /upload` returns 401.
15. `test_upload_endpoint_persists_sqlite_record`: Authenticated upload creates row in `student_documents`.
16. `test_list_documents_returns_only_owned_files`: Student A sees only Student A's documents.
17. `test_get_document_details_idor_blocked`: Student B querying Student A's `doc_id` receives 404.
18. `test_delete_document_idor_blocked`: Student B cannot delete Student A's document.
19. `test_atomic_delete_lifecycle`: Delete unlinks file, removes ChromaDB vectors, and deletes SQLite row.
20. `test_duplicate_file_upload_handled`: Uploading identical filename generates unique `doc_id` without collision.

### 3.4 Agent Grounding & Socratic Tutoring Tests (`tests/test_teacher_rag_grounding.py`)
21. `test_orchestrator_routes_document_qa`: Question mentioning uploaded document routes to `handle_document_tutoring`.
22. `test_teacher_task_injected_with_excerpt_tags`: Context injected inside `<student_document_excerpt>` tags.
23. `test_teacher_response_contains_page_citation`: Output includes `[Source: ..., Page X]`.
24. `test_prompt_injection_override_neutralized`: PDF containing *"Ignore previous instructions"* does not alter Teacher Socratic persona or leak secrets.
25. `test_unanswered_question_reports_document_gap`: When document lacks answer, Teacher acknowledges omission honestly without hallucination.
26. `test_standard_tutoring_without_docs_unaffected`: Standard questions continue executing unmodified `handle_teacher_answer`.

### 3.5 Lifecycle Recovery & Fault Tolerance
27. `test_partial_failure_leaves_no_orphans`: Extraction error unlinks partial PDF and marks SQLite status `failed`.
28. `test_startup_reconciliation_cleans_stale_jobs`: Documents stuck in `processing_*` for $> 10\text{ min}$ transitioned to `failed`.

---

## 4. Hardware Resource & Performance Benchmarks (RTX 2050)

| Metric | Target Boundary | Verification Method |
|---|---|---|
| **GPU VRAM Utilization** | $\le 3.2\text{ GB} / 4.0\text{ GB}$ ($\ge 800\text{ MB}$ headroom) | `nvidia-smi` monitor during generation |
| **CPU Embedding Latency** | $< 10\text{ ms}$ per 500-char chunk | In-process timer on `DefaultEmbeddingFunction` |
| **ChromaDB Query Latency** | $< 25\text{ ms}$ for $k=4$ nearest neighbors | In-process timer on `collection.query` |
| **Full PDF Ingestion (10 pages)** | $< 4.0\text{ seconds}$ total | End-to-end timer from upload to `ready` |
| **Teacher Answer Generation** | $12\text{s} - 22\text{s}$ (identical to current baseline) | `POST /api/v1/ask` timing |

---

## 5. Frontend Build & Regression Check

Before declaring Phase 5D complete:
```bash
cd frontend
npm run build
```
- **Acceptance Criteria**: 16/16 routes compile cleanly; zero TypeScript compiler errors (`tsc --noEmit`); zero ESLint errors; responsive mobile/desktop layout maintained.
