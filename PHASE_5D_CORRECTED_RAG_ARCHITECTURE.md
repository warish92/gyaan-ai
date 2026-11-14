# GYAAN AI — PHASE 5D: CORRECTED RAG ARCHITECTURE
**Date**: November 14, 2026  
**Target Hardware**: NVIDIA GeForce RTX 2050 (4GB VRAM) | Windows 11  
**Target Inference Engine**: Local Ollama `qwen2.5:3b` (Generation) + Local CPU ONNX MiniLM (Embeddings)  
**Project**: `D:\Gyaan AI` | **Protected Legacy**: `D:\GYAN Ai` (Untouched)  
**Authorization Mode**: Strictly Read-Only Architecture Design  

---

## 1. Corrected Architectural Topology

This architecture resolves all path ambiguities, respects the 4GB VRAM ceiling of the RTX 2050 laptop GPU, and preserves the eight canonical CrewAI specialist agents without modification.

```
[Student PDF Upload via Drag-and-Drop]
               │
               ▼ (Multipart stream validation: %PDF- magic bytes, <= 10MB)
[FastAPI: POST /api/v1/documents/upload] (in backend/app/main.py via router)
               │
               ▼ (Path.is_relative_to check: data/uploads/{student_id}/{doc_id}.pdf)
[Secure Disk Storage (Non-Public)]
               │
               ▼ (ProcessPoolExecutor with hard 15s timeout; pypdf parser)
[Isolated Text Extractor] ──(If 0 chars extracted)──► [Graceful Scanned-PDF Refusal]
               │ (Valid selectable digital text)
               ▼ (Sliding-window: 500 chars, 50 chars overlap, page-tagged)
[Semantic Text Chunker]
               │
               ▼ (chromadb.utils.embedding_functions.DefaultEmbeddingFunction)
[CPU-Bound ONNX MiniLM Generator] (384 dimensions, 0 MB GPU VRAM)
               │
               ▼ (Persistent collection 'student_documents' in data/vector_store/)
[ChromaDB In-Process Index] ◄───► [SQLite Metadata: student_documents table]
               │
               ├───────────────────────────────────────────────┐
               │                                               │
[Student Query in AI Teacher Studio]             [Curriculum / Resource Workflow]
               │                                               │
               ▼                                               ▼
[Orchestrator Intent: 'document_qa']            [Resource Agent Hybrid Retrieval]
               │                                               │
               ▼                                               ▼
[Query Vectorizer (384-d, CPU)]                 [Query Vectorizer (384-d, CPU)]
               │                                               │
               ▼ (where={"student_id": student_id})            ▼ (where={"student_id": student_id})
[Top-k Semantic Chunks (k=3-5)]                 [Top-k Semantic Chunks (k=3)]
               │                                               │
               ▼                                               ▼
[Teacher Task Context Augmentation]             [Resource Agent Content Comparison]
(Structured <student_document_excerpt> tags)    (NCERT baseline vs student notes)
               │                                               │
               ▼                                               ▼
[Ollama qwen2.5:3b Socratic Tutoring]           [Evidence-Backed Resource Summary]
(Explicit citations: [Doc.pdf, Page 4])         (Identifies textbook omissions/gaps)
```

---

## 2. Nine Core Architectural Pillars (Corrected Specifications)

### 2.1 PDF Upload & Validation Layer
- **Endpoint**: `POST /api/v1/documents/upload`
- **MIME & Header Verification**:
  - Rejects files where first 4 bytes do not match `%PDF-` (`0x25 0x50 0x44 0x46`).
  - Enforces strict streaming size limit: $\le 10\text{ MB}$ ($10,485,760\text{ bytes}$).
  - Filename sanitized using regex `^[a-zA-Z0-9_\-\.]{1,128}$`.
  - Internal storage key: `doc_{uuid4().hex[:16]}.pdf`.

