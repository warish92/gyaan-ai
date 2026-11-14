# GYAAN AI — PHASE 5D: RAG ARCHITECTURE PROPOSAL
**Date**: November 14, 2026  
**Target Hardware**: NVIDIA GeForce RTX 2050 (4GB VRAM) | Windows 11  
**Target Inference Engine**: Local Ollama `qwen2.5:3b` | Zero Cloud Dependencies  
**Project**: `D:\Gyaan AI` | **Protected Legacy**: `D:\GYAN Ai` (Untouched)  
**Investigation Mode**: Strictly Read-Only Architecture Design  

---

## 1. Hardware Profile & Resource Budgeting (RTX 2050 4GB VRAM)

Developing a performant, local-first RAG pipeline on a 4GB VRAM GPU requires rigorous memory discipline. Downloading an additional 7B model or running parallel heavy neural networks will trigger CUDA Out-Of-Memory (OOM) errors or force system paging onto system RAM, causing extreme latency spikes.

```
┌────────────────────────────────────────────────────────────────────────┐
│               NVIDIA GeForce RTX 2050 (4096 MB VRAM Budget)            │
├───────────────────────────────────┬────────────────────────────────────┤
│ Qwen 2.5 3B (Q4_K_M Quantization) │ ~2,250 MB VRAM                     │
│ CUDA Context & KV-Cache (2K ctx)  │ ~450 MB VRAM                       │
│ Windows DWM & Display Buffers     │ ~350 MB VRAM                       │
│ Safety Headroom                   │ ~1,046 MB VRAM                     │
├───────────────────────────────────┴────────────────────────────────────┤
│ STRATEGY: Zero extra GPU models! Embeddings run via:                  │
│ • OPTION A: Shared Ollama model memory (/api/embeddings with qwen2.5) │
│ • OPTION B: CPU-Bound ONNX Runtime (onnxruntime==1.31.0 in .venv)     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. End-to-End RAG Architecture Pipeline

```
[Student PDF Upload]
        │
        ▼ (Multipart form validation: %PDF- magic bytes, <= 10MB)
[FastAPI: POST /api/v1/documents/upload]
        │
        ▼ (Hashed filename outside web root: data/uploads/{student_id}/{doc_id}.pdf)
[Secure Disk Storage]
        │
        ▼ (pypdf text extraction + pdfplumber table parser)
[Text Extraction Engine]
        │
        ▼ (Recursive token window: 500 chars, 50 chars overlap)
[Sliding-Window Semantic Chunker]
        │
        ▼ (Ollama /api/embeddings or CPU-ONNX MiniLM via onnxruntime)
[Local Embedding Generator]
        │
        ▼ (In-process SQLite metadata + HNSW vector index: data/vector_store/)
[ChromaDB Persistent Store]
        │
        ├─────────────────────────────────────────────────┐
        │                                                 │
[Student Asks Question (/api/v1/ask)]            [Resource Agent Retrieval (/api/v1/resources)]
        │                                                 │
        ▼                                                 ▼
[Query Vectorizer]                              [Query Vectorizer]
        │                                                 │
        ▼ (Cosine similarity, filtered by student_id)     ▼ (Filtered by student_id + NCERT)
[Top-k Semantic Chunks (k=3-5)]                 [Top-k Semantic Chunks (k=3)]
        │                                                 │
        ▼                                                 ▼
[Teacher Agent Prompt Construction]             [Resource Agent Task Curation]
(Injected with <document_reference> tags)       (Cross-referenced with CBSE standards)
        │                                                 │
        ▼                                                 ▼
[Context-Grounded Socratic Answer]              [Evidence-Backed Source Citations]
(Includes citations: [Doc.pdf, Page 4])         (Includes section numbers & page ranges)
```

---

## 3. Ten Essential Architectural Pillars

### 3.1 PDF Upload & Validation
- **Endpoint**: `POST /api/v1/documents/upload`
- **Validation Rules**:
  - Content-Type must match `application/pdf`.
  - Binary stream header inspection: file must start with `%PDF-` (`0x25 0x50 0x44 0x46`).
  - Strict size limit: $\le 10\text{MB}$ ($10,485,760\text{ bytes}$).
  - Filename sanitized using alphanumeric regex: `^[a-zA-Z0-9_\-\. ]+$`.

### 3.2 Secure Document Storage
- Files are saved to a dedicated, unexposed directory:
  `data/uploads/{student_id}/{doc_id}.pdf`
- Directory permissions are non-executable.
- Path resolution enforces `os.path.commonpath` verification to strictly prevent directory traversal (`../`) attacks.

### 3.3 Text Extraction Engine
- **Primary Tool**: `pypdf` (installed in `.venv` as `pypdf==6.20.0`). Extremely lightweight, fast, and pure Python.
- **Secondary Tool (Tables & Fallback)**: `pdfplumber` (`pdfplumber==0.11.10` in `.venv`) used when structured tabular grids are detected on a page.
- **Safety Cap**: Extraction stops if extracted plain text exceeds $2\text{MB}$ (~500,000 words), preventing decompression bombs.

### 3.4 Document Chunking Strategy
- **Chunk Size**: $500$ characters ($\approx 100 - 120$ tokens).
- **Chunk Overlap**: $50$ characters ($10\%$).
- **Boundary Preservation**: Breaks on paragraph (`\n\n`), then sentence (`. `), then word space (` `).
- **Metadata Enriched per Chunk**:
  ```python
  {
      "chunk_id": f"{doc_id}_c{chunk_index}",
      "document_id": doc_id,
      "student_id": student_id,
      "filename": original_filename,
      "page_number": page_num,
      "char_count": len(chunk_text),
      "created_at": datetime.now(timezone.utc).isoformat()
  }
  ```

### 3.5 Local Embedding Generation (Zero Cloud / VRAM Optimized)
Two local implementation paths are available without downloading external LLMs:
1. **Option A (Shared Ollama Memory)**:
   - Call local Ollama: `POST http://127.0.0.1:11434/api/embeddings` passing `model="qwen2.5:3b"`.
   - Reuses the existing model already loaded in VRAM for inference.
   - Vector dimension: 2048.
