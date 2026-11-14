"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  GraduationCap,
  Send,
  Sparkles,
  RefreshCw,
  AlertCircle,
  Clock,
  Cpu,
  ShieldCheck,
  RotateCcw,
  BookOpen,
  ArrowRight,
  HelpCircle,
  CheckCircle2,
  Lightbulb,
  Layers,
  ChevronDown,
  Compass,
  Maximize2,
  Minimize2,
  Square,
  X,
} from "lucide-react";
import { PageHeader } from "../../components/ui/PageHeader";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { FormattedMessage } from "../../components/ui/FormattedMessage";
import { useBackendHealth } from "../../components/layout/AppShell";
import { apiClient } from "../../lib/api";
import {
  ChatMessage,
  AskResponse,
  CurriculumSubjectResponse,
  CurriculumChapterSummary,
  CurriculumTopicSummary,
} from "../../types";

const suggestedPrompts = [
  {
    title: "Magnesium Combustion",
    prompt: "What happens when magnesium ribbon burns in air? Give the balanced chemical equation and describe the observation.",
    subject: "Science",
    chapter: "Chemical Reactions and Equations",
    agent: "Teacher Agent",
  },
  {
    title: "Electricity Practice Quiz",
    prompt: "Create a 5-question practice test on Ohm's law, resistance, and electric circuits.",
    subject: "Science",
    chapter: "Electricity",
    agent: "Assessment Agent",
  },
  {
    title: "CBSE Syllabus Roadmap",
    prompt: "Show me the CBSE Class 10 Science curriculum roadmap, prerequisites, and learning objectives.",
    subject: "Science",
    chapter: "Life Processes",
    agent: "Curriculum Agent",
  },
  {
    title: "30-Day Revision Strategy",
    prompt: "Create a 30-day revision timetable and study strategy for CBSE Class 10 board exams.",
    subject: "Science",
    chapter: "Acids, Bases and Salts",
    agent: "Mentor Agent",
  },
  {
    title: "NCERT Study Notes",
    prompt: "Find verified NCERT study resources, textbook references, and notes for Metals and Non-metals.",
    subject: "Science",
    chapter: "Metals and Non-metals",
    agent: "Resource Agent",
  },
  {
    title: "Diagnostic Gap Analysis",
    prompt: "Analyse my understanding: I think rust is just iron oxide without water. Where did I go wrong?",
    subject: "Science",
    chapter: "Chemical Reactions and Equations",
    agent: "Diagnostic Agent",
  },
];

