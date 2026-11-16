# GYAAN AI — PHASE 5A: COMPREHENSIVE SECURITY AUDIT REPORT

**Project:** `D:\Gyaan AI`  
**Protected Legacy Project:** `D:\GYAN Ai` (Untouched, strictly isolated)  
**Phase:** Phase 5 — Security Guardrails  
**Stage:** Phase 5A — READ-ONLY SECURITY AUDIT  
**Audit Timestamp:** 2026-11-13 11:33:15 UTC  
**Audit Status:** COMPLETED  
**Mode:** Strictly Read-Only (Zero code edits, zero schema changes, zero database mutations, zero package installs)  

---

## 1. PROJECT OVERVIEW AND AUDIT OBJECTIVES

The **Gyaan AI** platform is an intelligent educational ecosystem designed for CBSE Class 10 science and mathematics instruction. The system integrates eight canonical CrewAI agents powered by a local Ollama LLM (`qwen2.5:3b`), an Agent-to-Agent (A2A) protocol implementation, a Google Agent Development Kit (ADK) subsystem, a Model Context Protocol (MCP) educational tool integration, a FastAPI backend, an SQLite database, and a Next.js 14 frontend.

### Audit Objectives
1. Perform an exhaustive, evidence-based security assessment across 16 architectural dimensions.
2. Identify concrete vulnerabilities, authorization gaps, information disclosure vectors, and missing guardrails.
3. Compare the current codebase against the 13 canonical security requirements defined by the professor.
4. Execute non-destructive security tests and verify input validation behaviors.
5. Provide a prioritized, actionable remediation blueprint for Phase 5B.

---

## 2. AUDIT SCOPE AND METHODOLOGY

The security audit was conducted using a defense-in-depth, multi-methodological approach:
- **Static Source Code Analysis:** Comprehensive inspection of 57 backend Python files, 42 frontend TypeScript files, and 28 test files.
- **Dynamic Input Validation Testing:** Targeted non-destructive testing of FastAPI endpoints using `TestClient` across 8 adversarial scenarios (malformed JSON, type mismatches, missing fields, path traversal, oversized inputs).
- **Security Test Suite Execution:** Automated execution and evaluation of 7 existing security-focused pytest suites (123 tests collected).
- **Cryptographic & Secret Scanning:** Static regex scanning for hardcoded credentials, token hashing implementations, and `.gitignore` hygiene.
- **Database & Data Privacy Inspection:** Static SQL query analysis across all database operations, followed by read-only SQLite schema and record verification.

### Strict Safety Invariants Maintained
- **Protected Legacy Project:** `D:\GYAN Ai` was untouched. Verified last modified: `10/28/2026 09:28:28 AM`.
- **Database Non-Destruction:** Active database `D:\Gyaan AI\data\gyaan_ai.db` was not modified, reset, reseeded, or truncated. Integrity verified: `PRAGMA integrity_check = ok`.
- **Backup Intact:** `data/gyaan_ai.db.bak_phase4` preserved intact (4,169,728 bytes).
- **Synthetic Data Exclusively:** No real student data, passwords, or live credentials were used or exposed.

---

## 3. SECURITY ARCHITECTURE REVIEWED

```mermaid
flowchart TD
    Client["Next.js 14 Frontend<br>(localStorage: gyaan_auth_token)"] -->|"HTTP / REST"| Gateway["FastAPI Application (Port 8000)<br>CORSMiddleware (localhost:3000)"]
    Gateway -->|"Opaque Token Auth (scrypt + SHA-256)"| DB[("SQLite Database<br>data/gyaan_ai.db (WAL Mode)")]
    Gateway -->|"Pipeline Dispatch"| Orch["Orchestrator Agent<br>(backend/agents/orchestrator.py)"]
    
    subgraph "Eight Canonical CrewAI Agents (Local Ollama: qwen2.5:3b)"
        Orch --> Teacher["Teacher Agent"]
        Orch --> Diag["Diagnostic Agent"]
        Orch --> Curric["Curriculum Agent"]
        Orch --> Res["Resource Agent"]
        Orch --> Assess["Assessment Agent"]
        Orch --> Prog["Progress Agent"]
        Orch --> Mentor["Mentor Agent"]
    end

    Gateway -->|"REST /api/v1/adk"| ADK["Google ADK Runner<br>(InMemorySessionService)"]
    Gateway -->|"JSON-RPC 2.0 /api/v1/a2a"| A2A["A2A Protocol Server<br>(Bearer / X-A2A-Internal-Token)"]
    Gateway -->|"REST /api/v1/mcp"| MCP["MCP Integration<br>(data/resources Sandbox)"]
    Gateway -->|"REST /api/v1/observability"| Obs["Observability Store & Logger<br>(HMAC Redaction)"]
```