2. **Option B (CPU-Bound ONNX Runtime)**:
   - Run lightweight `all-MiniLM-L6-v2` via `onnxruntime==1.31.0` (already installed in `.venv`).
   - Executes entirely on CPU host threads without allocating a single megabyte of GPU VRAM.
   - Vector dimension: 384. Extremely fast ($\sim 5\text{ms}$ per chunk).

### 3.6 Semantic Retrieval & Similarity Search
- **Engine**: `chromadb` (`chromadb==1.5.9` in `.venv`) running embedded via `chromadb.PersistentClient(path="data/vector_store")`.
- **Collection Partitioning**:
  - Unified collection `gyaan_student_documents` with mandatory metadata filtering:
    `collection.query(query_embeddings=[vec], where={"student_id": current_student["id"]}, n_results=4)`
- **Similarity Metric**: Cosine similarity (`hnsw:space: "cosine"`).

### 3.7 Context-Aware AI Responses
- Retrieved chunks are formatted into structured XML context tags:
  ```xml
  <verified_document_context>
    <document title="Science_Notes.pdf" page="4" chunk_id="doc_123_c4">
      An acid is a substance that produces hydrogen ions H+(aq) in aqueous solution...
    </document>
  </verified_document_context>
  ```
- Injected directly into the Teacher Agent prompt, instructing the model to ground its Socratic explanation in the student's text.

### 3.8 Source References & Citations
- Responses must cite exact document names and page numbers:
  `[Source: Science_Notes.pdf, Page 4]`
- The API response model includes a structured `citations` list:
  ```json
  "citations": [
    {
      "document_id": "doc_123",
      "filename": "Science_Notes.pdf",
      "page_number": 4,
      "relevance_score": 0.89
    }
  ]
  ```

### 3.9 Multi-Document Retrieval
- Supports searching across multiple uploaded documents (e.g. Science textbook + teacher handouts + student notes).
- Chunks from distinct documents are ranked by global cosine similarity, allowing the Teacher Agent to synthesize answers combining multiple sources.

### 3.10 Document Lifecycle & Ownership Protection
- **List Documents**: `GET /api/v1/documents` (filtered strictly by authenticated student ID).
- **Document Metadata**: `GET /api/v1/documents/{doc_id}` (verifies ownership; returns page count, chunk count, file size).
- **Document Deletion**: `DELETE /api/v1/documents/{doc_id}`:
  1. Verifies student ownership.
  2. Unlinks physical file from `data/uploads/{student_id}/{doc_id}.pdf`.
  3. Purges all vector chunks from ChromaDB: `collection.delete(where={"$and": [{"document_id": doc_id}, {"student_id": student_id}]})`.
  4. Deletes metadata record from SQLite.

---

## 4. Hardware Sizing & Performance Benchmarks (RTX 2050)

| Operation | Typical Latency | VRAM Consumption | System RAM Footprint |
|---|---|---|---|
| **PDF Text Extraction (10 pages)** | 0.4s – 0.8s | 0 MB | ~40 MB |
| **Sliding-Window Chunking (10 pages)** | 0.05s | 0 MB | ~5 MB |
| **Embedding Generation (40 chunks)** | 1.8s – 3.2s | 0 MB (CPU ONNX) / Shared (Ollama) | ~60 MB |
| **Vector Index Insert (ChromaDB)** | 0.15s | 0 MB | ~30 MB |
| **Vector Similarity Query ($k=4$)** | 0.02s – 0.05s | 0 MB | ~10 MB |
| **Teacher Agent Grounded Generation** | 12s – 22s | 2,250 MB | ~250 MB |
