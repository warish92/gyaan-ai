"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Sparkles,
  GraduationCap,
  Compass,
  Activity,
  Library,
  CheckSquare,
  TrendingUp,
  HeartHandshake,
  Cpu,
  ArrowRight,
  Server,
  Database,
  ShieldCheck,
  CheckCircle2,
  Clock,
  BookOpen,
  UserCheck,
  AlertCircle,
  LogIn,
  UserPlus,
  Award,
  BarChart3,
  Calendar,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { LoadingCard, Spinner } from "../components/ui/LoadingIndicator";
import { useBackendHealth } from "../components/layout/AppShell";
import { useAuth } from "../components/auth/AuthContext";
import { apiClient } from "../lib/api";
import { StudentDashboardResponse } from "../types";

interface FeatureCardInfo {
  title: string;
  description: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  agentName: string;
  agentRole: string;
  phase: string;
  badgeVariant: "primary" | "teal" | "ai";
}

const workspaceFeatures: FeatureCardInfo[] = [
  {
    title: "AI Teacher Studio",
    description: "Socratic concept explanations tailored for CBSE Class 10 Science & Mathematics.",
    href: "/teacher",
    icon: GraduationCap,
    agentName: "Teacher Agent",
    agentRole: "Socratic Pedagogy",
    phase: "Tutoring",
    badgeVariant: "primary",
  },
  {
    title: "Learning Plans",
    description: "Multi-week personalized curriculum schedules based on diagnosed student weaknesses.",
    href: "/learning-plans",
    icon: Compass,
    agentName: "Curriculum Agent",
    agentRole: "Curriculum Architect",
    phase: "7-Day Plan",
    badgeVariant: "primary",
  },
  {
    title: "Knowledge Diagnostics",
    description: "Multi-turn diagnostic assessments to discover specific topic gaps and misconceptions.",
    href: "/diagnostic",
    icon: Activity,
    agentName: "Diagnostic Agent",
    agentRole: "Gap Identification",
    phase: "Diagnostic",
    badgeVariant: "teal",
  },
  {
    title: "NCERT Resources",
    description: "Curated textbook references, verified external links, and structured study guides.",
    href: "/resources",
    icon: Library,
    agentName: "Resource Agent",
    agentRole: "Content Curation",
    phase: "NCERT Library",
    badgeVariant: "teal",
  },
  {
    title: "Practice & Assessments",
    description: "CBSE-aligned multiple-choice and conceptual quizzes with automated scoring.",
    href: "/practice",
    icon: CheckSquare,
    agentName: "Assessment Agent",
    agentRole: "Quiz Evaluation",
    phase: "Adaptive Quiz",
    badgeVariant: "teal",
  },
  {
    title: "My Progress Analytics",
    description: "Deterministic analytics tracking mastery levels, quiz attempts, and learning records.",
    href: "/progress",
    icon: TrendingUp,
    agentName: "Progress Agent",
    agentRole: "Learning Analytics",
    phase: "Analytics",
    badgeVariant: "ai",
  },
  {
    title: "AI Mentor Coach",
    description: "Personalized milestone guidance, study habit coaching, and encouraging feedback.",
    href: "/mentor",
    icon: HeartHandshake,
    agentName: "Mentor Agent",
    agentRole: "Academic Coach",
    phase: "Mentorship",
    badgeVariant: "ai",
  },
  {
    title: "Agent Arena & Routing",
    description: "Live inspection of the master Orchestrator Agent and multi-agent intent routing.",
    href: "/agent-arena",
    icon: Cpu,
    agentName: "Orchestrator Agent",
    agentRole: "Workflow Coordinator",
    phase: "Multi-Agent",
    badgeVariant: "ai",
  },
];

