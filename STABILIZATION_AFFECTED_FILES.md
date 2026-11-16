# GYAAN AI — STABILIZATION PHASE: AFFECTED FILES INVENTORY
## Stage B Proposed File Modifications & Surgical Justifications

**Document Identifier:** `GYAAN-AI-STABILIZATION-AFFECTED-FILES-v1.0`  
**Date:** November 14, 2026  
**Author:** Senior Principal Systems Architect  
**Project Path:** `D:\Gyaan AI`  
**Execution Condition:** **AUDIT INVENTORY ONLY. ZERO FILE EDITS AUTHORIZED UNTIL STAGE B APPROVAL.**  

---

## 1. SUMMARY MATRIX OF AFFECTED FILES

| # | File Path | Component | Primary Issue Addressed | Mod Type | DB Schema Impact |
|:---:|---|---|---|:---:|:---:|
| **1** | `frontend/app/diagnostic/page.tsx` | Frontend / Assessment | Issue A & Issue C | Edit | **NONE** |
| **2** | `frontend/app/practice/page.tsx` | Frontend / Practice | Issue A & Issue C | Edit | **NONE** |
| **3** | `backend/services/resource_retriever.py` | Backend / Resource Service | Issue B (Corpus Contamination) | Edit | **NONE** |
| **4** | `data/resources/ncert_class10_science.json` | Data / NCERT Corpus | Issue B (Missing Biology Corpus) | Append | **NONE** |
| **5** | `backend/services/curriculum_bank_seeder.py` | Backend / Bank Seeder | Issue B (25x Duplicate Loop) | Edit | **NONE** |
| **6** | `backend/services/diagnostic_service.py` | Backend / Diagnostic Service | Issue B (Deduplication Safeguard) | Edit | **NONE** |
| **7** | `backend/app/main.py` | Backend / API Routes | Issue E (Mentor 90s Cold-Start) | Edit | **NONE** |
| **8** | `frontend/app/mentor/page.tsx` | Frontend / Mentor View | Issue E & Issue F | Edit | **NONE** |
| **9** | `frontend/app/teacher/page.tsx` | Frontend / Teacher View | Issue D & Issue F | Edit | **NONE** |
| **10** | `frontend/app/learning-plans/page.tsx` | Frontend / Learning Plans | Issue F (Technical Labels) | Edit | **NONE** |
| **11** | `frontend/app/resources/page.tsx` | Frontend / Resource View | Issue F (Technical Labels) | Edit | **NONE** |

**Total Files Affected:** 11 files (6 Frontend, 4 Backend, 1 JSON Resource)  
**Database Schema Modifications:** **ZERO (0)**  
**Active Database Records Modified:** **ZERO (0)**  
**New Dependencies Added:** **ZERO (0)**  

---

## 2. DETAILED FILE-BY-FILE AUDIT & JUSTIFICATIONS

### 1. `frontend/app/diagnostic/page.tsx`
- **Exact File Path:** `frontend/app/diagnostic/page.tsx`
- **Current Responsibility:** Next.js client component managing the Diagnostic Assessment user journey: subject/chapter selection dropdowns, fetching diagnostic quizzes, timer handling, answering questions, and rendering diagnostic breakdown results.
- **Problem Identified:** Lines 405–409 hardcode `<option value="Mathematics">Mathematics</option>`. In `curriculum_subjects`, the database names are `"Mathematics Standard"` and `"Mathematics Basic"`. When a student selects `"Mathematics"`, `subjects.find(s => s.name.toLowerCase() === selectedSubject.toLowerCase())` returns `undefined`. As a result, `setChapters` is never invoked, leaving stale chapters from previously selected subjects (e.g. Social Science Chapter 1: "The Rise of Nationalism in Europe") or an empty dropdown.
- **Proposed Modification:**
  - Normalize subject matching:
    ```typescript
    const subjectObj = subjects.find((s) =>
      s.name.toLowerCase() === selectedSubject.toLowerCase() ||
      (selectedSubject === "Mathematics" && (s.category === "Mathematics" || s.name.startsWith("Mathematics")))
    );
    ```
  - When subject changes, immediately clear `chapters`, fetch chapters using `subjectObj.id`, and automatically select the first valid chapter (`chList[0].title`).
  - Provide a fallback static chapter list for Class 10 Mathematics (`["Real Numbers", "Polynomials", ...]`) if the API response is delayed.
