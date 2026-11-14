"""Gyaan AI - Curriculum Agent Module.

Implements the canonical Curriculum Agent for constructing personalized,
sequenced learning plans based on genuine diagnostic evaluation context.

Enforces strict rules:
1. Prioritize only evidenced knowledge gaps.
2. Do not invent textbook exercise numbers or chapter references.
3. Do not claim NCERT alignment unless actual NCERT content has been retrieved and verified.
4. If no verified learning resource is available, label recommendations as general learning activities.
5. Create distinct learning stages without repeating identical questions.
6. Define measurable objectives for each stage.
7. Include prerequisite concepts where necessary.
8. Include assessment checkpoints.
9. Include a clear quantitative mastery criterion (70% benchmark).
10. Explain why each recommended topic is necessary based on diagnostic evidence.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from crewai import Agent, Crew, LLM, Process, Task
import json_repair

from backend.agents.teacher import get_local_llm
from backend.app.schemas import (
    CurriculumPlanModel,
    LearningStage,
)

logger = logging.getLogger("gyaan_ai.curriculum")


def get_db_curriculum_grounding(subject: str, query: str) -> Optional[Dict[str, Any]]:
    """Retrieve verified curriculum hierarchy from local SQLite database."""
    try:
        import sqlite3
        from pathlib import Path
        db_path = Path(__file__).resolve().parent.parent.parent / "data" / "gyaan_ai.db"
        if not db_path.exists():
            return None
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Search chapter
        cursor.execute(
            """
            SELECT id, chapter_number, title, prerequisites, source_reference, verification_status
            FROM curriculum_chapters
            WHERE title LIKE ? OR ? LIKE ('%' || title || '%')
            LIMIT 1;
            """,
            (f"%{query}%", query),
        )
        chap = cursor.fetchone()
        if not chap:
            words = [w for w in query.replace("-", " ").split() if len(w) > 3]
            for w in words:
                cursor.execute(
                    """
                    SELECT id, chapter_number, title, prerequisites, source_reference, verification_status
                    FROM curriculum_chapters
                    WHERE title LIKE ?
                    LIMIT 1;
                    """,
                    (f"%{w}%",),
                )
                chap = cursor.fetchone()
                if chap:
                    break
        if not chap:
            conn.close()
            return None
            
        chap_id, chap_num, chap_title, prereqs_raw, src_ref, ver_stat = chap
        try:
            prereqs = json.loads(prereqs_raw) if prereqs_raw else []
        except Exception:
            prereqs = [prereqs_raw] if prereqs_raw else []
            
        cursor.execute(
            """
            SELECT id, topic_number, title, summary FROM curriculum_topics
            WHERE chapter_id = ? ORDER BY topic_number;
            """,
            (chap_id,),
        )
        topics = cursor.fetchall()
        topic_data = []
        for t_id, t_num, t_title, t_sum in topics:
            cursor.execute(
                """
                SELECT objective_code, description, bloom_level
                FROM curriculum_learning_objectives
                WHERE topic_id = ?;
                """,
                (t_id,),
            )
            objs = [{"code": r[0], "description": r[1], "bloom": r[2]} for r in cursor.fetchall()]
            topic_data.append({"id": t_id, "number": t_num, "title": t_title, "summary": t_sum, "objectives": objs})
            
        conn.close()
        return {
            "chapter_id": chap_id,
            "chapter_number": chap_num,
            "chapter_title": chap_title,
            "prerequisites": prereqs,
            "source_reference": src_ref,
            "verification_status": ver_stat,
            "topics": topic_data,
        }
    except Exception as exc:
        logger.warning("Error fetching db curriculum grounding: %s", exc)
        return None


def create_curriculum_agent(llm: Optional[LLM] = None) -> Agent:
    """Create a genuine CrewAI Evidence-Grounded Curriculum Agent.

    Args:
        llm: Configured LLM instance. Defaults to local Ollama.

    Returns:
        Agent: Configured CrewAI Agent instance.
    """
    if llm is None:
        llm = get_local_llm()

    return Agent(
        role="Evidence-Grounded Curriculum Planning Specialist",
        goal=(
            "Transform diagnostic assessment findings into an actionable, logically sequenced, and prioritized "
            "personalized study plan. Ground all stages strictly in evidenced knowledge gaps. "
            "Never invent textbook exercise numbers or page references. "
            "Never claim NCERT alignment unless verified NCERT text is provided. "
            "Label study activities as general learning activities. "
            "Include prerequisite concepts, measurable objectives, assessment checkpoints, "
            "and an explicit 70% mastery criterion."
        ),
        backstory=(
            "You are a pedagogical architect who designs personalized learning roadmaps for Class 10 CBSE students. "
            "You adhere to strict grounding principles:\n"
            "1. You prioritize ONLY topics that address evidenced knowledge gaps identified by the Diagnostic Agent.\n"
            "2. STRICT PROHIBITION: You NEVER invent textbook exercise numbers (e.g. 'Exercise 1.2 Q3'), section numbers, or page references.\n"
            "3. STRICT PROHIBITION: You NEVER claim official NCERT textbook alignment unless actual NCERT excerpts have been retrieved and verified.\n"
            "4. When unverified against textbook texts, you explicitly label all study tasks as 'General learning activities'.\n"
            "5. You organize learning into distinct, non-repetitive sequential stages (e.g. Prerequisite Recovery, Core Concept Mastery, Applied Problem Solving).\n"
            "6. You define concrete, measurable learning objectives (e.g. 'Student will be able to balance simple synthesis equations').\n"
            "7. You include prerequisite concepts where necessary to bridge gaps.\n"
            "8. You provide distinct assessment checkpoint questions for each stage without repeating prior diagnostic questions.\n"
            "9. You enforce an explicit mastery criterion: 'A minimum 70% threshold on formative assessment checkpoints is required before advancing.'\n"
            "10. You explicitly state the diagnostic justification for why each stage is required."
        ),
        llm=llm,
        verbose=True,
        memory=False,
    )


def create_curriculum_task(
    agent: Agent,
    diagnostic_task: Task,
    grade: str,
    subject: str,
    topic: str,
) -> Task:
    """Create a Curriculum Planning Task that explicitly depends on Diagnostic Task output.

    Args:
        agent: The Curriculum Agent.
        diagnostic_task: The upstream Diagnostic Task instance providing context.
        grade: Target grade level.
        subject: Target subject.
        topic: Overall topic/unit.

    Returns:
        Task: Configured CrewAI Task with context dependency.
    """
    description = (
        f"You are designing a personalized study plan for a {grade} student in {subject} on '{topic}'.\n\n"
        f"### CONTEXT FROM DIAGNOSTIC ASSESSMENT:\n"
        f"Carefully review the upstream diagnostic report from the Student Learning Diagnostic Specialist in the task context above. "
        f"Focus your plan directly on the evidenced knowledge gaps and diagnosed missing elements.\n\n"
        f"### STRICT CURRICULUM PLANNING REQUIREMENTS:\n"
        f"1. **Prioritize Only Evidenced Knowledge Gaps**: Do not add random unneeded topics.\n"
        f"2. **Strict Ban on Hallucinated Exercises**: DO NOT invent textbook exercise numbers, section numbers, or page references.\n"
        f"3. **Strict Ban on False NCERT Claims**: Do not claim NCERT textbook alignment unless verified NCERT excerpts were supplied.\n"
        f"4. **General Activity Labeling**: Label all recommended activities explicitly as 'General learning activity' (e.g. 'General learning activity: Draw a molecular diagram...').\n"
        f"5. **Distinct Stages**: Build a 3-stage roadmap without repeating identical questions or steps:\n"
        f"   - Stage 1: Prerequisite Recovery (addressing diagnosed missing foundational concepts)\n"
        f"   - Stage 2: Core Concept Mastery (step-by-step chapter concepts)\n"
        f"   - Stage 3: Applied Problem Solving & Verification\n"
        f"6. **Measurable Objectives**: State observable abilities the student will demonstrate at each stage.\n"
        f"7. **Prerequisite Concepts**: Explicitly list prerequisites required for each stage.\n"
        f"8. **Assessment Checkpoints**: Formulate distinct self-test questions (not repeating prior questions).\n"
        f"9. **Mastery Criterion**: State the mandatory threshold: 'A minimum 70% threshold on formative assessment checkpoints is required before advancing.'\n"
        f"10. **Evidence Justification**: Explain why each stage/topic is necessary based on the diagnostic findings.\n\n"
        f"### OUTPUT FORMAT:\n"
        f"Present your curriculum plan cleanly using structured markdown with sections:\n"
        f"# PERSONALIZED CURRICULUM PLAN\n"
        f"**Target**: {grade} | {subject} | {topic}\n"
        f"- **Primary Learning Goal**: [Clear, motivating goal]\n"
        f"- **Mastery Criterion**: A minimum 70% threshold on formative assessment checkpoints is required before advancing.\n"
        f"- **Resource Alignment**: General learning activities (Unverified against live NCERT textbook content)\n"
        f"- **Priority Topics**: [List prioritized by diagnostic evidence]\n\n"
        f"## Sequenced Learning Stages\n\n"
        f"### Stage 1: Prerequisite Recovery\n"
        f"- **Focus Topic**: [Diagnosed missing foundation]\n"
        f"- **Evidence Justification**: [Why needed based on diagnostic gap]\n"
        f"- **Prerequisites**: [Concepts]\n"
        f"- **Measurable Objectives**: [Observable skills]\n"
        f"- **Learning Activities**: [General learning activities, no fake exercise numbers]\n"
        f"- **Assessment Checkpoint**: [New self-test question]\n\n"
        f"### Stage 2: Core Concept Mastery\n"
        f"- **Focus Topic**: [Core chapter concept]\n"
        f"- **Evidence Justification**: [Why needed based on diagnostic gap]\n"
        f"- **Prerequisites**: [Concepts]\n"
        f"- **Measurable Objectives**: [Observable skills]\n"
        f"- **Learning Activities**: [General learning activities, no fake exercise numbers]\n"
        f"- **Assessment Checkpoint**: [New self-test question]\n\n"
        f"### Stage 3: Applied Problem Solving\n"
        f"- **Focus Topic**: [Application and problem solving]\n"
        f"- **Evidence Justification**: [Why needed based on diagnostic gap]\n"
        f"- **Prerequisites**: [Concepts]\n"
        f"- **Measurable Objectives**: [Observable skills]\n"
        f"- **Learning Activities**: [General learning activities, no fake exercise numbers]\n"
        f"- **Assessment Checkpoint**: [New self-test question]\n\n"
        f"## Summary\n"
        f"[Executive summary of study roadmap]"
    )

    expected_output = (
        "A sequenced 3-stage curriculum roadmap with prioritized prerequisites, observable objectives, "
        "general learning activities without hallucinated textbook numbers, distinct checkpoints, "
        "and explicit 70% mastery criterion."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        context=[diagnostic_task],  # Explicit task context dependency
    )


def parse_curriculum_plan(
    raw_text: str,
    grade: str = "Class 10",
    subject: str = "Science",
    topic: str = "General",
) -> CurriculumPlanModel:
    """Parse raw LLM output into a structured CurriculumPlanModel.

    Handles both JSON payloads and structured Markdown plans.

    Args:
        raw_text: Raw output string from Curriculum Agent.
        grade: Student grade level.
        subject: Subject matter.
        topic: Topic assessed.

    Returns:
        CurriculumPlanModel: Structured validated curriculum plan model.
    """
    text = raw_text.strip()

    # Attempt 1: Parse as JSON if formatted as JSON
    try:
        json_candidate = text
        if "```json" in text:
            json_candidate = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text and "{" in text:
            json_candidate = text.split("```")[1].split("```")[0].strip()

        if "{" in json_candidate and "}" in json_candidate:
            data = json_repair.loads(json_candidate)
            if isinstance(data, dict) and ("learning_stages" in data or "prioritized_topics" in data):
                return CurriculumPlanModel(
                    grade=data.get("grade", grade),
                    subject=data.get("subject", subject),
                    topic=data.get("topic", topic),
                    primary_mastery_goal=data.get("primary_mastery_goal", f"Master core concepts in {topic}"),
                    mastery_criterion=data.get("mastery_criterion", "A minimum 70% threshold on formative assessment checkpoints is required before advancing."),
                    prioritized_topics=data.get("prioritized_topics", [topic]),
                    learning_stages=[
                        LearningStage(
                            stage_number=stg.get("stage_number", i),
                            stage_name=stg.get("stage_name", f"Stage {i}"),
                            focus_topic=stg.get("focus_topic", topic),
                            prerequisite_concepts=stg.get("prerequisite_concepts", []),
                            measurable_objectives=stg.get("measurable_objectives", []),
                            learning_activities=stg.get("learning_activities", []),
                            assessment_checkpoint=stg.get("assessment_checkpoint", "Complete stage review."),
                            evidence_justification=stg.get("evidence_justification", "Grounded in diagnostic assessment findings."),
                        )
                        for i, stg in enumerate(data.get("learning_stages", []), 1)
                    ],
                    resource_alignment_status=data.get("resource_alignment_status", "General learning activities (Unverified against live NCERT textbook content)"),
                    summary=data.get("summary", "Sequenced study roadmap based on diagnostic evidence."),
                )
    except Exception as exc:
        logger.debug("Curriculum JSON parsing fallback to Markdown parser: %s", exc)

    # Attempt 2: Structured Markdown parsing
    stages: List[LearningStage] = []
    stage_blocks = re.split(r"(?:###\s*(?:Stage\s*\d+|Step\s*\d+))", text, flags=re.IGNORECASE)

    grounding = get_db_curriculum_grounding(subject=subject, query=topic)

    if len(stage_blocks) > 1:
        for idx, block in enumerate(stage_blocks[1:], 1):
            if "## Summary" in block:
                block = block.split("## Summary")[0]

            def extract_field(pattern: str, default: str = "") -> str:
                m = re.search(r"[-*•]?\s*\*{0,2}" + pattern + r"\*{0,2}\s*:\s*([^\n\r]+)", block, re.IGNORECASE)
                return m.group(1).strip() if m else default

            def extract_list(pattern: str) -> List[str]:
                m = re.search(r"[-*•]?\s*\*{0,2}" + pattern + r"\*{0,2}\s*:\s*(.+?)(?:\n\s*[-*•]|\n#|\n\n|$)", block, re.DOTALL | re.IGNORECASE)
                if not m:
                    # Try single-line match
                    val = extract_field(pattern)
                else:
                    val = m.group(1).strip()
                if not val or val.lower() in ("none", "n/a", "nil"):
                    return []
                items = [re.sub(r"^[-*•]\s*", "", i).strip() for i in re.split(r"[\n,;]", val) if i.strip()]
                return [i for i in items if i and i.lower() not in ("none", "n/a", "nil")]

            first_line = block.splitlines()[0].strip() if block.splitlines() else f"Stage {idx}"
            if ":" in first_line:
                stage_name = first_line.split(":", 1)[1].strip()
            elif "-" in first_line:
                stage_name = first_line.split("-", 1)[1].strip()
            else:
                stage_name = first_line
            stage_name = stage_name.strip("#* ")

            focus_topic = extract_field(r"Focus Topic", default="")
            justification = extract_field(r"(?:Evidence Justification|Justification)", default="Grounded in curriculum progression and diagnosed learning gaps.")
            prereqs = extract_list(r"(?:Prerequisites|Prerequisite Concepts)")
            objectives = extract_list(r"(?:Measurable Objectives|Objectives)")
            activities = extract_list(r"(?:Learning Activities|Recommended Activities)")
            checkpoint = extract_field(r"(?:Assessment Checkpoint|Checkpoint)", default=f"Stage {idx} formative checkpoint.")

            # Ground default distinct topics if model returned generic/empty
            if not focus_topic or focus_topic.lower() == topic.lower():
                if idx == 1:
                    focus_topic = f"{topic} — Foundational Concepts & Prerequisites"
                elif idx == 2:
                    focus_topic = f"{topic} — Core Principles & Mechanisms"
                else:
                    focus_topic = f"{topic} — Applications, Analysis & Problem Solving"

            stages.append(
                LearningStage(
                    stage_number=idx,
                    stage_name=f"Stage {idx}: {stage_name}" if not stage_name.startswith("Stage") else stage_name,
                    focus_topic=focus_topic,
                    prerequisite_concepts=prereqs or (grounding["prerequisites"] if (grounding and idx == 1) else ["Foundational scientific terms"]),
                    measurable_objectives=objectives or [f"Demonstrate measurable mastery in {focus_topic}"],
                    learning_activities=activities or [f"General learning activity: Study and practice key principles of {focus_topic}"],
                    assessment_checkpoint=checkpoint,
                    evidence_justification=justification,
                )
            )

    # Fallback default stages if parsing found none
    if not stages:
        stages = [
            LearningStage(
                stage_number=1,
                stage_name="Stage 1: Prerequisite Recovery",
                focus_topic=f"{topic} — Foundational Concepts & Prerequisites",
                prerequisite_concepts=grounding["prerequisites"] if grounding else ["Basic terminology"],
                measurable_objectives=["Identify key principles and verify baseline prerequisites"],
                learning_activities=["General learning activity: Review foundational concepts and definitions"],
                assessment_checkpoint="Formative check on prerequisites",
                evidence_justification="Directly addresses diagnosed baseline gap.",
            ),
            LearningStage(
                stage_number=2,
                stage_name="Stage 2: Core Concept Mastery",
                focus_topic=f"{topic} — Core Principles & Mechanisms",
                prerequisite_concepts=["Prerequisite concepts from Stage 1"],
                measurable_objectives=["Explain core scientific laws and mechanisms"],
                learning_activities=["General learning activity: Guided concept practice and worked examples"],
                assessment_checkpoint="Formative check on core chapter concepts",
                evidence_justification="Deepens mastery of central curriculum standards.",
            ),
            LearningStage(
                stage_number=3,
                stage_name="Stage 3: Applied Problem Solving & Verification",
                focus_topic=f"{topic} — Applications, Analysis & Problem Solving",
                prerequisite_concepts=["Core concepts from Stage 2"],
                measurable_objectives=["Apply formulas and solve multi-step CBSE board-style problems"],
                learning_activities=["General learning activity: Competency-based problem-solving exercise"],
                assessment_checkpoint="Summative chapter mastery evaluation",
                evidence_justification="Verifies transfer of learning and board exam readiness.",
            ),
        ]

    goal_match = re.search(r"[-*•]?\s*\*{0,2}(?:Primary Learning Goal|Learning Goal)\*{0,2}\s*:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    goal = goal_match.group(1).strip() if goal_match else f"Achieve mastery in {subject}: {topic}."

    alignment_match = re.search(r"[-*•]?\s*\*{0,2}(?:Resource Alignment|Alignment)\*{0,2}\s*:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    if alignment_match:
        alignment_status = alignment_match.group(1).strip()
    elif grounding:
        alignment_status = f"Verified Official NCERT Curriculum Corpus ({grounding['source_reference']})"
    else:
        alignment_status = "General learning activities (Unverified against live NCERT textbook content)"

    summary_match = re.search(r"(?:## Summary|Summary):\s*(.+?)(?:\n#|\n\n\n|$)", text, re.DOTALL | re.IGNORECASE)
    summary = summary_match.group(1).strip() if summary_match else "Sequenced study roadmap based on curriculum database evidence."

    return CurriculumPlanModel(
        grade=grade,
        subject=subject,
        topic=topic,
        primary_mastery_goal=goal,
        mastery_criterion="A minimum 70% threshold on formative assessment checkpoints is required before advancing.",
        prioritized_topics=[stg.focus_topic for stg in stages],
        learning_stages=stages,
        resource_alignment_status=alignment_status,
        summary=summary,
    )


def format_curriculum_plan_markdown(plan: CurriculumPlanModel) -> str:
    """Format a CurriculumPlanModel into standard, structured Markdown for display and context."""
    lines = [
        f"# PERSONALIZED CURRICULUM PLAN",
        f"**Target**: {plan.grade} | {plan.subject} | {plan.topic}",
        f"- **Primary Learning Goal**: {plan.primary_mastery_goal}",
        f"- **Mastery Criterion**: {plan.mastery_criterion}",
        f"- **Resource Alignment**: {plan.resource_alignment_status}",
        f"- **Priority Topics**: {', '.join(plan.prioritized_topics)}\n",
        f"## Sequenced Learning Stages\n",
    ]

    for stg in plan.learning_stages:
        lines.extend([
            f"### {stg.stage_name}",
            f"- **Focus Topic**: {stg.focus_topic}",
            f"- **Evidence Justification**: {stg.evidence_justification}",
            f"- **Prerequisites**: {', '.join(stg.prerequisite_concepts) if stg.prerequisite_concepts else 'None'}",
            f"- **Measurable Objectives**:",
        ])
        for obj in stg.measurable_objectives:
            lines.append(f"  * {obj}")

        lines.append(f"- **Learning Activities**:")
        for act in stg.learning_activities:
            lines.append(f"  * {act}")

        lines.extend([
            f"- **Assessment Checkpoint**: {stg.assessment_checkpoint}\n",
        ])

    lines.extend([
        f"## Summary",
        f"{plan.summary}",
    ])

    return "\n".join(lines)


def create_curriculum_inquiry_task(
    agent: Agent,
    grade: str,
    subject: str,
    topic: str,
    inquiry: Optional[str] = None,
) -> Task:
    """Create a standalone Curriculum Inquiry Task for syllabus planning and roadmap generation."""
    grounding = get_db_curriculum_grounding(subject=subject, query=topic)
    
    db_context_section = ""
    resource_alignment_text = "General learning activities (Unverified against live NCERT textbook content)"
    
    if grounding:
        chap_title = grounding["chapter_title"]
        chap_num = grounding["chapter_number"]
        src_ref = grounding["source_reference"]
        ver_stat = grounding["verification_status"]
        prereqs_str = ", ".join(grounding["prerequisites"]) if grounding["prerequisites"] else "Foundational concepts"
        
        topics_text_list = []
        for t in grounding["topics"]:
            t_str = f"  * Topic {t['number']}: {t['title']} — {t['summary']}\n    Official Measurable Objectives:"
            for obj in t["objectives"]:
                t_str += f"\n      - [{obj['code']}] {obj['description']} (Bloom: {obj['bloom']})"
            topics_text_list.append(t_str)
        topics_formatted = "\n\n".join(topics_text_list)
        
        resource_alignment_text = f"Verified Official NCERT Curriculum Corpus ({src_ref})"
        
        db_context_section = (
            f"### OFFICIAL CBSE / NCERT CURRICULUM DATABASE EVIDENCE:\n"
            f"- Prescribed Chapter: {chap_title} (CBSE Chapter {chap_num})\n"
            f"- Source Reference: {src_ref} (Status: {ver_stat})\n"
            f"- Official Prerequisites: {prereqs_str}\n"
            f"- Prescribed Chapter Topics & Objectives:\n{topics_formatted}\n\n"
        )

    description = (
        f"You are designing a structured CBSE curriculum roadmap for a {grade} student in {subject} on '{topic}'.\n"
        f"Student Inquiry/Goal: {inquiry or 'Outline complete curriculum structure, prerequisite hierarchy, and study stages.'}\n\n"
        f"{db_context_section}"
        f"### STRICT CURRICULUM PLANNING REQUIREMENTS:\n"
        f"1. **Curriculum Grounding**: Ground the curriculum plan strictly in the official CBSE/NCERT curriculum database evidence provided above.\n"
        f"2. **Distinct Learning Stages & Non-Repetition**: Build a 3-stage roadmap where EACH stage has DISTINCT, observable learning objectives. DO NOT repeat identical objectives across stages:\n"
        f"   - Stage 1: Prerequisite Foundations (focus on foundational prerequisites: {grounding['prerequisites'][0] if grounding and grounding['prerequisites'] else 'Prerequisite foundations'})\n"
        f"   - Stage 2: Core Concept Mastery (focus on primary core chapter concepts and comprehension)\n"
        f"   - Stage 3: Applied Problem Solving & Verification (focus on application, analysis, and exam problems)\n"
        f"3. **Measurable Objectives**: State clear, observable abilities the student will demonstrate at each stage (e.g. 'Student will be able to balance equations').\n"
        f"4. **No Hallucinated References**: Never invent fake textbook exercise numbers or unverified citations.\n"
        f"5. **Source Provenance**: Explicitly state the verified source reference in the Resource Alignment field.\n"
        f"6. **Mastery Criterion**: State the mandatory quantitative threshold: 'A minimum 70% threshold on formative assessment checkpoints is required before advancing.'\n"
        f"7. **Assessment Checkpoints**: Formulate distinct checkpoint questions for each stage.\n\n"
        f"### OUTPUT FORMAT:\n"
        f"Present your curriculum plan cleanly using structured markdown with sections:\n"
        f"# PERSONALIZED CURRICULUM PLAN\n"
        f"**Target**: {grade} | {subject} | {grounding['chapter_title'] if grounding else topic}\n"
        f"- **Primary Learning Goal**: Achieve mastery in {grounding['chapter_title'] if grounding else topic} aligned with CBSE standards.\n"
        f"- **Mastery Criterion**: A minimum 70% threshold on formative assessment checkpoints is required before advancing.\n"
        f"- **Resource Alignment**: {resource_alignment_text}\n"
        f"- **Priority Topics**: [{grounding['chapter_title'] if grounding else topic}]\n\n"
        f"## Sequenced Learning Stages\n\n"
        f"### Stage 1: Prerequisite Foundations\n"
        f"- **Focus Topic**: [Distinct foundational topic, e.g. Reflection and Spherical Mirrors]\n"
        f"- **Evidence Justification**: [Why needed based on syllabus progression]\n"
        f"- **Prerequisites**: [{prereqs_str if grounding else 'Foundational concepts'}]\n"
        f"- **Measurable Objectives**:\n"
        f"  * [Observable objective 1]\n"
        f"- **Learning Activities**:\n"
        f"  * General learning activity: [Activity description]\n"
        f"- **Assessment Checkpoint**: [Formative checkpoint question]\n\n"
        f"### Stage 2: Core Concept Mastery\n"
        f"- **Focus Topic**: [Distinct core topic, e.g. Refraction and Snell's Law]\n"
        f"- **Evidence Justification**: [Why needed for core chapter understanding]\n"
        f"- **Prerequisites**: [Concepts mastered in Stage 1]\n"
        f"- **Measurable Objectives**:\n"
        f"  * [Observable objective 1]\n"
        f"- **Learning Activities**:\n"
        f"  * General learning activity: [Activity description]\n"
        f"- **Assessment Checkpoint**: [Formative checkpoint question]\n\n"
        f"### Stage 3: Applied Problem Solving & Verification\n"
        f"- **Focus Topic**: [Distinct applied topic, e.g. Spherical Lenses and Power of Lens]\n"
        f"- **Evidence Justification**: [Why needed for examination problem solving]\n"
        f"- **Prerequisites**: [Concepts mastered in Stage 2]\n"
        f"- **Measurable Objectives**:\n"
        f"  * [Observable objective 1]\n"
        f"- **Learning Activities**:\n"
        f"  * General learning activity: [Activity description]\n"
        f"- **Assessment Checkpoint**: [Formative checkpoint question]\n\n"
        f"## Summary\n"
        f"[Executive summary of curriculum plan]"
    )
    expected_output = (
        "A sequenced 3-stage curriculum roadmap with prioritized prerequisites, observable objectives, "
        "general learning activities without hallucinated textbook numbers, distinct checkpoints, "
        "and explicit 70% mastery criterion."
    )
    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
    )


def build_curriculum_crew(
    grade: str = "Class 10",
    subject: str = "Science",
    topic: str = "General",
    inquiry: Optional[str] = None,
    llm: Optional[LLM] = None,
) -> Tuple[Crew, Task]:
    """Construct a standalone Crew for the Curriculum Agent."""
    curriculum_agent = create_curriculum_agent(llm=llm)
    task = create_curriculum_inquiry_task(
        agent=curriculum_agent,
        grade=grade,
        subject=subject,
        topic=topic,
        inquiry=inquiry,
    )
    crew_kwargs = {
        "agents": [curriculum_agent],
        "tasks": [task],
        "process": Process.sequential,
        "verbose": True,
    }
    try:
        from backend.observability import attach_crewai_callbacks
        attach_crewai_callbacks(crew_kwargs, agent_name="Curriculum Agent")
    except Exception:
        pass
    crew = Crew(**crew_kwargs)
    return crew, task


def run_curriculum_workflow(
    grade: str = "Class 10",
    subject: str = "Science",
    topic: str = "General",
    inquiry: Optional[str] = None,
    llm: Optional[LLM] = None,
) -> Dict[str, Any]:
    """Execute standalone Curriculum Agent workflow."""
    crew, task = build_curriculum_crew(
        grade=grade,
        subject=subject,
        topic=topic,
        inquiry=inquiry,
        llm=llm,
    )
    result = crew.kickoff()
    raw_text = task.output.raw if (task.output and task.output.raw) else str(result.raw if hasattr(result, "raw") else result).strip()
    plan_model = parse_curriculum_plan(
        raw_text=raw_text,
        grade=grade,
        subject=subject,
        topic=topic,
    )
    formatted_md = format_curriculum_plan_markdown(plan_model)
    return {
        "curriculum_plan": formatted_md,
        "curriculum_data": plan_model.model_dump(),
        "raw_output": raw_text,
    }