---

## 4. EXECUTIVE SUMMARY

The audit identified **14 total security findings** across the platform:
- **CRITICAL:** **0**
- **HIGH:** **5** (Authentication bypass on student history, unauthenticated MCP tool execution, unauthenticated ADK analysis, unauthenticated observability endpoints, complete absence of toxicity/content moderation).
- **MEDIUM:** **6** (Hardcoded A2A fallback secret & timing attack, A2A session isolation bypass, missing prompt injection on chat endpoints, missing security headers & exposed `/docs`, missing rate limiting, frontend token storage in `localStorage`).
- **LOW:** **3** (Google ADK in-memory session loss risk, residual legacy JWT configuration in `.env.example`, test suite database pollution).

### Core Security Strengths Confirmed
1. **100% Parameterized SQL Execution:** All database queries utilize parameterized tuples `(?, ...)`, preventing SQL injection across all 23 database tables.
2. **Robust Password & Token Cryptography:** Passwords use standard-library `hashlib.scrypt` with a 16-byte random salt and constant-time verification. Session tokens are 256-bit URL-safe strings stored exclusively as SHA-256 hashes.
3. **Strict MCP Filesystem Sandboxing:** The MCP subsystem restricts file reading strictly to `data/resources` using `Path.relative_to()`, blocks directory traversal (`..`), restricts extensions to `.json`, `.txt`, `.md`, `.csv`, and enforces a 3-tool allowlist.
4. **Strict HMAC Telemetry Redaction:** `backend/observability/redaction.py` enforces HMAC-SHA256 student pseudonymization without fallback secrets, omitting student IDs if the secret is unavailable.

---

## 5. DETAILED ANALYSIS OF AUDIT FINDINGS

### 5.1 HIGH-Severity Findings

#### SEC-FIND-01: Unauthenticated Access and IDOR on Student Assessment History & Learning Journeys
- **Component:** FastAPI Core Application (`backend/app/main.py`)
- **Affected Endpoints:** `GET /api/v1/assessments/history/{student_id}`, `GET /api/v1/learning-journey/student/{student_id}`
- **Description:** Both endpoints depend on `get_optional_current_student`. The authorization check reads:
  ```python
  if current_student and current_student["id"] != student_id:
      raise HTTPException(status_code=403, detail="Access denied")
  ```
  When an unauthenticated caller sends a request without an `Authorization` header, `current_student` is `None`. The condition `if current_student` evaluates to `False`, skipping the check entirely and returning the complete assessment attempts and sequential learning journeys for any requested `student_id`.
- **Evidence:** TestClient request `GET /api/v1/assessments/history/student_123` with no token returned `HTTP 200 OK` with full JSON payload.
- **Impact:** Complete failure of student data privacy; anonymous enumeration and scraping of historical scores, quiz attempts, and learning journeys.
- **Recommendation:** Replace `get_optional_current_student` with `Depends(get_current_student)` and strictly enforce `current_student["id"] == student_id`.

#### SEC-FIND-02: Unauthenticated HTTP Execution of MCP Tools and Educational Research
- **Component:** MCP Integration Subsystem (`backend/mcp_integration/client.py`, `backend/app/main.py`)
- **Affected Endpoints:** `POST /api/v1/mcp/execute`, `POST /api/v1/mcp/research`
- **Description:** `mcp_router` is mounted with zero route-level dependencies (`dependencies=[]`). Neither endpoint requires an active student session or API token.
- **Evidence:** Route table inspection confirms `APIRoute(path='/api/v1/mcp/execute', methods=['POST'], dependencies=[])`.
- **Impact:** Uncontrolled consumption of local compute and potential abuse of web search tools by anonymous network actors.
- **Recommendation:** Add `Depends(get_current_student)` to require active student authentication on tool execution endpoints.

