import sys
sys.path.insert(0, ".")
import time
from backend.app.schemas import (
    DiagnosticAssessmentGenerateRequest,
    DiagnosticEvaluateRequest,
    AdaptiveProbeRequest,
    ChapterPracticeSetRequest,
)
from backend.services.diagnostic_service import (
    generate_diagnostic_assessment_sync,
    evaluate_diagnostic_assessment_sync,
    generate_adaptive_remedial_probes_sync,
)
from backend.services.practice_service import (
    get_chapter_practice_set_sync,
)
from backend.services.progress_analyzer import (
    get_comprehensive_progress_dashboard_sync,
)

print("="*60)
print("TESTING PHASE PRE-0 2.0 SERVICES")
print("="*60)

# 1. Test Progress Dashboard
print("\n[1] Testing get_comprehensive_progress_dashboard_sync...")
t0 = time.perf_counter()
dash = get_comprehensive_progress_dashboard_sync("stu_24b4854b69b4")
print(f"  Duration: {(time.perf_counter() - t0):.2f}s")
print(f"  Student: {dash['student_name']} (Accuracy: {dash['overall_accuracy']}%, Trend: {dash['performance_trend']})")
print(f"  Subject Progress Count: {len(dash['subject_progress'])}")
print(f"  Chapter Completion Count: {len(dash['chapter_completion'])}")
print(f"  Topic Mastery Count: {len(dash['topic_mastery'])}")
print(f"  Recent Attempts Count: {len(dash['recent_attempts'])}")

# 2. Test Empty Student Progress Dashboard
print("\n[2] Testing Empty Student Progress Dashboard...")
dash_empty = get_comprehensive_progress_dashboard_sync("stu_non_existent_999")
print(f"  Has sufficient history: {dash_empty['has_sufficient_history']}")
print(f"  Empty guide: {dash_empty['empty_state_guide']}")

# 3. Test Practice Set Retrieval / Generation (Basic tier)
print("\n[3] Testing Practice Set generation (Basic Tier)...")
t0 = time.perf_counter()
prac_req = ChapterPracticeSetRequest(
    subject="Science",
    chapter="Electricity",
    difficulty_tier="basic",
)
prac_res = get_chapter_practice_set_sync(prac_req)
print(f"  Duration: {(time.perf_counter() - t0):.2f}s")
print(f"  Practice Set ID: {prac_res.practice_set_id}")
print(f"  Tier: {prac_res.difficulty_tier}, Total Returned: {prac_res.total_questions}")
print(f"  Counts - Basic: {prac_res.basic_count}, Medium: {prac_res.medium_count}, Hard: {prac_res.hard_count}")
if prac_res.questions:
    print(f"  Sample Q1: {prac_res.questions[0].id} [{prac_res.questions[0].question_type}] {prac_res.questions[0].question[:60]}")

# 4. Test Diagnostic Assessment Generation (25 questions)
print("\n[4] Testing Diagnostic Assessment Generation (25 questions)...")
t0 = time.perf_counter()
diag_req = DiagnosticAssessmentGenerateRequest(
    subject="Science",
    chapter="Chemical Reactions and Equations",
    num_questions=25,
)
diag_res = generate_diagnostic_assessment_sync(diag_req)
print(f"  Duration: {(time.perf_counter() - t0):.2f}s")
print(f"  Assessment ID: {diag_res.assessment_id}")
print(f"  Total Questions: {diag_res.total_questions}")
print(f"  Target Topics: {diag_res.target_topics}")
if diag_res.questions:
    print(f"  Sample Q1: {diag_res.questions[0].id} [{diag_res.questions[0].question_type}] {diag_res.questions[0].question[:60]}")

# 5. Test Diagnostic Evaluation
print("\n[5] Testing Diagnostic Evaluation...")
t0 = time.perf_counter()
# Prepare mock student answers
answers = {}
for q in diag_res.questions[:5]:
    answers[q.id] = "Displacement reaction where iron displaces copper and turns solution greenish"
# Submit evaluation
eval_req = DiagnosticEvaluateRequest(
    assessment_id=diag_res.assessment_id,
    student_id="stu_24b4854b69b4",
    subject="Science",
    chapter="Chemical Reactions and Equations",
    answers=answers,
)
eval_res = evaluate_diagnostic_assessment_sync(eval_req)
print(f"  Duration: {(time.perf_counter() - t0):.2f}s")
print(f"  Score: {eval_res.total_score} / {eval_res.max_marks} ({eval_res.percentage}%)")
print(f"  Classification: {eval_res.overall_classification}")
print(f"  Topic Results Count: {len(eval_res.topic_results)}")
print(f"  Adaptive Probes Recommended: {eval_res.adaptive_probes_recommended}")

print("\nALL SERVICE TESTS COMPLETED!")
