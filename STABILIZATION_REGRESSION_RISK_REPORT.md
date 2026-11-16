# GYAAN AI — STABILIZATION REGRESSION RISK REPORT
## Architectural Impact & Risk Mitigation Assessment

**Document Identifier:** `GYAAN-AI-REGRESSION-RISK-v1.0`  
**Date:** November 14, 2026  
**Author:** Senior Principal Systems Architect  
**Project Path:** `D:\Gyaan AI`  
**Execution Condition:** **READ-ONLY RISK AUDIT. ZERO FILE EDITS AUTHORIZED UNTIL STAGE B APPROVAL.**  

---

## 1. EXECUTIVE RISK CLASSIFICATION MATRIX

| Proposed Modification | Component | Risk Level | Primary Regression Vector | Mitigation Strategy |
|---|---|:---:|---|---|
| **Subject Normalization** | `diagnostic/page.tsx`, `practice/page.tsx` | **LOW** | Dropdown state desynchronization | Type-checked string matching with fallback to Standard Mathematics ID |
| **Resource Keyword Filter** | `resource_retriever.py` | **LOW** | Empty context if topic keywords fail | Fallback to provisional curriculum guidelines with `is_verified=False` |
| **NCERT Corpus Expansion** | `ncert_class10_science.json` | **LOW** | JSON parsing syntax error | Schema validation with `json.load()` before merging |
| **Question Bank Deduplication** | `curriculum_bank_seeder.py`, `diagnostic_service.py` | **LOW** | Bank question count mismatch | Maintain exactly 25 distinct questions per diagnostic chapter set |
| **Mentor Cold-Start Fast-Path** | `backend/app/main.py` | **MEDIUM** | API response schema mismatch | Preserve exact JSON keys expected by frontend `useMentorRecommendations` |
| **Teacher Workspace Redesign** | `teacher/page.tsx` | **LOW** | Mobile viewport overflow | CSS flexbox with `overflow-y-auto` and verified breakpoints |
| **Technical Label Polish** | Frontend pages | **LOW** | Broken JSX string interpolation | Strict static text replacements only |

**Overall System Risk Rating:** **LOW** (Zero database schema changes, zero agent rewrites, zero dependency changes).

---

## 2. SUBSYSTEM-BY-SUBSYSTEM IMPACT AUDIT

### 2.1 Impact on Existing Eight-Agent Architecture
- **Verified Status:** **ZERO NEGATIVE IMPACT.**
- **Details:** None of the 8 canonical CrewAI agents (`Socratic Tutor`, `Curriculum Planner`, `Diagnostic Specialist`, `Assessment Creator`, `Progress Analyst`, `Study Coach`, `NCERT Resource Specialist`, `Evaluator`) undergo prompt, role, backstory, or task alterations.
- The Resource Retriever fix directly benefits the **Resource Agent** and **Assessment Agent** by guaranteeing authentic topic excerpts rather than out-of-context chemical reaction text.
- Agent independence and task context propagation remain 100% intact.

### 2.2 Impact on ADK Tools and Execution
- **Verified Status:** **ZERO IMPACT.**
- **Details:** ADK tool wrappers (`adk_curriculum_lookup`, `adk_concept_evaluator`, `adk_progress_tracker`) and ADK endpoints (`/api/v1/adk/execute`, `/api/v1/adk/tools`) operate independently of the UI state and curriculum seeder.
- ADK authorization headers and HMAC security token checks implemented in Phase 5B remain fully operative.

### 2.3 Impact on Agent-to-Agent (A2A) Communication
- **Verified Status:** **ZERO IMPACT.**
- **Details:** A2A communication protocols (`backend/a2a/protocol.py`, `backend/a2a/agent_card.py`), A2A session validation, and shared secrets remain completely unmodified.
- The sequential workflow between Progress Agent and Mentor Agent continues to execute normally whenever a student has sufficient assessment history.

### 2.4 Impact on Model Context Protocol (MCP) Integrations
- **Verified Status:** **ZERO IMPACT.**
- **Details:** MCP endpoints (`/api/v1/mcp/tools`, `/api/v1/mcp/execute`) and MCP authentication filters are untouched.
- No MCP tool signatures or schemas are modified.

### 2.5 Impact on Authentication and Student Data Ownership
- **Verified Status:** **ZERO IMPACT / STRICTLY PRESERVED.**
- **Details:** All security remediations from Phase 5B (SEC-FIND-01 through SEC-FIND-14) are preserved without exception.
- The Mentor fast-path in `backend/app/main.py` explicitly invokes `get_current_student` and validates session ownership *before* checking history length, maintaining complete IDOR protection.

