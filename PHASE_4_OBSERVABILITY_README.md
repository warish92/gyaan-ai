# GYAAN AI — PHASE 4: OBSERVABILITY, MONITORING & LANGFUSE ARCHITECTURE

Welcome to Phase 4 of Gyaan AI. This document outlines the design, configuration, and API reference for the unified observability, monitoring, and telemetry subsystem implemented across the multi-agent educational platform.

---

## 1. Subsystem Architecture Overview

Phase 4 establishes real-time, non-invasive observability across all components of Gyaan AI:
- **8 Canonical CrewAI Agents**: Orchestrator, Diagnostic, Curriculum, Resource, Teacher, Assessment, Progress, and Mentor.
- **Google Agent Development Kit (ADK)**: Learning Intelligence Agent.
- **Agent-to-Agent (A2A) Protocol**: Cross-framework agent delegation over HTTP / JSON-RPC.
- **Model Context Protocol (MCP)**: Web Search MCP and Filesystem MCP servers.

```
                              [ Incoming Educational Request ]
                                              │
                                              ▼
                         ┌────────────────────────────────────────┐
                         │   Orchestrator Agent (Workflow Root)   │
                         │   - Root Trace ID (32-char hex UUID)   │
                         └──────────────────┬─────────────────────┘
                                            │
               ┌────────────────────────────┼───────────────────────────┐
               ▼                            ▼                           ▼
   ┌───────────────────────┐   ┌────────────────────────┐  ┌────────────────────────┐
   │ CrewAI Specialist     │   │ Google ADK Learning    │  │ MCP Tool Subprocesses  │
   │ Agents (8 Specialists)│   │ Intelligence Gateway   │  │ (Web Search, File Sys) │
   │ - task_callback       │   │ - Session Isolation    │  │ - CallTool Spans       │
   │ - step_callback       │   │ - adk_span Telemetry   │  │ - Provenance Citations │
   │ - kickoff_callbacks   │   │                        │  │                        │
   └───────────┬───────────┘   └───────────┬────────────┘  └───────────┬────────────┘
               │                           │                           │
               └───────────────────────────┼───────────────────────────┘
                                           │
                                           ▼
             ┌───────────────────────────────────────────────────────────┐
             │            backend.observability Subsystem                │
             │                                                           │
             │  * trace_scope Context Manager (ContextVar Propagation)   │
             │  * Redaction & PII Masking Engine                         │
             │  * In-Memory Bounded Ring-Buffer Store (Zero DB changes)  │
             │  * Structured JSON Rotating File Logger                   │
             │  * Langfuse 4.x Client (Non-blocking, Zero-Impact Mode)   │
             └─────────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
             ┌───────────────────────────────────────────────────────────┐
             │        FastAPI REST API (/api/v1/observability)           │
             │   /health | /status | /metrics | /traces | /agents        │
             └───────────────────────────────────────────────────────────┘
```

---

## 2. Directory & Package Structure

The observability subsystem is housed within `backend/observability/`:

```
backend/observability/
├── __init__.py           # Unified exports for schemas, store, logger, and callbacks
├── schemas.py            # Pydantic v2 schemas: TraceRecord, SpanRecord, Metrics, etc.
├── redaction.py          # PII detection & credential redaction algorithms
├── store.py              # Thread-safe bounded in-memory ring-buffer store
├── logger.py             # Single-line JSON logger with rotating file handler
├── callbacks.py          # CrewAI task/step/kickoff callbacks & trace_scope manager
├── langfuse_client.py    # Official Langfuse 4.x SDK wrapper with error shielding
└── service.py            # FastAPI APIRouter mounted at /api/v1/observability
```

---

## 3. Configuration & Environment Variables

All settings are configured via environment variables. See `.env.example`:

| Environment Variable | Default Value | Description |
| :--- | :--- | :--- |
| `LANGFUSE_ENABLED` | `false` | Set to `true` to enable outbound Langfuse telemetry. |
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-...` | Public API key generated from your Langfuse project. |
| `LANGFUSE_SECRET_KEY` | `sk-lf-...` | Secret API key generated from your Langfuse project. |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Host URL for Langfuse Cloud or self-hosted Langfuse. |
| `OBSERVABILITY_MAX_TRACES`| `1000` | Maximum root traces retained in bounded memory buffer. |
| `OBSERVABILITY_MAX_EVENTS`| `5000` | Maximum lifecycle events retained in bounded memory buffer. |

> **Zero-Impact Fallback**: When `LANGFUSE_ENABLED=false` or credentials are unset, the system runs in zero-impact mode. No network calls are made to Langfuse, and all educational workflows function completely normally.

---

## 4. REST API Reference

The monitoring router is mounted at `/api/v1/observability`:

### 1. `GET /api/v1/observability/health`
Checks the operational readiness of the observability subsystem.
- **Response**: `ObservabilityHealth` (`status`, `subsystem`, `version`, `langfuse_configured`, `langfuse_status`, `buffered_traces`, `buffered_events`, `log_file_present`, `timestamp`).

### 2. `GET /api/v1/observability/status`
Returns high-level runtime status, active traces count, and error summary.

### 3. `GET /api/v1/observability/metrics`
Returns aggregated execution metrics across all recorded educational workflows:
- `total_traces`, `total_spans`, `total_events`, `total_errors`, `error_rate`, `avg_trace_duration_ms`, `spans_by_type`, `agent_activity`.

### 4. `GET /api/v1/observability/traces`
Returns a paginated list of root traces in reverse chronological order.
- **Query Parameters**:
  - `limit`: int (1-200, default: 50)
  - `offset`: int (default: 0)
  - `status`: str (optional filter: `started`, `completed`, `failed`)

### 5. `GET /api/v1/observability/traces/{trace_id}`
Retrieves full details for a single root trace, including all its nested child execution spans.

### 6. `GET /api/v1/observability/agents`
Returns operational telemetry, invocation counts, error counts, and average durations for each canonical agent:
- Orchestrator Agent
- Diagnostic Agent
- Curriculum Agent
- Resource Agent
- Teacher Agent
- Assessment Agent
- Progress Agent
- Mentor Agent
- Learning Intelligence Agent (ADK)

### 7. `GET /api/v1/observability/errors`
Returns recent operational exceptions and failures.

---

## 5. Security, Redaction & Privacy

To protect student privacy and prevent credential leaks:
1. **Credential Masking**: Automatically strips passwords, tokens, API keys, JWTs, and Authorization headers (`[REDACTED_CREDENTIAL]`).
2. **PII Masking**: Uses regex heuristic patterns to mask:
   - Email addresses (`[REDACTED_EMAIL]`)
   - Indian mobile phone numbers (`[REDACTED_PHONE]`)
   - Aadhaar card and national ID patterns (`[REDACTED_ID]`)
3. **Payload Truncation**: Strings exceeding 1,500 characters are safely bounded to prevent memory bloat.
4. **Database Safety**: All observability events are stored in a separate bounded in-memory buffer and a rotating JSONL file (`data/logs/observability.jsonl`). **The SQLite student database (`data/gyaan_ai.db`) is 100% untouched.**

---

## 6. How to Run Tests

Run the dedicated Phase 4 test suite using `pytest`:
```bash
& "D:\Gyaan AI\.venv\Scripts\python.exe" -m pytest "D:\Gyaan AI\tests\test_observability.py" -v
```

All 25 unit and integration tests run in under 25 seconds without dependencies on external networks or live LLMs.
