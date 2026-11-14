"use client";

import React, { useState, useEffect, useCallback, useMemo, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  BookOpen,
  Search,
  CheckCircle2,
  Bookmark,
  ExternalLink,
  GraduationCap,
  Sparkles,
  Layers,
  Clock,
  AlertTriangle,
  Lightbulb,
  FileText,
  ChevronRight,
  ChevronDown,
  Check,
  Star,
  Cpu,
  ArrowRight,
  Filter,
  X,
  Compass,
} from "lucide-react";
import { PageHeader } from "../../components/ui/PageHeader";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { useAuth } from "../../components/auth/AuthContext";
import { apiClient } from "../../lib/api";
import {
  CurriculumSubjectResponse,
  CurriculumChapterDetail,
  CurriculumChapterSummary,
  CurriculumTopicDetail,
  StudentEnrolledSubjectResponse,
  SubjectProgressResponse,
  CurriculumSearchResponse,
} from "../../types";

function CurriculumExplorerContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { student, isAuthenticated } = useAuth();

  // State
  const [subjects, setSubjects] = useState<CurriculumSubjectResponse[]>([]);
  const [enrolledSubjects, setEnrolledSubjects] = useState<StudentEnrolledSubjectResponse[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>("subj_science_086");
  const [subjectHierarchy, setSubjectHierarchy] = useState<any | null>(null);
  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null);
  const [chapterDetails, setChapterDetails] = useState<CurriculumChapterDetail | null>(null);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [topicDetails, setTopicDetails] = useState<CurriculumTopicDetail | null>(null);

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchResults, setSearchResults] = useState<CurriculumSearchResponse | null>(null);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  // Progress & Bookmarks
  const [subjectProgress, setSubjectProgress] = useState<SubjectProgressResponse | null>(null);
  const [bookmarkedTopicIds, setBookmarkedTopicIds] = useState<Set<string>>(new Set());
  const [completedTopicIds, setCompletedTopicIds] = useState<Set<string>>(new Set());
  const [revealedAnswers, setRevealedAnswers] = useState<Set<string>>(new Set());

  // UI state
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingChapter, setLoadingChapter] = useState<boolean>(false);
  const [showEnrollModal, setShowEnrollModal] = useState<boolean>(false);
  const [enrollSelection, setEnrollSelection] = useState<Set<string>>(new Set());
  const [isSavingEnrollment, setIsSavingEnrollment] = useState<boolean>(false);

  // Load initial catalogue
  useEffect(() => {
    async function loadCatalogue() {
      setLoading(true);
      try {
        const subjs = await apiClient.getCurriculumSubjects();
        setSubjects(subjs);

        // If URL has query params, select matching subject/chapter/topic
        const querySubj = searchParams.get("subject");
        if (querySubj && subjs.some((s) => s.id === querySubj)) {
          setSelectedSubjectId(querySubj);
        } else if (subjs.length > 0) {
          setSelectedSubjectId(subjs[0].id);
        }

        if (isAuthenticated) {
          try {
            const enrolled = await apiClient.getEnrolledSubjects();
            setEnrolledSubjects(enrolled);
            setEnrollSelection(new Set(enrolled.map((e) => e.id)));
          } catch (err) {
            console.error("Failed to load enrolled subjects:", err);
          }
        }
      } catch (err) {
        console.error("Failed to load curriculum subjects:", err);
      } finally {
        setLoading(false);
      }
    }
    loadCatalogue();
  }, [isAuthenticated, searchParams]);

  // Load subject hierarchy when subject changes
  useEffect(() => {
    if (!selectedSubjectId) return;

    async function loadHierarchy() {
      try {
        const hierarchy = await apiClient.getSubjectHierarchy(selectedSubjectId);
        setSubjectHierarchy(hierarchy);

        // Check if chapter was in URL
        const queryChap = searchParams.get("chapter");
        if (queryChap) {
          setSelectedChapterId(queryChap);
        } else if (hierarchy && hierarchy.units && hierarchy.units.length > 0) {
          const firstUnit = hierarchy.units[0];
          if (firstUnit.chapters && firstUnit.chapters.length > 0) {
            setSelectedChapterId(firstUnit.chapters[0].id);
          }
        }
      } catch (err) {
        console.error("Failed to load subject hierarchy:", err);
      }
    }

    loadHierarchy();

    // Load progress if authenticated
    if (isAuthenticated) {
      apiClient
        .getSubjectProgress(selectedSubjectId)
        .then((prog) => setSubjectProgress(prog))
        .catch((err) => console.error("Failed to load subject progress:", err));
    }
  }, [selectedSubjectId, isAuthenticated, searchParams]);

  // Load chapter details when chapter changes
  useEffect(() => {
    if (!selectedChapterId) return;
    const targetChapterId = selectedChapterId;

    async function loadChapter() {
      setLoadingChapter(true);
      try {
        const details = await apiClient.getChapterDetails(targetChapterId);
        setChapterDetails(details);

        // Check query topic or default to first topic
        const queryTop = searchParams.get("topic");
        if (queryTop && details.topics.some((t) => t.id === queryTop)) {
          setSelectedTopicId(queryTop);
        } else if (details.topics && details.topics.length > 0) {
          setSelectedTopicId(details.topics[0].id);
        } else {
          setSelectedTopicId(null);
        }
      } catch (err) {
        console.error("Failed to load chapter details:", err);
      } finally {
        setLoadingChapter(false);
      }
    }

    loadChapter();
  }, [selectedChapterId, searchParams]);

  // Load topic details when topic changes
  useEffect(() => {
    if (!selectedTopicId) {
      setTopicDetails(null);
      return;
    }
    const targetTopicId = selectedTopicId;

    // Try to find topic in current chapter details first
    if (chapterDetails && chapterDetails.topics) {
      const match = chapterDetails.topics.find((t) => t.id === targetTopicId);
      if (match) {
        setTopicDetails(match);
        return;
      }
    }

    // Otherwise fetch
    apiClient
      .getTopicDetails(targetTopicId)
      .then((det) => setTopicDetails(det))
      .catch((err) => console.error("Failed to load topic details:", err));
  }, [selectedTopicId, chapterDetails]);

  // Handle Search
  const handleSearch = useCallback(
    async (q: string) => {
      setSearchQuery(q);
      if (q.trim().length < 2) {
        setSearchResults(null);
        return;
      }
      setIsSearching(true);
      try {
        const res = await apiClient.searchCurriculum(q.trim());
        setSearchResults(res);
      } catch (err) {
        console.error("Search failed:", err);
      } finally {
        setIsSearching(false);
      }
    },
    []
  );

  // Toggle Topic Completion
  const handleToggleTopicComplete = async (topicId: string) => {
    const isCompleted = completedTopicIds.has(topicId);
    const newStatus = isCompleted ? "not_started" : "completed";

    try {
      if (isAuthenticated) {
        await apiClient.updateTopicProgress({
          topic_id: topicId,
          status: newStatus,
          time_spent_seconds: 300,
        });
      }
      setCompletedTopicIds((prev) => {
        const next = new Set(prev);
        if (isCompleted) next.delete(topicId);
        else next.add(topicId);
        return next;
      });

      // Refresh progress
      if (isAuthenticated && selectedSubjectId) {
        const prog = await apiClient.getSubjectProgress(selectedSubjectId);
        setSubjectProgress(prog);
      }
    } catch (err) {
      console.error("Failed to update topic progress:", err);
    }
  };

  // Toggle Bookmark
  const handleToggleBookmark = async (topicId: string) => {
    try {
      if (isAuthenticated) {
        await apiClient.toggleBookmark({
          entity_type: "topic",
          entity_id: topicId,
        });
      }
      setBookmarkedTopicIds((prev) => {
        const next = new Set(prev);
        if (next.has(topicId)) next.delete(topicId);
        else next.add(topicId);
        return next;
      });
    } catch (err) {
      console.error("Failed to toggle bookmark:", err);
    }
  };

  // Toggle practice answer reveal
  const toggleAnswer = (questionId: string) => {
    setRevealedAnswers((prev) => {
      const next = new Set(prev);
      if (next.has(questionId)) next.delete(questionId);
      else next.add(questionId);
      return next;
    });
  };

  // Save Subject Enrollment
  const handleSaveEnrollment = async () => {
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    setIsSavingEnrollment(true);
    try {
      const updated = await apiClient.setEnrolledSubjects(Array.from(enrollSelection));
      setEnrolledSubjects(updated);
      setShowEnrollModal(false);
    } catch (err) {
      console.error("Failed to save enrollment:", err);
    } finally {
      setIsSavingEnrollment(false);
    }
  };

  // Filtered subjects
  const filteredSubjects = useMemo(() => {
    if (categoryFilter === "all") return subjects;
    if (categoryFilter === "compulsory") return subjects.filter((s) => s.is_compulsory);
    if (categoryFilter === "languages") return subjects.filter((s) => s.category.includes("Language"));
    if (categoryFilter === "skills") return subjects.filter((s) => s.category.includes("Skill") || s.category.includes("Elective"));
    return subjects;
  }, [subjects, categoryFilter]);

  const activeSubject = subjects.find((s) => s.id === selectedSubjectId);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* 1. Official Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-[#0F172A] via-[#1E293B] to-[#0F172A] p-6 sm:p-8 text-white shadow-xl border border-slate-700/50">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-3 max-w-2xl">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-blue-500/20 text-blue-300 border border-blue-400/30">
                CBSE Class 10
              </span>
              <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-400/30">
                Academic Session 2026–2027
              </span>
              <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-400/30">
                100% NCERT Aligned
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              CBSE Secondary School Curriculum System
            </h1>
            <p className="text-sm text-slate-300 leading-relaxed">
              Explore officially verified CBSE chapters, units, topics, learning objectives, definitions, formulas, and common exam pitfalls across all 17 prescribed subjects.
            </p>
            <div className="flex items-center gap-4 pt-1">
              <a
                href="https://cbseacademic.nic.in/curriculum_2027.html"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-400 hover:text-blue-300 transition-colors"
              >
                Official CBSE Curriculum Portal <ExternalLink className="w-3.5 h-3.5" />
              </a>
              {isAuthenticated && (
                <button
                  onClick={() => setShowEnrollModal(true)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-300 hover:text-amber-200 underline underline-offset-4"
                >
                  Manage My Subjects ({enrolledSubjects.length} enrolled)
                </button>
              )}
            </div>
          </div>

          {/* Search Bar */}
          <div className="w-full md:w-80 space-y-2">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                placeholder="Search topics, formulas, laws..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800/90 border border-slate-700 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
              />
              {searchQuery && (
                <button
                  onClick={() => handleSearch("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            {isSearching && <p className="text-xs text-slate-400">Searching verified curriculum...</p>}
          </div>
        </div>

        {/* Search Results Dropdown */}
        {searchResults && searchQuery.trim().length >= 2 && (
          <div className="mt-6 pt-6 border-t border-slate-700/80 bg-slate-900/90 rounded-xl p-4 max-h-80 overflow-y-auto space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Search Results for &ldquo;{searchResults.query}&rdquo;</span>
              <span>{searchResults.total_matches} matches found</span>
            </div>
            {searchResults.total_matches === 0 ? (
              <p className="text-sm text-slate-400 py-2">No direct curriculum matches found.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {searchResults.chapters.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => {
                      setSelectedSubjectId(c.subject_id);
                      setSelectedChapterId(c.id);
                      setSearchResults(null);
                    }}
                    className="p-3 text-left rounded-lg bg-slate-800/70 hover:bg-slate-700/80 border border-slate-700 transition-all flex flex-col gap-1"
                  >
                    <span className="text-xs font-semibold text-blue-400">
                      {c.subject_name} • Chapter {c.chapter_number}
                    </span>
                    <span className="text-sm font-bold text-white">{c.title}</span>
                    <span className="text-xs text-slate-300 line-clamp-1">{c.description}</span>
                  </button>
                ))}
                {searchResults.topics.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => {
                      if (t.subject_id) setSelectedSubjectId(t.subject_id);
                      setSelectedChapterId(t.chapter_id);
                      setSelectedTopicId(t.id);
                      setSearchResults(null);
                    }}
                    className="p-3 text-left rounded-lg bg-slate-800/70 hover:bg-slate-700/80 border border-slate-700 transition-all flex flex-col gap-1"
                  >
                    <span className="text-xs font-semibold text-emerald-400">
                      {t.subject_name} • Topic {t.topic_number}
                    </span>
                    <span className="text-sm font-bold text-white">{t.title}</span>
                    <span className="text-xs text-slate-300 line-clamp-1">{t.summary}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 2. Subject Selection Chips & Filter */}
      <div className="space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Filter Subjects:</span>
            <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1 text-xs">
              <button
                onClick={() => setCategoryFilter("all")}
                className={`px-3 py-1 rounded-md font-medium transition-all ${
                  categoryFilter === "all" ? "bg-blue-600 text-white shadow-sm" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                All (17)
              </button>
              <button
                onClick={() => setCategoryFilter("compulsory")}
                className={`px-3 py-1 rounded-md font-medium transition-all ${
                  categoryFilter === "compulsory" ? "bg-blue-600 text-white shadow-sm" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Core Compulsory
              </button>
              <button
                onClick={() => setCategoryFilter("languages")}
                className={`px-3 py-1 rounded-md font-medium transition-all ${
                  categoryFilter === "languages" ? "bg-blue-600 text-white shadow-sm" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Languages
              </button>
              <button
                onClick={() => setCategoryFilter("skills")}
                className={`px-3 py-1 rounded-md font-medium transition-all ${
                  categoryFilter === "skills" ? "bg-blue-600 text-white shadow-sm" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Skills & Electives
              </button>
            </div>
          </div>

          {activeSubject && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span>CBSE Code: <strong className="text-slate-800">{activeSubject.code}</strong></span>
              <span>•</span>
              <span>{activeSubject.chapter_count || 0} Prescribed Chapters</span>
            </div>
          )}
        </div>

        {/* Scrollable Subject Pills */}
        <div className="flex items-center gap-2.5 overflow-x-auto pb-2 scrollbar-thin">
          {filteredSubjects.map((s) => {
            const isSelected = s.id === selectedSubjectId;
            const isEnrolled = enrolledSubjects.some((e) => e.id === s.id);
            return (
              <button
                key={s.id}
                onClick={() => setSelectedSubjectId(s.id)}
                className={`flex-shrink-0 px-4 py-2.5 rounded-xl border text-sm font-semibold transition-all flex items-center gap-2 shadow-sm ${
                  isSelected
                    ? "bg-blue-600 text-white border-blue-600 shadow-blue-100"
                    : "bg-white text-slate-700 border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <span>{s.short_name || s.name}</span>
                <span
                  className={`text-[11px] px-1.5 py-0.5 rounded font-mono ${
                    isSelected ? "bg-blue-700 text-blue-100" : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {s.code}
                </span>
                {isEnrolled && (
                  <span className={`w-2 h-2 rounded-full ${isSelected ? "bg-emerald-300" : "bg-emerald-500"}`} />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. Main Split View: Chapter Tree & Topic Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Subject Units & Chapters Accordion (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-blue-600" /> Prescribed Chapters
            </h2>
            {subjectProgress && (
              <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                {subjectProgress.progress_percentage}% Completed
              </span>
            )}
          </div>

          {loading || !subjectHierarchy ? (
            <div className="p-8 text-center bg-white rounded-xl border border-slate-200 text-slate-400">
              Loading syllabus hierarchy...
            </div>
          ) : (
            <div className="space-y-4">
              {subjectHierarchy.units &&
                subjectHierarchy.units.map((unit: any) => (
                  <div key={unit.id} className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
                    {/* Unit Header */}
                    <div className="px-4 py-3 bg-slate-50/80 border-b border-slate-200/80 flex items-center justify-between">
                      <div className="space-y-0.5">
                        <span className="text-xs font-bold text-slate-500 tracking-wide uppercase">
                          {unit.section_tag || `Unit ${unit.unit_number}`}
                        </span>
                        <h3 className="text-sm font-semibold text-slate-800">{unit.title}</h3>
                      </div>
                      {unit.weightage_marks > 0 && (
                        <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                          {unit.weightage_marks} Marks
                        </span>
                      )}
                    </div>

                    {/* Chapters in Unit */}
                    <div className="divide-y divide-slate-100">
                      {unit.chapters &&
                        unit.chapters.map((chap: any) => {
                          const isSelected = chap.id === selectedChapterId;
                          return (
                            <button
                              key={chap.id}
                              onClick={() => setSelectedChapterId(chap.id)}
                              className={`w-full p-4 text-left transition-all flex items-start justify-between gap-3 ${
                                isSelected
                                  ? "bg-blue-50/70 border-l-4 border-l-blue-600"
                                  : "hover:bg-slate-50"
                              }`}
                            >
                              <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className="text-xs font-bold font-mono text-slate-400">
                                    Ch {chap.chapter_number}
                                  </span>
                                  {chap.section_tag && (
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
                                      {chap.section_tag}
                                    </span>
                                  )}
                                </div>
                                <h4 className={`text-sm font-bold ${isSelected ? "text-blue-900" : "text-slate-800"}`}>
                                  {chap.title}
                                </h4>
                                <p className="text-xs text-slate-500 line-clamp-2">{chap.description}</p>
                              </div>
                              <ChevronRight
                                className={`w-4 h-4 flex-shrink-0 mt-1 transition-transform ${
                                  isSelected ? "text-blue-600 translate-x-1" : "text-slate-400"
                                }`}
                              />
                            </button>
                          );
                        })}
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>

        {/* Right Column: Active Chapter & Topic Content (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {loadingChapter ? (
            <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 text-slate-400">
              Loading chapter curriculum...
            </div>
          ) : !chapterDetails ? (
            <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 text-slate-400">
              Select a chapter to explore verified topics, formulas, definitions, and learning objectives.
            </div>
          ) : (
            <>
              {/* Active Chapter Card */}
              <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-700 font-mono">
                        Chapter {chapterDetails.chapter_number}
                      </span>
                      {chapterDetails.section_tag && (
                        <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                          {chapterDetails.section_tag}
                        </span>
                      )}
                      <span className="text-xs text-slate-400 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" /> {chapterDetails.estimated_minutes} mins
                      </span>
                    </div>
                    <h2 className="text-xl font-extrabold text-slate-900">{chapterDetails.title}</h2>
                  </div>

                  {/* Action: Start 8-Agent Journey */}
                  <Link
                    href={`/agent-arena?subject=${encodeURIComponent(
                      chapterDetails.subject_name || "Science"
                    )}&chapter=${encodeURIComponent(chapterDetails.title)}`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-sm"
                  >
                    <Cpu className="w-3.5 h-3.5" />
                    <span>8-Agent Journey</span>
                  </Link>
                </div>

                <p className="text-sm text-slate-600 leading-relaxed">{chapterDetails.description}</p>

                {/* Excluded Topics Alert (CBSE 2026-27 rationalisation check) */}
                {chapterDetails.excluded_topics && (
                  <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-2.5 text-xs text-amber-800">
                    <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <strong className="font-semibold">CBSE Assessment Notice (2026–27):</strong>{" "}
                      {chapterDetails.excluded_topics}
                    </div>
                  </div>
                )}

                {/* Chapter Official Resources */}
                {chapterDetails.resources && chapterDetails.resources.length > 0 && (
                  <div className="pt-2 flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-slate-500">Official Prescribed Material:</span>
                    {chapterDetails.resources.map((res) => (
                      <a
                        key={res.id}
                        href={res.url || "https://ncert.nic.in/textbook.php"}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition-colors"
                      >
                        <FileText className="w-3.5 h-3.5 text-blue-600" />
                        {res.title}
                        <ExternalLink className="w-3 h-3 text-slate-400" />
                      </a>
                    ))}
                  </div>
                )}
              </div>

              {/* Topics Selection Bar */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
                    Topics in this Chapter ({chapterDetails.topics.length})
                  </h3>
                  <span className="text-xs text-slate-500">Click a topic to view definitions, formulas & practice</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {chapterDetails.topics.map((t) => {
                    const isSelected = t.id === selectedTopicId;
                    const isCompleted = completedTopicIds.has(t.id);
                    return (
                      <button
                        key={t.id}
                        onClick={() => setSelectedTopicId(t.id)}
                        className={`p-4 text-left rounded-xl border transition-all space-y-2 relative ${
                          isSelected
                            ? "bg-blue-50/60 border-blue-500 shadow-sm ring-1 ring-blue-500"
                            : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/50"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-bold font-mono text-slate-500">
                            Topic {t.topic_number}
                          </span>
                          <div className="flex items-center gap-1.5">
                            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                              {t.importance} Priority
                            </span>
                            {isCompleted && (
                              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                            )}
                          </div>
                        </div>
                        <h4 className="text-sm font-bold text-slate-900 leading-snug">{t.title}</h4>
                        <p className="text-xs text-slate-500 line-clamp-2">{t.summary}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Topic Detailed Deep-Dive Card */}
              {topicDetails && (
                <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-6">
                  {/* Topic Header & Actions */}
                  <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 pb-4">
                    <div className="space-y-1 max-w-lg">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                          Topic {topicDetails.topic_number} Details
                        </span>
                        <span className="text-xs font-medium text-slate-500">
                          Level: {topicDetails.difficulty_level}
                        </span>
                      </div>
                      <h3 className="text-lg font-bold text-slate-900">{topicDetails.title}</h3>
                      <p className="text-xs text-slate-600">{topicDetails.summary}</p>
                    </div>

                    {/* Action buttons */}
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/teacher?subject=${encodeURIComponent(
                          activeSubject?.name || "Science"
                        )}&chapter=${encodeURIComponent(
                          chapterDetails.title
                        )}&topic=${encodeURIComponent(topicDetails.title)}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-all shadow-sm"
                      >
                        <GraduationCap className="w-3.5 h-3.5" />
                        <span>AI Teacher Studio</span>
                      </Link>
                      <button
                        onClick={() => handleToggleTopicComplete(topicDetails.id)}
                        className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
                          completedTopicIds.has(topicDetails.id)
                            ? "bg-emerald-50 text-emerald-700 border-emerald-300"
                            : "bg-white hover:bg-slate-50 text-slate-700 border-slate-200"
                        }`}
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>
                          {completedTopicIds.has(topicDetails.id) ? "Completed" : "Mark Complete"}
                        </span>
                      </button>
                      <button
                        onClick={() => handleToggleBookmark(topicDetails.id)}
                        className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-500 transition-colors"
                        title="Bookmark topic"
                      >
                        <Bookmark
                          className={`w-4 h-4 ${
                            bookmarkedTopicIds.has(topicDetails.id) ? "fill-amber-400 text-amber-500" : ""
                          }`}
                        />
                      </button>
                    </div>
                  </div>

                  {/* 1. Learning Objectives (Bloom's Taxonomy) */}
                  {topicDetails.learning_objectives && topicDetails.learning_objectives.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                        Learning Objectives (Bloom&rsquo;s Taxonomy)
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {topicDetails.learning_objectives.map((obj) => (
                          <div
                            key={obj.id}
                            className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-700 flex items-start gap-2"
                          >
                            <span className="px-1.5 py-0.5 rounded font-mono font-bold text-[10px] bg-blue-100 text-blue-700 flex-shrink-0">
                              {obj.bloom_level}
                            </span>
                            <span>{obj.description}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 2. Key Concepts */}
                  {topicDetails.key_concepts && topicDetails.key_concepts.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                        Key Concepts & Principles
                      </h4>
                      <ul className="space-y-1.5 text-xs text-slate-700 list-disc list-inside bg-blue-50/40 p-4 rounded-xl border border-blue-100">
                        {topicDetails.key_concepts.map((kc, idx) => (
                          <li key={idx} className="leading-relaxed">
                            {kc}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* 3. Formal Definitions */}
                  {topicDetails.definitions && Object.keys(topicDetails.definitions).length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                        Formal Prescribed Definitions
                      </h4>
                      <div className="space-y-2">
                        {Object.entries(topicDetails.definitions).map(([term, def]) => (
                          <div key={term} className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                            <span className="font-bold text-slate-900">{term}:</span>{" "}
                            <span className="text-slate-700">{def}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 4. Formulas / Governing Rules */}
                  {topicDetails.formulas && topicDetails.formulas.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                        Governing Formulas & Scientific Laws
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {topicDetails.formulas.map((form, idx) => (
                          <div
                            key={idx}
                            className="p-3 rounded-xl bg-slate-900 text-white font-mono text-xs flex items-center shadow-inner"
                          >
                            <span>{form}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 5. Common Misconceptions Alert */}
                  {topicDetails.common_misconceptions && topicDetails.common_misconceptions.length > 0 && (
                    <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 space-y-2">
                      <div className="flex items-center gap-2 text-rose-800 text-xs font-bold">
                        <AlertTriangle className="w-4 h-4 text-rose-600" />
                        <span>Common Board Exam Pitfalls & Misconceptions</span>
                      </div>
                      <ul className="text-xs text-rose-900 space-y-1 list-disc list-inside">
                        {topicDetails.common_misconceptions.map((mis, idx) => (
                          <li key={idx}>{mis}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* 6. Curated Practice Questions */}
                  {topicDetails.practice_questions && topicDetails.practice_questions.length > 0 && (
                    <div className="space-y-3 pt-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                        Curated Board Practice Questions
                      </h4>
                      <div className="space-y-3">
                        {topicDetails.practice_questions.map((pq, idx) => {
                          const qId = pq.id || `pq-${idx}`;
                          const isRevealed = revealedAnswers.has(qId);
                          return (
                            <div key={qId} className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5 text-xs">
                              <div className="flex items-start justify-between gap-2">
                                <span className="font-bold text-slate-900">
                                  Q{idx + 1}. {pq.question}
                                </span>
                                {pq.type && (
                                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-200 text-slate-700">
                                    {pq.type}
                                  </span>
                                )}
                              </div>
                              <button
                                onClick={() => toggleAnswer(qId)}
                                className="text-xs font-bold text-blue-600 hover:text-blue-700 flex items-center gap-1"
                              >
                                <span>{isRevealed ? "Hide Expected Answer" : "Show Expected Answer"}</span>
                                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isRevealed ? "rotate-180" : ""}`} />
                              </button>
                              {isRevealed && (
                                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-900 mt-2 space-y-1">
                                  <strong className="block text-[11px] uppercase tracking-wider text-emerald-700 font-bold">
                                    Standard Answer:
                                  </strong>
                                  <p>{pq.expected_answer}</p>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* 4. Subject Enrollment Modal */}
      {showEnrollModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900">Select Your Enrolled Subjects</h3>
                <p className="text-xs text-slate-500">Pick the CBSE Class 10 subjects you are studying this academic year.</p>
              </div>
              <button onClick={() => setShowEnrollModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-2">
              {subjects.map((subj) => {
                const isChecked = enrollSelection.has(subj.id);
                return (
                  <label
                    key={subj.id}
                    className={`flex items-center justify-between p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                      isChecked
                        ? "bg-blue-50/70 border-blue-500 font-semibold text-blue-900"
                        : "bg-white border-slate-200 hover:bg-slate-50 text-slate-700"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => {
                          setEnrollSelection((prev) => {
                            const next = new Set(prev);
                            if (next.has(subj.id)) next.delete(subj.id);
                            else next.add(subj.id);
                            return next;
                          });
                        }}
                        className="rounded text-blue-600 focus:ring-blue-500 w-4 h-4"
                      />
                      <span>{subj.name}</span>
                    </div>
                    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                      Code {subj.code}
                    </span>
                  </label>
                );
              })}
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
              <Button variant="outline" size="sm" onClick={() => setShowEnrollModal(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSaveEnrollment}
                isLoading={isSavingEnrollment}
              >
                Save My Enrolled Subjects
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CurriculumExplorerPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center text-slate-400">
          Loading CBSE Class 10 Curriculum Explorer...
        </div>
      }
    >
      <CurriculumExplorerContent />
    </Suspense>
  );
}