- **Justification:** Resolves Issue A and Issue C cleanly in the UI layer where the mismatch originates.
- **Alternative Approaches Rejected:**
  - *Renaming database subject records to "Mathematics":* Rejected because it would alter the active database (`data/gyaan_ai.db`), break CBSE curriculum conventions (CBSE classifies Class 10 Mathematics into Standard [041] and Basic [241]), and invalidate existing database foreign keys and test assertions.
- **Database Schema or Existing Records Affected:** **NO.**

---

### 2. `frontend/app/practice/page.tsx`
- **Exact File Path:** `frontend/app/practice/page.tsx`
- **Current Responsibility:** Next.js client component for generating and taking Practice Quizzes, selecting subjects, chapters, difficulty levels, and reviewing instant evaluations.
- **Problem Identified:** Lines 400–404 contain the identical hardcoded `<option value="Mathematics">Mathematics</option>` bug, causing chapter state to desynchronize whenever Mathematics is selected.
- **Proposed Modification:**
  - Implement subject normalization and category fallback matching identical to `diagnostic/page.tsx`.
  - Ensure `selectedChapter` resets to the first valid chapter of the newly selected subject upon change.
- **Justification:** Ensures seamless subject-to-chapter switching across Practice Quizzes.
- **Alternative Approaches Rejected:**
  - *Hardcoding all chapters into the frontend:* Rejected because it duplicates curriculum data and bypasses the authoritative backend curriculum API.
- **Database Schema or Existing Records Affected:** **NO.**

---

### 3. `backend/services/resource_retriever.py`
- **Exact File Path:** `backend/services/resource_retriever.py`
- **Current Responsibility:** Service class `ResourceRetriever` responsible for querying the local NCERT Class 10 curriculum corpus, scoring relevant excerpts, and setting `is_verified` flags before excerpts are injected into agent task contexts.
- **Problem Identified:** In `find_relevant_resources`, `query_terms` blindly appends `subject.lower()` ("science"). Because all entries in `ncert_class10_science.json` contain `"NCERT Class 10 Science"` in their title, every entry receives an automatic keyword match score of 3. When a query for "Life Processes" is executed, the retriever erroneously matches Chapter 1 ("Chemical Reactions and Equations") and marks it `is_verified=True`. This corrupts the Resource Agent's context, which is passed to the Assessment Agent, causing questions about iron, water, and zinc to be generated for a Life Processes assessment.
- **Proposed Modification:**
  - Decouple subject filtering from topic/chapter keyword scoring.
  - Require `topic_match_score >= 2` (matching at least one substantive topic or chapter keyword) before assigning `is_verified = True`.
  - When only the subject matches and topic score is zero, set `is_verified = False` and `source_type = "Provisional Curriculum Guidelines"`.
- **Justification:** Eliminates cross-chapter context leakage and guarantees that agents receive only topic-relevant NCERT excerpts.
- **Alternative Approaches Rejected:**
  - *Instructing LLM via prompt to disregard unverified context:* Rejected because CrewAI agent task contexts strongly bias the LLM, and prompt instructions cannot reliably overcome false `is_verified=True` flags.
- **Database Schema or Existing Records Affected:** **NO.**

---

### 4. `data/resources/ncert_class10_science.json`
- **Exact File Path:** `data/resources/ncert_class10_science.json`
- **Current Responsibility:** Local JSON reference corpus containing verified NCERT textbook excerpts for CBSE Class 10 Science.
- **Problem Identified:** Currently contains only Chapters 1 ("Chemical Reactions"), 2 ("Acids, Bases and Salts"), and 11 ("Human Eye and Colourful World"). Chapter 5 ("Life Processes") and other biology chapters are completely absent from the local corpus.
- **Proposed Modification:**
  - Append verified NCERT Class 10 Science Chapter 5 ("Life Processes") excerpts covering:
    - Autotrophic nutrition and photosynthesis equations.
    - Heterotrophic nutrition and human digestive system organs/enzymes.
    - Respiration (aerobic vs. anaerobic, ATP, alveoli).
    - Transportation (human heart, double circulation, xylem, phloem).
    - Excretion (human excretory system, structure of nephron).
- **Justification:** Provides authentic local grounding for the Resource Retriever, ensuring offline, high-fidelity curriculum context without external network calls.
- **Alternative Approaches Rejected:**
  - *Dynamic web scraping or third-party API lookups:* Rejected due to strict offline constraints and zero-cloud policy.
- **Database Schema or Existing Records Affected:** **NO.**

---

