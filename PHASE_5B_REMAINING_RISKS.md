# GYAAN AI — PHASE 5B: REMAINING RISKS & ARCHITECTURAL LIMITATIONS

**Document Identifier:** `GYAAN-AI-PHASE5B-REMAINING-RISKS-v1.0`  
**Date:** November 13, 2026  
**Auditor / Author:** Lead Security Architect & Quality Assurance Engine  
**Project Path:** `D:\Gyaan AI`  
**Current Phase:** Phase 5B — Critical Security Implementation (Completed)  
**Target Milestone:** Phase 5C Readiness & Phase 6 Production Hardening  

---

## 1. EXECUTIVE SUMMARY

Phase 5B successfully remediated all 14 identified security vulnerabilities (SEC-FIND-01 through SEC-FIND-14) discovered during the Phase 5A Security Audit. Access controls (IDOR prevention), fail-closed A2A and telemetry secrets, authenticated MCP endpoints, content moderation, prompt injection detection, secure HttpOnly cookie session management, HTTP security headers, and in-memory rate limiting are now fully operational and verified by 152 automated tests.

While these implementations establish a robust, defense-in-depth security perimeter suitable for development, testing, and pilot deployments, several architectural trade-offs and residual risks remain due to the local, standalone nature of the current deployment stack (SQLite, in-memory state, local Ollama LLM).

This report identifies, classifies, and evaluates all remaining risks, detailing specific remediation roadmaps for Phase 6 (Production Deployment & Hardening).

---

## 2. COMPREHENSIVE RESIDUAL RISK REGISTER

### Risk 1: ADK In-Memory Session Storage Lifecycle
- **Risk ID:** `RISK-P5B-01`
- **Component:** `backend/adk/session.py` (`learning_sessions: Dict[str, LearningSession]`)
- **Vulnerability / Limitation:**
  Active multi-agent conversational sessions within the Agent Development Kit (ADK) are held in a process-local Python dictionary in memory. If the FastAPI/Uvicorn server process restarts, crashes, or is deployed with multiple worker processes (`uvicorn --workers > 1`), active session contexts are lost or not shared across workers.
- **Likelihood:** High (on server restart or multi-worker scaling).
- **Impact:** Medium. Persistent student records, assessment results, and learning history stored in SQLite remain completely safe. However, active multi-step interactive dialogues require the student to initiate a new session context upon server restart.
- **Current Safeguard:** Single-worker process in development; student ID isolation enforced upon session lookup.
- **Phase 6 Remediation Roadmap:**
  Implement a pluggable session storage adapter (`RedisSessionStorage` or `SQLiteSessionStorage`) implementing the ADK `SessionBackend` interface with automated TTL expiration and distributed locks.

---

### Risk 2: Process-Local In-Memory Sliding-Window Rate Limiting
- **Risk ID:** `RISK-P5B-02`
- **Component:** `backend/app/main.py` (`InMemoryRateLimiter`)
- **Vulnerability / Limitation:**
  Rate limiting for authentication endpoints (5 req/min) and LLM inference endpoints (30 req/min) is implemented using thread-safe in-memory deques (`collections.deque`) within the single application process. In a distributed, clustered, or multi-process deployment (e.g., behind a load balancer with multiple pods or Uvicorn workers), each worker maintains independent state. A malicious actor could theoretically achieve `N * limit` requests by distributing requests across worker nodes. Additionally, rate limits reset upon application restart.
- **Likelihood:** Medium.
- **Impact:** Low/Medium. While brute-force attempts are throttled locally, distributed rate-limit enforcement is necessary for production-scale deployments.
- **Current Safeguard:** Thread-safe `asyncio.Lock`, IP-based sliding window, strict local throttling.
- **Phase 6 Remediation Roadmap:**
  Transition from `InMemoryRateLimiter` to a distributed Redis-backed rate limiter executing sliding-window counter scripts in Lua or utilizing a Token Bucket algorithm with Redis key expiration.

---

### Risk 3: Heuristic & Regex Content Moderation / Prompt Guard Boundaries
- **Risk ID:** `RISK-P5B-03`
- **Component:** `backend/services/content_moderator.py` & `backend/services/prompt_guard.py`
- **Vulnerability / Limitation:**
  Content moderation and prompt injection detection currently utilize deterministic regular expressions, keyword heuristics, structural sanitizers, and educational whitelisting (specifically tuned for CBSE Class 10 Science). While this provides sub-millisecond latency and zero GPU compute overhead, deterministic heuristics can be vulnerable to novel, highly sophisticated adversarial jailbreaks, multilingual homoglyph obfuscation, or subtle zero-day evasion prompts that do not match existing regex patterns.
