"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Library,
  BookOpen,
  Search,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  FileText,
  Bookmark,
  Cpu,
  Clock,
  ArrowRight,
  ShieldCheck,
  GraduationCap,
  CheckSquare,
  Layers,
  ChevronRight,
} from "lucide-react";
import { PageHeader } from "../../components/ui/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { FormattedMessage } from "../../components/ui/FormattedMessage";
import { EmptyState } from "../../components/ui/EmptyState";
import { useAuth } from "../../components/auth/AuthContext";
import { apiClient } from "../../lib/api";
import { ResourceRequest, ResourceResponse, ResourceSourceItem } from "../../types";

interface TopicPreset {
  subject: string;
  topic: string;
  chapter: string;
  objective: string;
}

const ncertPresets: TopicPreset[] = [
  {
    subject: "Science",
    topic: "Acids, Bases and Salts",
    chapter: "Chapter 2",
    objective: "Understand chemical properties of acids, bases, neutralization, and the pH scale.",
  },
  {
    subject: "Science",
    topic: "Chemical Reactions and Equations",
    chapter: "Chapter 1",
    objective: "Master displacement, combination, and redox reactions with balanced chemical equations.",
  },
  {
    subject: "Science",
    topic: "Metals and Non-metals",
    chapter: "Chapter 3",
    objective: "Explore physical/chemical properties, reactivity series, and ionic compound formation.",
  },
  {
    subject: "Science",
    topic: "Life Processes",
    chapter: "Chapter 6",
    objective: "Study autotrophic nutrition, cellular respiration, and human excretory system.",
  },
  {
    subject: "Science",
    topic: "Electricity",
    chapter: "Chapter 12",
    objective: "Understand Ohm's law, series/parallel resistance combinations, and Joule's heating effect.",
  },
];

