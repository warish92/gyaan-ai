# GYAAN AI — AI TEACHER WORKSPACE AUDIT
**Date**: November 14, 2026  
**Environment**: Windows 11 | Next.js 14.2.35 Frontend | Tailwind CSS  
**Project**: `D:\Gyaan AI` | **Protected Legacy**: `D:\GYAN Ai` (Untouched)  
**Investigation Mode**: Strictly Read-Only Investigation  

---

## 1. Executive Summary

This audit provides a comprehensive, read-only UI/UX, layout, and ergonomic investigation of the **AI Teacher & Socratic Studio** (`frontend/app/teacher/page.tsx`).

The AI Teacher is the core conversational learning hub of Gyaan AI, allowing Class 10 CBSE students to interact with the Socratic Tutor and seven specialized learning agents. While the underlying backend agent orchestration operates effectively, the interface suffers from acute **viewport fragmentation, double scrolling, and pedagogical rendering limitations** that degrade the student learning experience—particularly on laptop screens ($\le 800\text{px}$ height) and tablets.

### Critical Deficiencies Identified:
1. **The Double-Scrollbar Defect**: `frontend/components/layout/AppShell.tsx` wraps pages in `<main className="flex-1 p-4 sm:p-6 lg:p-8">`, while `teacher/page.tsx` specifies `h-[calc(100vh-4.5rem)]`. Because the 4.5rem subtraction only accounts for the TopNav and ignores the parent `main` padding ($32\text{px} - 64\text{px}$ total), the total rendered height exceeds $100\text{vh}$, creating an outer browser scrollbar alongside the internal message scrollbar.
2. **Above-the-Fold Real Estate Squeeze**: On a standard $1366 \times 768$ laptop screen, non-message UI chrome (TopNav, page padding, teacher title bar, expanded curriculum selectors, and composer) consumes $\sim 480\text{px}$, leaving **less than $290\text{px}$** for reading AI teacher explanations.
3. **Table & Math Rendering Gaps in `FormattedMessage.tsx`**:
   - **Markdown Tables**: Completely unparsed; table rows (`| col1 | col2 |`) render as raw, separated plain-text paragraphs.
   - **LaTeX Mathematics**: Block math (`\[ ... \]` / `$$ ... $$`) renders as raw unformatted code in a gray box; inline math (`$...$`) is not recognized. Students see raw LaTeX syntax rather than rendered mathematical notation.
4. **Composer Ergonomics**: On vertical scrolling, the input composer can get pushed below the visible viewport fold. Quick-prompt chips lack scrolling indicators, and there is no active submission abort/cancel mechanism.

To resolve these issues cleanly without disrupting backend APIs or agent workflows, this audit presents a formal **Two-Mode Architecture Proposal**: **Standard Mode** (Curriculum Studio) and **Focus Mode** (Distraction-Free Immersion).

---

## 2. Viewport Height & Width Math Analysis

### Current Layout Hierarchy & Dimension Mismatch

