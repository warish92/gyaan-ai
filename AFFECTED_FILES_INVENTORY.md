# GYAAN AI — AFFECTED FILES INVENTORY
**Date**: November 14, 2026  
**Environment**: Windows 11 | Python 3.11.9 (`.venv`) | Next.js 14.2.35  
**Project**: `D:\Gyaan AI` | **Protected Legacy**: `D:\GYAN Ai` (Untouched)  
**Investigation Mode**: Strictly Read-Only Investigation  

---

## 1. Stage A Investigation Status: Zero File Modifications

During this Stage A Read-Only Investigation, **ZERO APPLICATION FILES OR DATABASE RECORDS WERE MODIFIED**.  
Only the five analytical report deliverables requested by the user are written to disk.

---

## 2. Anticipated Files for Authorized Stage B Implementation

The table below catalogs all files proposed for modification during Stage B. All proposed changes are strictly restricted to frontend user-interface components and client-side utilities.

| File Path | Component / Role | Proposed Modification | Lines / Scope | Impact & Risk |
|---|---|---|---|---|
| `frontend/lib/api.ts` | API Client Foundation | Add `timeoutMs` (75s default) and `AbortController` support to `apiFetch`; handle aborts gracefully. | Lines ~110–165 | **Very Low**: Non-breaking parameter addition. Protects against UI freezes. |
| `frontend/components/ui/FormattedMessage.tsx` | Pedagogical Markdown Engine | Add Markdown table parsing (`<table>`), inline/display math formatting, and code-block copy button. | Lines ~58–200 | **Low**: Pure rendering upgrade. Existing Markdown formatting is preserved. |
| `frontend/app/teacher/page.tsx` | AI Teacher Studio | Fix container sizing (`h-full` flex containment); compact curriculum breadcrumb; implement two-mode toggle (`isFocusMode` fullscreen overlay). | Lines ~310–675 | **Low**: Frontend layout and state only. All backend `/api/v1/ask` request bodies and types remain identical. |
| `frontend/app/mentor/page.tsx` | AI Mentor Workspace | Add 5-minute `sessionStorage` recommendation caching; add dynamic progress stages to loading indicator; refine empty state CTAs. | Lines ~38–78, ~131–158 | **Very Low**: Frontend caching and animation improvements. Backend endpoint remains unchanged. |

---

## 3. Explicit Inventory of Protected & Untouched Components

To ensure absolute stability, the following architectural components are strictly untouched, unedited, and protected from modification:

### 3.1 Backend Application & API Endpoints (100% UNTOUCHED)
- `backend/app/main.py`: All 16+ endpoints, including `/api/v1/ask`, `/api/v1/students/me/mentor-recommendations`, and `/api/v1/students/me/progress-mentoring`, remain byte-for-byte identical.
- `backend/core/auth.py` & `backend/core/security_middleware.py`: Authentication, token parsing, password hashing, and IDOR ownership checks remain completely untouched.

### 3.2 Canonical CrewAI Multi-Agent Architecture (100% UNTOUCHED)
All 8 canonical CrewAI agents and their workflow orchestrators remain completely untouched:
1. `backend/agents/teacher.py` (Teacher Agent / Socratic Tutor)
2. `backend/agents/progress.py` (Progress Analyst)
3. `backend/agents/mentor.py` (Study Coach / Learning Mentor)
4. `backend/agents/assessment.py` (Assessment Creator)
5. `backend/agents/curriculum.py` (Curriculum Planner)
6. `backend/agents/diagnostic.py` (Diagnostic Specialist)
7. `backend/agents/resource.py` (NCERT Resource Specialist)
8. `backend/agents/evaluator.py` (Objective Evaluator)
- `backend/agents/progress_workflow.py`: Untouched; the sequential 2-agent crew remains preserved.
- `backend/agents/learning_workflow.py`: Untouched; intent-routing remains preserved.

### 3.3 Protocol Integrations (100% UNTOUCHED)
- `adk/` (Google Agent Development Kit integration): Untouched.
- `a2a/` (Agent-to-Agent protocol communication): Untouched.
- `mcp/` (Model Context Protocol server & tool bridges): Untouched.

### 3.4 Database Persistence & Active Production Data (100% UNTOUCHED)
- `backend/db/database.py`: Untouched. Zero schema migrations or DDL changes.
- `data/gyaan_ai.db`: **Strictly protected and untouched**.
  - Current verified records:
    - **793** registered students
    - **440** recorded learning sessions
    - **253** generated quizzes
    - **236** evaluated assessment attempts
    - **150** diagnostic records
  - PRAGMA integrity check: `ok`.

### 3.5 Protected Legacy Workspace (100% UNTOUCHED)
- `D:\GYAN Ai`: Strictly isolated, unopened, unread, and unmodified. LastWriteTime: `10/28/2026 09:28:28 AM`.
