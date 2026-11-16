# GYAAN AI — PHASE 4 OBSERVABILITY & PRIVACY REMEDIATION README

## 1. OVERVIEW

Phase 4 implements a privacy-first, distributed observability and monitoring architecture for Gyaan AI. It instruments all eight canonical CrewAI agents, the Google ADK Learning Intelligence Specialist, A2A HTTP gateway communication, and MCP stdio subprocesses.

---

## 2. KEY CAPABILITIES & REMEDIATION HIGHLIGHTS

1. **Eight Canonical CrewAI Agents Instrumented:**
   - Centralized `attach_crewai_callbacks()` automatically binds `task_callback`, `step_callback`, `before_kickoff_callbacks`, and `after_kickoff_callbacks` to every canonical agent crew.
   - Non-blocking, exception-shielded: Telemetry errors never disrupt student learning workflows.
2. **Concurrency-Safe Distributed Tracing:**
   - Replaced `threading.local()` with `contextvars.ContextVar` (`_trace_id_var`, `_span_id_var`).
   - Guarantees strict trace isolation across concurrent async coroutines and thread pool workers (`asyncio.to_thread`).
3. **A2A HTTP Protocol Trace Propagation:**
   - Client automatically injects standard W3C `traceparent` (`00-{trace_id}-{span_id}-01`) and fallback `X-Trace-Id` / `X-Parent-Span-Id` headers.
   - FastAPI A2A server parses incoming headers and establishes a causal child span under the existing root trace.
4. **MCP Subprocess Trace Propagation:**
   - MCP client injects `GYAAN_TRACE_ID`, `GYAAN_PARENT_SPAN_ID`, and `GYAAN_CORRELATION_ID` into stdio subprocess environments.
   - Passes optional `trace_context` dictionary to FastMCP tools, returning correlation IDs in tool output without violating JSON-RPC schemas.
5. **Privacy-First Data Protection (FERPA/COPPA Compliant):**
   - **Keyed HMAC Pseudonymization:** Raw student identifiers (`student_aarav_01`) are hashed to `pseudo_<16-character-hex>`.
   - **Conversation Exclusion:** Student queries and conversation turns are replaced with `[REDACTED_STUDENT_CONVERSATION]`.
   - **Chain-of-Thought Suppression:** Raw intermediate LLM thoughts are stripped from step logs and replaced with safe operational metadata (`tool_invoked`, `reasoning_step`).
   - **PII Redaction:** Indian phone numbers, emails, Aadhaar numbers, and passwords are recursively scrubbed.
6. **Live Hardware Verification:**
   - Verified live Ollama inference (`qwen2.5:3b`) on an NVIDIA GeForce RTX 2050 Laptop GPU (4GB VRAM).

---

## 3. OBSERVABILITY API ENDPOINTS

Base Route: `/api/v1/observability`

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | System health, Ollama status, store capacity, active traces |
| `/status` | GET | Execution counts across all eight agents, error counts, uptime |
| `/metrics` | GET | Monotonic telemetry counters: total traces, completed spans, failed spans |
| `/traces` | GET | Paginated list of recent execution traces (with pseudonymized IDs) |
| `/traces/{trace_id}` | GET | Detailed causal span tree, durations, status, and event timeline |
| `/agents` | GET | Canonical agent registry and runtime status |
| `/errors` | GET | Recent sanitized execution error logs |

---

## 4. HOW TO RUN TESTS & VERIFICATION

Ensure the project virtual environment is active:
```powershell
# Active workspace
cd "D:\Gyaan AI"

# 1. Run Phase 4 Observability Suite (32 tests)
.venv\Scripts\python -m pytest tests/test_observability.py -v

# 2. Run Phase 3 MCP Integration Suite (23 tests)
.venv\Scripts\python -m pytest tests/test_mcp_integration.py -v

# 3. Run Phase 2 A2A Interoperability Suite (17 tests)
.venv\Scripts\python -m pytest tests/test_a2a_interoperability.py -v

# 4. Run Phase 1 Google ADK Foundation Suite (9 tests)
.venv\Scripts\python -m pytest tests/test_adk_foundation.py -v

# 5. Run Next.js Frontend Production Build (16 routes)
cd frontend
npm run build
```

---

## 5. DATABASE INTEGRITY VERIFICATION

To verify database preservation and table invariants:
```powershell
.venv\Scripts\python -c "
import sqlite3
conn = sqlite3.connect('data/gyaan_ai.db')
c = conn.cursor()
c.execute('PRAGMA integrity_check;')
print('Integrity:', c.fetchone()[0])
c.execute(\"SELECT COUNT(*) FROM students;\")
print('Students:', c.fetchone()[0])
c.execute(\"SELECT COUNT(*) FROM student_sessions;\")
print('Sessions:', c.fetchone()[0])
conn.close()
"
```
Expected output:
- `Integrity: ok`
- `Students: 781`
- `Sessions: 782`
- Total database rows: `8,192` across 23 tables.

---

## 6. PROJECT SAFETY INVARIANTS

- **Protected Directory:** `D:\GYAN Ai` is strictly protected and never accessed or modified.
- **Database Backup:** `data/gyaan_ai.db.bak_phase4` is preserved and untouched.
- **Scope Limit:** Phase 4 is complete; no Phase 5 or subsequent features have been started.
