# GYAAN AI — MENTOR & TEACHER IMPLEMENTATION PLAN
**Date**: November 14, 2026  
**Environment**: Windows 11 | Python 3.11.9 (`.venv`) | Next.js 14.2.35  
**Project**: `D:\Gyaan AI` | **Protected Legacy**: `D:\GYAN Ai` (Untouched)  
**Status**: Read-Only Plan (Stage A Deliverable) — Awaiting User Authorization for Stage B  

---

## 1. Objectives & Safety Boundaries

This implementation plan outlines the minimal, controlled, and non-breaking enhancements proposed for the AI Mentor and AI Teacher interfaces in Gyaan AI. 

### Absolute Safety Guarantees:
1. **Zero Database Modifications**: No schema migrations, no table alters, and zero mutations or deletions of existing student records (`793 students`, `440 sessions`, `253 quizzes`, `236 attempts`).
2. **Zero Agent & Backend Integration Disruption**:
   - All 8 canonical CrewAI agents retain their exact prompt backstories, roles, goals, and domain boundaries.
   - Google ADK (`adk/`), Agent-to-Agent (`a2a/`), and Model Context Protocol (`mcp/`) integrations remain untouched.
   - Authentication middleware, JWT verification, and student ownership checks remain untouched.
   - Local Ollama with `qwen2.5:3b` remains the sole, local inference engine.
3. **Pure Frontend & Client Presentation Layer Scope**: All modifications are strictly isolated to frontend components and client-side utilities.

---

## 2. Phased Implementation Roadmap

```
Phase 1: API Client Resilience ──────► Phase 2: FormattedMessage Content Engine
  • AbortController timeout (75s)        • Markdown table tokenizer
  • Timeout & network error catch        • KaTeX / math symbol rendering
               │                                      │
               ▼                                      ▼
Phase 4: AI Mentor UX Resilience ◄──── Phase 3: AI Teacher Two-Mode Studio
  • sessionStorage caching (5m TTL)      • Viewport flexbox containment
  • Dynamic progress stages              • Standard Mode single-line toolbar
  • Direct diagnostic CTA links          • Focus Mode fullscreen overlay
               │                                      │
               └──────────────────┬───────────────────┘
                                  │
                                  ▼
                    Phase 5: Verification & Testing
                      • Unit Tests (248/248)
                      • Live Integration Tests (9/9)
                      • Security & Isolation (34/34)
                      • Next.js Production Build (16/16)
```

---

## 3. Detailed Phase Specifications

### Phase 1: API Client Resilience & Timeout Controller
**Target File**: `frontend/lib/api.ts`  
**Purpose**: Protect the UI from indefinite freezes when local Ollama is handling heavy compute loads.

1. **AbortController with Timeout**:
   - Update `apiFetch<T>` to accept an optional `timeoutMs` parameter (defaulting to 75,000ms / 75 seconds for agent workflows, 15,000ms for lightweight metadata queries).
   - Instantiate `const controller = new AbortController()`.
   - Clear timer on completion; catch `AbortError` and translate to a user-friendly message: `"The AI Tutor took too long to respond. Local Ollama may be busy with another task. Please try again."`
2. **Cancellation Support**:
   - Expose an `abortSignal` hook or method in `apiClient.askTeacher` allowing the frontend to cancel an in-flight prompt.

---

### Phase 2: FormattedMessage Table & KaTeX Math Parsing Engine
**Target File**: `frontend/components/ui/FormattedMessage.tsx`  
**Purpose**: Allow Socratic explanations, science distinction tables, and mathematical formulas to render cleanly.

1. **Markdown Table Tokenizer**:
   - Detect markdown table blocks matching `| ... | ... |`.
   - Extract table headers, alignment rows (`|---|---|`), and body rows.
   - Render semantically clean HTML `<table>` elements wrapped in `<div className="overflow-x-auto my-3 rounded-lg border border-slate-200">` with alternating row background striping (`bg-slate-50/50`) and bold headers.
2. **LaTeX Math & Chemical Formula Parsing**:
   - Parse display math blocks (`\[ ... \]` and `$$ ... $$`) and inline math (`$...$` and `\( ... \)`).
   - Render mathematical symbols, subscripts, superscripts, and reaction arrows cleanly.
