# GYAAN AI — PHASE 5A: SECURITY REMEDIATION ROADMAP

**Project:** `D:\Gyaan AI`  
**Protected Legacy Project:** `D:\GYAN Ai` (Untouched, strictly isolated)  
**Phase:** Phase 5 — Security Guardrails  
**Stage:** Phase 5B / 5C Implementation & Verification Blueprint  
**Roadmap Generated:** 2026-11-13 11:33:15 UTC  
**Status:** PROPOSED & READY FOR IMPLEMENTATION AUTHORIZATION  

---

## 1. ROADMAP OVERVIEW & OBJECTIVES

Following the comprehensive Phase 5A security audit, this roadmap establishes the prioritized, actionable engineering plan for **Phase 5B (Implementation)** and **Phase 5C (Verification)**.

### Primary Objectives
1. **Remediate High-Severity Authentication and IDOR Bypasses:** Enforce mandatory student authentication on all sensitive endpoints, MCP tool routes, Google ADK analysis, and Observability telemetry.
2. **Implement Educational Content Moderation Guardrails:** Deploy a low-latency, two-tiered content safety filter to detect profanity, harassment, and abuse across student-agent dialogues.
3. **Harden A2A Protocol & Inter-Agent Boundaries:** Eliminate hardcoded fallback secrets, prevent timing side-channels, and validate session ownership against SQLite.
4. **Deploy Defense-in-Depth Prompt Injection Guards:** Integrate multi-tier adversarial prompt filtering on student inputs and reinforce agent system prompts with strict XML/Markdown delimiters.
5. **FastAPI Web Security & Frontend Token Hardening:** Add security response headers, rate limiting, and migrate tokens to `HttpOnly` cookies.
6. **Ensure Database Test Isolation:** Refactor test fixtures to execute against temporary or in-memory SQLite databases.

---

## 2. PRIORITY 1 — CRITICAL & HIGH-SEVERITY SECURITY FIXES

### 2.1 Remediation 1: Fix Flawed Optional Authentication and IDOR on Student Endpoints
- **Finding ID:** `SEC-FIND-01`
- **Problem:** `GET /api/v1/assessments/history/{student_id}` and `GET /api/v1/learning-journey/student/{student_id}` use `get_optional_current_student`, allowing unauthenticated callers to bypass student ownership checks.
- **Affected Files:** `backend/app/main.py`
- **Required Change:**
  1. Replace `Depends(get_optional_current_student)` with `Depends(get_current_student)` on all student-specific data retrieval and submission endpoints.
  2. Enforce strict ownership check:
     ```python
     if current_student["id"] != student_id:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Access denied: You cannot view another student's data.",
         )
     ```
  3. Review all 17 routes using `get_optional_current_student` and convert sensitive stateful endpoints (`/api/v1/assessments/submit`, `/api/v1/learning-journey/start`, `/api/v1/quizzes`) to mandatory `get_current_student`.
- **Expected Outcome:** Anonymous requests rejected with 401 Unauthorized; cross-student requests rejected with 403 Forbidden.
- **Test Cases Required:**
  - GET `/api/v1/assessments/history/stu_1` with no token -> 401.
  - GET `/api/v1/assessments/history/stu_1` with token for `stu_2` -> 403.
  - GET `/api/v1/assessments/history/stu_1` with token for `stu_1` -> 200.
- **Acceptance Criteria:** Zero anonymous or cross-student access permitted to student assessment history or learning journeys.
- **Dependencies / Risks:** Low risk. Frontend must ensure valid Bearer token is attached to all history requests.

### 2.2 Remediation 2: Enforce Authentication on MCP Tool Execution Endpoints
- **Finding ID:** `SEC-FIND-02`
- **Problem:** `POST /api/v1/mcp/execute` and `POST /api/v1/mcp/research` lack authentication dependencies (`dependencies=[]`).
- **Affected Files:** `backend/mcp_integration/client.py`, `backend/app/main.py`
- **Required Change:**
  1. Add `current_student: Dict[str, Any] = Depends(get_current_student)` to `execute_mcp_tool_endpoint` and `execute_mcp_research_endpoint`.
  2. Log the executing `student_id` for auditability in telemetry.
- **Expected Outcome:** MCP tool execution restricted strictly to authenticated students.
- **Test Cases Required:**
  - POST `/api/v1/mcp/execute` without token -> 401.
  - POST `/api/v1/mcp/execute` with valid token -> 200.
- **Acceptance Criteria:** Unauthenticated requests blocked with 401.

### 2.3 Remediation 3: Secure Google ADK Learning Intelligence Endpoint
- **Finding ID:** `SEC-FIND-03`
- **Problem:** `POST /api/v1/adk/learning-analysis` allows anonymous callers to run the ADK Runner and inject arbitrary student IDs.
- **Affected Files:** `backend/adk/api.py`
- **Required Change:**
  1. Add `current_student: Dict[str, Any] = Depends(get_current_student)` to `run_learning_analysis()`.
  2. Verify that `request.student_id == current_student["id"]`; raise 403 Forbidden on mismatch.