```
┌─────────────────────────────────────────────────────────────┐
│ Window Viewport (100vh)                                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ TopNav (h-16 / 64px)                                  │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ AppShell <main> (Padding: p-4 to p-8 = 16px to 32px)   │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │ Teacher Container: h-[calc(100vh - 4.5rem)]      │  │  │
│  │  │                                                 │  │  │
│  │  │  TOTAL COMPUTED HEIGHT:                         │  │  │
│  │  │  64px (TopNav)                                  │  │  │
│  │  │  + 32px (main padding-top)                      │  │  │
│  │  │  + (100vh - 72px) (teacher container)           │  │  │
│  │  │  + 32px (main padding-bottom)                   │  │  │
│  │  │  = 100vh + 56px  ==> OVERFLOW / OUTER SCROLL!   │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

#### Pixel Allocation on Standard 1366 × 768 Laptop Display:

| UI Component | Allocated Height | Cumulative Used | Remaining Chat Height |
|---|---|---|---|
| **Top Navigation** | 64px | 64px | 704px |
| **AppShell Vertical Padding** | 48px ($24\text{px} \times 2$) | 112px | 656px |
| **Teacher Header & Controls** | 56px | 168px | 600px |
| **Curriculum Context Strip (when open)** | 136px | 304px | 464px |
| **Composer Form & Action Chips** | 108px | 412px | 356px |
| **Container Borders & Margins** | 24px | 436px | 332px |
| **Net Available Message Canvas** | — | — | **~332px** (Only 1 message visible!) |

---

## 3. Nested Scrolling & Container Constraints

### The "Scroll Kidnapping" Phenomenon:
1. When a student uses a trackpad or mouse wheel inside the chat area, if the cursor moves slightly outside the message box boundary or reaches the scroll boundary, the event bubbles to `window`.
2. Because the total document height is $100\text{vh} + 56\text{px}$, the browser scrolls the outer page downwards.
3. This pushes the TopNav offscreen and slides the input composer below the bottom fold, forcing the student to manually scroll the entire browser window back up to find the composer.
4. **Root Cause**: The layout relies on an arbitrary `calc(100vh - 4.5rem)` height rather than a strict flexbox contract (`flex-1 min-h-0 flex flex-col`) with `overflow-hidden` on the parent shell.

---

## 4. Pedagogical Content Rendering Audit

The AI Teacher frequently outputs structured pedagogical content including formulas, chemical reactions, and comparative study tables. These are processed through `frontend/components/ui/FormattedMessage.tsx`.

### 4.1 Markdown Table Rendering (Severe Defect)
- **Current Behavior**: `FormattedMessage.tsx` contains no table tokenizer. A table such as:
  ```markdown
  | Property | Acid | Base |
  |---|---|---|
  | Taste | Sour | Bitter |
  | Litmus | Blue to Red | Red to Blue |
  ```
  is parsed line-by-line as plain paragraphs (`<p>`).
- **Rendered Output**:
  ```
  | Property | Acid | Base |
  |---|---|---|
  | Taste | Sour | Bitter |
  | Litmus | Blue to Red | Red to Blue |
  ```
  The table is completely illegible to students reviewing CBSE board distinction questions.
- **Required Fix**: Add a native table parser to `FormattedMessage.tsx` that detects Markdown table blocks, splits rows and cells, and outputs responsive `<table>` elements with styled headers, alternating row striping, and `overflow-x-auto` wrappers.

### 4.2 LaTeX Mathematics & Chemical Equation Rendering
- **Current Behavior**:
  - `FormattedMessage.tsx` only checks for lines that strictly start with `\[` or `$$` and end with `\]` or `$$`.
  - Inside those blocks, it renders raw monospace text: `<div className="font-mono text-xs ... select-all">{mathContent}</div>`.
  - It does NOT render real mathematical typesetting (fractions, square roots, sub/superscripts, chemical reaction arrows).
  - Inline equations like `$2H_2 + O_2 \rightarrow 2H_2O$` or `$R = \frac{\rho L}{A}$` are completely ignored and displayed with literal dollar signs.
- **Required Fix**: Enhance `FormattedMessage.tsx` with KaTeX inline and display parsing, or clean KaTeX-compatible rendering that transforms LaTeX math blocks into legible symbols without crashing on malformed expressions.

### 4.3 Code Blocks & Typography
- **Current Behavior**: Code blocks render with a dark background (`bg-slate-900`) and language tag.
- **Deficiencies**: Lacks a one-click "Copy Code" button, and has fixed padding that can consume substantial vertical height when multiple snippets appear in a single response.

---

## 5. Input Composer & Ergonomic Usability Audit

### Evaluation of `frontend/app/teacher/page.tsx` Composer:
1. **Dynamic Resizing**: Textarea auto-expands cleanly up to `160px` (`max-h-36`) based on content.
2. **Keybindings**: Correctly submits on `Enter` and creates a newline on `Shift + Enter`.
3. **Quick Prompt Action Chips**:
   - Useful pedagogical shortcuts (`Explain core concept`, `Real-World Examples`, `Solved Question`, `Common Board Pitfalls`).
   - However, they take up static vertical height (~36px) above the composer even when the user has already typed a custom question.
4. **Missing Capabilities**:
   - **No Abort/Cancel Controller**: Once a question is submitted, the student must wait for the full LLM completion. There is no "Stop Generating" button.
   - **No Character Counter or Validation Pill**: Short or empty inputs are rejected only via browser `alert()`.

---

## 6. Multi-Device Responsiveness Analysis

| Viewport | Typical Devices | Current Limitations | Usability Rating |
|---|---|---|---|
| **Mobile (< 640px)** | Phones | Context selectors stack into 3 rows; chat messages squeezed horizontally; composer consumes 30% of screen. | **Marginal** |
| **Tablet (641px – 1024px)** | iPads, Surface Go | Squeezed vertically; dual scrollbars cause accidental window scrolling. | **Fair** |
| **Laptop (1024px – 1440px)** | 13" & 14" Laptops ($768\text{px} - 900\text{px}$ H) | Severe vertical cramping; less than 350px available for reading. | **Poor** |
| **Desktop (> 1440px)** | External Monitors | Excess margins; `max-w-5xl` is centered, but vertical space is well-proportioned. | **Good** |

---

## 7. Two-Mode Architecture Proposal

To provide an optimal experience for both guided curriculum browsing and deep, uninterrupted study sessions, we propose a clean **Two-Mode Architecture**.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TWO-MODE TEACHER STUDIO                         │
├───────────────────────────────────┬────────────────────────────────────┤
│ 1. STANDARD MODE                  │ 2. FOCUS MODE                      │
│ (Guided Curriculum Studio)        │ (Distraction-Free Immersion)       │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Integrated inside AppShell      │ • Fullscreen Overlay (fixed z-50)  │
│ • Sidebar & TopNav visible        │ • Sidebar & TopNav hidden          │
│ • Rich curriculum breadcrumbs     │ • Ultra-minimal 40px top bar       │
│ • Quick-action topic chips        │ • Maximized vertical reading canvas│
│ • Agent status & telemetry        │ • Floating ergonomic composer      │
│ • Best for: Discovery & Planning  │ • Best for: Deep Socratic Study    │
└───────────────────────────────────┴────────────────────────────────────┘
```

