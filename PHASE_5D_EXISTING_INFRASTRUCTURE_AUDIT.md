# GYAAN AI — PHASE 5D: EXISTING INFRASTRUCTURE AUDIT
**Date**: November 14, 2026  
**Environment**: Windows 11 | Local Ollama `qwen2.5:3b` | NVIDIA GeForce RTX 2050 (4GB VRAM)  
**Project**: `D:\Gyaan AI` | **Protected Legacy**: `D:\GYAN Ai` (Untouched)  
**Investigation Mode**: Strictly Read-Only Audit  

---

## 1. Executive Summary

This audit evaluates the current state of document intelligence, vector indexing, and Retrieval-Augmented Generation (RAG) capabilities across the Gyaan AI codebase (`D:\Gyaan AI`). 

### Core Audit Finding:
While the Python virtual environment (`.venv`) possesses a rich set of pre-installed document extraction and vector database libraries (including `chromadb`, `lancedb`, `pdfplumber`, `pypdf`, `pypdfium2`, `onnxruntime`, `tiktoken`, and `python-multipart`), the **active backend application (`backend/`) currently contains ZERO document upload, PDF parsing, text chunking, embedding generation, or vector database integrations**. 

Current educational resource retrieval relies entirely on a single 20KB static JSON file (`data/resources/ncert_class10_science.json`) queried via deterministic keyword matching.

---

## 2. Comprehensive Component-by-Component Audit

| Infrastructure Component | Implementation Status | Existing Foundation | Missing Capabilities |
|---|---|---|---|
| **1. PDF & Document Upload** | **NOT IMPLEMENTED** | `python-multipart==0.0.32` installed in `.venv`. | No FastAPI upload routes; no upload storage directory; no upload schemas; no frontend file picker. |
| **2. Document Extraction** | **UNINTEGRATED LIBRARIES** | `pdfplumber==0.11.10`, `pypdf==6.20.0`, `pypdfium2==5.14.0`, `pdfminer.six` installed in `.venv`. | No service modules import or utilize these libraries. No PDF text/table extraction logic. |
| **3. Text Processing & Chunking** | **PRIMITIVE TOKEN MATCHING** | String splitting on stop words in `resource_retriever.py`. | No semantic chunker; no recursive token sliding window; no overlap management; no document metadata tagging. |
| **4. Embedding Generation** | **NOT IMPLEMENTED** | Ollama running `qwen2.5:3b`; `onnxruntime==1.31.0` in `.venv`. | No embedding client service; no vectorizer; no batch embedding generation pipeline. |
| **5. Vector Database & Indexing** | **UNINTEGRATED LIBRARIES** | `chromadb==1.5.9`, `lancedb==0.40.0`, `pyarrow==26.0.0` in `.venv`. | No active vector store client; no persistent collections; no index directory on disk. |
| **6. Retrieval Mechanism** | **DETERMINISTIC KEYWORD ONLY** | Token intersection score against static JSON in `resource_retriever.py`. | No semantic search; no cosine similarity ranking; no hybrid dense+sparse retrieval; no top-$k$ chunk fetch. |
| **7. MCP Document Tools** | **RESTRICTED TO STATIC REPO** | `filesystem_server.py` implements sandboxed JSON/text listing & reading. | Cannot read PDFs; cannot query vector indices; cannot accept student-uploaded documents. |
| **8. Resource Agent Retrieval** | **STATIC JSON CURATION** | `create_resource_task` in `backend/agents/resource.py` formats JSON excerpts. | Cannot search vector stores or curate student-uploaded notes/documents. |
| **9. Teacher Agent Answering** | **METADATA-BOUND ONLY** | Injects CBSE grade, subject, chapter, and topic strings into prompt. | No mechanism to ingest retrieved document excerpts or ground explanations on student PDFs. |
| **10. APIs & Frontend Pages** | **STATIC PRESETS ONLY** | `POST /api/v1/resources` and `frontend/app/resources/page.tsx`. | No document upload, list, or delete APIs; frontend lacks file upload UI and PDF viewing components. |

---

## 3. Deep-Dive Codebase Inspections

