"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  HeartHandshake,
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
  Layers,
  Target,
  Compass,
  Bookmark,
  Calendar,
  LogIn,
  Lightbulb,
  Square,
  Database,
} from "lucide-react";
import { PageHeader } from "../../components/ui/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { FormattedMessage } from "../../components/ui/FormattedMessage";
import { EmptyState } from "../../components/ui/EmptyState";
import { useAuth } from "../../components/auth/AuthContext";
import { apiClient } from "../../lib/api";
import { MentorRecommendationsResponse, MentorRecommendationItem } from "../../types";

const CACHE_KEY_PREFIX = "gyaan_mentor_recommendations_";
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

interface CachedMentorData {
  data: MentorRecommendationsResponse;
  timestamp: number;
}

function getCachedMentorData(studentId: string): CachedMentorData | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(`${CACHE_KEY_PREFIX}${studentId}`);
    if (!raw) return null;
    const parsed: CachedMentorData = JSON.parse(raw);

    // Invalidation check: if a new assessment was submitted since cached timestamp
    const latestAssessmentTs = parseInt(sessionStorage.getItem("gyaan_latest_assessment_ts") || "0", 10);
    if (latestAssessmentTs > parsed.timestamp) {
      sessionStorage.removeItem(`${CACHE_KEY_PREFIX}${studentId}`);
      return null;
    }

    if (Date.now() - parsed.timestamp > CACHE_TTL_MS) {
      sessionStorage.removeItem(`${CACHE_KEY_PREFIX}${studentId}`);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function setCachedMentorData(studentId: string, data: MentorRecommendationsResponse): void {
  if (typeof window === "undefined") return;
  try {
    const record: CachedMentorData = {
      data,
      timestamp: Date.now(),
    };
    sessionStorage.setItem(`${CACHE_KEY_PREFIX}${studentId}`, JSON.stringify(record));
  } catch {
    // Ignore storage quota limits
  }
}

function clearCachedMentorData(studentId: string): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(`${CACHE_KEY_PREFIX}${studentId}`);
  } catch {
    // Ignore
  }
}