- **Expected Outcome:** Google ADK execution restricted to authenticated student caller matching request student ID.
- **Test Cases Required:**
  - POST `/api/v1/adk/learning-analysis` without token -> 401.
  - POST `/api/v1/adk/learning-analysis` with token for student A but `student_id` student B in payload -> 403.
- **Acceptance Criteria:** Anonymous callers rejected; student ID spoofing blocked.

### 2.4 Remediation 4: Protect Observability & Telemetry Endpoints
- **Finding ID:** `SEC-FIND-04`
- **Problem:** Telemetry endpoints (`/api/v1/observability/traces`, `/errors`, `/metrics`, `/agents`) are exposed publicly without authentication.
- **Affected Files:** `backend/observability/service.py`
- **Required Change:**
  1. Create an admin dependency `verify_admin_or_internal_token` checking for an admin session role or `X-Telemetry-Admin-Token` header.
  2. Mount the dependency on sensitive observability routes. Retain public access only for `/api/v1/observability/health`.
- **Expected Outcome:** System traces, error logs, and metrics protected from unauthorized reconnaissance.
- **Test Cases Required:**
  - GET `/api/v1/observability/traces` without admin token -> 401.
  - GET `/api/v1/observability/health` without token -> 200.
- **Acceptance Criteria:** Anonymous access to system traces and error stacks completely blocked.

### 2.5 Remediation 5: Implement Educational Content Moderation Guardrails
- **Finding ID:** `SEC-FIND-05`
- **Problem:** Zero content moderation, profanity filtering, or anti-bullying guardrails exist across the platform.
- **Affected Files:** `backend/app/main.py`, `backend/agents/teacher.py`, `backend/services/content_moderator.py` (new)
- **Required Change:**
  1. Create `backend/services/content_moderator.py` with:
     - Pre-execution normalized keyword/regex rule engine targeting profanity, harassment, self-harm, and severe hate speech.
     - Pedagogical refusal generator providing polite educational redirections appropriate for Class 10 CBSE students.
  2. Intercept student inputs in `/api/v1/teacher/chat`, `/api/v1/ask`, `/api/v1/orchestrate`, and `/api/v1/assessments/submit`.
  3. Short-circuit flagged requests immediately, returning a friendly pedagogical guidance response without invoking LLM inference.
- **Expected Outcome:** Harmful student inputs blocked before reaching LLM; safe, supportive educational redirection provided.
- **Test Cases Required:**
  - POST `/api/v1/ask` with abusive/profane phrasing -> 400 with pedagogical safety message.
  - POST `/api/v1/ask` with legitimate science question -> 200 with concept explanation.
- **Acceptance Criteria:** 100% of tested abusive/profane inputs safely blocked.

---

## 3. PRIORITY 2 — MEDIUM-SEVERITY IMPROVEMENTS

### 3.1 Remediation 6: Harden A2A Protocol Secret & Constant-Time Verification
- **Finding ID:** `SEC-FIND-06`
- **Problem:** Hardcoded fallback secret `DEFAULT_INTERNAL_SECRET` and non-constant-time string comparison (`!=`).
- **Affected Files:** `backend/a2a_protocol/security.py`
- **Required Change:**
  1. Remove `DEFAULT_INTERNAL_SECRET`. Raise `RuntimeError` if `A2A_INTERNAL_SECRET` is unset.
  2. Replace `!=` with `hmac.compare_digest(provided_token, expected_token)`.
- **Acceptance Criteria:** A2A requests fail if environment variable missing; constant-time comparison prevents timing attacks.

### 3.2 Remediation 7: Fix A2A Session Isolation Format Bypass
- **Finding ID:** `SEC-FIND-07`
- **Problem:** `validate_student_isolation()` skips check if session ID lacks colon.
- **Affected Files:** `backend/a2a_protocol/security.py`
- **Required Change:** Query SQLite `student_sessions` table to verify session ownership regardless of session ID string format.
- **Acceptance Criteria:** Session hijacking blocked across all session ID formats.

### 3.3 Remediation 8: Deploy Multi-Tier Prompt Injection Defenses
- **Finding ID:** `SEC-FIND-08`
- **Problem:** Student chat endpoints lack prompt injection scrubbing; agent prompts lack defensive delimiters.
- **Affected Files:** `backend/app/main.py`, `backend/services/prompt_guard.py` (new), `backend/agents/teacher.py`
- **Required Change:**
  1. Implement `validate_prompt_safety()` scanning for role-overrides, system delimiter escapes, and instruction resets.
  2. Update agent backstories with anti-jailbreak instructions and XML delimiters.
- **Acceptance Criteria:** Jailbreak payloads rejected before LLM invocation.