### 3.1 Document Extraction & Installed Libraries
An inspection of the virtual environment (`.venv`) confirms the presence of industry-standard document intelligence packages:
```
chromadb                  1.5.9
lancedb                   0.40.0
pdfplumber                0.11.10
pypdf                     6.20.0
pypdfium2                 5.14.0
pdfminer.six              20260107
onnxruntime               1.31.0
tiktoken                  0.14.0
tokenizers                0.23.3
python-multipart          0.0.32
```
However, an exhaustive search across all active Python source files in `backend/` confirmed that **none of these packages are currently imported or referenced in application logic**.

### 3.2 Existing Resource Retrieval Service
- **File**: `backend/services/resource_retriever.py` (116 lines)
- **Function**: `retrieve_local_resources(subject, topic, grade, max_results=3)`
- **Mechanism**:
  - Scans `data/resources/*.json`.
  - Splits `topic` into tokens, filters a hardcoded `stop_words` set (`{"and", "the", "for", "with", ...}`).
  - Computes a primitive heuristic score:
    - Direct phrase in title/chapter/section: $+10$ points.
    - Phrase in keywords: $+8$ points.
    - Token in chapter/section: $+4$ points.
    - Token in title: $+3$ points.
  - Returns raw excerpt strings from `data/resources/ncert_class10_science.json` (20,254 bytes).
- **Limitations**:
  - Strictly limited to one Science chapter corpus.
  - Zero semantic understanding (synonyms, conceptual paraphrasing, or multilingual queries fail completely).
  - Incapable of expanding beyond pre-curated JSON files.

### 3.3 Existing MCP Filesystem Server
- **File**: `backend/mcp_integration/servers/filesystem_server.py` (236 lines)
- **Server Name**: `gyaan_educational_filesystem`
- **Capabilities**:
  - `list_educational_resources(sub_directory)`: Lists files within `data/resources`.
  - `read_educational_resource(file_name, sub_directory)`: Reads text/JSON files under strict path traversal checks (`validate_and_resolve_resource_path`).
- **Limitations**:
  - Strictly sandboxed to `data/resources`.
  - Rejects binary files (`.pdf`, `.docx`).
  - No indexing or text chunking capabilities.

### 3.4 Teacher Agent & Prompt Context Constraints
- **File**: `backend/agents/crew.py` (lines 35–85)
- **Function**: `create_teacher_task`
- **Current Prompt Structure**:
  ```python
  context_spec = f"{grade} CBSE student studying {subject}, Chapter: '{chapter}', Topic: '{topic}'"
  description = (
      f"A {context_spec} has asked the following question:\n\n"
      f"\"{student_question}\"\n\n"
      f"Pedagogical Mode: {lesson_mode.upper()} — {mode_guidance}\n"
      f"{obj_text}\n"
      f"Instructions: Explain concepts clearly following NCERT/CBSE standards..."
  )
  ```
- **Limitation**: The Teacher Agent relies exclusively on the parametric knowledge of `qwen2.5:3b`. It does not receive retrieved textual evidence, textbook excerpts, or student-uploaded source material.

### 3.5 API Endpoints & Frontend Real Estate
- **FastAPI Endpoints (`backend/app/main.py`)**:
  - Out of 57 registered endpoints, only `/api/v1/resources` touches educational resources.
  - There are zero endpoints supporting file uploads, document management, or vector querying.
- **Frontend (`frontend/app/resources/page.tsx`)**:
  - UI offers 5 static NCERT Science presets and a text input field.
  - There is no document library, file drop zone, progress bar, or document management interface.

---

## 4. Gap Analysis: What Must Be Built for Phase 5D

1. **Upload Gateway**: Multipart endpoint with magic byte validation, file size enforcement (10MB max), and secure student-isolated directory storage.
2. **Text Extraction Pipeline**: Multi-format extractor leveraging `pypdf` for fast digital text and `pdfplumber` for structured tables.
3. **Semantic Chunking Service**: Sliding window chunker (500 chars / ~120 tokens with 10% overlap) preserving page numbers and chapter metadata.
4. **Local Embedding Service**: Zero-cloud vectorizer utilizing local Ollama `qwen2.5:3b` or CPU-bound `onnxruntime` to respect RTX 2050 4GB VRAM bounds.
5. **Persistent Vector Store**: Embedded `chromadb` client storing collections in `data/vector_store/` with strict `student_id` metadata isolation.
6. **Agent Pipeline Integration**: Connecting retrieved vector chunks to Resource Agent and Teacher Agent tasks with explicit citation tracking.
7. **Document Management UI**: Dedicated Next.js interface for uploading, previewing, querying, and deleting study documents.
