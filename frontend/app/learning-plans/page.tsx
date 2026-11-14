"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Compass,
  ArrowRight,
  BookOpen,
  Calendar,
  CheckCircle2,
  Cpu,
  History,
  Activity,
  Sparkles,
  Layers,
  GraduationCap,
  MessageSquare,
  FileText,
} from "lucide-react";
import { PageHeader } from "../../components/ui/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { FormattedMessage } from "../../components/ui/FormattedMessage";
import { EmptyState } from "../../components/ui/EmptyState";
import { useAuth } from "../../components/auth/AuthContext";
import { apiClient } from "../../lib/api";
import { LearningPlanResponse, SavedCurriculumPlan } from "../../types";

export default function LearningPlansPage() {
  const { student, isAuthenticated, token } = useAuth();

  const [latestPlan, setLatestPlan] = useState<LearningPlanResponse | null>(null);
  const [savedPlans, setSavedPlans] = useState<SavedCurriculumPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | "latest">("latest");
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [showDiagnosticContext, setShowDiagnosticContext] = useState(false);

  // Load latest plan from sessionStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = sessionStorage.getItem("gyaan_latest_learning_plan");
        if (stored) {
          const parsed: LearningPlanResponse = JSON.parse(stored);
          setLatestPlan(parsed);
          setSelectedPlanId("latest");
        }
      } catch (err) {
        console.warn("Failed to load latest learning plan from session:", err);
      }
    }
  }, []);

  // Load saved plans for authenticated student
  useEffect(() => {
    if (isAuthenticated && token) {
      setIsLoadingHistory(true);
      apiClient
        .getDashboard(token)
        .then((dash) => {
          if (dash.recent_curriculum_plans && dash.recent_curriculum_plans.length > 0) {
            setSavedPlans(dash.recent_curriculum_plans);
            // If no latestPlan in sessionStorage, default to the most recent saved plan
            setLatestPlan((current) => {
              if (!current) {
                setSelectedPlanId(dash.recent_curriculum_plans[0].plan_id);
              }
              return current;
            });
          }
        })
        .catch((err) => {
          console.warn("Could not fetch curriculum plans from dashboard:", err);
        })
        .finally(() => {
          setIsLoadingHistory(false);
        });
    }
  }, [isAuthenticated, token]);

  // Determine currently active plan content to display
  let activePlanContent: string | null = null;
  let activePlanSubject = "Science";
  let activePlanTopic = "Curriculum Roadmap";
  let activePlanDate: string | null = null;
  let activeDiagnosticContent: string | null = null;
  let activeModel = "qwen2.5:3b (Ollama GPU)";

  if (selectedPlanId === "latest" && latestPlan) {
    activePlanContent = latestPlan.curriculum_plan;
    activeDiagnosticContent = latestPlan.diagnostic_report;
    activeModel = latestPlan.model || "qwen2.5:3b";
  } else {
    const found = savedPlans.find((p) => p.plan_id === selectedPlanId);
    if (found) {
      activePlanContent = found.plan_output;
      activePlanSubject = found.subject;
      activePlanTopic = found.topic;
      activePlanDate = found.created_at;
    } else if (latestPlan) {
      activePlanContent = latestPlan.curriculum_plan;
      activeDiagnosticContent = latestPlan.diagnostic_report;
      activeModel = latestPlan.model || "qwen2.5:3b";
    }
  }

  const hasAnyPlan = Boolean(activePlanContent || latestPlan || savedPlans.length > 0);

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <PageHeader
        title="Personalized Learning Plans"
        description="Structured multi-week curriculum roadmaps dynamically synthesized by the CrewAI Curriculum Agent based on diagnostic gap analysis and NCERT syllabus milestones."
        breadcrumbs={[{ label: "Learning Core", href: "/" }, { label: "Learning Plans" }]}
        icon={<Compass className="w-7 h-7 text-[#2563EB]" />}
        badge={
          <Badge variant="primary" size="md">
            Personalized 7-Day Study Plans
          </Badge>
        }
      />

      {/* Main Content Area */}
      {!hasAnyPlan && !isLoadingHistory ? (
        <EmptyState
          icon={Compass}
          title="No Learning Plans Generated Yet"
          description="Learning plans in Gyaan AI are synthesized automatically when you complete a diagnostic assessment. The Diagnostic Specialist identifies your knowledge gaps, and the Curriculum Planner constructs a tailored 3-stage study roadmap."
          agentInfo={{
            name: "Curriculum Planner",
            role: "Syllabus decomposition, weekly study schedules, and NCERT curriculum alignment",
            phase: "CBSE Class 10 Curriculum Engine",
            status: "Ready for Assessment Probes",
          }}
          action={
            <div className="flex flex-col sm:flex-row items-center gap-3">
              <Link href="/diagnostic">
                <Button variant="primary" size="lg" rightIcon={<ArrowRight className="w-4 h-4" />}>
                  Start Diagnostic Assessment
                </Button>
              </Link>
              <Link href="/teacher">
                <Button variant="secondary" size="lg" leftIcon={<GraduationCap className="w-4 h-4" />}>
                  Explore AI Teacher Studio
                </Button>
              </Link>
            </div>
          }
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Left Column: Plan Selector & Meta */}
          <div className="lg:col-span-1 space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
                  <History className="w-4 h-4 text-[#2563EB]" />
                  Available Plans
                </CardTitle>
                <CardDescription className="text-xs">
                  Select a generated curriculum roadmap
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 pt-0">
                {latestPlan && (
                  <button
                    type="button"
                    onClick={() => setSelectedPlanId("latest")}
                    className={`w-full text-left p-2.5 rounded-lg border text-xs transition-all ${
                      selectedPlanId === "latest"
                        ? "border-[#2563EB] bg-blue-50/70 font-medium text-blue-900 shadow-xs"
                        : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 text-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-slate-900 truncate">
                        Active Session Plan
                      </span>
                      <Badge variant="teal" size="sm">
                        Latest
                      </Badge>
                    </div>
                    <p className="text-[11px] text-slate-500 truncate">
                      {latestPlan.student_id ? `Student: ${latestPlan.student_id}` : "Current Session"}
                    </p>
                  </button>
                )}

                {savedPlans.map((plan) => {
                  const isSelected = selectedPlanId === plan.plan_id;
                  return (
                    <button
                      key={plan.plan_id}
                      type="button"
                      onClick={() => setSelectedPlanId(plan.plan_id)}
                      className={`w-full text-left p-2.5 rounded-lg border text-xs transition-all ${
                        isSelected
                          ? "border-[#2563EB] bg-blue-50/70 font-medium text-blue-900 shadow-xs"
                          : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 text-slate-700"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-slate-900 truncate">
                          {plan.topic || "Curriculum Plan"}
                        </span>
                        <span className="text-[10px] text-slate-400">
                          {new Date(plan.created_at).toLocaleDateString("en-IN", {
                            day: "numeric",
                            month: "short",
                          })}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 truncate">
                        {plan.subject} &bull; {plan.plan_id.substring(0, 8)}...
                      </p>
                    </button>
                  );
                })}

                <div className="pt-3 border-t border-slate-100">
                  <Link href="/diagnostic" className="w-full block">
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full text-xs justify-center"
                      leftIcon={<Sparkles className="w-3.5 h-3.5 text-[#0F9F9A]" />}
                    >
                      New Diagnostic
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>

            {/* Agent Pipeline Card */}
            <Card className="bg-slate-50/50 border-slate-200">
              <CardContent className="p-4 space-y-3 text-xs">
                <div className="flex items-center gap-2 font-semibold text-slate-800">
                  <Layers className="w-4 h-4 text-[#2563EB]" />
                  Sequential Crew Pipeline
                </div>
                <div className="space-y-2 text-slate-600">
                  <div className="flex items-start gap-2">
                    <div className="w-5 h-5 rounded-full bg-teal-100 text-[#0F9F9A] flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                      1
                    </div>
                    <div>
                      <span className="font-medium text-slate-800">Diagnostic Agent</span>
                      <p className="text-[11px] text-slate-500">Evaluates answers, tags gaps & misconceptions</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="w-5 h-5 rounded-full bg-blue-100 text-[#2563EB] flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                      2
                    </div>
                    <div>
                      <span className="font-medium text-slate-800">Curriculum Agent</span>
                      <p className="text-[11px] text-slate-500">Generates 3-stage NCERT sequenced study roadmap</p>
                    </div>
                  </div>
                </div>
                <div className="pt-2 border-t border-slate-200 text-[11px] text-slate-500 flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-slate-400" />
                  Local Ollama &bull; {activeModel}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Column: Active Learning Plan Viewer */}
          <div className="lg:col-span-3 space-y-4">
            {/* Roadmap Card */}
            <Card className="border-blue-100 shadow-xs">
              <CardHeader className="bg-gradient-to-r from-blue-50/60 to-indigo-50/30 border-b border-blue-100/80 pb-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="primary" size="sm">
                        Curriculum Roadmap
                      </Badge>
                      <span className="text-xs text-slate-500 flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5" />
                        {activePlanDate
                          ? new Date(activePlanDate).toLocaleString("en-IN", {
                              day: "numeric",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "Active Session"}
                      </span>
                    </div>
                    <CardTitle className="text-lg text-slate-900">
                      {activePlanTopic}
                    </CardTitle>
                    <CardDescription className="text-xs text-slate-600">
                      Tailored learning roadmap based on diagnosed student knowledge gaps
                    </CardDescription>
                  </div>

                  <div className="flex items-center gap-2">
                    {activeDiagnosticContent && (
                      <Button
                        type="button"
                        variant={showDiagnosticContext ? "primary" : "secondary"}
                        size="sm"
                        onClick={() => setShowDiagnosticContext(!showDiagnosticContext)}
                        leftIcon={<Activity className="w-3.5 h-3.5" />}
                      >
                        {showDiagnosticContext ? "Hide Diagnostic" : "View Diagnostic"}
                      </Button>
                    )}
                    <Link href="/teacher">
                      <Button
                        variant="secondary"
                        size="sm"
                        leftIcon={<GraduationCap className="w-3.5 h-3.5 text-[#2563EB]" />}
                      >
                        Practice with Teacher
                      </Button>
                    </Link>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="p-6 space-y-6">
                {/* Diagnostic Context Accordion/Block */}
                {showDiagnosticContext && activeDiagnosticContent && (
                  <div className="p-4 rounded-xl bg-teal-50/60 border border-teal-200/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-xs font-semibold text-teal-900">
                        <Activity className="w-4 h-4 text-[#0F9F9A]" />
                        Underlying Diagnostic Report (Diagnostic Agent)
                      </div>
                      <Badge variant="teal" size="sm">
                        Input Context
                      </Badge>
                    </div>
                    <div className="text-xs text-slate-700 bg-white p-3 rounded-lg border border-teal-100 max-h-60 overflow-y-auto">
                      <FormattedMessage content={activeDiagnosticContent} />
                    </div>
                  </div>
                )}

                {/* Plan Content */}
                {activePlanContent ? (
                  <div className="prose prose-slate max-w-none text-slate-800">
                    <FormattedMessage content={activePlanContent} />
                  </div>
                ) : (
                  <div className="text-center py-10 text-slate-500 text-sm">
                    No roadmap content found for this selected plan.
                  </div>
                )}

                {/* Action Footer */}
                <div className="pt-6 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div className="text-xs text-slate-500 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    Aligned with NCERT Class 10 Syllabus & Pedagogical Standards
                  </div>
                  <div className="flex items-center gap-2">
                    <Link href="/diagnostic">
                      <Button variant="secondary" size="sm" leftIcon={<Sparkles className="w-3.5 h-3.5 text-[#0F9F9A]" />}>
                        Take Another Diagnostic
                      </Button>
                    </Link>
                    <Link href="/teacher">
                      <Button variant="primary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                        Ask Teacher Questions
                      </Button>
                    </Link>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