function ResourcesContent() {
  const searchParams = useSearchParams();
  const initialSubject = searchParams.get("subject") || "Science";
  const initialTopic = searchParams.get("topic") || "Acids, Bases and Salts";

  const { student, isAuthenticated, token } = useAuth();

  const [grade, setGrade] = useState("Class 10");
  const [subject, setSubject] = useState(initialSubject);
  const [topic, setTopic] = useState(initialTopic);
  const [learningObjective, setLearningObjective] = useState(ncertPresets[0].objective);

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ResourceResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSelectPreset = (preset: TopicPreset) => {
    setSubject(preset.subject);
    setTopic(preset.topic);
    setLearningObjective(preset.objective);
    setErrorMessage(null);
  };

  const handleFetchResources = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!topic.trim()) {
      setErrorMessage("Please enter a valid study topic.");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await apiClient.getResources(
        {
          grade: grade.trim() || "Class 10",
          subject: subject.trim(),
          topic: topic.trim(),
          learning_objective: learningObjective.trim() || undefined,
        },
        token
      );
      setResult(response);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to retrieve educational resources.";
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <PageHeader
        title="NCERT Educational Resources"
        description="Curated textbook chapters, official NCERT exercise guides, and verified educational references retrieved and analyzed by the CrewAI Resource Agent."
        breadcrumbs={[{ label: "Assessment & Resources", href: "/" }, { label: "Resources" }]}
        icon={<Library className="w-7 h-7 text-[#0F9F9A]" />}
        badge={
          <Badge variant="teal" size="md">
            NCERT Verified Study Materials
          </Badge>
        }
      />

      {/* Preset Topics Bar */}
      <div className="space-y-2">
        <span className="text-xs font-semibold text-[#64748B] uppercase tracking-wider block">
          Select an NCERT Class 10 Science Chapter Preset:
        </span>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {ncertPresets.map((preset, idx) => {
            const isSelected = topic.toLowerCase() === preset.topic.toLowerCase();
            return (
              <button
                key={idx}
                type="button"
                onClick={() => handleSelectPreset(preset)}
                disabled={isLoading}
                className={`p-3 text-left rounded-xl border transition-all ${
                  isSelected
                    ? "border-[#0F9F9A] bg-teal-50/70 shadow-xs ring-1 ring-[#0F9F9A]"
                    : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-slate-800 truncate">
                    {preset.topic}
                  </span>
                  <Badge variant={isSelected ? "teal" : "neutral"} size="sm">
                    {preset.chapter}
                  </Badge>
                </div>
                <p className="text-[11px] text-slate-500 line-clamp-1">
                  {preset.objective}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Search / Topic Form */}
      <Card>
        <CardHeader className="pb-3 border-b border-slate-100">
          <CardTitle className="text-sm font-semibold flex items-center gap-2 text-slate-800">
            <Search className="w-4 h-4 text-[#0F9F9A]" />
            Resource Query Parameters
          </CardTitle>
          <CardDescription className="text-xs">
            Query the verified NCERT corpus or search custom academic curriculum units
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <form onSubmit={handleFetchResources} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Grade / Class
                </label>
                <input
                  type="text"
                  value={grade}
                  onChange={(e) => setGrade(e.target.value)}
                  disabled={isLoading}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F9F9A]/30 focus:border-[#0F9F9A]"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Subject
                </label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  disabled={isLoading}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F9F9A]/30 focus:border-[#0F9F9A]"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Topic / Unit <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  disabled={isLoading}
                  placeholder="e.g. Acids, Bases and Salts"
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F9F9A]/30 focus:border-[#0F9F9A]"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Target Learning Objective (Optional)
              </label>
              <input
                type="text"
                value={learningObjective}
                onChange={(e) => setLearningObjective(e.target.value)}
                disabled={isLoading}
                placeholder="e.g. Understand chemical reactions, pH scale, and salt families"
                className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F9F9A]/30 focus:border-[#0F9F9A]"
              />
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
              <div className="text-xs text-slate-500 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-[#0F9F9A]" />
                {isAuthenticated ? (
                  <span>
                    Logged in as <strong className="text-slate-700">{student?.display_name}</strong> (Revision activity is automatically tracked in your history)
                  </span>
                ) : (
                  <span>Guest mode active (All NCERT resources available without login)</span>
                )}
              </div>

              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={isLoading}
                leftIcon={<Sparkles className="w-4 h-4" />}
              >
                {isLoading ? "Curating Resources..." : "Curate NCERT Resources"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Error Banner */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold block">Failed to Curate Resources</span>
            <p>{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <Card className="border-teal-200 bg-teal-50/30 text-center py-12">
          <CardContent className="space-y-4">
            <div className="inline-flex p-3 rounded-full bg-teal-100 text-[#0F9F9A] animate-pulse">
              <Library className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-900">
                Resource Agent is Analyzing NCERT Corpora...
              </h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Querying verified local NCERT textbooks and generating pedagogical guidance on local Ollama GPU (qwen2.5:3b).
              </p>
            </div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white border border-teal-200 text-[11px] text-teal-800">
              <Cpu className="w-3.5 h-3.5 text-[#0F9F9A]" />
              Local Inference &bull; Verified Offline Retrieval
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results Display */}
      {result && !isLoading && (
        <div className="space-y-6">
          {/* Metadata Top Banner */}
          <div className="p-4 rounded-xl border bg-white shadow-xs flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Badge variant={result.is_verified ? "teal" : "neutral"} size="md">
                {result.is_verified ? "✓ Verified NCERT Corpus" : "Provisional Guidelines"}
              </Badge>
              <Badge variant="primary" size="md">
                {result.source_type}
              </Badge>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1">
                <Cpu className="w-3.5 h-3.5 text-slate-400" />
                {result.model}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                {(result.duration_ms / 1000).toFixed(2)}s
              </span>
            </div>
          </div>

          {/* Agent Recommendation Card */}
          <Card className="border-teal-100 shadow-xs">
            <CardHeader className="bg-gradient-to-r from-teal-50/60 to-emerald-50/30 border-b border-teal-100/80 pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="teal" size="sm">
                      Resource Agent Analysis
                    </Badge>
                  </div>
                  <CardTitle className="text-lg text-slate-900">
                    Curated Guidance: {topic}
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-600">
                    Syllabus mapping and textbook study strategies synthesized by the Resource Agent
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6">
              <div className="prose prose-slate max-w-none text-slate-800 text-sm">
                <FormattedMessage content={result.resource_recommendation} />
              </div>
            </CardContent>
          </Card>

          {/* Verified Sources & Excerpts */}
          {result.sources && result.sources.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                  <Bookmark className="w-4 h-4 text-[#0F9F9A]" />
                  Retrieved Textbook References ({result.sources.length})
                </h3>
                <span className="text-xs text-slate-500">
                  Direct citations from official NCERT Class 10 curriculum
                </span>
              </div>

              <div className="grid grid-cols-1 gap-4">
                {result.sources.map((src, idx) => (
                  <Card key={idx} className="border-slate-200">
                    <CardHeader className="pb-2 bg-slate-50/70 border-b border-slate-100">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <CardTitle className="text-xs font-bold text-slate-900 flex items-center gap-2">
                          <FileText className="w-3.5 h-3.5 text-[#0F9F9A]" />
                          {src.title || src.chapter || `Reference Source #${idx + 1}`}
                        </CardTitle>
                        <div className="flex items-center gap-2">
                          {src.section && (
                            <Badge variant="neutral" size="sm">
                              {src.section}
                            </Badge>
                          )}
                          {src.page_start && src.page_end && (
                            <span className="text-[11px] text-slate-500 font-medium">
                              pp. {src.page_start}–{src.page_end}
                            </span>
                          )}
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-3 space-y-2 text-xs">
                      {src.excerpt && (
                        <blockquote className="p-3 rounded-lg bg-teal-50/40 border-l-4 border-[#0F9F9A] text-slate-700 italic">
                          &ldquo;{src.excerpt}&rdquo;
                        </blockquote>
                      )}
                      {src.keywords && src.keywords.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5 pt-1">
                          <span className="text-[10px] uppercase font-semibold text-slate-400">
                            Key Terms:
                          </span>
                          {src.keywords.map((kw, kidx) => (
                            <span
                              key={kidx}
                              className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-[10px]"
                            >
                              {kw}
                            </span>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Action Footer */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-xs text-slate-600 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              Ready to test your understanding of this topic?
            </div>
            <div className="flex items-center gap-2">
              <Link href={`/practice?subject=${encodeURIComponent(subject)}&topic=${encodeURIComponent(topic)}`}>
                <Button variant="primary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                  Take Practice Quiz
                </Button>
              </Link>
              <Link href="/teacher">
                <Button variant="secondary" size="sm" leftIcon={<GraduationCap className="w-3.5 h-3.5 text-[#2563EB]" />}>
                  Ask Teacher Questions
                </Button>
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Initial Empty State when no query run yet */}
      {!result && !isLoading && (
        <EmptyState
          icon={Library}
          title="NCERT Study Material & Verified Reference Library"
          description="Select any Class 10 chapter above or enter custom curriculum queries to receive textbook citations, section references, and study recommendations synthesized by the Resource Agent."
          agentInfo={{
            name: "Resource Agent",
            role: "NCERT textbook citation, chapter mapping, verified educational links, and diagram curation",
            phase: "Verified in Phase 4 &bull; Phase 8.7 Live",
            status: "Ready for Retrieval",
          }}
          action={
            <Button
              variant="primary"
              size="md"
              onClick={() => handleFetchResources()}
              leftIcon={<Sparkles className="w-4 h-4" />}
            >
              Curate Class 10 Science Resources
            </Button>
          }
        />
      )}
    </div>
  );
}

export default function ResourcesPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs text-slate-500">Loading Resources Workspace...</div>}>
      <ResourcesContent />
    </Suspense>
  );
}
