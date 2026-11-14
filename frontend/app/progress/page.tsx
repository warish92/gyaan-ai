"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  TrendingUp,
  BarChart2,
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
  Layers,
  Sparkles,
  Target,
  AlertTriangle,
  HeartHandshake,
  LogIn,
  CheckSquare,
  Activity,
  Compass,
} from "lucide-react";
import { PageHeader } from "../../components/ui/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { FormattedMessage } from "../../components/ui/FormattedMessage";
import { EmptyState } from "../../components/ui/EmptyState";
import { useAuth } from "../../components/auth/AuthContext";
import { apiClient } from "../../lib/api";
import { ComprehensiveProgressDashboardResponse } from "../../types";

export default function ProgressPage() {
  const { student, isAuthenticated, token } = useAuth();

  const [isLoading, setIsLoading] = useState(false);
  const [dashboard, setDashboard] = useState<ComprehensiveProgressDashboardResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchProgressDashboard = async () => {
    if (!isAuthenticated || !token) return;

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const data = await apiClient.getComprehensiveProgressDashboard(token);
      setDashboard(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load progress dashboard.";
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated && token) {
      fetchProgressDashboard();
    }
  }, [isAuthenticated, token]);

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <PageHeader
        title="Student Progress & Learning Analytics"
        description="Comprehensive tracking of subject progress, chapter completion, and topic mastery synthesized deterministically and evaluated by the CrewAI Progress Agent."
        breadcrumbs={[{ label: "Coaching & System", href: "/" }, { label: "My Progress" }]}
        icon={<TrendingUp className="w-7 h-7 text-[#7C5CFC]" />}
        badge={
          <Badge variant="ai" size="md">
            Progress Agent &bull; Multi-Tier Analytics Live
          </Badge>
        }
      />

      {/* STATE 1: GUEST / UNAUTHENTICATED NOTICE */}
      {!isAuthenticated && (
        <Card className="border-amber-200 bg-amber-50/40">
          <CardContent className="p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="p-2.5 rounded-xl bg-amber-100 text-amber-800 shrink-0 mt-0.5">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    Authentication Required for Learning Analytics
                  </h3>
                  <p className="text-xs text-slate-600 mt-1 max-w-xl leading-relaxed">
                    Personalized progress analytics in Gyaan AI are derived deterministically from your persistent SQLite assessment attempts, diagnostic probes, and practice sessions. Log in or create an account to view your verified learning trajectory.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Link href="/login">
                  <Button variant="primary" size="sm" leftIcon={<LogIn className="w-3.5 h-3.5" />}>
                    Log In
                  </Button>
                </Link>
                <Link href="/register">
                  <Button variant="secondary" size="sm">
                    Register
                  </Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* STATE 2: LOADING */}
      {isLoading && (
        <Card className="border-purple-200 bg-purple-50/20 text-center py-12">
          <CardContent className="space-y-4">
            <div className="inline-flex p-3 rounded-full bg-purple-100 text-[#7C5CFC] animate-pulse">
              <TrendingUp className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-900">
                Progress Agent is Aggregating Learning Dashboard...
              </h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Compiling deterministic mastery statistics across subjects, chapters, and assessment attempts.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* STATE 3: ERROR */}
      {errorMessage && !isLoading && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-semibold block">Failed to Load Progress Dashboard</span>
              <p>{errorMessage}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={fetchProgressDashboard} leftIcon={<RotateCcw className="w-3.5 h-3.5" />}>
            Retry
          </Button>
        </div>
      )}

      {/* STATE 4: DASHBOARD CONTENT */}
      {dashboard && !isLoading && (
        <div className="space-y-6">
          {/* Top Metadata Bar */}
          <div className="p-4 rounded-xl border bg-white shadow-xs flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Badge variant="ai" size="md">
                Student: {dashboard.student_name}
              </Badge>
              <Badge variant="teal" size="md">
                {dashboard.grade}
              </Badge>
              <Badge
                variant={
                  dashboard.performance_trend === "improving"
                    ? "teal"
                    : dashboard.performance_trend === "declining"
                    ? "neutral"
                    : "primary"
                }
                size="md"
              >
                Trend: {dashboard.performance_trend.replace("_", " ").toUpperCase()}
              </Badge>
            </div>

            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                {(dashboard.duration_ms / 1000).toFixed(2)}s
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchProgressDashboard}
                leftIcon={<RotateCcw className="w-3 h-3" />}
              >
                Refresh
              </Button>
            </div>
          </div>

          {/* HONEST EMPTY STATE FOR NEW STUDENTS (0 ATTEMPTS) */}
          {!dashboard.has_sufficient_history && (
            <Card className="border-teal-200 bg-teal-50/30 p-6 text-center">
              <div className="max-w-xl mx-auto space-y-4">
                <div className="w-12 h-12 rounded-full bg-teal-100 text-[#0F9F9A] flex items-center justify-center mx-auto">
                  <Sparkles className="w-6 h-6" />
                </div>
                <div className="space-y-1.5">
                  <h3 className="text-base font-bold text-slate-900">
                    Welcome to Your CBSE Class 10 Learning Journey!
                  </h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {dashboard.empty_state_guide ||
                      "You have not taken any assessments yet. Gyaan AI tracks your progress honestly from real test attempts without fabricating scores. Take your first diagnostic or practice set to unlock real-time progress metrics!"}
                  </p>
                </div>

                <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                  <Link href="/diagnostic">
                    <Button variant="primary" size="sm" leftIcon={<Activity className="w-4 h-4" />}>
                      Take 25-Question Diagnostic
                    </Button>
                  </Link>
                  <Link href="/practice">
                    <Button variant="secondary" size="sm" leftIcon={<CheckSquare className="w-4 h-4 text-[#0F9F9A]" />}>
                      Practice Chapter Sets
                    </Button>
                  </Link>
                  <Link href="/teach">
                    <Button variant="secondary" size="sm" leftIcon={<BookOpen className="w-4 h-4 text-[#7C5CFC]" />}>
                      Interactive Lesson
                    </Button>
                  </Link>
                </div>
              </div>
            </Card>
          )}

          {/* TOP METRIC CARDS */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card className="p-4 bg-white border-slate-200">
              <span className="text-[11px] uppercase font-semibold text-slate-400 block mb-1">
                Overall Accuracy
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">
                  {dashboard.overall_accuracy !== null && dashboard.overall_accuracy !== undefined
                    ? `${dashboard.overall_accuracy}%`
                    : "N/A"}
                </span>
                <span className="text-[11px] text-slate-500">score</span>
              </div>
            </Card>

            <Card className="p-4 bg-white border-slate-200">
              <span className="text-[11px] uppercase font-semibold text-slate-400 block mb-1">
                Assessments Completed
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">
                  {dashboard.total_assessments}
                </span>
                <span className="text-[11px] text-slate-500">quizzes</span>
              </div>
            </Card>

            <Card className="p-4 bg-white border-slate-200">
              <span className="text-[11px] uppercase font-semibold text-slate-400 block mb-1">
                Questions Answered
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">
                  {dashboard.total_questions_answered}
                </span>
                <span className="text-[11px] text-emerald-600 font-medium">recorded</span>
              </div>
            </Card>

            <Card className="p-4 bg-white border-slate-200">
              <span className="text-[11px] uppercase font-semibold text-slate-400 block mb-1">
                Performance Trend
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-base font-bold text-slate-900 uppercase">
                  {dashboard.performance_trend.replace("_", " ")}
                </span>
              </div>
            </Card>
          </div>

          {/* SUBJECT-WISE PROGRESS CARDS */}
          {dashboard.subject_progress.length > 0 && (
            <div className="space-y-3">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                Subject Mastery &amp; Assessment Counts:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {dashboard.subject_progress.map((sp, idx) => (
                  <Card key={idx} className="p-4 border-slate-200 bg-white space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-slate-900">{sp.subject}</span>
                      <Badge variant="teal" size="sm">
                        {sp.quizzes_taken} quizzes
                      </Badge>
                    </div>

                    <div className="flex items-baseline justify-between text-xs text-slate-600">
                      <span>Average Accuracy:</span>
                      <span className="font-bold text-slate-900">
                        {sp.average_score !== null && sp.average_score !== undefined
                          ? `${sp.average_score}%`
                          : "N/A"}
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-1 pt-1 text-center text-[10px]">
                      <div className="p-1.5 rounded bg-emerald-50 text-emerald-800 font-semibold">
                        <div>{sp.topics_mastered}</div>
                        <div className="text-[9px] text-emerald-600 font-normal">Mastered</div>
                      </div>
                      <div className="p-1.5 rounded bg-blue-50 text-blue-800 font-semibold">
                        <div>{sp.topics_in_progress}</div>
                        <div className="text-[9px] text-blue-600 font-normal">Learning</div>
                      </div>
                      <div className="p-1.5 rounded bg-amber-50 text-amber-800 font-semibold">
                        <div>{sp.topics_needing_revision}</div>
                        <div className="text-[9px] text-amber-600 font-normal">Revision</div>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* CHAPTER COMPLETION CHECKLIST */}
          {dashboard.chapter_completion.length > 0 && (
            <Card className="p-6">
              <CardHeader className="p-0 pb-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-[#0F9F9A]" />
                    CBSE Class 10 Chapter Completion Tracker
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Curriculum learning objectives completed based on assessment records
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent className="p-0 pt-4 space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {dashboard.chapter_completion.map((ch, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-2 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900 line-clamp-1">{ch.title}</span>
                        <Badge
                          variant={
                            ch.status === "completed"
                              ? "teal"
                              : ch.status === "in_progress"
                              ? "primary"
                              : "neutral"
                          }
                          size="sm"
                        >
                          {ch.status.replace("_", " ")}
                        </Badge>
                      </div>

                      {/* Progress Bar */}
                      <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-[#0F9F9A] h-full rounded-full transition-all duration-300"
                          style={{ width: `${Math.min(100, Math.max(0, ch.mastery_percentage))}%` }}
                        />
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-slate-500">
                        <span>
                          {ch.objectives_completed} / {ch.total_objectives} objectives
                        </span>
                        <span className="font-semibold text-slate-700">{ch.mastery_percentage}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* TOPIC MASTERY MATRIX */}
          {dashboard.topic_mastery.length > 0 && (
            <Card className="p-6">
              <CardHeader className="p-0 pb-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <Target className="w-4 h-4 text-[#7C5CFC]" />
                    Topic Mastery Observations
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Deterministic status classification across tested topics
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent className="p-0 pt-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {dashboard.topic_mastery.map((tm, idx) => (
                    <div key={idx} className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1.5 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900">{tm.topic}</span>
                        <Badge
                          variant={
                            tm.status === "mastered"
                              ? "teal"
                              : tm.status === "needs_revision"
                              ? "neutral"
                              : "primary"
                          }
                          size="sm"
                        >
                          {tm.status.replace("_", " ")}
                        </Badge>
                      </div>
                      <p className="text-slate-600 text-[11px] leading-relaxed">{tm.observation}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* RECENT ATTEMPTS TABLE */}
          {dashboard.recent_attempts.length > 0 && (
            <Card className="p-6">
              <CardHeader className="p-0 pb-3 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-slate-900">
                    Recent Assessment Attempts ({dashboard.recent_attempts.length})
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Chronological attempts evaluated by Assessment Agent
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent className="p-0 pt-3">
                <div className="divide-y divide-slate-100">
                  {dashboard.recent_attempts.map((att, idx) => (
                    <div key={idx} className="py-2.5 flex items-center justify-between text-xs">
                      <div>
                        <span className="font-semibold text-slate-900">{att.topic || "Assessment"}</span>
                        <span className="text-slate-400 ml-2">({att.subject || "Science"})</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-[11px] text-slate-400">
                          {att.created_at ? new Date(att.created_at).toLocaleDateString() : "Recent"}
                        </span>
                        <Badge
                          variant={
                            (att.percentage || 0) >= 80 ? "teal" : (att.percentage || 0) >= 50 ? "neutral" : "primary"
                          }
                          size="sm"
                        >
                          {att.score} / {att.max_marks} ({att.percentage ?? 0}%)
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* ACTION FOOTER */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-xs text-slate-600 flex items-center gap-2">
              <HeartHandshake className="w-4 h-4 text-[#7C5CFC]" />
              Ready to continue your customized study plan?
            </div>
            <div className="flex items-center gap-2">
              <Link href="/mentor">
                <Button variant="primary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                  Consult AI Mentor
                </Button>
              </Link>
              <Link href="/practice">
                <Button variant="secondary" size="sm" leftIcon={<Award className="w-3.5 h-3.5 text-[#0F9F9A]" />}>
                  Practice Exercises
                </Button>
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
