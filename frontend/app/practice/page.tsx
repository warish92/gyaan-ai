"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  CheckSquare,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Clock,
  Cpu,
  ArrowRight,
  ShieldCheck,
  RotateCcw,
  BookOpen,
  GraduationCap,
  Award,
  History,
  FileText,
  Send,
  Layers,
  BarChart3,
  XCircle,
  Save,
  Filter,
  Check,
} from "lucide-react";
import { PageHeader } from "../../components/ui/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { FormattedMessage } from "../../components/ui/FormattedMessage";
import { EmptyState } from "../../components/ui/EmptyState";
import { useAuth } from "../../components/auth/AuthContext";
import { apiClient } from "../../lib/api";
import {
  QuizGenerationRequest,
  QuizGenerationResponse,
  StudentQuizQuestion,
  AssessmentSubmissionResponse,
  AssessmentHistoryItem,
  ChapterPracticeSetResponse,
  PracticeQuestionItem,
  CurriculumSubjectResponse,
} from "../../types";

type PracticeMode = "chapter_60" | "quick_quiz";
type DifficultyFilter = "all" | "basic" | "medium" | "hard";

const DEFAULT_CHAPTERS = [
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

function PracticeContent() {
  const searchParams = useSearchParams();
  const initialSubject = searchParams.get("subject") || "Science";
  const initialChapter = searchParams.get("chapter") || searchParams.get("topic") || "Electricity";

  const { student, isAuthenticated, token } = useAuth();

  const [activeTab, setActiveTab] = useState<"practice" | "history">("practice");
  const [mode, setMode] = useState<PracticeMode>("chapter_60");

  // Curriculum State
  const [subjects, setSubjects] = useState<CurriculumSubjectResponse[]>([]);
  const [selectedSubject, setSelectedSubject] = useState(initialSubject);
  const [chapters, setChapters] = useState<string[]>(DEFAULT_CHAPTERS);
  const [selectedChapter, setSelectedChapter] = useState(initialChapter);
  const [difficultyFilter, setDifficultyFilter] = useState<DifficultyFilter>("all");

  // 60-Question Chapter Practice Set State
  const [isGenerating60, setIsGenerating60] = useState(false);
  const [practiceSet, setPracticeSet] = useState<ChapterPracticeSetResponse | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [savedSessionStatus, setSavedSessionStatus] = useState<string | null>(null);
  const [isSavingSession, setIsSavingSession] = useState(false);

  // Evaluation State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [evaluationResult, setEvaluationResult] = useState<AssessmentSubmissionResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Quick Quiz State (legacy compatibility)
  const [numQuickQuestions, setNumQuickQuestions] = useState(5);
  const [isGeneratingQuick, setIsGeneratingQuick] = useState(false);
  const [quickQuiz, setQuickQuiz] = useState<QuizGenerationResponse | null>(null);

  // History State
  const [historyItems, setHistoryItems] = useState<AssessmentHistoryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Load curriculum subjects
  useEffect(() => {
    apiClient
      .getCurriculumSubjects()
      .then((res) => {
        if (res && res.length > 0) setSubjects(res);
      })
      .catch(() => {});
  }, []);

  // Update chapters when subject changes
  useEffect(() => {
    const subObj = subjects.find(
      (s) =>
        s.name.toLowerCase() === selectedSubject.toLowerCase() ||
        (selectedSubject === "Mathematics" && (s.category === "Mathematics" || s.name.startsWith("Mathematics")))
    );
    if (subObj) {
      apiClient
        .getSubjectChapters(subObj.id)
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
            setChapters(DEFAULT_CHAPTERS);
            setSelectedChapter((prev) => (DEFAULT_CHAPTERS.includes(prev) ? prev : DEFAULT_CHAPTERS[0]));
          }
        });
    } else if (selectedSubject === "Mathematics") {
      setChapters(DEFAULT_MATH_CHAPTERS);
      setSelectedChapter((prev) => (DEFAULT_MATH_CHAPTERS.includes(prev) ? prev : DEFAULT_MATH_CHAPTERS[0]));
    } else if (selectedSubject === "Science") {
      setChapters(DEFAULT_CHAPTERS);
      setSelectedChapter((prev) => (DEFAULT_CHAPTERS.includes(prev) ? prev : DEFAULT_CHAPTERS[0]));
    }
  }, [selectedSubject, subjects]);

  // Load history
  useEffect(() => {
    if (isAuthenticated && token && student?.id && activeTab === "history") {
      setIsLoadingHistory(true);
      apiClient
        .getAssessmentHistory(student.id, token)
        .then((res) => {
          if (res.attempts) setHistoryItems(res.attempts);
        })
        .catch(() => {})
        .finally(() => setIsLoadingHistory(false));
    }
  }, [isAuthenticated, token, student?.id, activeTab]);

  // Generate 60-Question Chapter Practice Set
  const handleGenerateChapterPracticeSet = async () => {
    setIsGenerating60(true);
    setErrorMessage(null);
    setEvaluationResult(null);
    setSavedSessionStatus(null);
    setAnswers({});

    try {
      const res = await apiClient.generateChapterPracticeSet(
        {
          student_id: student?.id ?? null,
          grade: student?.grade || "Class 10",
          subject: selectedSubject,
          chapter: selectedChapter,
          difficulty_tier: difficultyFilter,
        },
        token
      );
      setPracticeSet(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate chapter practice set.";
      setErrorMessage(msg);
    } finally {
      setIsGenerating60(false);
    }
  };

  // Quick Quiz Generator (retained)
  const handleGenerateQuickQuiz = async () => {
    setIsGeneratingQuick(true);
    setErrorMessage(null);
    setEvaluationResult(null);
    setAnswers({});

    try {
      const res = await apiClient.generateQuiz(
        {
          student_id: student?.id ?? null,
          grade: student?.grade || "Class 10",
          subject: selectedSubject,
          topic: selectedChapter,
          num_questions: numQuickQuestions,
          question_types: ["mcq", "short_answer"],
        },
        token
      );
      setQuickQuiz(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate quick quiz.";
      setErrorMessage(msg);
    } finally {
      setIsGeneratingQuick(false);
    }
  };

  // Answer handler
  const handleAnswerChange = (questionId: string, answer: string) => {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: answer,
    }));
  };

  // Quick fill sample answers
  const handleQuickFill = () => {
    const questions = practiceSet ? practiceSet.questions : quickQuiz ? quickQuiz.questions : [];
    const sample: Record<string, string> = {};
    questions.forEach((q) => {
      if (q.options && q.options.length > 0) {
        sample[q.id] = q.options[0];
      } else {
        sample[q.id] = (q as any).expected_answer || "Standard CBSE explanation.";
      }
    });
    setAnswers(sample);
  };

  // Save practice session to SQLite
  const handleSaveSession = async () => {
    if (!practiceSet) return;
    setIsSavingSession(true);
    setSavedSessionStatus(null);
    try {
      const sessionId = `sess_${practiceSet.practice_set_id}_${student?.id || "guest"}`;
      await apiClient.savePracticeSession(
        {
          session_id: sessionId,
          student_id: student?.id ?? null,
          practice_set_id: practiceSet.practice_set_id,
          chapter: practiceSet.chapter,
          answers,
          current_index: Object.keys(answers).length,
        },
        token
      );
      setSavedSessionStatus("Session successfully saved! You can resume anytime.");
      setTimeout(() => setSavedSessionStatus(null), 5000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save session.";
      setErrorMessage(msg);
    } finally {
      setIsSavingSession(false);
    }
  };

  // Submit answers for evaluation
  const handleSubmitAnswers = async (e: React.FormEvent) => {
    e.preventDefault();
    const quizId = practiceSet?.practice_set_id || quickQuiz?.quiz_id;
    if (!quizId) return;

    const answeredCount = Object.keys(answers).filter((k) => answers[k]?.trim()).length;
    if (answeredCount === 0) {
      setErrorMessage("Please answer at least one question before submitting.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await apiClient.submitAssessment(
        {
          quiz_id: quizId,
          student_id: student?.id ?? null,
          answers,
        },
        token
      );
      setEvaluationResult(response);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to evaluate assessment.";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const currentQuestions: PracticeQuestionItem[] = practiceSet
    ? difficultyFilter === "all"
      ? practiceSet.questions
      : practiceSet.questions.filter((q) => q.difficulty === difficultyFilter)
    : [];

  const answeredCount = Object.keys(answers).filter((k) => answers[k]?.trim()).length;

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <PageHeader
        title="Practice & Assessments"
        description="60-question comprehensive chapter practice sets across 3 difficulty tiers (30 Basic, 20 Medium, 10 Hard) with rubric evaluations and session save/resume."
        breadcrumbs={[{ label: "Assessment & Resources", href: "/" }, { label: "Practice & Assessments" }]}
        icon={<CheckSquare className="w-7 h-7 text-[#0F9F9A]" />}
        badge={
          <Badge variant="teal" size="md">
            Assessment Agent &bull; 60-Question Chapter Sets Live
          </Badge>
        }
      />

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("practice")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "practice"
              ? "bg-teal-50 text-teal-800 border border-teal-200 shadow-xs"
              : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
          }`}
        >
          <Sparkles className="w-3.5 h-3.5 text-[#0F9F9A]" />
          Practice Workspace
        </button>
        {isAuthenticated && (
          <button
            type="button"
            onClick={() => setActiveTab("history")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "history"
                ? "bg-teal-50 text-teal-800 border border-teal-200 shadow-xs"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
            }`}
          >
            <History className="w-3.5 h-3.5 text-[#0F9F9A]" />
            Past Attempts ({historyItems.length})
          </button>
        )}
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800 flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
          <div className="leading-relaxed">{errorMessage}</div>
        </div>
      )}

      {/* Save Status Notification */}
      {savedSessionStatus && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{savedSessionStatus}</span>
        </div>
      )}

      {/* TAB 1: PRACTICE WORKSPACE */}
      {activeTab === "practice" && (
        <div className="space-y-6">
          {/* Practice Set Mode Toggle */}
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-500">Practice Mode:</span>
            <button
              type="button"
              onClick={() => {
                setMode("chapter_60");
                setErrorMessage(null);
              }}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${
                mode === "chapter_60"
                  ? "bg-[#0F9F9A] text-white shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              Complete Chapter Bank (60 Questions)
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("quick_quiz");
                setErrorMessage(null);
              }}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${
                mode === "quick_quiz"
                  ? "bg-[#0F9F9A] text-white shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              Quick Focused Quiz (3–10 Questions)
            </button>
          </div>

          {/* Config Card */}
          <Card className="p-6">
            <div className="space-y-4">
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
                        setChapters(DEFAULT_CHAPTERS);
                        setSelectedChapter(DEFAULT_CHAPTERS[0]);
                      }
                    }}
                    disabled={isGenerating60 || isGeneratingQuick}
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
                    disabled={isGenerating60 || isGeneratingQuick}
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

              {/* Mode Specific Options */}
              {mode === "chapter_60" ? (
                <div className="space-y-2 pt-1 border-t border-slate-100">
                  <span className="text-xs font-bold text-slate-700 block">Difficulty Tier Target:</span>
                  <div className="flex flex-wrap items-center gap-2">
                    {[
                      { id: "all", label: "All Tiers (60 Questions)" },
                      { id: "basic", label: "Basic Tier (30 Questions)" },
                      { id: "medium", label: "Medium Tier (20 Questions)" },
                      { id: "hard", label: "Hard Tier (10 Questions)" },
                    ].map((tier) => (
                      <button
                        key={tier.id}
                        type="button"
                        onClick={() => setDifficultyFilter(tier.id as DifficultyFilter)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                          difficultyFilter === tier.id
                            ? "bg-teal-50 border border-teal-300 text-teal-900 font-bold"
                            : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
                        }`}
                      >
                        {tier.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="space-y-2 pt-1 border-t border-slate-100">
                  <span className="text-xs font-bold text-slate-700 block">Number of Questions:</span>
                  <div className="flex items-center gap-2">
                    {[3, 5, 8, 10].map((num) => (
                      <button
                        key={num}
                        type="button"
                        onClick={() => setNumQuickQuestions(num)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                          numQuickQuestions === num
                            ? "bg-teal-50 border border-teal-300 text-teal-900 font-bold"
                            : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
                        }`}
                      >
                        {num} Questions
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Trigger */}
              <div className="pt-2 flex flex-wrap items-center justify-between gap-3">
                <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-[#0F9F9A]" />
                  NCERT Class 10 Curriculum Bank &bull; Batched Generation &amp; Persistent SQLite Cache
                </div>

                <Button
                  type="button"
                  variant="primary"
                  size="md"
                  onClick={mode === "chapter_60" ? handleGenerateChapterPracticeSet : handleGenerateQuickQuiz}
                  isLoading={isGenerating60 || isGeneratingQuick}
                  className="bg-[#0F9F9A] hover:bg-[#0B7A76]"
                  leftIcon={<CheckSquare className="w-4 h-4" />}
                >
                  {isGenerating60
                    ? "Loading Chapter Practice Set..."
                    : isGeneratingQuick
                    ? "Synthesizing Practice Quiz..."
                    : mode === "chapter_60"
                    ? `Load ${difficultyFilter === "all" ? "60-Question" : difficultyFilter.toUpperCase()} Practice Set`
                    : `Generate ${numQuickQuestions}-Question Quiz`}
                </Button>
              </div>
            </div>
          </Card>

          {/* Loading Indicator */}
          {(isGenerating60 || isGeneratingQuick) && (
            <Card className="p-6 bg-teal-50/40 border-teal-200">
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 border-2 border-[#0F9F9A] border-t-transparent rounded-full animate-spin shrink-0" />
                <div>
                  <h4 className="text-sm font-bold text-[#0F9F9A]">
                    Assessment Agent Retrieving Chapter Question Bank...
                  </h4>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Querying verified NCERT practice items with rubrics for <strong>{selectedChapter}</strong>. Pre-cached chapters load instantly; new chapter sets are synthesized across 3 difficulty tiers and cached automatically.
                  </p>
                </div>
              </div>
            </Card>
          )}

          {/* 60-Question Chapter Presentation */}
          {practiceSet && !evaluationResult && (
            <form onSubmit={handleSubmitAnswers} className="space-y-6">
              {/* Practice Set Header Status Bar */}
              <div className="p-4 rounded-xl border bg-white shadow-xs flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <Badge variant="teal" size="md">
                      {practiceSet.chapter}
                    </Badge>
                    <span className="text-xs font-bold text-slate-700">
                      {answeredCount} / {currentQuestions.length} Answered
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Tier Counts &bull; Basic: {practiceSet.basic_count} | Medium: {practiceSet.medium_count} | Hard: {practiceSet.hard_count}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={handleSaveSession}
                    isLoading={isSavingSession}
                    leftIcon={<Save className="w-3.5 h-3.5" />}
                  >
                    Save Session
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleQuickFill}
                    leftIcon={<Sparkles className="w-3.5 h-3.5 text-[#0F9F9A]" />}
                  >
                    Fill Sample
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    isLoading={isSubmitting}
                    className="bg-[#0F9F9A] hover:bg-[#0B7A76]"
                    rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                  >
                    {isSubmitting ? "Evaluating..." : "Submit Answers"}
                  </Button>
                </div>
              </div>

              {/* Questions List */}
              <div className="space-y-4">
                {currentQuestions.map((q, idx) => {
                  const isAnswered = Boolean(answers[q.id]?.trim());
                  return (
                    <Card
                      key={q.id}
                      className={`p-5 transition-all ${
                        isAnswered ? "border-teal-200 bg-teal-50/10" : "border-slate-200 bg-white"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3 mb-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="w-6 h-6 rounded-full bg-[#0F9F9A] text-white flex items-center justify-center font-bold text-xs shrink-0">
                            {idx + 1}
                          </span>
                          <span className="text-xs font-bold text-slate-900">{q.topic}</span>
                          <Badge
                            variant={
                              q.difficulty === "basic"
                                ? "teal"
                                : q.difficulty === "medium"
                                ? "warning"
                                : "neutral"
                            }
                            size="sm"
                          >
                            {q.difficulty.toUpperCase()}
                          </Badge>
                          <Badge variant="neutral" size="sm">
                            {q.question_type.replace("_", " ").toUpperCase()}
                          </Badge>
                          <span className="text-xs text-slate-500 font-semibold">{q.marks} {q.marks === 1 ? "mark" : "marks"}</span>
                        </div>
                        {isAnswered && (
                          <span className="text-[11px] text-teal-700 font-semibold flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" />
                            Answered
                          </span>
                        )}
                      </div>

                      <p className="text-xs sm:text-sm font-semibold text-slate-800 leading-relaxed mb-3">
                        {q.question}
                      </p>

                      {q.options && q.options.length > 0 ? (
                        <div className="space-y-2 pt-1">
                          {q.options.map((opt, optIdx) => {
                            const isSelected = answers[q.id] === opt;
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
                      ) : (
                        <div className="pt-1">
                          <textarea
                            rows={3}
                            value={answers[q.id] || ""}
                            onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                            placeholder="Write your step-by-step solution, formula, or explanation..."
                            className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:border-teal-500 font-medium"
                          />
                        </div>
                      )}
                    </Card>
                  );
                })}
              </div>

              {/* Bottom Action */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleSaveSession}
                  isLoading={isSavingSession}
                  leftIcon={<Save className="w-3.5 h-3.5" />}
                >
                  Save Practice Session
                </Button>

                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  isLoading={isSubmitting}
                  className="bg-[#0F9F9A] hover:bg-[#0B7A76]"
                  leftIcon={<Award className="w-4 h-4" />}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  {isSubmitting ? "Evaluating..." : `Submit ${answeredCount} Answers for Evaluation`}
                </Button>
              </div>
            </form>
          )}

          {/* Quick Quiz Presentation */}
          {quickQuiz && !evaluationResult && !practiceSet && (
            <form onSubmit={handleSubmitAnswers} className="space-y-6">
              <div className="p-4 rounded-xl border bg-white shadow-xs flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-bold text-slate-900">{quickQuiz.topic}</h4>
                  <p className="text-xs text-slate-500">{quickQuiz.questions.length} questions</p>
                </div>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isSubmitting}
                  className="bg-[#0F9F9A] hover:bg-[#0B7A76]"
                >
                  {isSubmitting ? "Evaluating..." : "Submit Quiz"}
                </Button>
              </div>

              <div className="space-y-4">
                {quickQuiz.questions.map((q, idx) => (
                  <Card key={q.id} className="p-5">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="w-5 h-5 rounded-full bg-[#0F9F9A] text-white flex items-center justify-center font-bold text-xs">
                        {idx + 1}
                      </span>
                      <span className="text-xs font-bold text-slate-900">{(q as any).topic || quickQuiz?.topic || "Quiz"}</span>
                    </div>
                    <p className="text-xs sm:text-sm font-semibold text-slate-800 mb-3">{q.question}</p>
                    {q.options && q.options.length > 0 ? (
                      <div className="space-y-2">
                        {q.options.map((opt, oIdx) => (
                          <button
                            key={oIdx}
                            type="button"
                            onClick={() => handleAnswerChange(q.id, opt)}
                            className={`w-full text-left p-2.5 rounded-lg border text-xs font-medium ${
                              answers[q.id] === opt ? "border-[#0F9F9A] bg-teal-50" : "border-slate-200"
                            }`}
                          >
                            {opt}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <textarea
                        rows={2}
                        value={answers[q.id] || ""}
                        onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                        placeholder="Type answer..."
                        className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-200"
                      />
                    )}
                  </Card>
                ))}
              </div>
            </form>
          )}

          {/* Assessment Evaluation Output */}
          {evaluationResult && (
            <Card className="p-6 border-teal-200 shadow-sm space-y-6">
              <CardHeader className="p-0 pb-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <CardTitle className="text-lg font-bold text-[#172033] flex items-center gap-2">
                    <Award className="w-5 h-5 text-[#0F9F9A]" />
                    Assessment Evaluation Report
                  </CardTitle>
                  <CardDescription>
                    Graded with genuine rubrics by CrewAI Assessment Agent
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      evaluationResult.percentage >= 80
                        ? "success"
                        : evaluationResult.percentage >= 50
                        ? "warning"
                        : "neutral"
                    }
                    size="md"
                  >
                    Score: {evaluationResult.total_score} / {evaluationResult.max_marks} ({evaluationResult.percentage}%)
                  </Badge>
                  {evaluationResult.persisted && (
                    <Badge variant="teal" size="sm" dot>
                      Saved to Progress DB
                    </Badge>
                  )}
                </div>
              </CardHeader>

              <CardContent className="p-0 space-y-5">
                {/* Overall Feedback */}
                <div className="p-4 rounded-xl bg-teal-50/50 border border-teal-100">
                  <span className="text-xs font-bold text-teal-900 uppercase tracking-wider block mb-1">
                    Overall Evaluator Feedback:
                  </span>
                  <p className="text-xs text-slate-800 leading-relaxed font-medium">
                    {evaluationResult.overall_feedback}
                  </p>
                </div>

                {/* Per-Question Results */}
                <div className="space-y-3">
                  <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                    Itemized Question Evaluations:
                  </span>
                  {(evaluationResult.evaluations || []).map((qe, idx) => {
                    const isCorrect = qe.status === "correct";
                    const isPartial = qe.status === "partially_correct";
                    return (
                      <div
                        key={idx}
                        className={`p-4 rounded-xl border text-xs space-y-2 ${
                          isCorrect
                            ? "border-emerald-200 bg-emerald-50/20"
                            : isPartial
                            ? "border-amber-200 bg-amber-50/20"
                            : "border-rose-200 bg-rose-50/20"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-900">
                            Question #{idx + 1} {qe.revision_topic ? `• ${qe.revision_topic}` : ""}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-700">
                              {qe.score_awarded} / {qe.max_marks} marks
                            </span>
                            <Badge
                              variant={isCorrect ? "success" : isPartial ? "warning" : "neutral"}
                              size="sm"
                            >
                              {isCorrect ? "Correct" : isPartial ? "Partial" : "Incorrect"}
                            </Badge>
                          </div>
                        </div>

                        <div className="text-slate-600">
                          <strong>Student Response:</strong> {qe.student_answer || "(No answer provided)"}
                        </div>
                        <div className="text-slate-800 font-medium">
                          <strong>Rubric Feedback:</strong> {qe.feedback}
                        </div>
                        {qe.expected_answer && (
                          <div className="text-slate-500 text-[11px]">
                            <strong>Expected NCERT Answer:</strong> {qe.expected_answer}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Action Buttons */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setEvaluationResult(null);
                      setPracticeSet(null);
                      setQuickQuiz(null);
                    }}
                    leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                  >
                    Start New Practice Set
                  </Button>

                  <div className="flex items-center gap-2">
                    <Link href="/progress">
                      <Button variant="secondary" size="sm" leftIcon={<BarChart3 className="w-3.5 h-3.5 text-[#0F9F9A]" />}>
                        View Progress Analytics
                      </Button>
                    </Link>
                    <Link href={`/teach?subject=${encodeURIComponent(selectedSubject)}&topic=${encodeURIComponent(selectedChapter)}`}>
                      <Button variant="primary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                        Learn with Teacher Agent
                      </Button>
                    </Link>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* TAB 2: PAST ATTEMPTS HISTORY */}
      {activeTab === "history" && (
        <Card className="p-6">
          <CardHeader className="p-0 pb-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-bold text-slate-900">Assessment History</CardTitle>
              <CardDescription>Verified attempts recorded in SQLite database</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="p-0 pt-4">
            {isLoadingHistory ? (
              <div className="py-8 text-center text-xs text-slate-500">Loading assessment history...</div>
            ) : historyItems.length === 0 ? (
              <EmptyState
                icon={CheckSquare}
                title="No Assessment Attempts Yet"
                description="Complete a practice set or diagnostic probe above to build your verified learning record."
                action={
                  <Button variant="primary" size="sm" onClick={() => setActiveTab("practice")}>
                    Start Practice Set
                  </Button>
                }
              />
            ) : (
              <div className="divide-y divide-slate-100">
                {historyItems.map((item, idx) => (
                  <div key={idx} className="py-3 flex items-center justify-between text-xs">
                    <div>
                      <span className="font-bold text-slate-900">{item.topic || "Practice Set"}</span>
                      <span className="text-slate-400 ml-2">({item.subject || "Science"})</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[11px] text-slate-400">
                        {item.created_at ? new Date(item.created_at).toLocaleDateString() : "Recent"}
                      </span>
                      <Badge
                        variant={(item.percentage || 0) >= 80 ? "teal" : (item.percentage || 0) >= 50 ? "neutral" : "primary"}
                        size="sm"
                      >
                        {item.score}/{item.max_marks} ({item.percentage ?? 0}%)
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function PracticePage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs text-slate-400">Loading Practice Workspace...</div>}>
      <PracticeContent />
    </Suspense>
  );
}