export default function MentorPage() {
  const { student, isAuthenticated, token } = useAuth();

  const [isLoading, setIsLoading] = useState(false);
  const [loadingSeconds, setLoadingSeconds] = useState(0);
  const [mentorData, setMentorData] = useState<MentorRecommendationsResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isCached, setIsCached] = useState<boolean>(false);
  const [cacheTimestamp, setCacheTimestamp] = useState<number | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Loading elapsed timer
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isLoading) {
      setLoadingSeconds(0);
      timer = setInterval(() => {
        setLoadingSeconds((s) => s + 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isLoading]);

  // Request cancellation on component unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsLoading(false);
  };

  const fetchMentorRecommendations = async (forceRefresh = false) => {
    if (!isAuthenticated || !token) return;

    const studentId = student?.id || "guest";

    // Check client-side session cache unless forceRefresh is true
    if (!forceRefresh && student?.id) {
      const cached = getCachedMentorData(student.id);
      if (cached) {
        setMentorData(cached.data);
        setIsCached(true);
        setCacheTimestamp(cached.timestamp);
        setErrorMessage(null);
        return;
      }
    }

    if (forceRefresh && student?.id) {
      clearCachedMentorData(student.id);
    }

    // Cancel any previous in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setIsLoading(true);
    setErrorMessage(null);
    setIsCached(false);

    try {
      const data = await apiClient.getMentorRecommendations(token, {
        signal: abortControllerRef.current.signal,
        timeoutMs: 75000,
      });

      setMentorData(data);
      if (student?.id) {
        setCachedMentorData(student.id, data);
        setCacheTimestamp(Date.now());
      }
    } catch (err: unknown) {
      const isAbort =
        err instanceof Error &&
        (err.name === "AbortError" ||
          err.message.includes("cancelled") ||
          err.message.includes("timed out"));

      const msg = isAbort
        ? "Mentor analysis was stopped or timed out after 75s. Local Ollama may be busy processing another task."
        : err instanceof Error
        ? err.message
        : "Failed to load mentor recommendations.";

      setErrorMessage(msg);
    } finally {
      abortControllerRef.current = null;
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated && token) {
      fetchMentorRecommendations();
    }
  }, [isAuthenticated, token]);

  // Compute loading status stage
  const getLoadingPhase = (seconds: number) => {
    if (seconds <= 15) {
      return {
        stage: "Stage 1 of 3: Progress Analysis",
        detail: "Evaluating verified assessment scores & historical learning patterns from SQLite...",
      };
    }
    if (seconds <= 35) {
      return {
        stage: "Stage 2 of 3: Diagnostic Synthesis",
        detail: "Evaluating longitudinal concept mastery curves & identifying NCERT curriculum gaps...",
      };
    }
    return {
      stage: "Stage 3 of 3: Mentor Recommendations",
      detail: "Synthesizing prioritized study interventions & verified textbook citations...",
    };
  };

  const loadingPhase = getLoadingPhase(loadingSeconds);

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <PageHeader
        title="AI Mentor & Learning Coach"
        description="Personalized academic coaching and evidence-backed study strategies tailored to your Class 10 learning journey."
        breadcrumbs={[{ label: "Coaching & System", href: "/" }, { label: "AI Mentor" }]}
        icon={<HeartHandshake className="w-7 h-7 text-[#7C5CFC]" />}
        badge={
          <Badge variant="ai" size="md">
            Personalized Learning Coach
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
                    Authentication Required for Personalized Mentoring
                  </h3>
                  <p className="text-xs text-slate-600 mt-1 max-w-xl leading-relaxed">
                    Your AI Learning Coach synthesizes individualized guidance based on your actual performance records, diagnostic gap analyses, and learning history. Log in or register an account to receive tailored study recommendations.
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
        <Card className="border-purple-200 bg-purple-50/20 text-center py-10 shadow-xs">
          <CardContent className="space-y-4 max-w-lg mx-auto">
            <div className="inline-flex p-3 rounded-full bg-purple-100 text-[#7C5CFC] animate-pulse">
              <HeartHandshake className="w-8 h-8" />
            </div>

            <div className="space-y-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-purple-700 bg-purple-50 px-2.5 py-0.5 rounded-full border border-purple-200">
                {loadingPhase.stage}
              </span>
              <h3 className="text-base font-bold text-slate-900">
                Synthesizing Personalized Learning Guidance...
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                {loadingPhase.detail}
              </p>
            </div>

            <div className="flex flex-col items-center gap-2.5 pt-2">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-purple-200 text-xs text-purple-800 font-semibold shadow-2xs">
                <Layers className="w-3.5 h-3.5 text-[#7C5CFC]" />
                <span>Running Sequential Progress &rarr; Mentor Crew</span>
                <span className="text-slate-300">&bull;</span>
                <span className="font-mono text-purple-900">{loadingSeconds}s elapsed</span>
              </div>

              {loadingSeconds > 25 && (
                <p className="text-[11px] text-purple-600 animate-in fade-in">
                  Running comprehensive longitudinal analysis via private local Ollama AI.
                </p>
              )}

              <button
                onClick={handleCancel}
                className="mt-2 text-xs text-slate-500 hover:text-red-600 px-3 py-1 rounded-md border border-slate-200 hover:bg-white flex items-center gap-1.5 transition-colors"
              >
                <Square className="w-3 h-3 fill-current" />
                <span>Cancel Analysis</span>
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* STATE 3: ERROR */}
      {errorMessage && !isLoading && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-2xs">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-bold block text-sm">Failed to Load Mentor Recommendations</span>
              <p className="text-slate-700 leading-relaxed">{errorMessage}</p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchMentorRecommendations(true)}
            leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            className="shrink-0 border-red-300 text-red-700 hover:bg-red-100"
          >
            Retry Analysis
          </Button>
        </div>
      )}

      {/* STATE 4: MENTORING CONTENT */}
      {mentorData && !isLoading && (
        <div className="space-y-6">
          {/* Top Metadata Bar */}
          <div className="p-4 rounded-xl border bg-white shadow-2xs flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="ai" size="md">
                Personalized Study Guidance
              </Badge>
              <Badge variant="primary" size="md">
                {mentorData.recommendations.length} Actionable Recommendations
              </Badge>
              {isCached && (
                <Badge variant="neutral" size="sm">
                  <Database className="w-3 h-3 mr-1 text-slate-500" />
                  Cached (Fast Load)
                </Badge>
              )}
            </div>

            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1 font-medium text-slate-600">
                <Cpu className="w-3.5 h-3.5 text-[#0F9F9A]" />
                Private Local AI
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                {(mentorData.duration_ms / 1000).toFixed(2)}s
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => fetchMentorRecommendations(true)}
                leftIcon={<RotateCcw className="w-3 h-3" />}
                title="Regenerate fresh recommendations from latest SQLite assessment data"
              >
                Refresh
              </Button>
            </div>
          </div>

          {/* Mentor Overview Card */}
          <Card className="border-purple-100 shadow-2xs">
            <CardHeader className="bg-gradient-to-r from-purple-50/70 via-indigo-50/30 to-pink-50/20 border-b border-purple-100/80 pb-4">
              <div className="flex items-center gap-2 mb-1">
                <Badge variant="ai" size="sm">
                  Coaching Message
                </Badge>
                {student?.display_name && (
                  <span className="text-xs text-slate-500 font-medium">
                    Personalized for {student.display_name}
                  </span>
                )}
              </div>
              <CardTitle className="text-lg text-slate-900">
                Mentor Strategic Overview
              </CardTitle>
              <CardDescription className="text-xs text-slate-600">
                Action-oriented learning coaching based on your recent assessment attempts and identified conceptual gaps
              </CardDescription>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="prose prose-slate max-w-none text-slate-800 text-sm">
                <FormattedMessage content={mentorData.mentor_overview} />
              </div>

              {/* Study Tip & Next Milestone Highlights */}
              {(mentorData.study_tip || mentorData.next_milestone) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                  {mentorData.study_tip && (
                    <div className="p-3.5 rounded-xl bg-amber-50/60 border border-amber-200/80 space-y-1">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-amber-900">
                        <Lightbulb className="w-4 h-4 text-amber-600" />
                        Study Habit Tip:
                      </div>
                      <p className="text-xs text-amber-950 leading-relaxed">
                        {mentorData.study_tip}
                      </p>
                    </div>
                  )}

                  {mentorData.next_milestone && (
                    <div className="p-3.5 rounded-xl bg-indigo-50/60 border border-indigo-200/80 space-y-1">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-900">
                        <Target className="w-4 h-4 text-indigo-600" />
                        Target Next Milestone:
                      </div>
                      <p className="text-xs text-indigo-950 leading-relaxed">
                        {mentorData.next_milestone}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Actionable Recommendations List */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Target className="w-4 h-4 text-[#7C5CFC]" />
                Recommended Study Tasks ({mentorData.recommendations.length})
              </h3>
              <span className="text-xs text-slate-500">
                Ranked by priority to maximize concept mastery
              </span>
            </div>

            {mentorData.recommendations.length === 0 ? (
              <EmptyState
                icon={HeartHandshake}
                title="Welcome to AI Mentoring!"
                description="Complete your first practice quiz or diagnostic assessment to unlock personalized study recommendations and learning trajectory analysis."
                action={
                  <div className="flex flex-wrap items-center justify-center gap-3">
                    <Link href="/practice">
                      <Button variant="primary" size="sm" rightIcon={<ArrowRight className="w-4 h-4" />}>
                        Take Practice Quiz
                      </Button>
                    </Link>
                    <Link href="/diagnostic">
                      <Button variant="secondary" size="sm">
                        Take Diagnostic Assessment
                      </Button>
                    </Link>
                  </div>
                }
              />
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {mentorData.recommendations.map((rec, idx) => {
                  const isHigh = rec.priority === "high";
                  const isMedium = rec.priority === "medium";

                  return (
                    <Card key={idx} className="border-slate-200">
                      <CardHeader className="pb-3 bg-slate-50/60 border-b border-slate-100">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div className="flex items-center gap-2.5">
                            <span className="w-5 h-5 rounded-full bg-purple-100 text-[#7C5CFC] font-bold text-xs flex items-center justify-center shrink-0">
                              {idx + 1}
                            </span>
                            <CardTitle className="text-sm font-bold text-slate-900">
                              {rec.title}
                            </CardTitle>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={isHigh ? "neutral" : isMedium ? "primary" : "teal"}
                              size="sm"
                            >
                              {rec.priority.toUpperCase()} PRIORITY
                            </Badge>
                            {rec.estimated_minutes && (
                              <span className="text-[11px] text-slate-500 flex items-center gap-1 font-medium">
                                <Clock className="w-3 h-3" />
                                ~{rec.estimated_minutes} mins
                              </span>
                            )}
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="pt-4 space-y-3 text-xs">
                        <div className="space-y-1">
                          <span className="font-semibold text-slate-500 uppercase text-[10px] tracking-wider block">
                            Suggested Action:
                          </span>
                          <p className="text-slate-900 font-medium bg-slate-50 p-2.5 rounded-lg border border-slate-100 leading-relaxed">
                            {rec.suggested_action}
                          </p>
                        </div>

                        <div className="space-y-1">
                          <span className="font-semibold text-slate-500 uppercase text-[10px] tracking-wider block">
                            Reason & Evidence:
                          </span>
                          <p className="text-slate-600 leading-relaxed">
                            {rec.reason}
                          </p>
                          {rec.supporting_evidence && (
                            <p className="text-[11px] text-slate-500 italic">
                              Evidence: {rec.supporting_evidence}
                            </p>
                          )}
                        </div>

                        {rec.resource_reference && (
                          <div className="p-2 rounded bg-purple-50/40 border border-purple-100 text-[11px] text-purple-900 flex items-center gap-1.5">
                            <Bookmark className="w-3.5 h-3.5 text-[#7C5CFC] shrink-0" />
                            <span>
                              <strong>Curriculum Reference:</strong> {rec.resource_reference}
                            </span>
                          </div>
                        )}

                        {/* Direct Action Links */}
                        <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
                          <span className="text-[11px] text-slate-400">
                            Topic: <strong className="text-slate-700">{rec.topic}</strong>
                          </span>
                          <div className="flex items-center gap-2">
                            <Link href={`/resources?topic=${encodeURIComponent(rec.topic)}`}>
                              <Button variant="secondary" size="sm" leftIcon={<BookOpen className="w-3.5 h-3.5 text-[#0F9F9A]" />}>
                                Study Resources
                              </Button>
                            </Link>
                            <Link href={`/practice?topic=${encodeURIComponent(rec.topic)}`}>
                              <Button variant="primary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                                Practice Now
                              </Button>
                            </Link>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>

          {/* Underlying Analytics Context Box */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-xs text-slate-600 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              Recommendations generated from verified Progress Agent trajectory statistics.
            </div>
            <div className="flex items-center gap-2">
              <Link href="/progress">
                <Button variant="secondary" size="sm" leftIcon={<Award className="w-3.5 h-3.5 text-[#7C5CFC]" />}>
                  View Progress Analytics
                </Button>
              </Link>
              <Link href="/teacher">
                <Button variant="secondary" size="sm" leftIcon={<GraduationCap className="w-3.5 h-3.5 text-[#2563EB]" />}>
                  Ask AI Teacher
                </Button>
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
