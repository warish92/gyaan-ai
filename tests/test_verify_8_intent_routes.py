"""Test intent routing for all 8 canonical agent inquiry prompts."""

import sys
from pathlib import Path

# Add project root to path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.agents.orchestrator import classify_educational_intent

TEST_QUERIES = [
    ("Teacher", "Explain displacement reaction", "teacher_answer", "Teacher Agent"),
    ("Diagnostic", "Analyse submitted answers and identify knowledge gaps", "diagnostic_evaluation", "Diagnostic Agent"),
    ("Curriculum", "Identify learning objectives for Light and Optics", "curriculum_inquiry", "Curriculum Agent"),
    ("Resource", "Recommend resources for electricity", "resource_search", "Resource Agent"),
    ("Assessment", "Generate and evaluate an Ohm's Law quiz", "quiz_generation", "Assessment Agent"),
    ("Progress", "Analyse existing student learning progress", "progress_analysis", "Progress Agent"),
    ("Mentor", "Create a revision timetable", "study_guidance", "Mentor Agent"),
    ("Orchestrator", "Coordinate a multi-agent request about what to study next", "study_next_coordination", "Progress Agent"),
    ("Orchestrator Alt", "Based on my performance, what should I study next?", "progress_and_mentoring", "Progress Agent"),
]

def main():
    print("=" * 80)
    print("VERIFYING CLASSIFICATION FOR ALL 8 CANONICAL TARGET QUERIES")
    print("=" * 80)

    all_passed = True
    for role, q, expected_wf, expected_agent in TEST_QUERIES:
        wf, ags, reason, clar, _ = classify_educational_intent(q)
        wf_match = (wf == expected_wf)
        agent_match = any(expected_agent in a for a in ags)
        passed = wf_match and agent_match and not clar

        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False

        print(f"[{status}] Role: {role:15} | WF: {wf:24} | Agents: {ags}")
        print(f"       Query: \"{q}\"")
        if not passed:
            print(f"       Expected WF: {expected_wf}, Expected Agent: {expected_agent}")

    print("=" * 80)
    print(f"Overall Result: {'ALL 9 PASSED' if all_passed else 'SOME FAILED'}")
    print("=" * 80)
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