#### SEC-FIND-03: Unauthenticated Execution of Google ADK Learning Intelligence Analysis
- **Component:** Google ADK Subsystem (`backend/adk/api.py`)
- **Affected Endpoints:** `POST /api/v1/adk/learning-analysis`
- **Description:** Endpoint accepts a `LearningIntelligenceRequest` and executes the Google ADK Runner without verifying caller identity.
- **Evidence:** Function signature `async def run_learning_analysis(request: LearningIntelligenceRequest)` lacks any authentication dependency.
- **Impact:** Resource exhaustion on the local Ollama LLM and student identity spoofing in learning analysis records.
- **Recommendation:** Require `Depends(get_current_student)` and assert `request.student_id == current_student["id"]`.

#### SEC-FIND-04: Unauthenticated Exposure of System Observability, Traces, and Error Stacks
- **Component:** Observability Subsystem (`backend/observability/service.py`)
- **Affected Endpoints:** `GET /api/v1/observability/traces`, `/traces/{trace_id}`, `/errors`, `/metrics`, `/agents`, `/status`
- **Description:** All endpoints under `/api/v1/observability/` lack authentication dependencies.
- **Evidence:** Anonymous GET request to `/api/v1/observability/traces` returns `HTTP 200 OK` containing execution spans and agent activity.
- **Impact:** Reconnaissance of internal agent prompts, execution timings, backend failures, and internal error stack traces.
- **Recommendation:** Gate all observability endpoints behind admin authentication or an internal secret token.

#### SEC-FIND-05: Complete Absence of Toxicity, Profanity, and Abusive Content Moderation
- **Component:** Educational Safety Guardrails (`backend/app/main.py`, `backend/agents/teacher.py`)
- **Affected Endpoints:** `POST /api/v1/teacher/chat`, `POST /api/v1/ask`, `POST /api/v1/orchestrate`, `POST /api/v1/assessments/submit`
- **Description:** Zero content moderation filters, toxicity classifiers, or profanity lists exist across the codebase. Student inputs are passed directly to local LLMs.
- **Evidence:** Static search across all 57 backend Python files yielded zero occurrences of moderation/toxicity checks. Teacher Agent prompt contains zero safety or anti-bullying directives.
- **Impact:** Vulnerability to student harassment, generation of inappropriate educational explanations, and non-compliance with student safety standards.
- **Recommendation:** Implement a two-tiered content moderation guardrail with fast regex denial lists and pedagogical refusal messages.

---

### 5.2 MEDIUM-Severity Findings

#### SEC-FIND-06: Hardcoded A2A Fallback Secret and Non-Constant-Time Token Comparison
- **Component:** A2A Protocol Subsystem (`backend/a2a_protocol/security.py`)
- **Description:** Line 21 defines `DEFAULT_INTERNAL_SECRET = "gyaan_ai_internal_a2a_secret_key_v1"`, used if `A2A_INTERNAL_SECRET` is unset. Line 66 uses non-constant-time string comparison (`provided_token != expected_token`).
- **Impact:** Known default secret allows inter-agent request forgery; timing side-channel assists token brute-forcing.
- **Recommendation:** Enforce environment-only secret configuration; adopt `secrets.compare_digest`.

#### SEC-FIND-07: A2A Student Session Isolation Format Bypass
- **Component:** A2A Protocol Subsystem (`backend/a2a_protocol/security.py`)
- **Description:** Line 103 checks session ownership only `if clean_session_id and ":" in clean_session_id`. If `session_id` does not contain a colon (e.g. UUID format), the check is bypassed.
- **Impact:** Cross-student session hijacking in A2A task dispatching.
- **Recommendation:** Query SQLite database to verify session ownership regardless of session ID format.

#### SEC-FIND-08: Missing Prompt Injection Guardrails on Student-Facing Endpoints
- **Component:** FastAPI Core & Agent Definitions (`backend/app/main.py`, `backend/agents/teacher.py`)
- **Description:** Student chat and ask endpoints perform zero prompt injection scanning. The 5-6 regex patterns in A2A/MCP are trivial to bypass with basic paraphrasing or multilingual phrasing.
- **Impact:** System prompt extraction and agent instruction override.
- **Recommendation:** Deploy multi-tier prompt injection detection and reinforce agent system prompts with strict delimitations.

#### SEC-FIND-09: Missing Security Headers Middleware and Publicly Exposed API Documentation
- **Component:** FastAPI Web Layer (`backend/app/main.py`)
- **Description:** Application lacks security response headers (`X-Content-Type-Options`, `X-Frame-Options`, `HSTS`, `CSP`). Interactive documentation (`/docs`, `/redoc`, `/openapi.json`) is enabled by default.
- **Impact:** Clickjacking, MIME-sniffing, and public API schema reconnaissance.
- **Recommendation:** Add security headers middleware; disable `/docs` in production.