export default function OverviewPage() {
  const { health, loading: healthLoading, latencyMs } = useBackendHealth();
  const { student, isAuthenticated, token, isLoading: authLoading } = useAuth();

  const [dashboard, setDashboard] = useState<StudentDashboardResponse | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState<boolean>(false);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  // Fetch real student dashboard when authenticated
  const fetchDashboard = useCallback(async () => {
    if (!isAuthenticated || !token) return;
    setDashboardLoading(true);
    setDashboardError(null);
    try {
      const data = await apiClient.getDashboard(token);
      setDashboard(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load dashboard data.";
      setDashboardError(msg);
    } finally {
      setDashboardLoading(false);
    }
  }, [isAuthenticated, token]);

  useEffect(() => {
    if (isAuthenticated && token) {
      fetchDashboard();
    } else {
      setDashboard(null);
    }
  }, [isAuthenticated, token, fetchDashboard]);

  return (
    <div className="space-y-8">
      {/* Dynamic Header */}
      {isAuthenticated && student ? (
        <PageHeader
          title={`Welcome back, ${student.display_name}!`}
          description={`Class 10 CBSE Learning Workspace • Preferred Language: ${student.preferred_language || "English"}`}
          breadcrumbs={[{ label: "Workspace" }, { label: "Personalized Dashboard" }]}
          badge={
            <Badge variant="success" size="md" dot>
              Verified Student Account
            </Badge>
          }
        />
      ) : (
        <PageHeader
          title="Educational Workspace Overview"
          description="Gyaan AI is an intelligent, multi-agent educational platform for CBSE Class 10. Powered by CrewAI agent orchestration and local Ollama inference with zero cloud dependency."
          breadcrumbs={[{ label: "Workspace" }, { label: "System Overview" }]}
          badge={
            <Badge variant="primary" size="md">
              Guest Student Mode
            </Badge>
          }
        />
      )}

      {/* Authenticated Student Dashboard View */}
      {isAuthenticated && student ? (
        <div className="space-y-8">
          {dashboardLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <LoadingCard rows={2} />
              <LoadingCard rows={2} />
              <LoadingCard rows={2} />
              <LoadingCard rows={2} />
            </div>
          ) : dashboardError ? (
            <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
              <span>{dashboardError}</span>
            </div>
          ) : dashboard ? (
            <>
              {/* Genuine Stats Row from SQLite Database */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
                <Card className="p-4 bg-white border-[#E2E8F0]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider">
                      Sessions
                    </span>
                    <Clock className="w-4 h-4 text-blue-600" />
                  </div>
                  <div className="text-2xl font-extrabold text-[#172033]">
                    {dashboard.stats.total_sessions}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-0.5">Tutoring lessons recorded</p>
                </Card>

                <Card className="p-4 bg-white border-[#E2E8F0]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider">
                      Quizzes Taken
                    </span>
                    <CheckSquare className="w-4 h-4 text-teal-600" />
                  </div>
                  <div className="text-2xl font-extrabold text-[#172033]">
                    {dashboard.stats.total_quizzes_taken}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-0.5">Completed assessments</p>
                </Card>

                <Card className="p-4 bg-white border-[#E2E8F0]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider">
                      Mastered
                    </span>
                    <Award className="w-4 h-4 text-emerald-600" />
                  </div>
                  <div className="text-2xl font-extrabold text-emerald-700">
                    {dashboard.stats.topics_mastered}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-0.5">High proficiency topics</p>
                </Card>

                <Card className="p-4 bg-white border-[#E2E8F0]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider">
                      In Progress
                    </span>
                    <BarChart3 className="w-4 h-4 text-blue-600" />
                  </div>
                  <div className="text-2xl font-extrabold text-blue-700">
                    {dashboard.stats.topics_in_progress}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-0.5">Active curriculum items</p>
                </Card>

                <Card className="p-4 bg-white border-[#E2E8F0] col-span-2 sm:col-span-1">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider">
                      Needs Revision
                    </span>
                    <Activity className="w-4 h-4 text-amber-600" />
                  </div>
                  <div className="text-2xl font-extrabold text-amber-700">
                    {dashboard.stats.topics_needing_revision}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-0.5">Diagnosed gap topics</p>
                </Card>
              </div>

              {/* Learning History & Topic Mastery Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Real Recent Learning Sessions (Section 8) */}
                <Card className="p-6">
                  <CardHeader className="p-0 pb-3 flex flex-row items-center justify-between">
                    <div>
                      <CardTitle className="text-sm font-bold flex items-center gap-2">
                        <BookOpen className="w-4 h-4 text-blue-600" />
                        Recent Learning Sessions
                      </CardTitle>
                      <CardDescription>
                        Chronological tutoring and lesson records from SQLite
                      </CardDescription>
                    </div>
                    <Badge variant="neutral" size="sm">
                      {dashboard.recent_learning_sessions.length} logged
                    </Badge>
                  </CardHeader>
                  <CardContent className="p-0 pt-3">
                    {dashboard.recent_learning_sessions.length === 0 ? (
                      <div className="py-8 text-center text-xs text-[#64748B] space-y-3 bg-slate-50 rounded-xl border border-dashed border-slate-200 p-4">
                        <p className="font-medium text-[#172033]">No learning sessions recorded yet.</p>
                        <p>Ask questions in AI Teacher Studio to automatically record tutoring sessions.</p>
                        <Link href="/teacher">
                          <Button variant="primary" size="sm">
                            Ask AI Teacher
                          </Button>
                        </Link>
                      </div>
                    ) : (
                      <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                        {dashboard.recent_learning_sessions.map((sess) => (
                          <div
                            key={sess.id}
                            className="p-3 rounded-xl border border-slate-200 bg-slate-50/60 flex items-center justify-between text-xs"
                          >
                            <div className="space-y-0.5 max-w-[70%]">
                              <div className="flex items-center gap-1.5">
                                <span className="font-semibold text-[#172033] truncate">
                                  {sess.topic}
                                </span>
                                <Badge variant="secondary" size="sm">
                                  {sess.subject}
                                </Badge>
                              </div>
                              <p className="text-[11px] text-slate-400">
                                {new Date(sess.started_at).toLocaleString([], {
                                  month: "short",
                                  day: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </p>
                            </div>
                            <Badge
                              variant={sess.status === "completed" ? "success" : "neutral"}
                              size="sm"
                            >
                              {sess.status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Real Topic Mastery (Section 9) */}
                <Card className="p-6">
                  <CardHeader className="p-0 pb-3 flex flex-row items-center justify-between">
                    <div>
                      <CardTitle className="text-sm font-bold flex items-center gap-2">
                        <Award className="w-4 h-4 text-emerald-600" />
                        Topic Mastery Records
                      </CardTitle>
                      <CardDescription>
                        Objective scores and evaluation status per topic
                      </CardDescription>
                    </div>
                    <Badge variant="neutral" size="sm">
                      {dashboard.topic_mastery.length} topics
                    </Badge>
                  </CardHeader>
                  <CardContent className="p-0 pt-3">
                    {dashboard.topic_mastery.length === 0 ? (
                      <div className="py-8 text-center text-xs text-[#64748B] space-y-3 bg-slate-50 rounded-xl border border-dashed border-slate-200 p-4">
                        <p className="font-medium text-[#172033]">No topic assessments completed yet.</p>
                        <p>Complete quizzes in Practice &amp; Assessments to establish topic mastery.</p>
                        <Link href="/practice">
                          <Button variant="secondary" size="sm">
                            Open Practice Arena
                          </Button>
                        </Link>
                      </div>
                    ) : (
                      <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                        {dashboard.topic_mastery.map((tm) => (
                          <div
                            key={tm.id}
                            className="p-3 rounded-xl border border-slate-200 bg-white flex items-center justify-between text-xs"
                          >
                            <div className="space-y-0.5">
                              <div className="flex items-center gap-1.5">
                                <span className="font-semibold text-[#172033]">{tm.topic}</span>
                                <span className="text-[10px] text-slate-400">({tm.subject})</span>
                              </div>
                              <p className="text-[11px] text-slate-500">
                                Latest score: {tm.latest_score}/{tm.max_marks} ({Math.round(tm.percentage)}%) • {tm.attempts_count} attempt(s)
                              </p>
                            </div>
                            <Badge
                              variant={
                                tm.mastery_status === "mastered"
                                  ? "success"
                                  : tm.mastery_status === "in_progress"
                                  ? "primary"
                                  : "warning"
                              }
                              size="sm"
                              dot
                            >
                              {tm.mastery_status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Recent Assessment Attempts */}
              {dashboard.recent_assessments.length > 0 && (
                <Card className="p-6">
                  <CardHeader className="p-0 pb-3">
                    <CardTitle className="text-sm font-bold flex items-center gap-2">
                      <CheckSquare className="w-4 h-4 text-teal-600" />
                      Recent Assessment Attempts
                    </CardTitle>
                    <CardDescription>
                      Verified quiz evaluation history recorded in SQLite
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-0 pt-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {dashboard.recent_assessments.map((att, idx) => {
                        const attId = att.id || att.attempt_id || `att_${idx}`;
                        const pct = att.percentage ?? Math.round((att.score / (att.max_marks || 1)) * 100);
                        const dateStr = att.completed_at || att.created_at;

                        return (
                          <div
                            key={attId}
                            className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/50 space-y-1.5 text-xs"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-[#172033]">
                                {att.topic || "Class 10 Quiz"}
                              </span>
                              <Badge variant="teal" size="sm">
                                {pct}%
                              </Badge>
                            </div>
                            <p className="text-[11px] text-slate-500">
                              Score: {att.score} / {att.max_marks} marks
                            </p>
                            {dateStr && (
                              <p className="text-[10px] text-slate-400">
                                {new Date(dateStr).toLocaleDateString()}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          ) : null}
        </div>
      ) : (
        /* Unauthenticated Mode: Welcoming Hero & Sign-in Banner */
        <div className="relative overflow-hidden rounded-2xl border border-blue-200/80 bg-gradient-to-b from-blue-50/50 via-white to-white p-6 sm:p-8 shadow-xs">
          <div className="relative z-10 max-w-2xl space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-100/80 text-blue-800 text-xs font-semibold border border-blue-200">
              <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              <span>CBSE Class 10 &bull; Multi-Agent Learning Workspace</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-[#172033] tracking-tight">
              Personalized Learning for CBSE Class 10
            </h2>
            <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
              Create a free student account to persistently track your topic mastery, learning plans, quiz scores, and Socratic tutoring history with SQLite. Or begin exploring immediately as a guest.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link href="/register">
                <Button
                  variant="primary"
                  size="md"
                  leftIcon={<UserPlus className="w-4 h-4" />}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  Create Student Account
                </Button>
              </Link>
              <Link href="/login">
                <Button
                  variant="secondary"
                  size="md"
                  leftIcon={<LogIn className="w-4 h-4" />}
                >
                  Sign In
                </Button>
              </Link>
              <Link href="/teacher">
                <Button
                  variant="ghost"
                  size="md"
                  leftIcon={<GraduationCap className="w-4 h-4" />}
                >
                  Guest AI Teacher
                </Button>
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Grid of 8 Core Multi-Agent Features */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-[#172033]">Learning Modules &amp; Agents</h2>
            <p className="text-xs text-[#64748B]">
              Eight canonical CrewAI agents collaborating to deliver personalized education
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {workspaceFeatures.map((feat) => {
            const Icon = feat.icon;
            return (
              <Card key={feat.href} hoverable className="flex flex-col justify-between p-5">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="w-10 h-10 rounded-xl bg-blue-50 text-[#2563EB] flex items-center justify-center border border-blue-100">
                      <Icon className="w-5 h-5" />
                    </div>
                    <Badge variant={feat.badgeVariant} size="sm">
                      {feat.phase}
                    </Badge>
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm text-[#172033]">{feat.title}</h3>
                    <p className="text-xs text-[#64748B] mt-1 line-clamp-2 leading-relaxed">
                      {feat.description}
                    </p>
                  </div>
                </div>

                <div className="pt-4 mt-4 border-t border-[#F1F5F9] flex items-center justify-between">
                  <div className="text-[11px] text-[#64748B]">
                    <span className="font-medium text-slate-700">{feat.agentName}</span>
                  </div>
                  <Link
                    href={feat.href}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8]"
                  >
                    <span>Open</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Real Backend & Ollama Architecture Status */}
      <Card className="p-6">
        <CardHeader className="p-0 pb-3 flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <Server className="w-4 h-4 text-[#2563EB]" />
              Local Infrastructure Telemetry
            </CardTitle>
            <CardDescription>
              FastAPI gateway, SQLite database, and GPU-accelerated local Ollama runtime
            </CardDescription>
          </div>
          <Badge variant="teal" size="sm">
            Zero Cloud Dependency
          </Badge>
        </CardHeader>
        <CardContent className="p-0 pt-3">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs">
            <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/60 space-y-1">
              <span className="text-[#64748B]">FastAPI Gateway</span>
              <p className="font-bold text-[#172033]">
                {healthLoading ? "Checking..." : health ? "Online (127.0.0.1:8000)" : "Offline"}
              </p>
            </div>
            <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/60 space-y-1">
              <span className="text-[#64748B]">Ollama LLM Engine</span>
              <p className="font-bold text-[#172033]">
                {health?.model_name || "qwen2.5:3b"} (Local GPU)
              </p>
            </div>
            <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/60 space-y-1">
              <span className="text-[#64748B]">Persistent Database</span>
              <p className="font-bold text-emerald-700 flex items-center gap-1">
                <Database className="w-3.5 h-3.5" /> SQLite (8 Tables)
              </p>
            </div>
            <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/60 space-y-1">
              <span className="text-[#64748B]">Round-Trip Latency</span>
              <p className="font-bold text-[#172033]">
                {latencyMs !== undefined ? `${latencyMs} ms` : "N/A"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