- **Likelihood:** Low / Medium.
- **Impact:** Low. Multi-layered defense: even if an input bypasses the regex guard, the reinforced system prompts in Orchestrator, Teacher, and Mentor explicitly forbid instruction overrides, persona adoption, and out-of-syllabus topics.
- **Current Safeguard:** Pre-execution regex scanning, untrusted input wrapping (`<untrusted_user_input>`), CBSE curriculum whitelisting, and strict agent system instructions.
- **Phase 6 Remediation Roadmap:**
  Deploy a lightweight, quantized local guard model (e.g., Llama Guard 3 1B or NeMo Guardrails) to act as a secondary semantic evaluation layer alongside the fast regex heuristic, providing semantic classification without requiring external cloud APIs.

---

### Risk 4: SQLite Database Concurrency & File-Lock Constraints
- **Risk ID:** `RISK-P5B-04`
- **Component:** `backend/db/database.py` (`data/gyaan_ai.db`)
- **Vulnerability / Limitation:**
  The project currently utilizes SQLite in Write-Ahead Logging (WAL) mode. While WAL allows multiple concurrent readers, write operations remain strictly serialized via filesystem locks. Under high concurrent write traffic (e.g., hundreds of students submitting assessments simultaneously), threads may experience contention or `sqlite3.OperationalError: database is locked` timeouts.
- **Likelihood:** Low for current pilot scale (<50 concurrent students); High for production multi-school deployment (>500 concurrent students).
- **Impact:** Medium. Potential request queuing or temporary 500 errors during peak write bursts.
- **Current Safeguard:** SQLite WAL mode (`PRAGMA journal_mode=WAL`), busy timeout set to 5000ms (`PRAGMA busy_timeout=5000`), and connection reuse.
- **Phase 6 Remediation Roadmap:**
  Migrate database backend to PostgreSQL with `asyncpg` connection pooling and Alembic schema migration management.

---

### Risk 5: Local Development vs. Production Cookie Flag Configuration
- **Risk ID:** `RISK-P5B-05`
- **Component:** `backend/app/main.py` (`set_cookie(..., secure=ENVIRONMENT == "production")`)
- **Vulnerability / Limitation:**
  To facilitate local development and automated testing over plain HTTP on `localhost:3000`, the `secure` flag on authentication cookies is conditionally disabled when `ENVIRONMENT != "production"`. If the application is deployed into a live production environment without explicitly setting the `ENVIRONMENT=production` environment variable, session cookies would be transmitted without the `Secure` attribute, creating exposure to interception on unencrypted networks.
- **Likelihood:** Low (standard configuration error).
- **Impact:** High (session token interception if deployed over unencrypted HTTP).
- **Current Safeguard:** Strict `HttpOnly=True` and `SameSite="Lax"` flags are always enforced regardless of environment.
- **Phase 6 Remediation Roadmap:**
  Implement a startup fail-safe: if the host IP/domain is not `127.0.0.1` or `localhost`, enforce `secure=True` automatically, and enforce HTTPS reverse proxy termination (Caddy / Nginx) with HSTS preloading.

---

### Risk 6: Local Ollama LLM Latency & Inference Queueing
- **Risk ID:** `RISK-P5B-06`
- **Component:** `backend/services/ollama_service.py` & Ollama runtime (`qwen2.5:3b`)
- **Vulnerability / Limitation:**
  Gyaan AI runs on a local Ollama instance. Local LLM inference on consumer-grade hardware processes requests sequentially or with limited parallelism (`OLLAMA_NUM_PARALLEL`). If multiple students send complex requests requiring multi-agent orchestration simultaneously, response latency will degrade, potentially triggering HTTP gateway timeouts.
- **Likelihood:** Medium.
- **Impact:** Low/Medium (User experience degradation / high latency).
- **Current Safeguard:** LLM rate limiting (30 requests/minute per IP) prevents single-user resource exhaustion.
- **Phase 6 Remediation Roadmap:**
  Optimize Ollama runtime parameters (`OLLAMA_NUM_PARALLEL=4`, KV cache quantization) or transition to a dedicated vLLM / Triton inference server with continuous batching.

---

## 3. RESIDUAL RISK MATRIX

