# GYAAN AI — PHASE PRE-0 2.0 INITIAL FUNCTIONAL & ARCHITECTURE AUDIT

**Project:** `D:\Gyaan AI`  
**Protected Legacy Project:** `D:\GYAN Ai` (Untouched, LastWriteTime: 10/28/2026 9:28:28 AM)  
**Database:** `D:\Gyaan AI\data\gyaan_ai.db` (Backup: `data\gyaan_ai.db.bak_pre0_2`)  
**Audit Timestamp:** 2026-11-11T00:37:00+05:30  
**Model Configuration:** Local Ollama (`qwen2.5:3b`) at `http://127.0.0.1:11434`  

---

## 1. EXECUTIVE SUMMARY

This initial audit examines the entire end-to-end multi-agent educational platform across backend execution modules, database tables, API routes, and frontend workspaces in accordance with the mandatory requirements of Phase Pre-0 2.0.

### Key Audit Findings & Problem Identification:
1. **Diagnostic Workspace (`/diagnostic`)**: **PARTIALLY FUNCTIONAL**.
   - *Problem*: Currently displays hardcoded presets containing only 2 or 3 static question probes (e.g., 3 for Chemistry, 2 for Physics, 2 for Biology).
   - *Root Cause*: No integration with the curriculum database to dynamically select chapters/topics, and no generator task to synthesize comprehensive 20–30 question diagnostic assessments.
2. **Practice & Assessments (`/practice`)**: **PARTIALLY FUNCTIONAL / BROKEN IN EXTENDED WORKFLOWS**.
   - *Problem*: User observed infinite loading ("Assessment Agent is Synthesizing Quiz Questions..."), but questions fail to appear or generation hangs.
   - *Root Cause*: The quiz generation endpoint calls `run_quiz_generation_workflow` in a single monolithic CrewAI invocation without batching, without progress tracking, and without supporting selectable difficulty tiers (Low: 30, Medium: 20, Hard: 10). If the model delays or times out, the frontend has no batch polling or recovery mechanism. Furthermore, the frontend only offered a simplistic 1–5 question count picker.
3. **Student Progress & Analytics (`/progress`)**: **PARTIALLY FUNCTIONAL**.
   - *Problem*: User observed infinite loading ("Progress Agent is Analyzing Learning History...") and missing reports.
   - *Root Cause*: When unauthenticated or when the backend returns 401/403 or takes >15s without cached state, the page remains in an ambiguous state. In addition, when a student has zero assessment history, there was no honest, friendly empty state explaining how to begin their first assessment.
4. **Learning Lifecycle Continuity**: **IMPLEMENTED BUT NOT END-TO-END UNIFIED**.
   - *Problem*: While `backend/agents/chapter_journey.py` contains a sequential 8-agent journey, the individual frontend workspaces (Diagnostic, Practice, Teacher, Progress, Mentor) operated as disparate tabs rather than guiding the student through an integrated prerequisite $\to$ diagnosis $\to$ teaching $\to$ practice $\to$ evaluation $\to$ progress $\to$ mentoring lifecycle.

---

## 2. FEATURE-BY-FEATURE CLASSIFICATION MATRIX

| # | Workspace / Capability | Backend Endpoint / Function | Database Tables | Status Classification | Details / Observations |
|---|---|---|---|---|---|
| 1 | **Teacher Agent (`/teacher`)** | `POST /api/v1/teacher/ask` via `run_canonical_teacher_agent` | `learning_sessions`, `lesson_sessions` | **FUNCTIONAL AND LIVE VERIFIED** | Generates pedagogical explanations, step-by-step math, and conceptual breakdowns using local Ollama. |
| 2 | **Diagnostic Agent (`/diagnostic`)** | `POST /api/v1/learning-plan` via `run_diagnostic_curriculum_workflow` | `diagnostic_records`, `curriculum_plans` | **PARTIALLY FUNCTIONAL** | Evaluates 2–3 submitted answers accurately, but lacks dynamic 20–30 question generation and topic selection. |
| 3 | **Curriculum Agent (`/curriculum`)** | `GET /api/v1/curriculum/*`, `run_curriculum_inquiry_workflow` | `curriculum_chapters`, `curriculum_topics`, `curriculum_learning_objectives` | **FUNCTIONAL AND LIVE VERIFIED** | 106 chapters, 209 topics, 404 objectives verified in SQLite; successfully retrieved in tasks. |
| 4 | **Resource Agent (`/resources`)** | `POST /api/v1/resources` via `run_resource_search_workflow` | `data/resources/ncert_class10_science.json`, `curriculum_resources` | **FUNCTIONAL AND LIVE VERIFIED** | Grounded in authentic NCERT Class 10 Science corpus; retrieves chapter, section, and publisher citations. |
| 5 | **Assessment Agent - Generation (`/practice`)** | `POST /api/v1/quizzes` via `run_quiz_generation_workflow` | `quizzes` | **PARTIALLY FUNCTIONAL** | Generates 3-question quizzes, but lacks multi-difficulty sets (30/20/10 = 60), batching, and topic-wise mapping. |
| 6 | **Assessment Agent - Evaluation (`/practice`)** | `POST /api/v1/assessments/submit` via `run_assessment_evaluation_workflow` | `assessment_attempts`, `student_topic_mastery` | **FUNCTIONAL AND LIVE VERIFIED** | Rubric scoring (full, partial, zero), rejection of instruction strings, and verbatim answer retention verified. |
| 7 | **Progress Agent (`/progress`)** | `GET /api/v1/students/me/progress` via `run_progress_analysis_workflow` | `assessment_attempts`, `student_topic_mastery`, `students` | **PARTIALLY FUNCTIONAL** | Executes analysis on existing records (75.0%), but lacks honest empty state in UI and subject/chapter dashboards. |
| 8 | **Mentor Agent (`/mentor`)** | `GET /api/v1/students/me/mentor-recommendations` | `diagnostic_records`, `assessment_attempts` | **FUNCTIONAL AND LIVE VERIFIED** | Synthesizes progress into actionable study tasks with verified NCERT citations and notes on unassessed topics. |
| 9 | **Orchestrator Agent (`/agent-arena`)** | `POST /api/v1/orchestrator/dispatch` via `run_orchestration_directive` | `learning_journeys` | **FUNCTIONAL AND LIVE VERIFIED** | Formulates structured routing directives and executes as first agent in 5-agent and 8-agent sequential Crews. |
| 10 | **Complete Chapter Learning Journey** | `POST /api/v1/journey/start`, `POST /api/v1/journey/interact` | `learning_journeys`, `student_topic_progress` | **IMPLEMENTED BUT NOT LIVE VERIFIED** | Chained 8-agent Crew defined in `chapter_journey.py`, but requires end-to-end lifecycle verification in the UI. |

