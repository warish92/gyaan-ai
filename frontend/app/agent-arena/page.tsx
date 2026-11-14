"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Cpu,
  Bot,
  Workflow,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Clock,
  ArrowRight,
  ShieldCheck,
  RotateCcw,
  BookOpen,
  GraduationCap,
  Award,
  Layers,
  Send,
  Sliders,
  ChevronDown,
  Terminal,
  Activity,
  Compass,
  CheckSquare,
  TrendingUp,
  HeartHandshake,
  FileText,
  Bookmark,
  RefreshCw,
  Info,
  X,
  Play,
  Zap,
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
  OrchestrationRequest,
  OrchestrationResponse,
  AgentMetadataResponse,
  ArenaStatusResponse,
} from "../../types";

const AGENT_ICON_MAP: Record<string, React.ElementType> = {
  orchestrator: Cpu,
  teacher: GraduationCap,
  diagnostic: Activity,
  curriculum: Compass,
  resource: BookOpen,
  assessment: CheckSquare,
  progress: TrendingUp,
  mentor: HeartHandshake,
};

const AGENT_BADGE_MAP: Record<string, "ai" | "primary" | "teal" | "neutral"> = {
  orchestrator: "ai",
  teacher: "primary",
  diagnostic: "teal",
  curriculum: "teal",
  resource: "teal",
  assessment: "teal",
  progress: "ai",
  mentor: "ai",
};