---

### 7.1 Mode 1: Standard Mode (Refined Studio)

#### Design Specifications:
1. **Zero Outer Scrollbar**: Fix parent container to `h-[calc(100vh-5rem)]` with exact flexbox containment (`flex flex-col min-h-0`), ensuring the outer page never scrolls.
2. **Single-Line Breadcrumb Toolbar**:
   - Collapse the 3 separate subject/chapter/topic dropdowns into a single horizontal breadcrumb strip:
     `Science › Ch 1: Chemical Reactions › Topic 1.1 › [Conceptual ▾]`
   - Saves **90px of vertical space** above the fold.
3. **Fixed Pinned Composer Dock**: The bottom input bar remains permanently anchored to the bottom of the container, immune to parent window scrolling.
4. **Enhanced Table & Math Formatting**: Automatic rendering of Markdown tables and KaTeX formulas.

---

### 7.2 Mode 2: Focus Mode (Distraction-Free Immersion)

#### Design Specifications:
1. **Fullscreen Canvas**:
   - Activated via a prominent `[Enter Focus Mode]` button in the header or `F11` / shortcut.
   - Implemented via a high z-index overlay (`fixed inset-0 z-50 bg-[#F8FAFC] flex flex-col`).
   - Automatically hides the global AppShell Sidebar and TopNav.
2. **Minimal Glassmorphic Utility Strip (40px)**:
   - Left: Compact pill badge showing current subject and chapter (`Science › Ch 1`).
   - Center: Private Local AI indicator (`qwen2.5:3b • 100% Genuine Local Inference`).
   - Right: Message count, Clear Chat button, and a prominent `[Exit Focus Mode (Esc)]` button.
3. **Maximized Reading Canvas**:
   - **88% of vertical viewport** dedicated entirely to the conversation history.
   - Constrained to `max-w-3xl mx-auto` for optimal typographic line length (65–75 characters per line).
   - Generous line height (`leading-relaxed`), clear distinction between student questions and Socratic tutor responses.
4. **Floating Ergonomic Composer**:
   - Pinned cleanly to the bottom: `sticky bottom-0 bg-white/95 backdrop-blur-md border-t border-slate-200 px-6 py-4`.
   - Centered with `max-w-3xl mx-auto`.
   - Subtle keyboard shortcut cues (`Enter` to send, `Shift+Enter` for newline).
   - Instant "Escape" key handling to return to Standard Mode.

---

## 8. Summary of Implementation Recommendations

1. **Fix Layout Math**: Replace arbitrary `h-[calc(100vh-4.5rem)]` with true flex container hierarchy to eradicate double scrollbars.
2. **Upgrade `FormattedMessage.tsx`**: Add table tokenizer and KaTeX math parsing to support CBSE formulas and comparison tables.
3. **Compact Curriculum Context**: Replace multi-row selector grid with an elegant single-line breadcrumb selector.
4. **Implement Focus Mode**: Add a distraction-free fullscreen overlay state (`isFocusMode`) with `Esc` key listener.
5. **Add Abort Support**: Integrate client-side cancellation to allow students to stop generation without reloading.
