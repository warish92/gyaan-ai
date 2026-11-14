"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Plus,
  Trash2,
  ArrowRight,
  BookOpen,
  Cpu,
  Clock,
  ShieldCheck,
  History,
  Compass,
  CheckSquare,
  HelpCircle,
  Lightbulb,
  Target,
  Layers,
  ChevronRight,
  RotateCcw,
} from "lucide-react";
import { PageHeader } from "../../components/ui/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { FormattedMessage } from "../../components/ui/FormattedMessage";
import { useBackendHealth } from "../../components/layout/AppShell";
import { useAuth } from "../../components/auth/AuthContext";
import { apiClient } from "../../lib/api";
import {
  AssessmentItem,
  LearningPlanResponse,
  SavedDiagnosticRecord,
  DiagnosticAssessmentGenerateResponse,
  FullDiagnosticReportResponse,
  DiagnosticQuestionItem,
  CurriculumSubjectResponse,
  CurriculumChapterSummary,
} from "../../types";

type DiagnosticMode = "chapter_assessment" | "custom_probe";

const DEFAULT_SCIENCE_CHAPTERS = [
  "Chemical Reactions and Equations",
  "Acids, Bases and Salts",
  "Electricity",
  "Life Processes",
  "Light - Reflection and Refraction",
];

const DEFAULT_MATH_CHAPTERS = [
  "Real Numbers",
  "Polynomials",
  "Pair of Linear Equations in Two Variables",
  "Quadratic Equations",
  "Arithmetic Progressions",
  "Coordinate Geometry",
  "Triangles",
  "Circles",
  "Introduction to Trigonometry",
  "Some Applications of Trigonometry",
  "Areas Related to Circles",
  "Surface Areas and Volumes",
  "Statistics",
  "Probability",
];