### 5. `backend/services/curriculum_bank_seeder.py`
- **Exact File Path:** `backend/services/curriculum_bank_seeder.py`
- **Current Responsibility:** Seeder module that populates the CBSE Class 10 question banks and diagnostic baseline assessment sets.
- **Problem Identified:** Lines 326–344 (`seed_life_processes()`) and lines 359–377 (`seed_light_reflection_refraction()`) execute a nested loop (5 subtopics × 5 questions) that instantiates the identical question template 25 times! In `data/gyaan_ai.db`, `diag_assess_life_processes_science` holds 25 copies of *"Which organelle is the site of photosynthesis in green plant cells?"*.
- **Proposed Modification:**
  - Replace the repetitive loop in `seed_life_processes()` with 25 distinct, pedagogically sound CBSE Class 10 questions covering all 5 subtopics.
  - Replace the repetitive loop in `seed_light_reflection_refraction()` with 25 distinct questions covering reflection, spherical mirrors, refraction, lens formula, and power of lenses.
- **Justification:** Solves the 25x identical question defect at its root.
- **Alternative Approaches Rejected:**
  - *Generating questions on the fly via LLM for every diagnostic quiz:* Rejected because diagnostic baselines must return instantaneously (<100ms), deterministically, and reproducibly across students.
- **Database Schema or Existing Records Affected:** **NO.** (Applies to fresh seeds; existing student attempt records remain completely untouched).

---

### 6. `backend/services/diagnostic_service.py`
- **Exact File Path:** `backend/services/diagnostic_service.py`
- **Current Responsibility:** Service managing diagnostic assessment assembly, caching, and student diagnostic result evaluation.
- **Problem Identified:** The diagnostic cache retrieves questions from the database without deduplicating question stems. If a seeded bank contains duplicate entries, the cache serves them directly to the student.
- **Proposed Modification:**
  - Add a deduplication check when assembling diagnostic quiz sets: verify that each question has a distinct question stem before inclusion. If duplicates exist in the bank, select distinct alternatives.
- **Justification:** Provides defensive architecture ensuring students never receive duplicate questions regardless of bank state.
- **Alternative Approaches Rejected:**
  - *Frontend-only deduplication:* Rejected because deduplicating in the frontend would result in quizzes with fewer than the required 25 questions, corrupting backend scoring and progress calculations.
- **Database Schema or Existing Records Affected:** **NO.**

---

### 7. `backend/app/main.py`
- **Exact File Path:** `backend/app/main.py`
- **Current Responsibility:** FastAPI entry point defining API routes, middleware, and student endpoints including `GET /api/v1/students/me/mentor-recommendations`.
- **Problem Identified:** Lines 894–962 unconditionally launch a synchronous two-agent CrewAI workflow (`Progress Agent` → `Mentor Agent`) on local Ollama. For a student with zero completed assessments, `calculate_objective_statistics` returns `has_sufficient_history: False`, yet the backend still spends 60–90+ seconds running the LLM, only to return an empty recommendation array (`recommendations: []`).
- **Proposed Modification:**
  - Inspect `objective_stats.get("has_sufficient_history")`. If `False`, immediately return structured onboarding guidance:
    ```json
    {
      "mentor_overview": "Welcome to AI Mentoring! You have not completed any quizzes or diagnostics yet. Complete your first practice set so I can analyze your strengths and tailor personalized recommendations.",
      "recommendations": [],
      "study_tip": "Start by taking a 5-question quick quiz in Practice & Assessments.",
      "next_milestone": "Complete your first Class 10 assessment."
    }
    ```
    Response time: < 50ms (saving 90 seconds of unnecessary Ollama inference).
- **Justification:** Solves the 90-second freeze for new students, providing immediate, encouraging orientation.
- **Alternative Approaches Rejected:**
  - *Throwing an HTTP 400 error when assessments are zero:* Rejected because a new student legitimately visiting their mentor should receive helpful guidance, not an error screen.
- **Database Schema or Existing Records Affected:** **NO.**

---

### 8. `frontend/app/mentor/page.tsx`
- **Exact File Path:** `frontend/app/mentor/page.tsx`
- **Current Responsibility:** Next.js client component displaying AI Mentor recommendations, priority study areas, and weekly milestones.
- **Problem Identified:** Displays a static loading card with internal jargon (`"Mentor Agent • Phase 8.8 Live"`, `"Sequential Multi-Agent Crew"`). When recommendations are empty, it appears stuck in an indefinite loading state with no call to action.
- **Proposed Modification:**
  - Render an engaging onboarding card when `recommendations.length === 0` with a direct action button: `[Take Practice Quiz]`.
  - Add an elapsed loading timer and a 30-second timeout handler for active LLM runs.
  - Replace technical badges with student-friendly labels:
    - `"Mentor Agent • Phase 8.8 Live"` → `"Personalized Learning Coach"`
    - `"Sequential Multi-Agent Crew • Task Context Injected"` → `"Synthesizing Study Strategy"`