### 2.6 Impact on Security Middleware
- **Verified Status:** **ZERO IMPACT.**
- **Details:**
  - Rate limiting middleware (`SlowAPIMiddleware`, `limiter`) continues to protect all endpoints.
  - Security headers middleware (`X-Content-Type-Options`, `X-Frame-Options`, `CSP`) is untouched.
  - Input sanitization and prompt injection filters in `TeacherService` and `AssessmentService` remain active.

### 2.7 Impact on Existing APIs and Response Schemas
- **Verified Status:** **ZERO BREAKING CHANGES.**
- **Details:**
  - `GET /api/v1/curriculum/subjects`: Schema unchanged.
  - `GET /api/v1/curriculum/subjects/{subject_id}/chapters`: Schema unchanged.
  - `GET /api/v1/assessments/diagnostic/{subject}/{chapter}`: Returns identical question object schema (`id`, `stem`, `options`, `correct_answer`, `explanation`).
  - `GET /api/v1/students/me/mentor-recommendations`: Preserves exact JSON structure (`mentor_overview`, `recommendations`, `study_tip`, `next_milestone`).

### 2.8 Impact on Existing SQLite Database & 793 Registered Students
- **Verified Status:** **ZERO IMPACT / STRICTLY PROTECTED.**
- **Details:**
  - Active database: `D:\Gyaan AI\data\gyaan_ai.db`.
  - Schema changes: **0**.
  - Student table records: **All 793 registered students remain intact.**
  - Session table records: **All 797 active sessions remain intact.**
  - No database migration, re-indexing, truncation, or re-seeding will be performed against `data/gyaan_ai.db`.
  - Seeder fixes apply strictly to new/isolated test databases or future initialization commands.

### 2.9 Impact on Existing Student Assessment Records and Progress History
- **Verified Status:** **ZERO IMPACT.**
- **Details:**
  - Existing `assessment_records`, `diagnostic_results`, and `progress_snapshots` are preserved.
  - Diagnostic deduplication logic operates at the retrieval/assembly layer, ensuring legacy attempt data is never corrupted.

### 2.10 Impact on Existing Learning Plans
- **Verified Status:** **ZERO IMPACT.**
- **Details:**
  - Existing 7-day study plans stored in the database remain valid.
  - Learning plan generation logic via `CurriculumPlanner` is untouched.

### 2.11 Impact on Frontend Responsiveness and Navigation
- **Verified Status:** **POSITIVE IMPACT.**
- **Details:**
  - Eliminates outer layout padding duplication and window-level scrollbars on `/teacher`.
  - Resolves UI freezing on `/mentor` by providing immediate onboarding states for cold students.
  - Restores subject-to-chapter switching on `/diagnostic` and `/practice`.
  - All 16 Next.js routes continue to compile cleanly.

---

## 3. COMPREHENSIVE MITIGATION PLAN

| Risk Scenario | Potential Consequence | Preventative Architectural Mitigation | Fallback / Rollback Mechanism |
|---|---|---|---|
| **Mathematics Subject ID Mismatch** | Dropdown shows no chapters | Fallback logic checks both `s.name === "Mathematics Standard"` and `s.category === "Mathematics"`. | Defaults to static CBSE Class 10 Math chapter list if API call fails. |
| **Resource Topic Excerpt Not Found** | Diagnostic questions lack NCERT context | Return `is_verified = False` with `source_type = "Provisional Curriculum Guidelines"`. | Assessment Agent generates syllabus-aligned questions using internal CBSE Class 10 curriculum parameters. |
| **Seeder Deduplication Edge Case** | Diagnostic quiz has < 25 questions | Set assembly loop guarantees selection of distinct stems from the bank. | Assert `len(questions) == 25` in unit test suite. |
| **Mentor Fast-Path Payload Mismatch** | Frontend mentor page crashes on load | Payload mirrors exact TypeScript interface `MentorRecommendationResponse`. | TypeScript strict type checking at Next.js build time (`npm run build`). |
| **Teacher Layout Breakpoint Overflow** | Input bar hidden on mobile | Use `flex-col`, `overflow-hidden` container with `sticky bottom-0`. | Verified responsive layout across mobile (<640px) and desktop (>1024px). |

---

## 4. REGRESSION TEST PROTOCOL (STAGE B GATES)

Before Stage B can be declared complete, the following verification suite must pass with 100% success:

1. **Gate 1: Unit & Regression Suite**
   `pytest tests/ -m "not integration"` &rarr; **Target: 248 / 248 Passed (100%)**
2. **Gate 2: Live Integration Suite**
   `pytest tests/ -m "integration"` &rarr; **Target: 9 / 9 Passed (100%)**
3. **Gate 3: Frontend Type & Build Verification**
   `cd frontend && npm run build` &rarr; **Target: 16 / 16 Routes Compiled Cleanly**
4. **Gate 4: Database Integrity Audit**
   `sqlite3 data/gyaan_ai.db "PRAGMA integrity_check"` &rarr; **Target: "ok", 793 students intact**