### 3.4 Remediation 9: FastAPI Security Headers & Rate Limiting
- **Finding ID:** `SEC-FIND-09`, `SEC-FIND-10`
- **Problem:** Missing security headers (`X-Content-Type-Options`, `X-Frame-Options`); public `/docs`; missing rate limiting.
- **Affected Files:** `backend/app/main.py`, `requirements.txt`
- **Required Change:**
  1. Add security headers middleware (`nosniff`, `DENY`, `HSTS`, `CSP`).
  2. Integrate `slowapi` rate limiting on `/login` (5/min), `/register` (3/min), and `/ask` (20/min).
  3. Disable `/docs` in production environment.
- **Acceptance Criteria:** Security headers present on all responses; rapid login attempts trigger 429 Too Many Requests.

### 3.5 Remediation 10: Migrate Frontend Token Storage to HttpOnly Cookies
- **Finding ID:** `SEC-FIND-11`
- **Problem:** Session bearer tokens stored in `localStorage` (`gyaan_auth_token`), vulnerable to XSS exfiltration.
- **Affected Files:** `backend/app/main.py`, `frontend/components/auth/AuthContext.tsx`, `frontend/lib/api.ts`
- **Required Change:** Set session token in `Set-Cookie: HttpOnly; Secure; SameSite=Strict; Path=/api/v1` upon login; update `get_current_student` to accept cookie auth. Remove `localStorage` token storage.
- **Acceptance Criteria:** Tokens stored in HttpOnly cookies and not accessible to client JavaScript.

---

## 4. PRIORITY 3 — LOW-SEVERITY IMPROVEMENTS

### 4.1 Remediation 11: Implement Persistent Google ADK Session Store
- **Finding ID:** `SEC-FIND-12`
- **Problem:** `InMemorySessionService` loses session history on restart.
- **Affected Files:** `backend/adk/services/adk_runner.py`
- **Required Change:** Implement SQLite-backed session provider for Google ADK with TTL cleanup.

### 4.2 Remediation 12: Clean Up Environment Template
- **Finding ID:** `SEC-FIND-13`
- **Problem:** Legacy `JWT_SECRET_KEY` in `.env.example`.
- **Affected Files:** `.env.example`
- **Required Change:** Remove JWT keys; document active opaque scrypt session token settings.

### 4.3 Remediation 13: Isolate Pytest Database Fixtures
- **Finding ID:** `SEC-FIND-14`
- **Problem:** Running tests writes directly to active `data/gyaan_ai.db`.
- **Affected Files:** `tests/conftest.py`, `tests/test_auth_and_persistence.py`
- **Required Change:** Add pytest fixture provisioning a temporary SQLite file or `:memory:` database for test execution.
- **Acceptance Criteria:** Full test suite execution leaves row count of `data/gyaan_ai.db` completely unchanged.

---

## 5. PHASE 5B — SECURITY IMPLEMENTATION SCOPE

Phase 5B will execute the implementation tasks strictly within `D:\Gyaan AI`:
- **Sprint 1 (Days 1–2):** Authentication & IDOR hardening (FastAPI, MCP, ADK, Observability).
- **Sprint 2 (Days 3–4):** Educational content moderation & toxicity guardrails.
- **Sprint 3 (Day 5):** A2A protocol hardening & timing attack mitigation.
- **Sprint 4 (Days 6–7):** Prompt injection defenses & agent prompt delimiters.
- **Sprint 5 (Day 8):** FastAPI security headers & SlowAPI rate limiting.
- **Sprint 6 (Days 9–10):** Frontend cookie migration, ADK persistence, and pytest DB fixture isolation.

*Implementation Note: Phase 5B will NOT be started until explicit authorization is provided by the user.*

---

## 6. PHASE 5C — SECURITY VERIFICATION METHODOLOGY

Following Phase 5B implementation, Phase 5C will independently verify every control:
1. **Automated Test Suite Execution:** Re-run all 7 test suites with target **100% pass rate** (123/123 passing, 0 failures).
2. **Automated Penetration Suite:** Execute automated requests testing IDOR, unauthenticated endpoints, toxic inputs, prompt injection payloads, and rate limits.
3. **Database Immutability Verification:** Verify that `data/gyaan_ai.db` row counts remain unchanged after running the entire test suite.
4. **Final Verification Deliverable:** Generate `PHASE_5C_SECURITY_VERIFICATION.json` and `PHASE_5C_SECURITY_VERIFICATION_REPORT.md`.

---

## 7. FINAL ACCEPTANCE CRITERIA

Phase 5 remediation will be considered fully complete when:
- [ ] All 5 HIGH-severity findings are remediated and verified with passing automated tests.
- [ ] All 6 MEDIUM-severity findings are remediated and verified.
- [ ] All 3 LOW-severity findings are resolved.
- [ ] All 13 Professor Requirements achieve **VERIFIED** status in the Compliance Matrix.
- [ ] Automated pytest test suite passes with **100% success rate** without writing to `data/gyaan_ai.db`.
- [ ] The protected legacy project `D:\GYAN Ai` remains 100% untouched.