### 2.2 Secure Non-Public File Storage
- **Path Resolution**: Stored exclusively in `data/uploads/{student_id}/{doc_id}.pdf`.
- **Directory Traversal Defense**:
  ```python
  base_dir = (Path("data/uploads") / student_id).resolve()
  target_file = (base_dir / f"{doc_id}.pdf").resolve()
  if not target_file.is_relative_to(base_dir):
      raise HTTPException(status_code=400, detail="Invalid path containment")
  ```

### 2.3 Process-Isolated Text Extraction Engine
- **Parser**: `pypdf` text stream extractor with fallback to `pdfplumber` for tabular data.
- **Process Isolation Timeout**:
  - Python thread timeouts cannot reliably terminate stuck C-extensions or corrupted PDF decompression loops.
  - Extraction executes inside `concurrent.futures.ProcessPoolExecutor(max_workers=1)`.
  - Hard timeout enforced: $15\text{ seconds}$. If exceeded, the worker process is terminated via `.terminate()` and the document is marked `failed`.
- **Scanned PDF Handling**:
  - If total extracted characters across all pages is $< 50$, the system aborts indexing and returns an informative client error: *"No selectable text found in this PDF. Scanned images are not supported."*

### 2.4 Semantic Chunking Strategy
- **Chunk Geometry**: 500 characters per chunk with 50-character overlap ($10\%$).
- **Natural Boundary Preservation**: Paragraph breaks (`\n\n`), sentence endings (`. `), and word boundaries.
- **Metadata Tagging**: Every chunk retains `student_id`, `document_id`, `filename`, `page_number`, `chunk_index`, and `char_count`.

### 2.5 In-Process CPU Vector Embedding Engine
- **Engine**: Local ONNX `all-MiniLM-L6-v2` executed via `onnxruntime==1.31.0` on CPU threads.
- **Weights Source**: Cached locally at `C:\Users\waris\.cache\chroma\onnx_models\all-MiniLM-L6-v2\onnx\model.onnx`.
- **Zero VRAM Footprint**: Allocates $0\text{ MB}$ of GPU VRAM, leaving 100% of the RTX 2050 4GB memory for Ollama `qwen2.5:3b`.
- **Vector Dimension**: 384 dimensions.

### 2.6 ChromaDB Persistent Indexing
- **Client**: `chromadb.PersistentClient(path="data/vector_store")`.
- **Collection**: Unified `gyaan_student_documents` with HNSW cosine similarity space.
- **Multi-Tenant Filter**: Mandatory query filter `where={"student_id": current_student["id"]}`.

### 2.7 Multi-Layered Prompt Injection Containment
- Document text is wrapped in distinctive `<student_document_excerpt>` envelopes.
- Pre-retrieval pattern inspection checks for override signatures (`"ignore previous instructions"`, `"system override"`).
- System prompt instructs Teacher Agent that text inside excerpts has zero directive authority.
- The Teacher Agent operates in a read-only context with zero tool execution privileges.

### 2.8 Reliable Citation Extraction
- Citations are synthesized from actual chunk metadata (`filename`, `page_number`, `relevance_score`), never hallucinated by the LLM.
- The response returns a structured `citations` array alongside the text:
  ```json
  "citations": [
    {
      "document_id": "doc_8f1a2c",
      "filename": "Science_Notes.pdf",
      "page_number": 4,
      "relevance_score": 0.89
    }
  ]
  ```

### 2.9 Atomic Document Lifecycle & Deletion
- **Delete Operation (`DELETE /api/v1/documents/{doc_id}`)**:
  1. Verify ownership in SQLite `student_documents` table for `current_student["id"]`.
  2. Mark status as `deleting`.
  3. Purge all chunks from ChromaDB: `collection.delete(where={"$and": [{"document_id": doc_id}, {"student_id": student_id}]})`.
  4. Unlink physical file from disk `data/uploads/{student_id}/{doc_id}.pdf`.
  5. Delete row from SQLite `student_documents`.
  6. Return confirmation: `{ "deleted": True, "document_id": doc_id }`.