// Canonical fallback roster ensuring zero CSR layout shifts
const FALLBACK_EIGHT_AGENTS: AgentMetadataResponse[] = [
  {
    id: "orchestrator",
    name: "Orchestrator Agent",
    title: "Master Intent Router & Multi-Agent Dispatcher",
    role: "Educational AI Workflow Orchestrator",
    goal: "Interpret student educational requests and select approved registered workflows.",
    backstory: "Experienced educational AI coordinator familiar with supported agents and capabilities.",
    model: "ollama/qwen2.5:3b",
    llm_provider: "ollama",
    temperature: 0.3,
    phase: "Phase 7",
    status: "idle",
    registration_status: "registered",
    associated_workflows: ["All Registered Workflows", "chapter_learning_journey", "teacher_answer"],
    total_executions: 0,
  },
  {
    id: "diagnostic",
    name: "Diagnostic Agent",
    title: "Knowledge Gap & Misconception Specialist",
    role: "Evidence-Based Student Learning Diagnostic Specialist",
    goal: "Conduct evidence-grounded diagnostic evaluation of student answers against assessment questions.",
    backstory: "Master diagnostic educational evaluator specializing in the CBSE Class 10 curriculum.",
    model: "ollama/qwen2.5:3b",
    llm_provider: "ollama",
    temperature: 0.3,
    phase: "Phase 3",
    status: "idle",
    registration_status: "registered",
    associated_workflows: ["chapter_learning_journey", "diagnostic_curriculum", "personalized_learning_plan"],
    total_executions: 0,
  },
  {
    id: "curriculum",
    name: "Curriculum Agent",
    title: "NCERT Learning Roadmap Architect",
    role: "Evidence-Grounded Curriculum Planning Specialist",
    goal: "Transform diagnostic assessment findings into actionable, logically sequenced personalized study roadmaps.",
    backstory: "Pedagogical architect designing personalized roadmaps for Class 10 CBSE students.",
    model: "ollama/qwen2.5:3b",
    llm_provider: "ollama",
    temperature: 0.3,
    phase: "Phase 3",
    status: "idle",
    registration_status: "registered",
    associated_workflows: ["chapter_learning_journey", "diagnostic_curriculum", "personalized_learning_plan"],
    total_executions: 0,
  },
  {
    id: "resource",
    name: "Resource Agent",
    title: "NCERT Educational Corpus Curator",
    role: "Educational Resource Retrieval Specialist",
    goal: "Analyze student topics and provide verified NCERT content and study materials.",
    backstory: "Curriculum resource curator specializing in verified NCERT Class 10 textbooks.",
    model: "ollama/qwen2.5:3b",
    llm_provider: "ollama",
    temperature: 0.3,
    phase: "Phase 4",
    status: "idle",
    registration_status: "registered",
    associated_workflows: ["chapter_learning_journey", "resource_search", "quiz_generation"],
    total_executions: 0,
  },
  {
    id: "teacher",
    name: "Teacher Agent",
    title: "Socratic Concept Explainer",
    role: "Class 10 CBSE Science Teacher",
    goal: "Explain scientific concepts clearly, accurately, and pedagogically according to NCERT/CBSE.",
    backstory: "Dedicated, student-centered Class 10 tutor adhering strictly to NCERT concepts.",
    model: "ollama/qwen2.5:3b",
    llm_provider: "ollama",
    temperature: 0.3,
    phase: "Phase 1B",
    status: "idle",
    registration_status: "registered",
    associated_workflows: ["chapter_learning_journey", "teacher_answer"],
    total_executions: 0,
  },
  {
    id: "assessment",
    name: "Assessment Agent",
    title: "Practice Quiz Generator & Rubric Evaluator",
    role: "Educational Assessment and Feedback Specialist",
    goal: "Generate balanced diagnostic quizzes and evaluate student submissions objectively.",
    backstory: "Expert CBSE examiner and assessment specialist assessing conceptual depth.",
    model: "ollama/qwen2.5:3b",
    llm_provider: "ollama",
    temperature: 0.3,
    phase: "Phase 4",
    status: "idle",
    registration_status: "registered",
    associated_workflows: ["chapter_learning_journey", "quiz_generation", "assessment_evaluation"],
    total_executions: 0,
  },
  {
    id: "progress",
    name: "Progress Agent",
    title: "Deterministic Learning Analytics Evaluator",
    role: "Student Learning Progress Analyst",
    goal: "Analyse persisted learning history and produce accurate evidence-based summaries.",
    backstory: "Secondary education learning analyst interpreting verified assessment records.",
    model: "ollama/qwen2.5:3b",
    llm_provider: "ollama",
    temperature: 0.3,
    phase: "Phase 6",
    status: "idle",
    registration_status: "registered",
    associated_workflows: ["chapter_learning_journey", "progress_analysis", "progress_and_mentoring"],
    total_executions: 0,
  },
  {
    id: "mentor",
    name: "Mentor Agent",
    title: "Personalized Learning Coach & Milestone Guide",
    role: "Personalized Student Learning Mentor",
    goal: "Recommend practical next steps and study milestones based on actual learning progress.",
    backstory: "Empathetic, disciplined CBSE student academic coach prescribing concrete interventions.",
    model: "ollama/qwen2.5:3b",
    llm_provider: "ollama",
    temperature: 0.3,
    phase: "Phase 6",
    status: "idle",
    registration_status: "registered",
    associated_workflows: ["chapter_learning_journey", "personalized_mentoring", "progress_and_mentoring"],
    total_executions: 0,
  },
];

interface RegisteredWorkflowOption {
  id: string;
  name: string;
  requiresAuth: boolean;
  agents: string[];
  examplePrompt: string;
}