| Risk ID | Vulnerability / Architectural Limitation | Severity | Likelihood | Residual Risk | Target Resolution Phase |
|---|---|---|---|---|---|
| `RISK-P5B-01` | ADK In-Memory Session Storage Lifecycle | Medium | High | **MODERATE** | Phase 6 (Redis / DB Session Backend) |
| `RISK-P5B-02` | Process-Local In-Memory Rate Limiting | Low | Medium | **LOW** | Phase 6 (Redis Distributed Limiter) |
| `RISK-P5B-03` | Heuristic Regex Content Moderation Limits | Medium | Low | **LOW** | Phase 6 (Llama Guard 3 / Semantic Guard) |
| `RISK-P5B-04` | SQLite Concurrency & File-Lock Constraints | Medium | Low | **LOW** (Dev) / **HIGH** (Prod) | Phase 6 (PostgreSQL Migration) |
| `RISK-P5B-05` | Dynamic Cookie `secure` Flag Config | High | Low | **LOW** | Phase 6 (Startup Assertion & TLS Guard) |
| `RISK-P5B-06` | Local Ollama Inference Queueing | Low | Medium | **LOW** | Phase 6 (vLLM Batching / GPU Scaling) |

---

## 4. DEFENSE-IN-DEPTH POSTURE EVALUATION

Despite the residual architectural risks identified above, the Gyaan AI platform currently possesses an exceptionally robust defense-in-depth posture:

```
[Layer 1: Network & HTTP Edge]
  ├── SecurityHeadersMiddleware (nosniff, DENY, HSTS, CSP, X-XSS-Protection)
  ├── InMemoryRateLimiter (Auth: 5/min, LLM: 30/min)
  └── CORS & Origin Restrictions

[Layer 2: Authentication & Session]
  ├── Dual-Mode Auth (HttpOnly Cookie & Authorization Bearer)
  ├── Opaque Cryptographic Tokens (32-byte hex, constant-time validation)
  ├── Explicit Session Revocation on Logout (Database row purge)
  └── Strict IDOR Checks (Caller student ID must match requested resource)

[Layer 3: Protocol & Agent Security]
  ├── A2A Fail-Closed HMAC Token Validation (No hardcoded secrets)
  ├── A2A Cross-Student Context Boundary Enforcement
  ├── MCP Tool Caller Authentication (Blocks unauthenticated execution)
  └── Observability Endpoint Access Controls

[Layer 4: Input & Content Guardrails]
  ├── Heuristic Content Moderation (CBSE Class 10 Science whitelist)
  ├── Prompt Guard & Jailbreak Pattern Scanner
  └── Untrusted User Input Tagging (<untrusted_user_input>)

[Layer 5: LLM & Agent Core]
  ├── Anti-Jailbreak Directives in Orchestrator, Teacher, and Mentor prompts
  ├── Syllabus Scoping (Strict CBSE Class 10 boundary)
  └── Pydantic v2 Output Schema Validation & Sanitization

[Layer 6: Persistence & Observability Privacy]
  ├── HMAC Pseudonymization for Student Telemetry
  ├── Sensitive Attribute Redaction (Passwords, tokens, credentials masked)
  └── Database Test Isolation Guard (RuntimeError on accidental prod DB write)
```

---

## 5. PHASE 5C READINESS & RECOMMENDATIONS

### Readiness Verdict
**STATUS: READY FOR PHASE 5C (SECURITY AUDIT CLOSURE & STAKEHOLDER VERIFICATION)**

The current implementation satisfies 100% of the Phase 5 security specifications. The remaining risks detailed in this document are operational and architectural considerations for production-scale deployment (Phase 6) and do not compromise the security, data privacy, or functional stability of the local, single-school, or development environment.

### Transition Checklist to Phase 5C
1. [x] All 14 security findings remediated and verified.
2. [x] Zero regressions across all 152 automated tests.
3. [x] Next.js frontend builds cleanly (16/16 routes).
4. [x] Active database (`gyaan_ai.db`) perfectly intact (793 students, 797 sessions).
5. [x] Protected legacy project (`D:\GYAN Ai`) strictly untouched.
6. [x] Complete Phase 5B documentation suite compiled and delivered:
   - `PHASE_5B_IMPLEMENTATION_REPORT.md`
   - `PHASE_5B_SECURITY_FIXES.json`
   - `PHASE_5B_TEST_RESULTS.md`
   - `PHASE_5B_REMAINING_RISKS.md`