3. **Code Snippet Ergonomics**:
   - Add a subtle "Copy" button to code blocks with visual feedback (`Copied!`).

---

### Phase 3: AI Teacher Studio Viewport Fixes & Two-Mode Implementation
**Target File**: `frontend/app/teacher/page.tsx`  
**Purpose**: Eliminate double scrollbars, reclaim above-the-fold vertical space, and provide a distraction-free Focus Mode.

1. **Layout Math & Flexbox Containment**:
   - Replace `h-[calc(100vh-4.5rem)]` with exact flexbox containment: `h-full flex-1 flex flex-col min-h-0 overflow-hidden`.
   - Ensure the outer AppShell does not scroll; only the internal message list will scroll.
2. **Compact Single-Line Curriculum Toolbar**:
   - Replace the bulky multi-row selector box with an elegant single-line breadcrumb selector:
     `[Subject Dropdown] › [Chapter Dropdown] › [Topic Dropdown] | [Mode: Conceptual ▾]`
   - Collapses into a single 38px strip, reclaiming ~90px of vertical space.
3. **Two-Mode Architecture**:
   - Introduce `isFocusMode` boolean state in `TeacherStudioContent`.
   - **Standard Mode**: Rendered within the AppShell with the compact toolbar and sidebar.
   - **Focus Mode**:
     - Fullscreen overlay (`fixed inset-0 z-50 bg-[#F8FAFC] flex flex-col`).
     - Minimal 40px glassmorphic header showing topic pill, agent status, and `[Exit Focus Mode (Esc)]`.
     - 88% vertical reading canvas constrained to `max-w-3xl mx-auto`.
     - Floating bottom composer with keyboard shortcuts (`Enter` send, `Shift+Enter` newline).
     - Global `keydown` listener for `Escape` to return to Standard Mode.
4. **Composer Ergonomics**:
   - Pinned bottom bar with auto-expanding textarea, topic quick chips, and stop/cancel indicator during generation.

---

### Phase 4: AI Mentor Client Caching & UX Resilience
**Target File**: `frontend/app/mentor/page.tsx`  
**Purpose**: Avoid redundant 45s LLM calls and improve transparency during long-running analysis.

1. **Client-Side Session Storage Caching**:
   - Key: `gyaan_mentor_cache_${student.id}`.
   - TTL: 5 minutes.
   - If cached recommendations exist and are less than 5 minutes old, display them immediately upon page mount, while offering a manual `"Refresh Recommendations"` button.
2. **Loading Progress Indicator**:
   - Enhance the elapsed seconds timer with educational status phases:
     - 0s – 15s: `"Analyzing recent quiz scores and diagnostic history..."`
     - 16s – 35s: `"Evaluating longitudinal topic-wise mastery curves..."`
     - 36s+: `"Synthesizing prioritized study plan and NCERT references..."`
3. **Empty-State Refinement**:
   - Keep the clean empty state with direct action buttons (`Take Practice Quiz` -> `/practice`, `Take Diagnostic Assessment` -> `/diagnostic`).

---

### Phase 5: Verification & Regression Testing Plan

1. **Unit Test Suite**:
   - Command: `python -m pytest tests/ -v -m "not integration"`
   - Target: 248/248 tests passing in isolated SQLite environment.
2. **Live Integration Test Suite**:
   - Command: `python -m pytest tests/ -v -m "integration"`
   - Target: 9/9 live integration tests passing against local Ollama.
3. **Security & Isolation Test Suite**:
   - Command: `python -m pytest tests/test_database_isolation.py tests/test_security_audit.py -v`
   - Target: 34/34 tests passing with 0 production database connections.
4. **Frontend Production Build**:
   - Command: `npm run build` in `frontend/`
   - Target: 16/16 routes successfully compiled with 0 TypeScript or linting errors.

---

## 4. Rollback & Fail-Safe Strategy

- Because all changes are confined to frontend presentation components (`frontend/app/teacher/page.tsx`, `frontend/app/mentor/page.tsx`, `frontend/components/ui/FormattedMessage.tsx`, `frontend/lib/api.ts`), the backend, database, and agents are physically insulated from risk.
- Git snapshots ensure any individual frontend file can be reverted in < 5 seconds with zero system side effects.