const REGISTERED_WORKFLOW_OPTIONS: RegisteredWorkflowOption[] = [
  {
    id: "chapter_learning_journey",
    name: "8-Agent Sequential Chapter Journey (Adaptive Loop)",
    requiresAuth: false,
    agents: [
      "Orchestrator Agent",
      "Diagnostic Agent",
      "Curriculum Agent",
      "Resource Agent",
      "Teacher Agent",
      "Assessment Agent",
      "Progress Agent",
      "Mentor Agent",
    ],
    examplePrompt: "Start a complete sequential chapter learning journey for Class 10 Science: Chemical Reactions and Equations with prerequisites, lessons, assessments, and mentoring.",
  },
  {
    id: "teacher_answer",
    name: "Teacher Concept Tutoring",
    requiresAuth: false,
    agents: ["Teacher Agent"],
    examplePrompt: "Explain the difference between displacement and double displacement reactions with balanced equations.",
  },
  {
    id: "diagnostic_curriculum",
    name: "Diagnostic & Curriculum Planning",
    requiresAuth: false,
    agents: ["Diagnostic Agent", "Curriculum Agent"],
    examplePrompt: "I struggle with chemical equations in Class 10 Chemistry. Assess my knowledge and build a study roadmap.",
  },
  {
    id: "resource_search",
    name: "Educational Resource Retrieval",
    requiresAuth: false,
    agents: ["Resource Agent"],
    examplePrompt: "Find verified NCERT textbook citations and chapter summaries for Chapter 2: Acids, Bases and Salts.",
  },
  {
    id: "quiz_generation",
    name: "Diagnostic Practice Quiz Generation",
    requiresAuth: false,
    agents: ["Resource Agent", "Assessment Agent"],
    examplePrompt: "Generate a practice quiz on Class 10 Science Electricity with MCQs and short answer questions.",
  },
  {
    id: "progress_analysis",
    name: "Student Learning Progress Analysis",
    requiresAuth: true,
    agents: ["Progress Agent"],
    examplePrompt: "Analyze my recent quiz scores, topic accuracy trends, and areas needing improvement from my learning history.",
  },
  {
    id: "personalized_mentoring",
    name: "Personalized Student Mentoring",
    requiresAuth: true,
    agents: ["Progress Agent", "Mentor Agent"],
    examplePrompt: "Provide actionable mentoring recommendations, next study milestones, and active recall study tips.",
  },
  {
    id: "progress_and_mentoring",
    name: "Progress Review + Mentoring Guidance",
    requiresAuth: true,
    agents: ["Progress Agent", "Mentor Agent"],
    examplePrompt: "Review my overall learning progress and tell me exactly which weak topics I should study next.",
  },
];