#### SEC-FIND-10: Missing Rate Limiting on Authentication and LLM Inference Endpoints
- **Component:** API Resilience (`backend/app/main.py`)
- **Description:** No rate limiting middleware is installed on `/api/v1/auth/login`, `/register`, `/ask`, or `/orchestrate`.
- **Impact:** Credential brute-forcing and resource exhaustion of local Ollama LLM.
- **Recommendation:** Integrate `slowapi` rate limiting on sensitive routes.

#### SEC-FIND-11: Frontend Storage of Authentication Tokens in Browser localStorage
- **Component:** Next.js Frontend (`frontend/components/auth/AuthContext.tsx`, `frontend/lib/api.ts`)
- **Description:** Bearer session tokens are stored in `window.localStorage` under `"gyaan_auth_token"`.
- **Impact:** Session token exfiltration if an XSS vulnerability occurs.
- **Recommendation:** Migrate session tokens to `HttpOnly`, `Secure`, `SameSite=Strict` cookies.

---

### 5.3 LOW-Severity Findings

#### SEC-FIND-12: Google ADK In-Memory Session Storage Lifecycle and Scale Limitations
- **Component:** Google ADK Subsystem (`backend/adk/services/adk_runner.py`)
- **Description:** Sessions reside in process RAM (`InMemorySessionService`). All active sessions are lost on restart; memory grows unbounded without eviction.
- **Recommendation:** Implement an SQLite-backed session store with TTL-based eviction.

#### SEC-FIND-13: Residual Legacy JWT Configuration in .env.example
- **Component:** Configuration Template (`.env.example`)
- **Description:** Lists `JWT_SECRET_KEY` and `JWT_ALGORITHM` despite system using opaque scrypt+SHA-256 tokens.
- **Recommendation:** Update `.env.example` to reflect opaque session token configuration.

#### SEC-FIND-14: Test Suite Writes Directly to Development SQLite Database
- **Component:** Test Suites (`tests/test_auth_and_persistence.py`, `tests/test_api_unit.py`)
- **Description:** Test execution writes directly to `data/gyaan_ai.db` without fixture isolation, polluting the student table.
- **Recommendation:** Use temporary or in-memory SQLite fixtures for test execution.

---

## 6. RESOLUTION OF AUDIT INCONSISTENCIES

### 6.1 Test-Count Discrepancy Resolution
- **Previously Reported:** 114 passed, 3 failed, 1 skipped, 119 total, 95.8% pass rate (114 + 3 + 1 = 118 != 119).
- **Investigation & Actual Findings:**
  Inspection of raw pytest execution logs across all 7 security test suites revealed the true breakdown:
  - `tests/test_auth_and_persistence.py`: **11 passed**, 0 failed, 0 skipped
  - `tests/test_database.py`: **5 passed**, 0 failed, 0 skipped
  - `tests/test_api_unit.py`: **26 passed**, 0 failed, 0 skipped
  - `tests/test_mcp_integration.py`: **22 passed**, **1 failed**, 0 skipped
  - `tests/test_a2a_interoperability.py`: **16 passed**, **1 failed**, 0 skipped
  - `tests/test_adk_foundation.py`: **9 passed**, 0 failed, 0 skipped
  - `tests/test_observability.py`: **30 passed**, **1 failed**, **1 skipped**
  - **TOTALS:** **119 PASSED**, **3 FAILED**, **1 SKIPPED** out of **123 TOTAL TESTS COLLECTED**.
  - **Actual Pass Rate:** **96.75%** (119 / 123) or **97.54%** excluding skipped.
- **Root Cause of Discrepancy:** The earlier report inadvertently used the actual passed count (**119**) as the total count, and miscalculated passed tests as 114 by subtracting 5. The raw pytest logs conclusively verify 123 total tests (119 passed, 3 failed, 1 skipped).