export default function DiagnosticPage() {
  const router = useRouter();
  const { health } = useBackendHealth();
  const { student, isAuthenticated, token } = useAuth();

  const [mode, setMode] = useState<DiagnosticMode>("chapter_assessment");

  // Curriculum dropdown selection
  const [subjects, setSubjects] = useState<CurriculumSubjectResponse[]>([]);
  const [selectedSubject, setSelectedSubject] = useState("Science");
  const [chapters, setChapters] = useState<string[]>(DEFAULT_SCIENCE_CHAPTERS);
  const [selectedChapter, setSelectedChapter] = useState("Chemical Reactions and Equations");

  // Mode A: 25-Question Chapter Diagnostic
  const [isGeneratingAssessment, setIsGeneratingAssessment] = useState(false);
  const [assessment, setAssessment] = useState<DiagnosticAssessmentGenerateResponse | null>(null);
  const [studentAnswers, setStudentAnswers] = useState<Record<string, string>>({});
  const [selectedSubtopicFilter, setSelectedSubtopicFilter] = useState<string>("all");

  const [isEvaluatingReport, setIsEvaluatingReport] = useState(false);
  const [diagnosticReport, setDiagnosticReport] = useState<FullDiagnosticReportResponse | null>(null);

  // Adaptive probes state
  const [isLoadingAdaptive, setIsLoadingAdaptive] = useState(false);
  const [adaptiveProbes, setAdaptiveProbes] = useState<DiagnosticQuestionItem[]>([]);

  // Mode B: Custom manual probe state (retained from legacy)
  const [customItems, setCustomItems] = useState<AssessmentItem[]>([
    {
      question: "What is observed when iron nails are placed in a copper sulphate solution? What type of reaction is this?",
      student_answer: "The blue colour turns greenish and reddish brown copper deposits on the iron nail. It is a displacement reaction.",
      expected_answer: "Iron displaces copper from copper sulphate solution: Fe + CuSO4 -> FeSO4 + Cu. Displacement reaction.",
    },
    {
      question: "Why should a magnesium ribbon be cleaned before burning in air?",
      student_answer: "To remove dust from its surface.",
      expected_answer: "To remove the protective layer of basic magnesium carbonate/oxide formed due to reaction with atmospheric gases.",
    },
    {
      question: "Explain what happens during the thermal decomposition of lead nitrate.",
      student_answer: "It breaks down when heated and gives brown fumes.",
      expected_answer: "2Pb(NO3)2 -> 2PbO + 4NO2 + O2. Emits brown nitrogen dioxide gas and leaves yellow lead oxide residue.",
    },
  ]);
  const [isEvaluatingCustom, setIsEvaluatingCustom] = useState(false);
  const [customPlanResult, setCustomPlanResult] = useState<LearningPlanResponse | null>(null);

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [previousDiagnostics, setPreviousDiagnostics] = useState<SavedDiagnosticRecord[]>([]);

  // Load curriculum subjects on mount
  useEffect(() => {
    apiClient
      .getCurriculumSubjects()
      .then((res) => {
        if (res && res.length > 0) {
          setSubjects(res);
        }
      })
      .catch(() => {});
  }, []);

  // Update chapters when subject changes
  useEffect(() => {
    const subjectObj = subjects.find(
      (s) =>
        s.name.toLowerCase() === selectedSubject.toLowerCase() ||
        (selectedSubject === "Mathematics" && (s.category === "Mathematics" || s.name.startsWith("Mathematics")))
    );
    if (subjectObj) {
      apiClient
        .getSubjectChapters(subjectObj.id)
        .then((chList) => {
          if (chList && chList.length > 0) {
            const titles = chList.map((c) => c.title);
            setChapters(titles);
            if (!titles.includes(selectedChapter)) {
              setSelectedChapter(titles[0]);
            }
          }
        })
        .catch(() => {
          if (selectedSubject === "Mathematics") {
            setChapters(DEFAULT_MATH_CHAPTERS);
            setSelectedChapter((prev) => (DEFAULT_MATH_CHAPTERS.includes(prev) ? prev : DEFAULT_MATH_CHAPTERS[0]));
          } else if (selectedSubject === "Science") {
            setChapters(DEFAULT_SCIENCE_CHAPTERS);
            setSelectedChapter((prev) => (DEFAULT_SCIENCE_CHAPTERS.includes(prev) ? prev : DEFAULT_SCIENCE_CHAPTERS[0]));
          }
        });
    } else if (selectedSubject === "Mathematics") {
      setChapters(DEFAULT_MATH_CHAPTERS);
      setSelectedChapter((prev) => (DEFAULT_MATH_CHAPTERS.includes(prev) ? prev : DEFAULT_MATH_CHAPTERS[0]));
    } else if (selectedSubject === "Science") {
      setChapters(DEFAULT_SCIENCE_CHAPTERS);
      setSelectedChapter((prev) => (DEFAULT_SCIENCE_CHAPTERS.includes(prev) ? prev : DEFAULT_SCIENCE_CHAPTERS[0]));
    }
  }, [selectedSubject, subjects]);

  // Load previous diagnostics for authenticated student
  useEffect(() => {
    if (isAuthenticated && token) {
      apiClient
        .getDashboard(token)
        .then((dash) => {
          if (dash.recent_diagnostics) {
            setPreviousDiagnostics(dash.recent_diagnostics);
          }
        })
        .catch(() => {});
    }
  }, [isAuthenticated, token]);

  // Mode A: Generate 25-Question Diagnostic Assessment
  const handleGenerateDiagnostic = async () => {
    setIsGeneratingAssessment(true);
    setErrorMsg(null);
    setDiagnosticReport(null);
    setAdaptiveProbes([]);
    setStudentAnswers({});

    try {
      const res = await apiClient.generateDiagnosticAssessment(
        {
          grade: student?.grade || "Class 10",
          subject: selectedSubject,
          chapter: selectedChapter,
          student_id: student?.id ?? null,
        },
        token
      );
      setAssessment(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate diagnostic assessment.";
      setErrorMsg(msg);
    } finally {
      setIsGeneratingAssessment(false);
    }
  };

  // Quick fill sample answers for testing / evaluation demo
  const handleQuickFillSampleAnswers = () => {
    if (!assessment) return;
    const sampleAnswers: Record<string, string> = {};
    assessment.questions.forEach((q, idx) => {
      if (q.question_type === "mcq" || q.question_type === "assertion_reason") {
        sampleAnswers[q.id] = q.options && q.options.length > 0 ? q.options[0] : "Option A";
      } else if (q.question_type === "true_false") {
        sampleAnswers[q.id] = "True";
      } else if (q.question_type === "fill_blank") {
        sampleAnswers[q.id] = q.expected_answer || "chemical energy";
      } else {
        sampleAnswers[q.id] = q.expected_answer || "Standard CBSE explanation demonstrating basic understanding.";
      }
    });
    setStudentAnswers(sampleAnswers);
  };

  // Handle single answer change
  const handleAnswerChange = (questionId: string, value: string) => {
    setStudentAnswers((prev) => ({
      ...prev,
      [questionId]: value,
    }));
  };

  // Submit 25-Question Diagnostic Assessment for evaluation
  const handleSubmitAssessmentEvaluation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assessment) return;

    const answeredCount = Object.keys(studentAnswers).filter((k) => studentAnswers[k]?.trim()).length;
    if (answeredCount === 0) {
      setErrorMsg("Please provide answers to at least one question before requesting diagnostic evaluation.");
      return;
    }

    setIsEvaluatingReport(true);
    setErrorMsg(null);

    try {
      const report = await apiClient.evaluateDiagnosticAssessment(
        {
          assessment_id: assessment.assessment_id,
          student_id: student?.id ?? assessment.student_id ?? null,
          subject: assessment.subject,
          chapter: assessment.chapter,
          answers: studentAnswers,
        },
        token
      );
      setDiagnosticReport(report);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to evaluate diagnostic assessment.";
      setErrorMsg(msg);
    } finally {
      setIsEvaluatingReport(false);
    }
  };

  // Generate Adaptive Follow-Up Probes
  const handleGenerateAdaptiveProbes = async (weakTopic: string) => {
    setIsLoadingAdaptive(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.generateAdaptiveProbes(
        {
          student_id: student?.id ?? null,
          subject: selectedSubject,
          chapter: selectedChapter,
          weak_topic: weakTopic,
          num_probes: 3,
        },
        token
      );
      setAdaptiveProbes(res.questions || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate adaptive remedial probes.";
      setErrorMsg(msg);
    } finally {
      setIsLoadingAdaptive(false);
    }
  };

  // Mode B: Custom manual probe submit
  const handleCustomSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    for (let i = 0; i < customItems.length; i++) {
      const it = customItems[i];
      if (!it.question.trim() || it.question.trim().length < 3) {
        setErrorMsg(`Item ${i + 1}: Please enter a valid test question.`);
        return;
      }
      if (!it.student_answer.trim()) {
        setErrorMsg(`Item ${i + 1}: Please provide a student response to evaluate.`);
        return;
      }
    }

    setIsEvaluatingCustom(true);
    setCustomPlanResult(null);

    try {
      const response = await apiClient.generateLearningPlan(
        {
          grade: student?.grade || "Class 10",
          subject: selectedSubject,
          topic: selectedChapter,
          display_name: student?.display_name || "Student",
          student_id: student?.id,
          assessment_items: customItems,
        },
        token
      );
      setCustomPlanResult(response);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Diagnostic evaluation failed.";
      setErrorMsg(msg);
    } finally {
      setIsEvaluatingCustom(false);
    }
  };

  const answeredCount = Object.keys(studentAnswers).filter((k) => studentAnswers[k]?.trim()).length;
  const filteredQuestions = assessment?.questions
    ? selectedSubtopicFilter === "all"
      ? assessment.questions
      : assessment.questions.filter((q) => q.topic === selectedSubtopicFilter)
    : [];

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <PageHeader
        title="Knowledge Gap Diagnostic Workspace"
        description="Comprehensive topic-wise diagnostic assessments evaluated by the CrewAI Diagnostic Agent to uncover demonstrated understanding, exact knowledge gaps, and specific misconceptions."
        breadcrumbs={[{ label: "Assessment & Resources", href: "/" }, { label: "Diagnostic" }]}
        icon={<Activity className="w-7 h-7 text-[#0F9F9A]" />}
        badge={
          <Badge variant="teal" size="md">
            Diagnostic Agent &bull; 25-Question Chapter Assessment Live
          </Badge>
        }
      />

      {/* Mode Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
        <button
          type="button"
          onClick={() => {
            setMode("chapter_assessment");
            setErrorMsg(null);
          }}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            mode === "chapter_assessment"
              ? "bg-teal-50 text-teal-800 border border-teal-200 shadow-xs"
              : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
          }`}
        >
          <Target className="w-3.5 h-3.5 text-[#0F9F9A]" />
          Comprehensive Chapter Diagnostic (25 Probes)
        </button>
        <button
          type="button"
          onClick={() => {
            setMode("custom_probe");
            setErrorMsg(null);
          }}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            mode === "custom_probe"
              ? "bg-teal-50 text-teal-800 border border-teal-200 shadow-xs"
              : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
          }`}
        >
          <Sparkles className="w-3.5 h-3.5 text-[#0F9F9A]" />
          Custom / Targeted Probe (Manual Items)
        </button>
      </div>

      {/* Global Error Banner */}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800 flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
          <div className="leading-relaxed">{errorMsg}</div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODE A: 25-QUESTION COMPREHENSIVE CHAPTER DIAGNOSTIC                      */}
      {/* ========================================================================= */}
      {mode === "chapter_assessment" && (
        <div className="space-y-6">
          {/* Chapter Selector Card */}
          <Card className="p-6">
            <CardHeader className="p-0 pb-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <CardTitle className="text-base font-bold text-[#172033] flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-[#0F9F9A]" />
                  Select CBSE Class 10 Subject & Chapter
                </CardTitle>
                <CardDescription>
                  The Diagnostic Agent evaluates your mastery across all 5 subtopics (5 probes per topic = 25 questions).
                </CardDescription>
              </div>
              <Badge variant="teal" size="sm">
                CBSE Class 10 Curriculum Bank
              </Badge>
            </CardHeader>

            <CardContent className="p-0 pt-4 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-700">Subject:</label>
                  <select
                    value={selectedSubject}
                    onChange={(e) => {
                      const newSub = e.target.value;
                      setSelectedSubject(newSub);
                      if (newSub === "Mathematics") {
                        setChapters(DEFAULT_MATH_CHAPTERS);
                        setSelectedChapter(DEFAULT_MATH_CHAPTERS[0]);
                      } else if (newSub === "Science") {
                        setChapters(DEFAULT_SCIENCE_CHAPTERS);
                        setSelectedChapter(DEFAULT_SCIENCE_CHAPTERS[0]);
                      }
                    }}
                    disabled={isGeneratingAssessment || isEvaluatingReport}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 bg-white font-medium focus:outline-none focus:border-teal-500"
                  >
                    <option value="Science">Science (Physics, Chemistry, Biology)</option>
                    <option value="Mathematics">Mathematics</option>
                    <option value="Social Science">Social Science</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-700">Chapter:</label>
                  <select
                    value={selectedChapter}
                    onChange={(e) => setSelectedChapter(e.target.value)}
                    disabled={isGeneratingAssessment || isEvaluatingReport}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 bg-white font-medium focus:outline-none focus:border-teal-500"
                  >
                    {chapters.map((ch, idx) => (
                      <option key={idx} value={ch}>
                        {ch}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Action Button */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-[#0F9F9A]" />
                  25 Diagnostic Probes &bull; MCQs, True/False, Fill in Blanks, Conceptual & Numerical
                </div>

                <Button
                  type="button"
                  variant="primary"
                  size="md"
                  onClick={handleGenerateDiagnostic}
                  isLoading={isGeneratingAssessment}
                  className="bg-[#0F9F9A] hover:bg-[#0B7A76]"
                  leftIcon={<Target className="w-4 h-4" />}
                >
                  {isGeneratingAssessment
                    ? "Diagnostic Agent Synthesizing 25 Probes..."
                    : "Generate 25-Question Diagnostic Assessment"}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Generating Indicator */}
          {isGeneratingAssessment && (
            <Card className="p-6 bg-teal-50/40 border-teal-200">
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 border-2 border-[#0F9F9A] border-t-transparent rounded-full animate-spin shrink-0" />
                <div>
                  <h4 className="text-sm font-bold text-[#0F9F9A]">
                    Diagnostic Agent Synthesizing Assessment Probes...
                  </h4>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Querying NCERT Class 10 curriculum database for <strong>{selectedChapter}</strong> and structuring 5 diagnostic probes per subtopic across diverse cognitive formats.
                  </p>
                </div>
              </div>
            </Card>
          )}

          {/* Assessment Question Presentation */}
          {assessment && !diagnosticReport && (
            <form onSubmit={handleSubmitAssessmentEvaluation} className="space-y-6">
              {/* Assessment Status Bar */}
              <div className="p-4 rounded-xl border bg-white shadow-xs flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <Badge variant="teal" size="md">
                      {assessment.chapter}
                    </Badge>
                    <span className="text-xs font-bold text-slate-700">
                      {answeredCount} / {assessment.total_questions} Answered
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Subject: {assessment.subject} &bull; Total Questions: {assessment.total_questions} &bull; 5 Subtopics
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleQuickFillSampleAnswers}
                    leftIcon={<Sparkles className="w-3.5 h-3.5 text-[#0F9F9A]" />}
                  >
                    Fill Sample Answers
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    isLoading={isEvaluatingReport}
                    className="bg-[#0F9F9A] hover:bg-[#0B7A76]"
                    rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                  >
                    {isEvaluatingReport ? "Diagnostic Agent Evaluating..." : "Evaluate Diagnostic Report"}
                  </Button>
                </div>
              </div>

              {/* Subtopic Filter Bar */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
                <span className="font-semibold text-slate-400 mr-1 shrink-0">Filter Subtopic:</span>
                <button
                  type="button"
                  onClick={() => setSelectedSubtopicFilter("all")}
                  className={`px-3 py-1 rounded-full shrink-0 transition-all ${
                    selectedSubtopicFilter === "all"
                      ? "bg-[#0F9F9A] text-white font-bold"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  All Subtopics ({assessment.questions.length})
                </button>
                {(assessment.target_topics || []).map((sub, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setSelectedSubtopicFilter(sub)}
                    className={`px-3 py-1 rounded-full shrink-0 transition-all line-clamp-1 max-w-[220px] ${
                      selectedSubtopicFilter === sub
                        ? "bg-[#0F9F9A] text-white font-bold"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {sub}
                  </button>
                ))}
              </div>

              {/* Question Cards List */}
              <div className="space-y-4">
                {filteredQuestions.map((q, idx) => {
                  const globalIdx = assessment.questions.findIndex((item) => item.id === q.id);
                  const isAnswered = Boolean(studentAnswers[q.id]?.trim());

                  return (
                    <Card
                      key={q.id}
                      className={`p-5 transition-all ${
                        isAnswered ? "border-teal-200 bg-teal-50/10" : "border-slate-200 bg-white"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3 mb-2.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="w-6 h-6 rounded-full bg-[#0F9F9A] text-white flex items-center justify-center font-bold text-xs shrink-0">
                            {globalIdx + 1}
                          </span>
                          <span className="text-xs font-bold text-slate-900">{q.topic}</span>
                          <Badge variant="neutral" size="sm">
                            {q.question_type.replace("_", " ").toUpperCase()}
                          </Badge>
                          <Badge variant="teal" size="sm">
                            {q.marks} {q.marks === 1 ? "mark" : "marks"}
                          </Badge>
                        </div>
                        {isAnswered && (
                          <span className="text-[11px] text-teal-700 font-semibold flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" />
                            Answered
                          </span>
                        )}
                      </div>

                      {/* Question Text */}
                      <p className="text-xs sm:text-sm font-semibold text-slate-800 leading-relaxed mb-3">
                        {q.question}
                      </p>

                      {/* Options or Answer Input */}
                      {q.options && q.options.length > 0 ? (
                        <div className="space-y-2 pt-1">
                          {q.options.map((opt, optIdx) => {
                            const isSelected = studentAnswers[q.id] === opt;
                            return (
                              <button
                                key={optIdx}
                                type="button"
                                onClick={() => handleAnswerChange(q.id, opt)}
                                className={`w-full text-left p-2.5 rounded-lg border text-xs font-medium transition-all flex items-center gap-2.5 ${
                                  isSelected
                                    ? "border-[#0F9F9A] bg-teal-50/70 text-teal-950 font-bold shadow-xs"
                                    : "border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700"
                                }`}
                              >
                                <span
                                  className={`w-4 h-4 rounded-full border flex items-center justify-center text-[10px] shrink-0 ${
                                    isSelected
                                      ? "border-[#0F9F9A] bg-[#0F9F9A] text-white"
                                      : "border-slate-300 text-transparent"
                                  }`}
                                >
                                  &bull;
                                </span>
                                <span>{opt}</span>
                              </button>
                            );
                          })}
                        </div>
                      ) : q.question_type === "fill_blank" ? (
                        <div className="pt-1">
                          <input
                            type="text"
                            value={studentAnswers[q.id] || ""}
                            onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                            placeholder="Type your answer here..."
                            className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:border-teal-500 font-medium"
                          />
                        </div>
                      ) : (
                        <div className="pt-1">
                          <textarea
                            rows={3}
                            value={studentAnswers[q.id] || ""}
                            onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                            placeholder="Write your explanation or reasoning step-by-step..."
                            className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:border-teal-500 font-medium"
                          />
                        </div>
                      )}
                    </Card>
                  );
                })}
              </div>

              {/* Bottom Submit Action */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
                <div className="text-xs text-slate-600">
                  Ready for evaluation? The Diagnostic Agent will parse every answer for misconceptions vs knowledge gaps.
                </div>
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  isLoading={isEvaluatingReport}
                  className="bg-[#0F9F9A] hover:bg-[#0B7A76] w-full sm:w-auto"
                  leftIcon={<Activity className="w-4 h-4" />}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  {isEvaluatingReport
                    ? "Diagnostic Agent Evaluating..."
                    : `Submit ${answeredCount} Answers for Diagnostic Analysis`}
                </Button>
              </div>
            </form>
          )}

          {/* Evaluating State */}
          {isEvaluatingReport && (
            <Card className="p-6 bg-teal-50/50 border-teal-200">
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 border-2 border-[#0F9F9A] border-t-transparent rounded-full animate-spin shrink-0" />
                <div>
                  <h4 className="text-sm font-bold text-[#0F9F9A]">
                    Diagnostic Agent Running Multi-Topic Rubric Analysis...
                  </h4>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Distinguishing demonstrated understanding from fundamental misconceptions and isolated missing knowledge. Calculating mastery levels for all 5 subtopics.
                  </p>
                </div>
              </div>
            </Card>
          )}

          {/* Diagnostic Evaluation Report */}
          {diagnosticReport && (
            <div className="space-y-6">
              <Card className="p-6 border-teal-200 shadow-sm">
                <CardHeader className="p-0 pb-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div>
                    <CardTitle className="text-lg font-bold text-[#172033] flex items-center gap-2">
                      <Activity className="w-5 h-5 text-[#0F9F9A]" />
                      Full Chapter Diagnostic Report: {diagnosticReport.chapter}
                    </CardTitle>
                    <CardDescription>
                      Synthesized by genuine CrewAI Diagnostic Agent via local Ollama
                    </CardDescription>
                  </div>

                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        diagnosticReport.percentage >= 80
                          ? "success"
                          : diagnosticReport.percentage >= 50
                          ? "warning"
                          : "neutral"
                      }
                      size="md"
                    >
                      Score: {diagnosticReport.total_score} / {diagnosticReport.max_marks} ({diagnosticReport.percentage}%)
                    </Badge>
                    <Badge variant="teal" size="sm">
                      <Clock className="w-3 h-3 mr-1" />
                      {(diagnosticReport.duration_ms / 1000).toFixed(2)}s
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="p-0 pt-5 space-y-6">
                  {/* Executive Diagnostic Summary */}
                  <div className="p-4 rounded-xl bg-teal-50/50 border border-teal-100 space-y-1.5">
                    <span className="text-xs font-bold text-teal-900 uppercase tracking-wider block">
                      Diagnostic Agent Executive Summary:
                    </span>
                    <p className="text-xs text-slate-800 leading-relaxed font-medium">
                      {diagnosticReport.overall_summary}
                    </p>
                  </div>

                  {/* 5-Subtopic Mastery Grid */}
                  <div className="space-y-2">
                    <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                      Subtopic Mastery Breakdown (5 Subtopics):
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {diagnosticReport.topic_results.map((tr, idx) => (
                        <div
                          key={idx}
                          className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-slate-900 line-clamp-1">
                              {tr.topic}
                            </span>
                            <Badge
                              variant={
                                tr.mastery_status === "mastered"
                                  ? "teal"
                                  : tr.mastery_status === "in_progress"
                                  ? "primary"
                                  : "neutral"
                              }
                              size="sm"
                            >
                              {tr.mastery_status.replace("_", " ")}
                            </Badge>
                          </div>
                          <div className="flex items-baseline justify-between text-xs text-slate-500">
                            <span>Score: {tr.score}/{tr.max_marks}</span>
                            <span className="font-bold text-slate-700">{tr.percentage}%</span>
                          </div>
                          {tr.misconceptions.length > 0 && (
                            <div className="text-[10px] text-amber-700 bg-amber-50 p-1.5 rounded">
                              <strong>Misconception:</strong> {tr.misconceptions[0]}
                            </div>
                          )}
                          {tr.mastery_status !== "mastered" && (
                            <button
                              type="button"
                              onClick={() => handleGenerateAdaptiveProbes(tr.topic)}
                              className="text-[11px] text-[#0F9F9A] hover:underline font-semibold flex items-center gap-1 mt-1"
                            >
                              <Sparkles className="w-3 h-3" />
                              Generate Targeted Remedial Probes
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Misconceptions vs Knowledge Gaps Split */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Demonstrated Misconceptions */}
                    <div className="p-4 rounded-xl bg-amber-50/50 border border-amber-200 space-y-2">
                      <div className="flex items-center gap-2 text-xs font-bold text-amber-900">
                        <AlertCircle className="w-4 h-4 text-amber-600" />
                        Demonstrated Misconceptions ({diagnosticReport.uncovered_misconceptions.length})
                      </div>
                      <p className="text-[11px] text-amber-800">
                        Flawed mental models where incorrect concepts were actively asserted:
                      </p>
                      {diagnosticReport.uncovered_misconceptions.length === 0 ? (
                        <p className="text-xs text-slate-500 italic">No critical misconceptions detected.</p>
                      ) : (
                        <ul className="space-y-1.5 text-xs text-slate-800">
                          {diagnosticReport.uncovered_misconceptions.map((m, mIdx) => (
                            <li key={mIdx} className="flex items-start gap-1.5">
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0 mt-1.5" />
                              <span>{m}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>

                    {/* Identified Knowledge Gaps */}
                    <div className="p-4 rounded-xl bg-blue-50/50 border border-blue-200 space-y-2">
                      <div className="flex items-center gap-2 text-xs font-bold text-blue-900">
                        <Target className="w-4 h-4 text-blue-600" />
                        Identified Knowledge Gaps ({diagnosticReport.evidenced_knowledge_gaps.length})
                      </div>
                      <p className="text-[11px] text-blue-800">
                        Topics or principles omitted or partially remembered without deep misconception:
                      </p>
                      {diagnosticReport.evidenced_knowledge_gaps.length === 0 ? (
                        <p className="text-xs text-slate-500 italic">No missing knowledge gaps identified.</p>
                      ) : (
                        <ul className="space-y-1.5 text-xs text-slate-800">
                          {diagnosticReport.evidenced_knowledge_gaps.map((kg, kgIdx) => (
                            <li key={kgIdx} className="flex items-start gap-1.5">
                              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0 mt-1.5" />
                              <span>{kg}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>

                  {/* Adaptive Remedial Probes Display */}
                  {isLoadingAdaptive && (
                    <div className="p-4 rounded-xl bg-teal-50 border border-teal-200 flex items-center gap-3">
                      <div className="w-4 h-4 border-2 border-[#0F9F9A] border-t-transparent rounded-full animate-spin" />
                      <span className="text-xs text-teal-900 font-semibold">
                        Diagnostic Agent is synthesizing targeted remedial probe questions...
                      </span>
                    </div>
                  )}

                  {adaptiveProbes.length > 0 && (
                    <div className="p-5 rounded-xl border border-teal-200 bg-teal-50/30 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold text-teal-950 uppercase tracking-wider flex items-center gap-1.5">
                          <Sparkles className="w-4 h-4 text-[#0F9F9A]" />
                          Adaptive Remedial Probes Generated ({adaptiveProbes.length})
                        </h4>
                        <Badge variant="teal" size="sm">
                          Targeted Reinforcement
                        </Badge>
                      </div>
                      <div className="space-y-2.5">
                        {adaptiveProbes.map((ap, apIdx) => (
                          <div
                            key={apIdx}
                            className="p-3 rounded-lg border border-teal-100 bg-white text-xs space-y-1.5"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-800">
                                Probe #{apIdx + 1} &bull; {ap.topic}
                              </span>
                              <Badge variant="neutral" size="sm">
                                {ap.question_type.toUpperCase()}
                              </Badge>
                            </div>
                            <p className="text-slate-700">{ap.question}</p>
                            {ap.options && ap.options.length > 0 && (
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-1">
                                {ap.options.map((opt, oIdx) => (
                                  <div
                                    key={oIdx}
                                    className="p-1.5 rounded bg-slate-50 border border-slate-200 text-[11px] text-slate-700"
                                  >
                                    {opt}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Next Step Navigation Actions */}
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
                    <div className="text-xs text-slate-600 flex items-center gap-2">
                      <Compass className="w-4 h-4 text-[#0F9F9A]" />
                      Continue your personalized learning journey with specialist agents:
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setDiagnosticReport(null);
                          setAssessment(null);
                        }}
                        leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                      >
                        Retake Diagnostic
                      </Button>
                      <Link href="/learning-plans">
                        <Button variant="primary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                          View Learning Plan
                        </Button>
                      </Link>
                      <Link href={`/teach?subject=${encodeURIComponent(selectedSubject)}&topic=${encodeURIComponent(selectedChapter)}`}>
                        <Button
                          variant="secondary"
                          size="sm"
                          leftIcon={<BookOpen className="w-3.5 h-3.5 text-[#0F9F9A]" />}
                        >
                          Learn with Teacher Agent
                        </Button>
                      </Link>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODE B: CUSTOM / TARGETED MANUAL PROBE ITEMS (RETAINED)                  */}
      {/* ========================================================================= */}
      {mode === "custom_probe" && (
        <Card className="p-6">
          <form onSubmit={handleCustomSubmit} className="space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-slate-100">
              <div>
                <CardTitle className="text-base font-bold text-[#172033]">
                  Targeted Diagnostic Probes ({selectedChapter})
                </CardTitle>
                <CardDescription>
                  Enter custom questions and answers to evaluate specific concepts with the Diagnostic Agent.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">Subject:</span>
                <span className="text-xs font-bold text-[#0F9F9A]">{selectedSubject}</span>
              </div>
            </div>

            {/* Assessment Items List */}
            <div className="space-y-4">
              {customItems.map((item, index) => (
                <div
                  key={index}
                  className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-3 relative group"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#172033] flex items-center gap-1.5">
                      <span className="w-5 h-5 rounded-full bg-[#0F9F9A] text-white flex items-center justify-center text-[10px]">
                        {index + 1}
                      </span>
                      Probe Item #{index + 1}
                    </span>
                    {customItems.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setCustomItems(customItems.filter((_, i) => i !== index))}
                        disabled={isEvaluatingCustom}
                        className="text-slate-400 hover:text-red-600 p-1 rounded-md transition-colors"
                        title="Remove this item"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-600">Test Question:</label>
                    <input
                      type="text"
                      required
                      value={item.question}
                      onChange={(e) => {
                        const updated = [...customItems];
                        updated[index] = { ...updated[index], question: e.target.value };
                        setCustomItems(updated);
                      }}
                      disabled={isEvaluatingCustom}
                      placeholder="e.g. What happens when acids react with metals?"
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:border-teal-500 font-medium"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-600">Student Answer (to diagnose):</label>
                    <textarea
                      rows={2}
                      required
                      value={item.student_answer}
                      onChange={(e) => {
                        const updated = [...customItems];
                        updated[index] = { ...updated[index], student_answer: e.target.value };
                        setCustomItems(updated);
                      }}
                      disabled={isEvaluatingCustom}
                      placeholder="Enter the student's submitted response..."
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:border-teal-500 font-medium"
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Action Row */}
            <div className="flex items-center justify-between pt-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  if (customItems.length >= 8) {
                    alert("A maximum of 8 assessment probe items is recommended.");
                    return;
                  }
                  setCustomItems([...customItems, { question: "", student_answer: "", expected_answer: "" }]);
                }}
                disabled={isEvaluatingCustom}
                leftIcon={<Plus className="w-4 h-4" />}
              >
                Add Assessment Item
              </Button>

              <Button
                type="submit"
                variant="primary"
                size="md"
                isLoading={isEvaluatingCustom}
                className="bg-[#0F9F9A] hover:bg-[#0B7A76]"
                leftIcon={<Activity className="w-4 h-4" />}
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                {isEvaluatingCustom ? "Diagnostic Agent Running..." : "Execute Diagnostic Evaluation"}
              </Button>
            </div>
          </form>

          {/* Custom Result */}
          {customPlanResult && (
            <div className="mt-6 p-5 rounded-xl border border-teal-200 bg-teal-50/20 space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-teal-950 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-teal-600" />
                  Diagnostic Report Synthesized
                </h4>
                <Badge variant="teal" size="sm">
                  {(customPlanResult.duration_ms / 1000).toFixed(1)}s
                </Badge>
              </div>
              <div className="p-4 rounded-xl bg-white border border-slate-200 text-xs text-slate-800">
                <FormattedMessage content={customPlanResult.diagnostic_report} />
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Historical Diagnostics for Authenticated Students */}
      {isAuthenticated && previousDiagnostics.length > 0 && (
        <Card className="p-6">
          <CardHeader className="p-0 pb-3 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-sm font-bold flex items-center gap-2">
                <History className="w-4 h-4 text-[#0F9F9A]" />
                Recent Diagnostic Evaluations
              </CardTitle>
              <CardDescription className="text-xs">
                Historical records saved in SQLite database
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="p-0 pt-3">
            <div className="divide-y divide-slate-100">
              {previousDiagnostics.map((diag, idx) => (
                <div key={idx} className="py-2.5 flex items-center justify-between text-xs">
                  <div>
                    <span className="font-semibold text-slate-800">{diag.topic}</span>
                    <span className="text-slate-400 ml-2">({diag.subject})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-slate-400">
                      {new Date(diag.created_at).toLocaleDateString()}
                    </span>
                    <Badge variant="neutral" size="sm">
                      {Array.isArray(diag.assessment_input)
                        ? `${diag.assessment_input.length} items`
                        : "Diagnostic Record"}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