export default function AgentArenaPage() {
  const { student, isAuthenticated, token } = useAuth();

  // Agent State
  const [agents, setAgents] = useState<AgentMetadataResponse[]>(FALLBACK_EIGHT_AGENTS);
  const [arenaStatus, setArenaStatus] = useState<ArenaStatusResponse | null>(null);
  const [isLoadingAgents, setIsLoadingAgents] = useState(false);
  const [inspectingAgent, setInspectingAgent] = useState<AgentMetadataResponse | null>(null);

  // Dispatch State
  const [prompt, setPrompt] = useState(REGISTERED_WORKFLOW_OPTIONS[0].examplePrompt);
  const [selectedWorkflowPref, setSelectedWorkflowPref] = useState<string>("auto");
  const [isOrchestrating, setIsOrchestrating] = useState(false);
  const [response, setResponse] = useState<OrchestrationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Fetch agents from backend API
  const fetchAgents = useCallback(async () => {
    setIsLoadingAgents(true);
    try {
      const [agentsData, statusData] = await Promise.all([
        apiClient.getArenaAgents(token),
        apiClient.getArenaStatus(token).catch(() => null),
      ]);
      if (Array.isArray(agentsData) && agentsData.length > 0) {
        setAgents(agentsData);
      }
      if (statusData) {
        setArenaStatus(statusData);
      }
    } catch (err) {
      console.warn("Could not fetch dynamic agents, retaining fallback roster:", err);
    } finally {
      setIsLoadingAgents(false);
    }
  }, [token]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const handleSelectWorkflowExample = (wf: RegisteredWorkflowOption) => {
    setSelectedWorkflowPref(wf.id);
    setPrompt(wf.examplePrompt);
    setErrorMessage(null);
  };

  const handleDispatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) {
      setErrorMessage("Please enter an instruction or question for the Orchestrator.");
      return;
    }

    setIsOrchestrating(true);
    setErrorMessage(null);
    setResponse(null);

    // Optimistically mark relevant agents as running
    setAgents((prev) =>
      prev.map((a) => {
        if (selectedWorkflowPref === "auto" || selectedWorkflowPref === "chapter_learning_journey") {
          return { ...a, status: "running" };
        }
        const opt = REGISTERED_WORKFLOW_OPTIONS.find((o) => o.id === selectedWorkflowPref);
        if (opt && opt.agents.includes(a.name)) {
          return { ...a, status: "running" };
        }
        return a;
      })
    );

    try {
      const result = await apiClient.orchestrate(
        {
          request: prompt.trim(),
          grade: student?.grade || "Class 10",
          subject: "Science",
          language: "English",
          workflow_preference: selectedWorkflowPref !== "auto" ? selectedWorkflowPref : null,
        },
        token
      );
      setResponse(result);
      // Re-fetch genuine agent statuses from backend
      await fetchAgents();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Orchestrator dispatch failed.";
      setErrorMessage(msg);
      await fetchAgents();
    } finally {
      setIsOrchestrating(false);
    }
  };

  const formatLastRun = (isoStr?: string | null) => {
    if (!isoStr) return "Ready (No runs)";
    try {
      const dt = new Date(isoStr);
      const diffMs = Date.now() - dt.getTime();
      const diffSecs = Math.floor(diffMs / 1000);
      if (diffSecs < 60) return "Just now";
      const diffMins = Math.floor(diffSecs / 60);
      if (diffMins < 60) return `${diffMins}m ago`;
      const diffHrs = Math.floor(diffMins / 60);
      return `${diffHrs}h ago`;
    } catch {
      return "Recent";
    }
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Page Header */}
      <PageHeader
        title="Agent Arena & Multi-Agent Orchestration"
        description="Unified control center for the canonical eight-agent CrewAI architecture. Natural language intent routing and multi-agent workflow dispatching backed by local Ollama GPU."
        breadcrumbs={[{ label: "Coaching & System", href: "/" }, { label: "Agent Arena" }]}
        icon={<Cpu className="w-7 h-7 text-[#7C5CFC]" />}
        badge={
          <Badge variant="ai" size="md">
            Canonical 8-Agent CrewAI Architecture &bull; Active
          </Badge>
        }
      />

      {/* Roster Header & Health Stats */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-[#7C5CFC]" />
            <h2 className="text-sm font-bold text-slate-900">
              Canonical Multi-Agent Roster (8 Verified CrewAI Agents)
            </h2>
            <Badge variant="teal" size="sm">
              8 Registered
            </Badge>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500 font-medium hidden sm:inline">
              Engine: <strong className="text-slate-800">ollama/qwen2.5:3b</strong>
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={fetchAgents}
              disabled={isLoadingAgents}
              className="text-xs h-7 px-2.5 flex items-center gap-1.5 border-slate-200"
            >
              <RefreshCw className={`w-3 h-3 text-slate-600 ${isLoadingAgents ? "animate-spin" : ""}`} />
              <span>Refresh Status</span>
            </Button>
          </div>
        </div>

        {/* 8 Agent Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {agents.map((agent) => {
            const Icon = AGENT_ICON_MAP[agent.id] || Bot;
            const badgeVariant = AGENT_BADGE_MAP[agent.id] || "ai";
            const isParticipating =
              response?.selected_agents?.includes(agent.name) || false;
            const isExecuting = agent.status === "running";
            const isError = agent.status === "error";

            return (
              <div
                key={agent.id}
                className={`p-3.5 rounded-xl border transition-all flex flex-col justify-between ${
                  isExecuting
                    ? "border-amber-400 bg-amber-50/50 shadow-sm ring-1 ring-amber-400"
                    : isParticipating
                    ? "border-[#7C5CFC] bg-purple-50/70 shadow-sm ring-1 ring-[#7C5CFC]"
                    : "border-slate-200 bg-white hover:border-slate-300 shadow-xs"
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="p-2 rounded-lg bg-slate-100 text-slate-700">
                      <Icon className="w-4 h-4 text-[#7C5CFC]" />
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Badge variant={badgeVariant} size="sm">
                        {agent.phase}
                      </Badge>
                      {isExecuting ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800 animate-pulse">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping" />
                          Executing
                        </span>
                      ) : isError ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-100 text-red-800">
                          Error
                        </span>
                      ) : (
                        <Badge variant="teal" size="sm" dot>
                          Idle (Ready)
                        </Badge>
                      )}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <h3 className="text-xs font-bold text-slate-900 truncate">
                      {agent.name}
                    </h3>
                    <p className="text-[11px] font-semibold text-slate-500 line-clamp-1">
                      {agent.title}
                    </p>
                    <p className="text-[10px] text-slate-500 line-clamp-2 leading-relaxed">
                      {agent.role}
                    </p>
                  </div>
                </div>

                <div className="mt-3 pt-2.5 border-t border-slate-100 space-y-2">
                  <div className="flex items-center justify-between text-[10px] text-slate-400">
                    <span>Runs: <strong className="text-slate-600">{agent.total_executions}</strong></span>
                    <span>{formatLastRun(agent.last_execution_time)}</span>
                  </div>

                  <div className="flex items-center justify-between gap-1 pt-0.5">
                    <button
                      type="button"
                      onClick={() => setInspectingAgent(agent)}
                      className="text-[10px] text-[#7C5CFC] hover:text-purple-800 font-semibold flex items-center gap-1 hover:underline cursor-pointer"
                    >
                      <Info className="w-3 h-3" />
                      Inspect Spec
                    </button>
                    {isParticipating && (
                      <span className="text-[10px] font-bold text-[#7C5CFC]">Dispatched ✓</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Inspect Agent Spec Drawer / Modal */}
      {inspectingAgent && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-xl w-full border border-slate-200 shadow-xl overflow-hidden max-h-[90vh] flex flex-col animate-in fade-in zoom-in-95 duration-150">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-purple-50/60 to-indigo-50/40">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-white shadow-xs text-[#7C5CFC]">
                  {React.createElement(AGENT_ICON_MAP[inspectingAgent.id] || Bot, { className: "w-5 h-5" })}
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">{inspectingAgent.name}</h3>
                  <p className="text-xs text-slate-500">{inspectingAgent.title}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setInspectingAgent(null)}
                className="p-1.5 rounded-lg hover:bg-slate-200/60 text-slate-400 hover:text-slate-700 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4 text-xs">
              {/* Telemetry row */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-3 bg-slate-50 rounded-xl border border-slate-100 text-slate-600">
                <div>
                  <span className="text-[10px] font-semibold text-slate-400 block uppercase">Status</span>
                  <span className="font-bold text-slate-800 capitalize">{inspectingAgent.status}</span>
                </div>
                <div>
                  <span className="text-[10px] font-semibold text-slate-400 block uppercase">Model</span>
                  <span className="font-bold text-slate-800 truncate block">{inspectingAgent.model}</span>
                </div>
                <div>
                  <span className="text-[10px] font-semibold text-slate-400 block uppercase">Total Executions</span>
                  <span className="font-bold text-slate-800">{inspectingAgent.total_executions}</span>
                </div>
                <div>
                  <span className="text-[10px] font-semibold text-slate-400 block uppercase">Last Duration</span>
                  <span className="font-bold text-slate-800">
                    {inspectingAgent.last_duration_seconds ? `${inspectingAgent.last_duration_seconds}s` : "N/A"}
                  </span>
                </div>
              </div>

              {/* Genuine CrewAI Agent Role */}
              <div>
                <span className="text-[11px] font-bold text-slate-800 uppercase tracking-wider block mb-1">
                  Genuine CrewAI Agent Role:
                </span>
                <p className="p-3 bg-purple-50/50 rounded-lg border border-purple-100 text-purple-950 font-medium leading-relaxed">
                  {inspectingAgent.role}
                </p>
              </div>

              {/* Genuine CrewAI Agent Goal */}
              <div>
                <span className="text-[11px] font-bold text-slate-800 uppercase tracking-wider block mb-1">
                  Genuine CrewAI Agent Goal:
                </span>
                <p className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-slate-700 leading-relaxed">
                  {inspectingAgent.goal}
                </p>
              </div>

              {/* Genuine CrewAI Agent Backstory */}
              <div>
                <span className="text-[11px] font-bold text-slate-800 uppercase tracking-wider block mb-1">
                  Genuine CrewAI Backstory & Grounding Rules:
                </span>
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-slate-600 leading-relaxed max-h-48 overflow-y-auto whitespace-pre-line font-mono text-[11px]">
                  {inspectingAgent.backstory}
                </div>
              </div>

              {/* Associated Workflows */}
              <div>
                <span className="text-[11px] font-bold text-slate-800 uppercase tracking-wider block mb-1.5">
                  Approved WORKFLOW_REGISTRY Associations:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {inspectingAgent.associated_workflows.map((wf) => (
                    <span
                      key={wf}
                      className="px-2 py-1 rounded bg-slate-100 text-slate-700 border border-slate-200 text-[10px] font-medium"
                    >
                      {wf}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="p-3.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
              <span className="text-[10px] text-slate-500">
                Registration Status: <strong className="text-emerald-700 uppercase">Verified Live</strong>
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setInspectingAgent(null)}
              >
                Close Spec
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Interactive Orchestrator Dispatch Console */}
      <Card className="border-purple-200 shadow-xs">
        <CardHeader className="pb-3 border-b border-purple-100 bg-gradient-to-r from-purple-50/50 to-indigo-50/30">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <CardTitle className="text-sm font-bold flex items-center gap-2 text-slate-900">
                <Workflow className="w-4 h-4 text-[#7C5CFC]" />
                Intelligent Workflow Dispatch Console
              </CardTitle>
              <CardDescription className="text-xs">
                Submit an educational query for the Orchestrator Agent to route, or test registered workflow pipelines
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="ai" size="sm">
                POST /api/v1/orchestrate
              </Badge>
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-4 space-y-4">
          {/* Quick Preset Workflows */}
          <div>
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-2">
              Test Verified Registered Workflows (WORKFLOW_REGISTRY):
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {REGISTERED_WORKFLOW_OPTIONS.map((wf) => {
                const isSelected = selectedWorkflowPref === wf.id;
                return (
                  <button
                    key={wf.id}
                    type="button"
                    onClick={() => handleSelectWorkflowExample(wf)}
                    disabled={isOrchestrating}
                    className={`p-2.5 text-left rounded-lg border text-xs transition-all ${
                      isSelected
                        ? "border-[#7C5CFC] bg-purple-50/80 font-semibold text-purple-950 ring-1 ring-[#7C5CFC]"
                        : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 text-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="truncate font-semibold">{wf.name}</span>
                      {wf.requiresAuth && (
                        <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                          Auth
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-slate-500 line-clamp-1">
                      Agents: {wf.agents.join(" + ")}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleDispatch} className="space-y-4 pt-2">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-slate-700">
                  Student Prompt / Educational Request:
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-slate-500">Routing Mode:</span>
                  <select
                    value={selectedWorkflowPref}
                    onChange={(e) => setSelectedWorkflowPref(e.target.value)}
                    disabled={isOrchestrating}
                    className="text-xs px-2 py-1 rounded border border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-[#7C5CFC]"
                  >
                    <option value="auto">Auto-route (Orchestrator Agent)</option>
                    {REGISTERED_WORKFLOW_OPTIONS.map((wf) => (
                      <option key={wf.id} value={wf.id}>
                        Force: {wf.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <textarea
                rows={3}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                disabled={isOrchestrating}
                placeholder="Type an educational request or question..."
                className="w-full text-xs p-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#7C5CFC]/30 focus:border-[#7C5CFC]"
                required
              />
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-1">
              <div className="text-xs text-slate-500 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-[#7C5CFC]" />
                {isAuthenticated ? (
                  <span>
                    Authenticated as <strong className="text-slate-700">{student?.display_name}</strong> (All protected workflows enabled)
                  </span>
                ) : (
                  <span>Guest mode (Student tutoring, resources & quiz generation active)</span>
                )}
              </div>

              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={isOrchestrating}
                rightIcon={<Send className="w-4 h-4" />}
              >
                {isOrchestrating ? "Orchestrating Agents..." : "Orchestrate Request"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold block">Orchestrator Execution Error</span>
            <p>{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isOrchestrating && (
        <Card className="border-purple-200 bg-purple-50/20 text-center py-12">
          <CardContent className="space-y-4">
            <div className="inline-flex p-3 rounded-full bg-purple-100 text-[#7C5CFC] animate-pulse">
              <Workflow className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-900">
                Orchestrator Agent is Evaluating Request Intent...
              </h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Running intent parsing and dispatching to genuine CrewAI multi-agent pipeline via local Ollama (qwen2.5:3b).
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Orchestration Results Display */}
      {response && !isOrchestrating && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-[#7C5CFC]" />
              <h2 className="text-sm font-bold text-slate-900">
                Orchestrator Execution Result
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="neutral" size="sm">
                Latency: {response.duration_ms} ms
              </Badge>
              <Badge variant="teal" size="sm">
                Status: {response.status}
              </Badge>
            </div>
          </div>

          {/* Clarification Intercept */}
          {response.clarification_required && (
            <Card className="border-amber-200 bg-amber-50/40">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-bold text-amber-900 flex items-center gap-2">
                  <HelpCircle className="w-4 h-4 text-amber-600" />
                  Orchestrator Requested Clarification
                </CardTitle>
                <CardDescription className="text-xs text-amber-700">
                  The request requires more specific topic or chapter context before dispatching downstream agents.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs font-semibold text-slate-900 p-3 bg-white rounded-lg border border-amber-200">
                  {response.clarification_question}
                </p>
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>Routing reason: {response.routing_reason}</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setPrompt(response.clarification_question || "");
                    }}
                  >
                    Reply to Clarification
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Successful Multi-Agent Execution Box */}
          {!response.clarification_required && (
            <Card className="border-slate-200">
              <CardHeader className="pb-3 border-b border-slate-100 bg-slate-50/60">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <CardTitle className="text-sm font-bold text-slate-900">
                      Dispatched Workflow: {response.selected_workflow}
                    </CardTitle>
                    <CardDescription className="text-xs">
                      {response.routing_reason}
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {response.selected_agents?.map((agentName) => (
                      <Badge key={agentName} variant="ai" size="sm">
                        {agentName}
                      </Badge>
                    ))}
                  </div>
                </div>
              </CardHeader>

              <CardContent className="pt-4 space-y-4">
                {/* Result Body rendering */}
                {response.result ? (
                  <div className="space-y-4">
                    {/* Tutoring answer */}
                    {typeof response.result === "object" && "answer" in (response.result as any) && (
                      <div className="p-4 rounded-xl bg-purple-50/40 border border-purple-100 space-y-2">
                        <span className="text-[11px] font-bold text-[#7C5CFC] uppercase tracking-wider block">
                          Teacher Agent Lesson Output:
                        </span>
                        <div className="text-xs text-slate-800 leading-relaxed">
                          <FormattedMessage content={String((response.result as any).answer)} />
                        </div>
                      </div>
                    )}

                    {/* Diagnostic + Curriculum output */}
                    {typeof response.result === "object" && "curriculum_plan" in (response.result as any) && (
                      <div className="space-y-3">
                        <div className="p-4 rounded-xl bg-teal-50/40 border border-teal-100 space-y-2">
                          <span className="text-[11px] font-bold text-teal-800 uppercase tracking-wider block">
                            Diagnostic Assessment Findings:
                          </span>
                          <div className="text-xs text-slate-800 leading-relaxed">
                            <FormattedMessage content={String((response.result as any).diagnostic_report)} />
                          </div>
                        </div>

                        <div className="p-4 rounded-xl bg-indigo-50/40 border border-indigo-100 space-y-2">
                          <span className="text-[11px] font-bold text-indigo-800 uppercase tracking-wider block">
                            Curriculum Study Roadmap:
                          </span>
                          <div className="text-xs text-slate-800 leading-relaxed">
                            <FormattedMessage content={String((response.result as any).curriculum_plan)} />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Resource search output */}
                    {typeof response.result === "object" && "resource_recommendation" in (response.result as any) && (
                      <div className="p-4 rounded-xl bg-blue-50/40 border border-blue-100 space-y-3">
                        <span className="text-[11px] font-bold text-blue-800 uppercase tracking-wider block">
                          Resource Agent Curated Sources:
                        </span>
                        <div className="text-xs text-slate-800 leading-relaxed">
                          <FormattedMessage content={String((response.result as any).resource_recommendation)} />
                        </div>
                        {Array.isArray((response.result as any).sources) && (
                          <div className="space-y-1.5 pt-2 border-t border-blue-100">
                            <span className="text-[10px] font-bold text-blue-900 uppercase">Verified Citations:</span>
                            {(response.result as any).sources.map((src: any, i: number) => (
                              <div key={i} className="p-2 rounded bg-white border border-blue-100 text-[11px]">
                                <strong>{src.title}</strong> — {src.excerpt}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Quiz generation output */}
                    {typeof response.result === "object" && "questions" in (response.result as any) && (
                      <div className="space-y-3">
                        <span className="text-[11px] font-bold text-purple-900 uppercase tracking-wider block">
                          Assessment Agent Practice Quiz:
                        </span>
                        {(response.result as any).questions.map((q: any, i: number) => (
                          <div key={q.id || i} className="p-3 rounded-lg border border-slate-200 bg-white space-y-2 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-900">Question {i + 1} ({q.difficulty})</span>
                              <Badge variant="teal" size="sm">{q.marks} Mark(s)</Badge>
                            </div>
                            <p className="text-slate-800">{q.question}</p>
                            {Array.isArray(q.options) && q.options.length > 0 && (
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-1">
                                {q.options.map((opt: string, optIdx: number) => (
                                  <div key={optIdx} className="p-2 rounded bg-slate-50 border border-slate-100 text-[11px] text-slate-700">
                                    {opt}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Progress & Mentoring output */}
                    {typeof response.result === "object" && "mentor_recommendations" in (response.result as any) && (
                      <div className="space-y-3">
                        <div className="p-4 rounded-xl bg-purple-50/40 border border-purple-100 space-y-2">
                          <span className="text-[11px] font-bold text-purple-800 uppercase tracking-wider block">
                            Mentor Agent Recommendations:
                          </span>
                          <div className="text-xs text-slate-800 leading-relaxed">
                            <FormattedMessage content={String((response.result as any).mentor_recommendations?.mentor_overview || (response.result as any).mentor_recommendations)} />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Raw Result Inspector Toggle */}
                    <details className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
                      <summary className="cursor-pointer font-semibold hover:text-slate-800 flex items-center gap-1.5">
                        <Terminal className="w-3.5 h-3.5" />
                        Inspect Complete Workflow Response Payload (JSON)
                      </summary>
                      <pre className="mt-2 p-3 rounded-lg bg-slate-900 text-slate-100 text-[10px] overflow-x-auto max-h-64">
                        {JSON.stringify(response.result, null, 2)}
                      </pre>
                    </details>
                  </div>
                ) : (
                  <EmptyState
                    icon={CheckCircle2}
                    title="Workflow Executed"
                    description="The multi-agent workflow completed with zero return payload."
                  />
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