- **Justification:** Enhances student UX, eliminates perceived freezes, and removes developer jargon.
- **Alternative Approaches Rejected:**
  - *Disabling the Mentor tab until a quiz is taken:* Rejected because students should be aware of the mentoring capability and understand how to unlock recommendations.
- **Database Schema or Existing Records Affected:** **NO.**

---

### 9. `frontend/app/teacher/page.tsx`
- **Exact File Path:** `frontend/app/teacher/page.tsx`
- **Current Responsibility:** Next.js client component providing the Socratic conversational tutoring workspace with AI Teacher.
- **Problem Identified:**
  - Layout is heavily constrained: wrapped in double padding (`AppShell` + `py-6`), fixed viewport calculation `h-[calc(100vh-5rem)]` causes dual scrollbars.
  - Large top header (~100px) and multi-line curriculum selector strip (~120px) consume ~220px before any chat messages are visible.
  - Message bubble canvas is restricted (`max-w-[85%]` within `max-w-6xl`), cramping LaTeX equations and code snippets.
  - Contains developer-facing technical strings: `"Orchestrated Multi-Agent System"`, `"qwen2.5:3b"`, `"Executing specialized task across canonical agents via local Ollama (qwen2.5:3b)..."`.
- **Proposed Modification:**
  - Refactor outer container to `flex-1 h-[calc(100vh-4.5rem)] overflow-hidden flex flex-col`.
  - Consolidate header and curriculum selector into a sleek, compact, collapsible single-line toolbar.
  - Expand message canvas to `w-full max-w-4xl mx-auto flex-1 overflow-y-auto px-4 py-4`.
  - Pin auto-expanding input box to the bottom with keyboard shortcuts (`Enter` send, `Shift+Enter` newline).
  - Replace technical labels:
    - `"Orchestrated Multi-Agent System"` → `"AI Study Companion"`
    - `"qwen2.5:3b"` → `"Private Local AI"`
    - `"Executing specialized task across canonical agents via local Ollama (qwen2.5:3b)..."` → `"Analyzing your question and preparing a step-by-step explanation..."`
- **Justification:** Transforms the cramped viewport into a spacious, distraction-free educational workspace optimized for reading, LaTeX math, and interactive dialogue.
- **Alternative Approaches Rejected:**
  - *Modal or popup chat window:* Rejected because Socratic tutoring requires an immersive, persistent study environment.
- **Database Schema or Existing Records Affected:** **NO.**

---

### 10. `frontend/app/learning-plans/page.tsx`
- **Exact File Path:** `frontend/app/learning-plans/page.tsx`
- **Current Responsibility:** Next.js client component for viewing, generating, and tracking personalized 7-day CBSE study plans.
- **Problem Identified:** Line 120 exposes internal developer milestone text: `"Curriculum Agent • Phase 8.6 Live"`.
- **Proposed Modification:** Replace badge with `"Personalized 7-Day Study Plans"`.
- **Justification:** Ensures consistent, professional, student-centered presentation.
- **Alternative Approaches Rejected:** Leaving developer labels in place.
- **Database Schema or Existing Records Affected:** **NO.**

---

### 11. `frontend/app/resources/page.tsx`
- **Exact File Path:** `frontend/app/resources/page.tsx`
- **Current Responsibility:** Next.js client component for searching, filtering, and reading verified NCERT curriculum resources.
- **Problem Identified:** Line 136 exposes internal developer milestone text: `"Resource Agent • Phase 8.7 Live"`.
- **Proposed Modification:** Replace badge with `"NCERT Verified Study Materials"`.
- **Justification:** Educational clarity and professional presentation.
- **Alternative Approaches Rejected:** Leaving developer labels in place.
- **Database Schema or Existing Records Affected:** **NO.**

---

## 3. CONFIRMATION OF DATABASE & AGENT PRESERVATION

```
Active SQLite Database:   D:\Gyaan AI\data\gyaan_ai.db
Schema Modifications:     NONE (0 table, column, index, or constraint changes)
Student Record Changes:   NONE (All 793 registered students remain untouched)
Session Record Changes:   NONE (All 797 active sessions remain untouched)
CrewAI Agents Modified:   NONE (All 8 canonical agents retain roles, backstories, tasks)
Ollama LLM Architecture:  UNCHANGED (qwen2.5:3b on http://127.0.0.1:11434 preserved)
```