function TeacherStudioContent() {
  const searchParams = useSearchParams();
  const { health, loading: healthLoading } = useBackendHealth();

  // Chat State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [lastFailedPrompt, setLastFailedPrompt] = useState<string | null>(null);
  const [isContextExpanded, setIsContextExpanded] = useState<boolean>(false);

  // Focus Mode State
  const [isFocusMode, setIsFocusMode] = useState<boolean>(false);

  // Curriculum State
  const [subjects, setSubjects] = useState<CurriculumSubjectResponse[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>("subj_science_086");
  const [chapters, setChapters] = useState<CurriculumChapterSummary[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState<string>("");
  const [topics, setTopics] = useState<CurriculumTopicSummary[]>([]);
  const [selectedTopicId, setSelectedTopicId] = useState<string>("");
  const [lessonMode, setLessonMode] = useState<string>("conceptual");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const focusTextareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load Curriculum Subjects
  useEffect(() => {
    async function loadSubjects() {
      try {
        const subjs = await apiClient.getCurriculumSubjects();
        setSubjects(subjs);

        const qSubj = searchParams.get("subject");
        if (qSubj) {
          const match = subjs.find(
            (s) =>
              s.id === qSubj ||
              s.name.toLowerCase() === qSubj.toLowerCase() ||
              s.short_name?.toLowerCase() === qSubj.toLowerCase()
          );
          if (match) setSelectedSubjectId(match.id);
        }
      } catch (err) {
        console.error("Failed to load subjects for teacher studio:", err);
      }
    }
    loadSubjects();
  }, [searchParams]);

  // Load Chapters when Subject changes
  useEffect(() => {
    if (!selectedSubjectId) return;

    async function loadChapters() {
      try {
        const chaps = await apiClient.getSubjectChapters(selectedSubjectId);
        setChapters(chaps);

        const qChap = searchParams.get("chapter");
        if (qChap) {
          const match = chaps.find(
            (c) => c.id === qChap || c.title.toLowerCase() === qChap.toLowerCase()
          );
          if (match) {
            setSelectedChapterId(match.id);
            return;
          }
        }
        if (chaps.length > 0) {
          setSelectedChapterId(chaps[0].id);
        } else {
          setSelectedChapterId("");
        }
      } catch (err) {
        console.error("Failed to load chapters:", err);
      }
    }
    loadChapters();
  }, [selectedSubjectId, searchParams]);

  // Load Topics when Chapter changes
  useEffect(() => {
    if (!selectedChapterId) {
      setTopics([]);
      setSelectedTopicId("");
      return;
    }

    async function loadTopics() {
      try {
        const tops = await apiClient.getChapterTopics(selectedChapterId);
        setTopics(tops);

        const qTop = searchParams.get("topic");
        if (qTop) {
          const match = tops.find(
            (t) => t.id === qTop || t.title.toLowerCase() === qTop.toLowerCase()
          );
          if (match) {
            setSelectedTopicId(match.id);
            return;
          }
        }
        if (tops.length > 0) {
          setSelectedTopicId(tops[0].id);
        } else {
          setSelectedTopicId("");
        }
      } catch (err) {
        console.error("Failed to load topics:", err);
      }
    }
    loadTopics();
  }, [selectedChapterId, searchParams]);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSubmitting]);

  // Handle textarea resize
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const activeRef = isFocusMode ? focusTextareaRef.current : textareaRef.current;
    if (activeRef) {
      activeRef.style.height = "auto";
      activeRef.style.height = `${Math.min(activeRef.scrollHeight, 160)}px`;
    }
  };

  // Keyboard shortcut listener for Focus Mode Escape key exit
  useEffect(() => {
    const handleEscapeKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFocusMode) {
        setIsFocusMode(false);
      }
    };
    window.addEventListener("keydown", handleEscapeKey);
    return () => window.removeEventListener("keydown", handleEscapeKey);
  }, [isFocusMode]);

  // Abort on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const currentSubject = subjects.find((s) => s.id === selectedSubjectId);
  const currentChapter = chapters.find((c) => c.id === selectedChapterId);
  const currentTopic = topics.find((t) => t.id === selectedTopicId);

  // Cancel in-flight question
  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsSubmitting(false);
  };

  // Send message
  const handleSend = async (textToSend?: string) => {
    const questionText = (textToSend || input).trim();
    if (!questionText || isSubmitting) return;

    if (questionText.length < 3) {
      alert("Please enter a question with at least 3 characters.");
      return;
    }

    const studentMessage: ChatMessage = {
      id: `msg-${Date.now()}-student`,
      sender: "student",
      text: questionText,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, studentMessage]);
    setInput("");
    setLastFailedPrompt(null);
    setIsSubmitting(true);

    if (textareaRef.current) textareaRef.current.style.height = "auto";
    if (focusTextareaRef.current) focusTextareaRef.current.style.height = "auto";

    abortControllerRef.current = new AbortController();

    try {
      const response: AskResponse = await apiClient.askTeacher(
        {
          question: questionText,
          grade: "Class 10",
          subject: currentSubject ? currentSubject.name : "Science",
          chapter: currentChapter ? currentChapter.title : undefined,
          topic: currentTopic ? currentTopic.title : undefined,
          lesson_mode: lessonMode,
          language: "English",
        },
        undefined,
        {
          signal: abortControllerRef.current.signal,
          timeoutMs: 75000,
        }
      );

      const agentDisplayName =
        response.agent_name ||
        (response.selected_agents && response.selected_agents.length > 0
          ? response.selected_agents.join(", ")
          : "Teacher Agent");

      const responseMessage: ChatMessage = {
        id: `msg-${Date.now()}-ai`,
        sender: "teacher",
        text: response.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        metadata: {
          requestId: response.request_id,
          model: response.model,
          durationMs: response.duration_ms,
          agentName: agentDisplayName,
          status: response.status,
          workflowExecuted: response.workflow_executed,
          detectedIntent: response.detected_intent,
        },
      };

      setMessages((prev) => [...prev, responseMessage]);
    } catch (err: unknown) {
      const isAbort =
        err instanceof Error &&
        (err.name === "AbortError" ||
          err.message.includes("cancelled") ||
          err.message.includes("timed out"));

      const errorMsg = isAbort
        ? "Question was stopped or timed out after 75 seconds. Local Ollama may be busy with another task."
        : err instanceof Error
        ? err.message
        : "Failed to obtain response from AI Learning Agents.";

      setLastFailedPrompt(questionText);

      const errorMessage: ChatMessage = {
        id: `msg-${Date.now()}-error`,
        sender: "teacher",
        text: `Error contacting AI Learning Agents: ${errorMsg}\n\nPlease verify that local Ollama is active on port 11434 with qwen2.5:3b.`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        isError: true,
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      abortControllerRef.current = null;
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearChat = () => {
    if (window.confirm("Clear the current tutoring conversation?")) {
      setMessages([]);
      setLastFailedPrompt(null);
    }
  };

  // Shared Message List Component
  const renderMessageList = () => {
    if (messages.length === 0) {
      return (
        <div className="h-full flex flex-col items-center justify-center text-center max-w-2xl mx-auto py-6">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 text-[#2563EB] flex items-center justify-center mb-3 shadow-xs">
            <GraduationCap className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-bold text-[#172033] mb-1">
            AI Multi-Agent Studio — {currentSubject?.name || "CBSE Class 10"}
          </h2>
          <p className="text-xs text-[#64748B] max-w-md leading-relaxed mb-4">
            Ask any question freely. Gyaan AI&apos;s Orchestrator interprets your intent and coordinates the designated CrewAI specialist agent (Teacher, Assessment, Curriculum, Diagnostic, Resource, Progress, or Mentor) to assist you.
          </p>

          <div className="w-full space-y-2 text-left">
            <span className="text-xs font-semibold text-[#64748B] uppercase tracking-wider block px-1">
              Try asking about this syllabus:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {suggestedPrompts.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSend(item.prompt)}
                  className="p-3 text-left rounded-xl border border-slate-200 hover:border-blue-300 hover:bg-blue-50/40 transition-all group flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between w-full mb-1">
                    <span className="font-semibold text-xs text-[#172033] group-hover:text-[#2563EB]">
                      {item.title}
                    </span>
                    <span className="text-[10px] text-slate-400 px-1.5 py-0.5 rounded bg-slate-100">
                      {item.subject}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#64748B] line-clamp-2 leading-relaxed">
                    {item.prompt}
                  </p>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-6 flex items-center gap-2 text-xs text-slate-400">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>100% Genuine Local Inference &bull; Verified CBSE 2026-27 Syllabus</span>
          </div>
        </div>
      );
    }

    return (
      <>
        {messages.map((msg) => {
          const isStudent = msg.sender === "student";

          return (
            <div
              key={msg.id}
              className={`flex flex-col ${isStudent ? "items-end" : "items-start"}`}
            >
              <div className="flex items-center gap-1.5 text-[11px] text-[#64748B] mb-1 px-1">
                {isStudent ? (
                  <>
                    <span>{msg.timestamp}</span>
                    <span className="font-semibold text-[#172033]">You (Student)</span>
                  </>
                ) : (
                  <>
                    <span className="font-semibold text-[#2563EB] flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-[#7C5CFC]" />
                      {msg.metadata?.agentName || "Gyaan AI Specialist"}
                    </span>
                    <span>&bull;</span>
                    <span>{msg.timestamp}</span>
                  </>
                )}
              </div>

              <div
                className={`max-w-[88%] sm:max-w-[82%] rounded-2xl p-4 sm:p-5 shadow-xs transition-all ${
                  isStudent
                    ? "bg-[#2563EB] text-white rounded-tr-xs"
                    : msg.isError
                    ? "bg-red-50 border border-red-200 text-red-900 rounded-tl-xs"
                    : "bg-[#F8FAFC] border border-[#E2E8F0] text-[#172033] rounded-tl-xs"
                }`}
              >
                {isStudent ? (
                  <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                ) : msg.isError ? (
                  <div className="space-y-3">
                    <div className="flex items-start gap-2 text-xs text-red-800">
                      <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                      <div className="whitespace-pre-wrap font-sans leading-relaxed">
                        {msg.text}
                      </div>
                    </div>
                    {lastFailedPrompt && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-red-300 text-red-700 hover:bg-red-100"
                        onClick={() => handleSend(lastFailedPrompt)}
                        leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                      >
                        Retry Question
                      </Button>
                    )}
                  </div>
                ) : (
                  <FormattedMessage content={msg.text} />
                )}

                {!isStudent && !msg.isError && msg.metadata && (
                  <div className="mt-3 pt-3 border-t border-slate-200/80 flex flex-wrap items-center justify-between gap-2 text-[10px] text-[#64748B]">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-700">
                        {msg.metadata.agentName || "Gyaan AI Specialist"}
                      </span>
                      <span>&bull;</span>
                      <span className="font-medium text-slate-500">Private Local AI</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {msg.metadata.durationMs !== undefined && (
                        <span className="flex items-center gap-1 font-mono">
                          <Clock className="w-3 h-3 text-slate-400" />
                          {(msg.metadata.durationMs / 1000).toFixed(1)}s
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {isSubmitting && (
          <div className="flex flex-col items-start space-y-1">
            <div className="flex items-center gap-1.5 text-[11px] text-[#64748B] mb-1 px-1">
              <span className="font-semibold text-[#2563EB] flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-[#7C5CFC]" />
                AI Study Companion
              </span>
              <span>&bull;</span>
              <span>Formulating response...</span>
            </div>

            <div className="max-w-[85%] rounded-2xl rounded-tl-xs p-4 sm:p-5 bg-blue-50/60 border border-blue-200 text-[#172033] shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-4 h-4 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin shrink-0" />
                  <span className="text-xs font-semibold text-[#2563EB]">
                    AI Tutor is thinking...
                  </span>
                </div>
                <button
                  onClick={handleCancel}
                  className="px-2 py-0.5 rounded text-[11px] font-medium bg-red-100 text-red-700 hover:bg-red-200 flex items-center gap-1 transition-colors"
                >
                  <Square className="w-3 h-3 fill-current" />
                  <span>Stop</span>
                </button>
              </div>
              <p className="text-xs text-[#64748B] leading-relaxed">
                Analyzing your question against CBSE curriculum standards and preparing a step-by-step Socratic explanation...
              </p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </>
    );
  };

  // Shared Composer Component
  const renderComposer = (isFocus: boolean) => (
    <div className={`space-y-2 ${isFocus ? "" : "p-3 sm:p-4 bg-slate-50/90 border-t border-[#E2E8F0] shrink-0"}`}>
      {/* Quick Action Chips for the selected topic */}
      {currentTopic && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex-shrink-0">
            Quick Prompts:
          </span>
          <button
            onClick={() => handleSend(`Explain the core concept of "${currentTopic.title}" in detail.`)}
            disabled={isSubmitting}
            className="px-2.5 py-1 rounded-md bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50 text-slate-700 text-[11px] flex-shrink-0 transition-all shadow-2xs"
          >
            Explain &ldquo;{currentTopic.title}&rdquo;
          </button>
          <button
            onClick={() => handleSend(`Give two real-world Indian examples illustrating "${currentTopic.title}".`)}
            disabled={isSubmitting}
            className="px-2.5 py-1 rounded-md bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50 text-slate-700 text-[11px] flex-shrink-0 transition-all shadow-2xs"
          >
            Real-World Examples
          </button>
          <button
            onClick={() => handleSend(`Provide a step-by-step solved CBSE board exam question on "${currentTopic.title}".`)}
            disabled={isSubmitting}
            className="px-2.5 py-1 rounded-md bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50 text-slate-700 text-[11px] flex-shrink-0 transition-all shadow-2xs"
          >
            Solved Question
          </button>
          <button
            onClick={() => handleSend(`What are the common board exam mistakes and misconceptions students make in "${currentTopic.title}"?`)}
            disabled={isSubmitting}
            className="px-2.5 py-1 rounded-md bg-white border border-slate-200 hover:border-rose-300 hover:bg-rose-50 text-slate-700 text-[11px] flex-shrink-0 transition-all shadow-2xs"
          >
            Common Pitfalls
          </button>
        </div>
      )}

      {/* Multiline Composer Form */}
      <div className="flex items-end gap-2 bg-white rounded-xl border border-[#E2E8F0] p-2 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-all shadow-2xs">
        <textarea
          ref={isFocus ? focusTextareaRef : textareaRef}
          rows={1}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          disabled={isSubmitting}
          placeholder="Ask any CBSE Class 10 question freely (e.g. Explain Ohm's law, Create 5-question test, 30-day revision plan)..."
          className="flex-1 max-h-36 resize-none bg-transparent px-2 py-1.5 text-sm text-[#172033] placeholder:text-slate-400 focus:outline-none disabled:opacity-50"
        />

        {isSubmitting ? (
          <Button
            variant="outline"
            size="sm"
            onClick={handleCancel}
            aria-label="Stop generation"
            className="h-9 px-3 shrink-0 text-red-600 border-red-200 hover:bg-red-50"
          >
            <Square className="w-4 h-4 fill-current" />
          </Button>
        ) : (
          <Button
            variant="primary"
            size="sm"
            disabled={input.trim().length === 0}
            onClick={() => handleSend()}
            aria-label="Send question"
            className="h-9 px-3 shrink-0"
          >
            <Send className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* ─────────────────────────────────────────────────────────────
          1. STANDARD MODE
      ───────────────────────────────────────────────────────────── */}
      <div className="w-full max-w-5xl mx-auto flex flex-col h-[calc(100vh-6.5rem)] sm:h-[calc(100vh-7.5rem)] lg:h-[calc(100vh-8.5rem)] min-h-0 overflow-hidden">
        {/* Header & Quick Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 pb-2.5 mb-2 shrink-0 border-b border-slate-200/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200 text-[#2563EB] flex items-center justify-center shrink-0">
              <GraduationCap className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-sm sm:text-base font-bold text-slate-900 leading-tight">
                AI Study Companion & Socratic Tutor
              </h1>
              <p className="text-[11px] text-slate-500">
                Interactive CBSE Class 10 Learning &bull; {currentSubject?.name || "Science"} {currentChapter ? `› Ch ${currentChapter.chapter_number}` : ""}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <button
              onClick={() => setIsFocusMode(true)}
              className="text-xs text-indigo-700 hover:text-indigo-800 px-2.5 py-1 rounded-md border border-indigo-200 bg-indigo-50/70 hover:bg-indigo-100 flex items-center gap-1.5 font-medium transition-colors shadow-2xs"
              title="Enter distraction-free fullscreen study mode"
            >
              <Maximize2 className="w-3.5 h-3.5" />
              <span>Focus Mode</span>
            </button>

            <button
              onClick={() => setIsContextExpanded((v) => !v)}
              className="text-xs text-blue-600 hover:text-blue-700 px-2.5 py-1 rounded-md border border-blue-200 bg-blue-50/50 flex items-center gap-1 font-medium transition-colors shadow-2xs"
            >
              <Compass className="w-3.5 h-3.5" />
              <span>{isContextExpanded ? "Hide Context" : "Curriculum Context"}</span>
              <ChevronDown className={`w-3 h-3 transition-transform ${isContextExpanded ? "rotate-180" : ""}`} />
            </button>

            {messages.length > 0 && (
              <button
                onClick={handleClearChat}
                className="text-xs text-slate-500 hover:text-red-600 px-2 py-1 rounded-md border border-slate-200 hover:bg-slate-50 transition-colors flex items-center gap-1"
                title="Clear current tutoring session"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Clear</span>
              </button>
            )}
          </div>
        </div>

        {/* Collapsible Curriculum Context Control Strip */}
        {isContextExpanded && (
          <div className="bg-slate-50/90 border border-slate-200 rounded-xl p-2.5 mb-2.5 space-y-2 shrink-0 animate-in fade-in duration-150">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {/* Subject Selector */}
              <div>
                <label className="block text-[10px] font-bold uppercase text-slate-500 mb-0.5">Subject</label>
                <select
                  value={selectedSubjectId}
                  onChange={(e) => setSelectedSubjectId(e.target.value)}
                  className="w-full text-xs font-semibold bg-white border border-slate-300 rounded-lg px-2 py-1 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.code})
                    </option>
                  ))}
                </select>
              </div>

              {/* Chapter Selector */}
              <div>
                <label className="block text-[10px] font-bold uppercase text-slate-500 mb-0.5">Prescribed Chapter</label>
                <select
                  value={selectedChapterId}
                  onChange={(e) => setSelectedChapterId(e.target.value)}
                  disabled={chapters.length === 0}
                  className="w-full text-xs font-semibold bg-white border border-slate-300 rounded-lg px-2 py-1 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-60"
                >
                  {chapters.map((c) => (
                    <option key={c.id} value={c.id}>
                      Ch {c.chapter_number}: {c.title}
                    </option>
                  ))}
                </select>
              </div>

              {/* Topic Selector */}
              <div>
                <label className="block text-[10px] font-bold uppercase text-slate-500 mb-0.5">Target Topic</label>
                <select
                  value={selectedTopicId}
                  onChange={(e) => setSelectedTopicId(e.target.value)}
                  disabled={topics.length === 0}
                  className="w-full text-xs font-semibold bg-white border border-slate-300 rounded-lg px-2 py-1 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-60"
                >
                  {topics.map((t) => (
                    <option key={t.id} value={t.id}>
                      Topic {t.topic_number}: {t.title}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Pedagogical Lesson Mode Selector */}
            <div className="flex items-center gap-1.5 pt-1 border-t border-slate-200/60 overflow-x-auto">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex-shrink-0">
                Mode:
              </span>
              {[
                { id: "conceptual", label: "Conceptual Deep-Dive" },
                { id: "simplified", label: "Explain Simpler (ELI10)" },
                { id: "real_world", label: "Real-World Examples" },
                { id: "practice", label: "Practice Problem" },
                { id: "doubt_clearing", label: "Clear Doubts" },
              ].map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => setLessonMode(mode.id)}
                  className={`text-[11px] px-2 py-0.5 rounded font-medium transition-all flex-shrink-0 ${
                    lessonMode === mode.id
                      ? "bg-blue-600 text-white font-semibold shadow-2xs"
                      : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Main Conversation Canvas (Standard Mode) */}
        <div className="flex-1 bg-white rounded-2xl border border-[#E2E8F0] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
            {renderMessageList()}
          </div>
          {renderComposer(false)}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          2. FOCUS MODE (Distraction-Free Immersion Overlay)
      ───────────────────────────────────────────────────────────── */}
      {isFocusMode && (
        <div className="fixed inset-0 z-50 bg-[#F8FAFC] flex flex-col overflow-hidden animate-in fade-in duration-200">
          {/* Minimal 48px Header */}
          <div className="h-12 px-4 sm:px-6 bg-white/95 backdrop-blur-md border-b border-slate-200 flex items-center justify-between shrink-0 shadow-2xs">
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-lg bg-blue-50 border border-blue-200 text-[#2563EB] flex items-center justify-center shrink-0">
                <GraduationCap className="w-4 h-4" />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs sm:text-sm font-bold text-slate-900">
                  Focus Studio
                </span>
                <span className="text-slate-300">&bull;</span>
                <span className="text-[11px] text-slate-600 font-medium">
                  {currentSubject?.name || "Science"} {currentChapter ? `› Ch ${currentChapter.chapter_number}` : ""} {currentTopic ? `› ${currentTopic.title}` : ""}
                </span>
                <Badge variant="teal" size="sm">
                  {lessonMode}
                </Badge>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Badge variant="teal" size="sm">
                <Cpu className="w-3 h-3 mr-1 text-[#0F9F9A]" />
                Local Ollama qwen2.5:3b
              </Badge>

              {messages.length > 0 && (
                <button
                  onClick={handleClearChat}
                  className="text-xs text-slate-500 hover:text-red-600 px-2 py-1 rounded-md border border-slate-200 hover:bg-slate-50 transition-colors flex items-center gap-1"
                  title="Clear conversation"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Clear</span>
                </button>
              )}

              <button
                onClick={() => setIsFocusMode(false)}
                className="text-xs text-slate-700 hover:text-slate-900 px-2.5 py-1 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 flex items-center gap-1.5 font-medium shadow-2xs transition-all"
                title="Exit Focus Mode (or press Esc)"
              >
                <Minimize2 className="w-3.5 h-3.5" />
                <span>Exit Focus (Esc)</span>
              </button>
            </div>
          </div>

          {/* Reading Canvas in Focus Mode */}
          <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 space-y-6 w-full max-w-3xl mx-auto">
            {renderMessageList()}
          </div>

          {/* Floating Docked Composer in Focus Mode */}
          <div className="shrink-0 w-full max-w-3xl mx-auto px-4 pb-4 pt-1">
            {renderComposer(true)}
          </div>
        </div>
      )}
    </>
  );
}

export default function TeacherStudioPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center text-slate-400">
          Loading AI Teacher Studio...
        </div>
      }
    >
      <TeacherStudioContent />
    </Suspense>
  );
}
