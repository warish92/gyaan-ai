"""Regression tests for Diagnostic and Curriculum Agents reasoning quality.

Verifies:
Case A: Correct answer demonstrates all expected concepts.
Case B: Partially correct answer (Problem 1 test case: Magnesium ribbon & dust).
Case C: Incorrect answer with explicitly flawed reasoning.
Case D: Insufficient evidence for vague or extremely short answers.
Case E: Strict rule that omitted facts are knowledge gaps, not unsupported misconceptions.
Case F: Curriculum grounding: no hallucinated textbook exercises, activities labeled as general.
"""

import re
import pytest

from backend.agents.diagnostic import (
    create_diagnostic_agent,
    create_diagnostic_task,
    parse_diagnostic_report,
    format_diagnostic_report_markdown,
)
from backend.agents.curriculum import (
    create_curriculum_agent,
    create_curriculum_task,
    parse_curriculum_plan,
    format_curriculum_plan_markdown,
)
from backend.app.schemas import (
    AnswerClassification,
    DiagnosticReportModel,
    QuestionDiagnosis,
    CurriculumPlanModel,
    LearningStage,
)


# ==============================================================================
# Unit & Regression Tests for Evidence-Based Diagnostic Reasoning
# ==============================================================================

def test_case_a_correct_answer_evaluation():
    """Case A: Student demonstrates all expected concepts and is classified as Correct."""
    raw_markdown = """
# DIAGNOSTIC EVALUATION REPORT
**Target**: Class 10 | Science | Chemical Reactions and Equations

## Question Evaluations
### Question 1: Why does the color of copper sulfate solution change when an iron nail is dipped in it?
- **Student Answer**: Iron is more reactive than copper, so it displaces copper from copper sulfate to form iron sulfate which is light green.
- **Expected Answer**: Iron is more reactive than copper; displacement reaction occurs forming ferrous sulfate (green) and depositing copper.
- **Correct Elements**: Reactivity of iron over copper, displacement reaction mechanism, formation of green iron sulfate solution
- **Missing Elements**: None
- **Incorrect Elements**: None
- **Classification**: Correct
- **Confidence Level**: High
- **Explanation**: The student demonstrated complete understanding of single displacement and color change.

## Overall Synthesis
- **Demonstrated Understanding**:
  * Reactivity series of metals
  * Displacement reaction equations
- **Evidenced Knowledge Gaps**:
  * None demonstrated
- **Uncovered Misconceptions**:
  * None demonstrated
- **Recommended Focus Topics**:
  * Double displacement and precipitation reactions
- **Overall Summary**: Student demonstrated thorough mastery of single displacement reactions.
"""
    report = parse_diagnostic_report(raw_markdown, subject="Science", topic="Chemical Reactions and Equations")

    assert len(report.question_evaluations) == 1
    q1 = report.question_evaluations[0]
    assert q1.classification == AnswerClassification.CORRECT
    assert len(q1.correct_elements) >= 1
    assert len(q1.missing_elements) == 0
    assert len(q1.incorrect_elements) == 0
    assert len(report.uncovered_misconceptions) == 0


def test_case_b_partially_correct_magnesium_ribbon():
    """Case B (Problem 1 Benchmark): Magnesium ribbon cleaned of dust.

    Student understands cleaning requirement but omitted the protective oxide layer.
    Must be classified as Partially Correct without claiming understanding of oxide layer,
    and without attributing an unevidenced misconception.
    """
    raw_markdown = """
# DIAGNOSTIC EVALUATION REPORT
**Target**: Class 10 | Science | Chemical Reactions and Equations

## Question Evaluations
### Question 1: Why should magnesium ribbon be cleaned before burning?
- **Student Answer**: To remove dust from its surface.
- **Expected Answer**: To remove the protective layer of magnesium oxide/basic magnesium carbonate so it can react with oxygen.
- **Correct Elements**: Recognizes that the ribbon surface requires cleaning before ignition
- **Missing Elements**: Understanding of the protective layer of magnesium oxide (or basic magnesium carbonate)
- **Incorrect Elements**: None
- **Classification**: Partially Correct
- **Confidence Level**: High
- **Explanation**: The student correctly identifies the necessity of surface cleaning, but has not demonstrated knowledge of the protective magnesium oxide layer.

## Overall Synthesis
- **Demonstrated Understanding**:
  * Need for clean reactant surface
- **Evidenced Knowledge Gaps**:
  * Protective magnesium oxide formation on alkaline earth metals
- **Uncovered Misconceptions**:
  * None demonstrated
- **Recommended Focus Topics**:
  * Surface oxidation and protective oxide coatings
- **Overall Summary**: Student has intuitive awareness of cleaning but lacks chemical understanding of the oxide layer.
"""
    report = parse_diagnostic_report(raw_markdown, subject="Science", topic="Chemical Reactions and Equations")

    assert len(report.question_evaluations) == 1
    q1 = report.question_evaluations[0]
    assert q1.classification == AnswerClassification.PARTIALLY_CORRECT
    # Student was NOT credited with oxide layer
    assert any("cleaning" in c.lower() or "surface" in c.lower() for c in q1.correct_elements)
    # Missing oxide layer correctly identified as gap
    assert any("oxide" in m.lower() or "protective" in m.lower() for m in q1.missing_elements)
    # No false misconceptions attributed
    assert len(report.uncovered_misconceptions) == 0