---

## 3. IDENTIFIED ROOT CAUSES & ACTION PLAN

### Root Cause 1: Diagnostic Assessment Limitation (2-3 Questions)
- **Current State**: `frontend/app/diagnostic/page.tsx` renders static probe arrays from client-side state (`topicPresets`).
- **Fix**:
  1. Add backend diagnostic question generation workflow (`generate_diagnostic_assessment`) in `backend/agents/diagnostic.py` capable of generating topic-wise diagnostic question sets (20–30 questions, default 25) across diverse question formats (MCQs, True/False, Fill in blanks, Short answer, Numerical, Assertion-Reason).
  2. Implement curriculum chapter and topic selection in `/diagnostic` backed by `GET /api/v1/curriculum/subjects/{subject_id}/chapters`.
  3. Ensure submitted answers are evaluated topic-wise by the Diagnostic Agent with misconception detection, knowledge gap identification, and persistent SQLite diagnostic report storage.

### Root Cause 2: Assessment Generation Pipeline Hangs / Limited Question Distribution
- **Current State**: Frontend practice interface sends single requests for 1–5 questions. Asking for 20–60 questions in one prompt to a 3B model causes token limits, timeouts, or JSON truncation.
- **Fix**:
  1. Implement **manageable batching strategy** in `backend/agents/assessment.py`: generate in batches of 5–10 questions.
  2. Support 3 selectable difficulty levels: **Low / Basic (30 questions)**, **Medium / Intermediate (20 questions)**, and **Hard / Advanced (10 questions)** $\to$ **Total: 60 questions per complete chapter practice set**.
  3. Map every question to Subject, Chapter, Topic, Objective, Difficulty, Question Type, Options, Marks, Expected Answer, Rubric, and Explanation.
  4. Cache and persist generated practice sets in SQLite (`quizzes` table) to prevent re-generating on page refresh.
  5. Upgrade `frontend/app/practice/page.tsx` with difficulty selector (Basic: 30, Medium: 20, Hard: 10, Complete: 60), batch generation progress bar, diverse response inputs (MCQ, text, numerical), and save/resume state.

### Root Cause 3: Progress Analytics Stalling / Missing Report Display
- **Current State**: If unauthenticated or if no attempts exist, the page hangs or fails to render a friendly empty state.
- **Fix**:
  1. Provide immediate deterministic statistical summary from SQLite without waiting for LLM if the student has 0 attempts (displaying an honest empty state with clear instructions to begin their first quiz).
  2. If the student has assessment history, execute the Progress Agent with local Ollama, persist the qualitative report, and render a comprehensive dashboard: Overall progress, Subject-wise progress, Chapter completion, Topic mastery grid, Attempt history, and Recommended priorities.

### Root Cause 4: Multi-Agent Context Handoffs & Learning Lifecycle
- **Current State**: Sequential execution exists in backend Crews, but the intermediate state between Diagnostic $\to$ Curriculum $\to$ Teacher $\to$ Assessment $\to$ Progress $\to$ Mentor must be seamlessly passed and visualized.
- **Fix**:
  1. Ensure structured Pydantic schemas are used for all handoffs.
  2. Maintain data provenance (`student_id`, `chapter_id`, `topic_id`, `task_id`, `agent_id`, timestamps).
  3. Connect the frontend journey so a student can seamlessly transition from diagnostic gaps to personalized teacher sessions, targeted practice, and mentor coaching.

---

**Next Steps**: Proceed with sequential implementation of Part 4 (Diagnostic Agent), Part 8 (Assessment Agent 60-Question Generation), Part 9 (Progress Agent), Part 3 (Learning Lifecycle), and end-to-end verification.