### 6.2 Database Pollution Investigation
- **Question:** Did the test failures affect only a temporary database or the active project database?
- **Investigation & Empirical Findings:**
  1. The pristine backup file `data/gyaan_ai.db.bak_phase4` contains **781 students** and **782 student sessions**.
  2. Inspection of the active project database `data/gyaan_ai.db` revealed **793 students** and **796 student sessions**.
  3. Analysis of the 12 additional student records confirmed they were inserted on `2026-11-12T19:14:23` to `2026-11-12T19:14:47` UTC during the execution of `test_auth_and_persistence.py` and `test_api_unit.py`.
  4. Subsequent tests (`test_mcp_integration.py::test_22_database_preservation`, `test_a2a_interoperability.py::test_16_database_preservation`, and `test_observability.py::test_25_database_preservation_and_integrity`) asserted `student_count == 781`, failing with `AssertionError: assert 793 == 781`.
- **Conclusion:** **The active project database was affected.** The test suite lacked temporary database fixture isolation and wrote directly to `data/gyaan_ai.db`. The pristine state remains safely preserved in `data/gyaan_ai.db.bak_phase4`. In accordance with safety rules, no records were deleted, reset, or modified during this audit.

---

## 7. PROFESSOR REQUIREMENT COMPLIANCE MATRIX

| Requirement | Existing Implementation | Empirical Evidence | Status |
|---|---|---|---|
| **Input type safety** | Pydantic v2 schemas across all API endpoints; field type validation; strict JSON parsing | 8/8 input validation tests passed (422 on bad JSON, missing fields, type errors) | **VERIFIED** |
| **Prompt-injection protection** | 5–6 heuristic regex patterns in A2A and MCP wrappers; `<external_untrusted_reference>` wrapping | Present in protocol wrappers, but completely absent from main API chat endpoints | **PARTIALLY VERIFIED** |
| **Toxicity detection** | None. Zero moderation filters, profanity lists, or classification models in codebase | Zero matches across all 57 backend Python files | **NOT IMPLEMENTED** |
| **Agent authorization** | Specialized agent prompts, goals, and explicit handler dispatching in Orchestrator | Functional separation exists, but lacks cryptographic tokens or formal RBAC | **PARTIALLY VERIFIED** |
| **MCP security** | Sandbox strictly enforces `relative_to(APPROVED_RESOURCES_DIR)`; 3 approved tools; extension whitelist | Path traversal blocked (422/SecurityError). However, HTTP endpoints are unauthenticated | **PARTIALLY VERIFIED** |
| **A2A security** | Bearer token verification; JSON-RPC 2.0 schema validation; 512 KB payload limit | Enforces token, but uses hardcoded fallback secret, `!=` comparison, colon bypass | **PARTIALLY VERIFIED** |
| **ADK security** | Google ADK Runner with session registry and typed schemas | 9/9 ADK tests passed. However, in-memory sessions only; unauthenticated API route | **PARTIALLY VERIFIED** |
| **Student privacy** | HMAC-SHA256 telemetry redaction without fallback; scrypt hashing; SHA-256 token hashing | Redaction verified. However, unauthenticated callers bypass IDOR check on history | **PARTIALLY VERIFIED** |
| **Database security** | 100% parameterized SQL queries `(?, ...)`; foreign keys enabled; WAL mode | Zero string formatting in SQL queries; `PRAGMA integrity_check = ok` | **VERIFIED** |
| **API authentication** | Bearer token auth via scrypt verification and SHA-256 token lookup in SQLite | 37 routes authenticated, but 17 use optional auth and protocol routers are public | **PARTIALLY VERIFIED** |
| **API authorization** | Student ownership matching `current_student['id'] == student_id` | Enforced when authenticated, but bypassed when unauthenticated | **PARTIALLY VERIFIED** |
| **Secrets management** | `.gitignore` excludes `.env`, `*.db`; telemetry secret loaded securely | No committed credentials, but hardcoded fallback secret in A2A code | **PARTIALLY VERIFIED** |
| **Security testing** | Automated pytest suites covering auth, persistence, database, MCP, A2A, ADK, observability | 119/123 tests passing across 7 suites with full test telemetry | **VERIFIED** |

---

## 8. FINAL AUDIT CONCLUSION & BOUNDARY CONFIRMATION

The Phase 5A security audit has delivered a truthful, evidence-backed evaluation of Gyaan AI. While the core foundation exhibits commendable engineering in SQL parameterization, password hashing, and filesystem sandboxing, critical authorization and content moderation gaps must be resolved in Phase 5B.

**Safety Invariant Confirmation:**
- No source code or configuration files were modified.
- No database contents or schemas were modified.
- No packages or dependencies were installed.
- The protected project `D:\GYAN Ai` remains untouched.
- Phase 5B implementation remains paused, awaiting explicit user authorization.