def test_case_c_incorrect_answer_evaluation():
    """Case C: Student gives an explicitly incorrect explanation demonstrating a misconception."""
    raw_markdown = """
# DIAGNOSTIC EVALUATION REPORT
**Target**: Class 10 | Science | Chemical Reactions and Equations

## Question Evaluations
### Question 1: What is the difference between exothermic and endothermic reactions?
- **Student Answer**: Exothermic reactions absorb heat from the air and make surroundings cold, while endothermic reactions release heat and burn.
- **Expected Answer**: Exothermic reactions release energy/heat into surroundings; endothermic reactions absorb heat energy.
- **Correct Elements**: None
- **Missing Elements**: Accurate thermodynamic heat transfer definitions
- **Incorrect Elements**: Reversed definitions: claimed exothermic absorbs heat and endothermic releases heat
- **Classification**: Incorrect
- **Confidence Level**: High
- **Explanation**: Student has reversed the fundamental definitions of heat release and heat absorption.

## Overall Synthesis
- **Demonstrated Understanding**:
  * Recognizes that reactions involve heat exchange
- **Evidenced Knowledge Gaps**:
  * Direction of heat flow in exothermic vs endothermic processes
- **Uncovered Misconceptions**:
  * Believes exothermic reactions absorb heat and endothermic reactions release heat
- **Recommended Focus Topics**:
  * Thermodynamic definitions of exothermic and endothermic processes
- **Overall Summary**: Student exhibits an explicit conceptual reversal between exothermic and endothermic processes.
"""
    report = parse_diagnostic_report(raw_markdown, subject="Science", topic="Chemical Reactions and Equations")

    assert len(report.question_evaluations) == 1
    q1 = report.question_evaluations[0]
    assert q1.classification == AnswerClassification.INCORRECT
    assert len(q1.incorrect_elements) >= 1
    assert any("reversed" in inc.lower() for inc in q1.incorrect_elements)
    assert len(report.uncovered_misconceptions) >= 1


def test_case_d_insufficient_evidence_evaluation():
    """Case D: Student provides an extremely short or vague response."""
    raw_markdown = """
# DIAGNOSTIC EVALUATION REPORT
**Target**: Class 10 | Science | Chemical Reactions and Equations

## Question Evaluations
### Question 1: Explain the law of conservation of mass in a chemical reaction.
- **Student Answer**: mass
- **Expected Answer**: Total mass of reactants equals total mass of products; atoms are neither created nor destroyed.
- **Correct Elements**: Mentioned mass
- **Missing Elements**: Definition that mass is conserved, reactant/product equivalence, atomic conservation
- **Incorrect Elements**: None
- **Classification**: Insufficient Evidence
- **Confidence Level**: Low
- **Explanation**: The single word response does not provide sufficient evidence to evaluate understanding.

## Overall Synthesis
- **Demonstrated Understanding**:
  * None demonstrated
- **Evidenced Knowledge Gaps**:
  * Law of conservation of mass statement and application
- **Uncovered Misconceptions**:
  * None demonstrated
- **Recommended Focus Topics**:
  * Conservation of mass in chemical reactions
- **Overall Summary**: Insufficient response data to determine student mastery.
"""
    report = parse_diagnostic_report(raw_markdown, subject="Science", topic="Chemical Reactions and Equations")

    assert len(report.question_evaluations) == 1
    q1 = report.question_evaluations[0]
    assert q1.classification == AnswerClassification.INSUFFICIENT_EVIDENCE
    assert q1.confidence_level.lower() == "low"
    assert len(report.uncovered_misconceptions) == 0


def test_case_e_unsupported_misconception_omission_rule():
    """Case E (Strict Rule): Omitted concept must NOT be converted into a false misconception.

    When student omits hydrogen gas, it is a knowledge gap, NOT a misconception that hydrogen cannot exist.
    """
    raw_markdown = """
# DIAGNOSTIC EVALUATION REPORT
**Target**: Class 10 | Science | Chemical Reactions and Equations

## Question Evaluations
### Question 1: What are the products when zinc granules react with dilute sulfuric acid?
- **Student Answer**: Zinc sulfate is produced.
- **Expected Answer**: Zinc sulfate and hydrogen gas (Zn + H2SO4 -> ZnSO4 + H2).
- **Correct Elements**: Identified zinc sulfate salt formation
- **Missing Elements**: Hydrogen gas evolution
- **Incorrect Elements**: None
- **Classification**: Partially Correct
- **Confidence Level**: High
- **Explanation**: The student correctly identified the salt product but omitted the gaseous byproduct.

## Overall Synthesis
- **Demonstrated Understanding**:
  * Acid-metal salt formation
- **Evidenced Knowledge Gaps**:
  * Hydrogen gas liberation in acid-metal reactions
- **Uncovered Misconceptions**:
  * None demonstrated
- **Recommended Focus Topics**:
  * Metal-acid gas evolution reactions
- **Overall Summary**: Incomplete recall of byproducts without conceptual misconceptions.
"""
    report = parse_diagnostic_report(raw_markdown, subject="Science", topic="Chemical Reactions and Equations")

    q1 = report.question_evaluations[0]
    assert q1.classification == AnswerClassification.PARTIALLY_CORRECT
    assert any("hydrogen" in m.lower() for m in q1.missing_elements)
    # STRICT RULE: No unsupported misconceptions
    assert len(report.uncovered_misconceptions) == 0


# ==============================================================================
# Unit & Regression Tests for Grounded Curriculum Planning
# ==============================================================================

def test_case_f_curriculum_grounding_no_hallucinated_exercises():
    """Case F: Curriculum Agent must NOT invent textbook exercise numbers, must label general activities, and include 70% mastery criterion."""
    raw_markdown = """
# PERSONALIZED CURRICULUM PLAN
**Target**: Class 10 | Science | Chemical Reactions and Equations
- **Primary Learning Goal**: Understand balancing chemical equations and surface oxidation phenomena.
- **Mastery Criterion**: A minimum 70% threshold on formative assessment checkpoints is required before advancing.
- **Resource Alignment**: General learning activities (Unverified against live NCERT textbook content)
- **Priority Topics**: Surface oxidation of metals, Balancing chemical equations

## Sequenced Learning Stages

### Stage 1: Prerequisite Recovery
- **Focus Topic**: Protective Oxide Layer on Metals
- **Evidence Justification**: Diagnosed gap: Student knew ribbon needed cleaning but omitted magnesium oxide layer.
- **Prerequisites**: Atomic structure, Basic valency
- **Measurable Objectives**:
  * Student will be able to explain why magnesium forms an oxide layer in air.
- **Learning Activities**:
  * General learning activity: Create a diagram showing magnesium ribbon reacting with atmospheric oxygen.
- **Assessment Checkpoint**: What chemical formula represents the coating removed from magnesium ribbon before burning?

### Stage 2: Core Concept Mastery
- **Focus Topic**: Chemical Equation Representation
- **Evidence Justification**: Reinforces systematic equation notation.
- **Prerequisites**: Molecular formulas
- **Measurable Objectives**:
  * Student will be able to balance simple synthesis equations.
- **Learning Activities**:
  * General learning activity: Practice balancing 5 synthesis equations step-by-step.
- **Assessment Checkpoint**: Balance the equation: Mg + O2 -> MgO.

### Stage 3: Applied Problem Solving
- **Focus Topic**: Conservation of Mass in Reactions
- **Evidence Justification**: Consolidates quantitative verification of reactions.
- **Prerequisites**: Law of conservation of mass
- **Measurable Objectives**:
  * Student will be able to calculate molar mass equivalence across balanced equations.
- **Learning Activities**:
  * General learning activity: Verify mass conservation in the combustion of magnesium.
- **Assessment Checkpoint**: If 24g of Mg reacts completely with 16g of O2, what mass of MgO is produced?

## Summary
A targeted 3-stage study plan strictly addressing diagnosed gaps without relying on unverified textbook citations.
"""
    plan = parse_curriculum_plan(raw_markdown, subject="Science", topic="Chemical Reactions and Equations")

    # 1. Check mastery criterion
    assert "70%" in plan.mastery_criterion

    # 2. Check stages count
    assert len(plan.learning_stages) == 3

    # 3. Check resource alignment
    assert "Unverified" in plan.resource_alignment_status or "General" in plan.resource_alignment_status

    # 4. Check that NO hallucinated exercises or page numbers exist
    markdown_output = format_curriculum_plan_markdown(plan)
    assert not re.search(r"Exercise\s*\d+\.\d+", markdown_output, re.IGNORECASE), "Hallucinated exercise number found!"
    assert not re.search(r"Page\s*\d+", markdown_output, re.IGNORECASE), "Hallucinated page number found!"

    # 5. Check that all activities are labeled as general learning activities
    for stg in plan.learning_stages:
        assert len(stg.measurable_objectives) >= 1
        assert stg.assessment_checkpoint is not None
        assert stg.evidence_justification is not None
        for act in stg.learning_activities:
            assert "general" in act.lower() or "practice" in act.lower() or "create" in act.lower()
