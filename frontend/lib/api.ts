/**
 * Gyaan AI - Frontend API Client Foundation
 *
 * Provides a clean, typed fetch wrapper for interacting with the Gyaan AI FastAPI backend.
 * Implements safe error handling and bearer authentication support without token leakage.
 */

import { API_BASE_URL } from "./config";
import {
  HealthResponse,
  AskRequest,
  AskResponse,
  OrchestrationRequest,
  OrchestrationResponse,
  StudentRegisterRequest,
  StudentLoginRequest,
  AuthTokenResponse,
  StudentProfileResponse,
  StudentProfileUpdateRequest,
  StudentDashboardResponse,
  LearningSessionResponse,
  TopicMasteryResponse,
  LearningPlanRequest,
  LearningPlanResponse,
  ResourceRequest,
  ResourceResponse,
  QuizGenerationRequest,
  QuizGenerationResponse,
  AssessmentSubmissionRequest,
  AssessmentSubmissionResponse,
  AssessmentHistoryResponse,
  ProgressReportResponse,
  MentorRecommendationsResponse,
  FullProgressMentoringResponse,
  LearningJourneyStartRequest,
  LearningJourneyInteractRequest,
  LearningJourneyResponse,
  CurriculumSubjectResponse,
  CurriculumUnitResponse,
  CurriculumChapterSummary,
  CurriculumChapterDetail,
  CurriculumTopicSummary,
  CurriculumTopicDetail,
  CurriculumSubtopicResponse,
  CurriculumObjectiveResponse,
  CurriculumResourceResponse,
  EnrollSubjectsRequest,
  StudentEnrolledSubjectResponse,
  TopicProgressUpdateRequest,
  TopicProgressResponse,
  SubjectProgressResponse,
  LessonSessionCreateRequest,
  LessonMessageRequest,
  LessonSessionResponse,
  BookmarkToggleRequest,
  BookmarkResponse,
  CurriculumSearchResponse,
  AgentMetadataResponse,
  ArenaStatusResponse,
  WorkflowDescriptorResponse,
  DiagnosticAssessmentGenerateRequest,
  DiagnosticAssessmentGenerateResponse,
  DiagnosticEvaluateRequest,
  FullDiagnosticReportResponse,
  AdaptiveProbeRequest,
  ChapterPracticeSetRequest,
  ChapterPracticeSetResponse,
  SavePracticeSessionRequest,
  SavePracticeSessionResponse,
  ComprehensiveProgressDashboardResponse,
} from "../types";

export interface RequestOptions extends RequestInit {
  token?: string | null;
  params?: Record<string, string | number | boolean>;
  timeoutMs?: number;
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

/**
 * Reusable core fetch wrapper
 */
export async function apiFetch<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { token, params, headers, timeoutMs, ...restOptions } = options;

  let url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    }
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes("?") ? "&" : "?") + queryString;
    }
  }

  const requestHeaders: Record<string, string> = {
    Accept: "application/json",
    ...((headers as Record<string, string>) || {}),
  };

  // Add JSON Content-Type if body is present and not explicitly set
  if (restOptions.body && !requestHeaders["Content-Type"]) {
    requestHeaders["Content-Type"] = "application/json";
  }

  // Attach Bearer token when provided (never logged)
  if (token) {
    requestHeaders["Authorization"] = `Bearer ${token.trim()}`;
  }

  let timeoutId: NodeJS.Timeout | null = null;
  let internalController: AbortController | null = null;
  let signalToUse = restOptions.signal;

  if (timeoutMs && timeoutMs > 0) {
    internalController = new AbortController();
    if (signalToUse) {
      if (signalToUse.aborted) {
        internalController.abort();
      } else {
        signalToUse.addEventListener("abort", () => internalController?.abort());
      }
    }
    signalToUse = internalController.signal;
    timeoutId = setTimeout(() => {
      internalController?.abort();
    }, timeoutMs);
  }

  try {
    const response = await fetch(url, {
      credentials: restOptions.credentials || "include",
      ...restOptions,
      headers: requestHeaders,
      signal: signalToUse,
    });

    const isJson = response.headers.get("content-type")?.includes("application/json");
    const data = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;

      if (typeof data === "object" && data !== null) {
        const obj = data as Record<string, unknown>;
        if ("detail" in obj) {
          if (typeof obj.detail === "string") {
            errorMessage = obj.detail;
          } else if (typeof obj.detail === "object" && obj.detail !== null) {
            const detailObj = obj.detail as Record<string, unknown>;
            errorMessage = String(detailObj.message || detailObj.error || JSON.stringify(detailObj));
          }
        } else if ("error" in obj) {
          errorMessage = String(obj.error);
        }
      }

      throw new ApiError(errorMessage, response.status, data);
    }

    return data as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === "AbortError") {
      throw new ApiError(
        "Request timed out or was cancelled by user. Local Ollama AI may be busy processing another task.",
        408
      );
    }
    const message = error instanceof Error ? error.message : "Network request failed";
    throw new ApiError(`Network error communicating with backend: ${message}`, 0);
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
}

/**
 * Helper to retrieve stored token on the client side
 */
function getStoredToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem("gyaan_auth_token");
  }
  return null;
}

/**
 * API client methods for Gyaan AI
 */
export const apiClient = {
  /**
   * Query the FastAPI health check endpoint
   */
  async getHealth(): Promise<HealthResponse> {
    return apiFetch<HealthResponse>("/health", { method: "GET" });
  },

  /**
   * Diagnostic connectivity test measuring latency and reporting status
   */
  async checkConnectivity(): Promise<{
    connected: boolean;
    latencyMs: number;
    health?: HealthResponse;
    error?: string;
  }> {
    const start = performance.now();
    try {
      const health = await this.getHealth();
      const latencyMs = Math.round(performance.now() - start);
      return {
        connected: health.status === "healthy" || health.app === "ok",
        latencyMs,
        health,
      };
    } catch (err) {
      const latencyMs = Math.round(performance.now() - start);
      const errorMsg = err instanceof Error ? err.message : String(err);
      return {
        connected: false,
        latencyMs,
        error: errorMsg,
      };
    }
  },

  // ============================================================================
  // Student Authentication Endpoints (POST /api/v1/auth/*)
  // ============================================================================

  /**
   * Register a new student account
   * Endpoint: POST /api/v1/auth/register
   */
  async register(data: StudentRegisterRequest): Promise<AuthTokenResponse> {
    return apiFetch<AuthTokenResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({
        display_name: data.display_name.trim(),
        email: data.email.trim().toLowerCase(),
        password: data.password,
        grade: data.grade || "Class 10",
        preferred_language: data.preferred_language || "English",
      }),
    });
  },

  /**
   * Authenticate student with email and password
   * Endpoint: POST /api/v1/auth/login
   */
  async login(credentials: StudentLoginRequest): Promise<AuthTokenResponse> {
    return apiFetch<AuthTokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: credentials.email.trim().toLowerCase(),
        password: credentials.password,
      }),
    });
  },

  /**
   * Revoke current session token
   * Endpoint: POST /api/v1/auth/logout
   */
  async logout(token?: string | null): Promise<{ status: string; message: string }> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<{ status: string; message: string }>("/api/v1/auth/logout", {
      method: "POST",
      token: activeToken,
    });
  },

  // ============================================================================
  // Student Profile & Dashboard Endpoints (GET /api/v1/students/me/*)
  // ============================================================================

  /**
   * Retrieve the authenticated student's profile
   * Endpoint: GET /api/v1/students/me
   */
  async getProfile(token?: string | null): Promise<StudentProfileResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<StudentProfileResponse>("/api/v1/students/me", {
      method: "GET",
      token: activeToken,
    });
  },

  /**
   * Update student profile fields (display_name, grade, preferred_language)
   * Endpoint: PATCH /api/v1/students/me
   */
  async updateProfile(
    data: StudentProfileUpdateRequest,
    token?: string | null
  ): Promise<StudentProfileResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<StudentProfileResponse>("/api/v1/students/me", {
      method: "PATCH",
      body: JSON.stringify(data),
      token: activeToken,
    });
  },

  /**
   * Retrieve complete aggregated learning dashboard data
   * Endpoint: GET /api/v1/students/me/dashboard
   */
  async getDashboard(token?: string | null): Promise<StudentDashboardResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<StudentDashboardResponse>("/api/v1/students/me/dashboard", {
      method: "GET",
      token: activeToken,
    });
  },

  /**
   * Retrieve chronological learning sessions
   * Endpoint: GET /api/v1/students/me/learning-history
   */
  async getLearningHistory(token?: string | null): Promise<LearningSessionResponse[]> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<LearningSessionResponse[]>("/api/v1/students/me/learning-history", {
      method: "GET",
      token: activeToken,
    });
  },

  /**
   * Retrieve topic-wise mastery evaluation records
   * Endpoint: GET /api/v1/students/me/topic-mastery
   */
  async getTopicMastery(token?: string | null): Promise<TopicMasteryResponse[]> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<TopicMasteryResponse[]>("/api/v1/students/me/topic-mastery", {
      method: "GET",
      token: activeToken,
    });
  },

  // ============================================================================
  // Diagnostic + Curriculum Sequential Workflow (Phase 3 & 8.6)
  // ============================================================================

  /**
   * Execute sequential Diagnostic + Curriculum multi-agent workflow
   * Endpoint: POST /api/v1/learning-plan
   */
  async generateLearningPlan(
    request: LearningPlanRequest,
    token?: string | null
  ): Promise<LearningPlanResponse> {
    const activeToken = token ?? getStoredToken();

    return apiFetch<LearningPlanResponse>("/api/v1/learning-plan", {
      method: "POST",
      body: JSON.stringify({
        grade: request.grade || "Class 10",
        subject: request.subject,
        topic: request.topic,
        display_name: request.display_name || "Student",
        student_id: request.student_id,
        assessment_items: request.assessment_items,
      }),
      token: activeToken,
    });
  },

  // ============================================================================
  // AI Tutoring & Orchestration Endpoints
  // ============================================================================

  /**
   * Submit an educational question to the central multi-agent system via Orchestrator
   * Endpoint: POST /api/v1/ask
   */
  async askTeacher(
    request: AskRequest,
    token?: string | null,
    options?: { signal?: AbortSignal; timeoutMs?: number }
  ): Promise<AskResponse> {
    const activeToken = token ?? getStoredToken();

    return apiFetch<AskResponse>("/api/v1/ask", {
      method: "POST",
      body: JSON.stringify({
        question: request.question.trim(),
        grade: request.grade || "Class 10",
        subject: request.subject || "Science",
        language: request.language || "English",
        chapter: request.chapter,
        topic: request.topic,
        subtopic: request.subtopic,
        learning_objectives: request.learning_objectives,
        lesson_mode: request.lesson_mode,
      }),
      token: activeToken,
      signal: options?.signal,
      timeoutMs: options?.timeoutMs ?? 75000,
    });
  },

  /**
   * Submit a request to the central AI Orchestrator Agent
   * Endpoint: POST /api/v1/orchestrate
   */
  async orchestrate(
    request: OrchestrationRequest,
    token?: string | null
  ): Promise<OrchestrationResponse> {
    const activeToken = token ?? getStoredToken();

    return apiFetch<OrchestrationResponse>("/api/v1/orchestrate", {
      method: "POST",
      body: JSON.stringify({
        request: request.request.trim(),
        grade: request.grade || "Class 10",
        subject: request.subject || "Science",
        language: request.language || "English",
        workflow_preference: request.workflow_preference,
        metadata: request.metadata,
      }),
      token: activeToken,
    });
  },

  /**
   * Fetch all 8 canonical CrewAI agents with real metadata, prompt specs, and runtime states
   * Endpoint: GET /api/v1/arena/agents
   */
  async getArenaAgents(token?: string | null): Promise<AgentMetadataResponse[]> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<AgentMetadataResponse[]>("/api/v1/arena/agents", {
      token: activeToken,
    });
  },

  /**
   * Fetch a single agent's real metadata and execution state
   * Endpoint: GET /api/v1/arena/agents/{agent_id}
   */
  async getArenaAgent(agentId: string, token?: string | null): Promise<AgentMetadataResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<AgentMetadataResponse>(`/api/v1/arena/agents/${encodeURIComponent(agentId)}`, {
      token: activeToken,
    });
  },

  /**
   * Fetch Agent Arena summary status and active agent counts
   * Endpoint: GET /api/v1/arena/status
   */
  async getArenaStatus(token?: string | null): Promise<ArenaStatusResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<ArenaStatusResponse>("/api/v1/arena/status", {
      token: activeToken,
    });
  },

  /**
   * Fetch all approved workflows registered in WORKFLOW_REGISTRY
   * Endpoint: GET /api/v1/arena/workflows
   */
  async getArenaWorkflows(token?: string | null): Promise<WorkflowDescriptorResponse[]> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<WorkflowDescriptorResponse[]>("/api/v1/arena/workflows", {
      token: activeToken,
    });
  },

  /**
   * Retrieve educational study materials & citations using the Resource Agent
   * Endpoint: POST /api/v1/resources
   */
  async getResources(
    request: ResourceRequest,
    token?: string | null
  ): Promise<ResourceResponse> {
    const activeToken = token ?? getStoredToken();

    return apiFetch<ResourceResponse>("/api/v1/resources", {
      method: "POST",
      body: JSON.stringify({
        grade: request.grade || "Class 10",
        subject: request.subject.trim(),
        topic: request.topic.trim(),
        learning_objective: request.learning_objective?.trim() || null,
      }),
      token: activeToken,
    });
  },

  /**
   * Generate diagnostic practice quiz using the Assessment Agent
   * Endpoint: POST /api/v1/quizzes
   */
  async generateQuiz(
    request: QuizGenerationRequest,
    token?: string | null
  ): Promise<QuizGenerationResponse> {
    const activeToken = token ?? getStoredToken();

    return apiFetch<QuizGenerationResponse>("/api/v1/quizzes", {
      method: "POST",
      body: JSON.stringify({
        student_id: request.student_id ?? null,
        grade: request.grade || "Class 10",
        subject: request.subject.trim(),
        topic: request.topic.trim(),
        num_questions: request.num_questions ?? 3,
        question_types: request.question_types ?? ["mcq", "short_answer"],
        learning_objectives: request.learning_objectives?.trim() || null,
      }),
      token: activeToken,
    });
  },

  /**
   * Submit student answers for constructive evaluation by Assessment Agent
   * Endpoint: POST /api/v1/assessments/submit
   */
  async submitAssessment(
    request: AssessmentSubmissionRequest,
    token?: string | null
  ): Promise<AssessmentSubmissionResponse> {
    const activeToken = token ?? getStoredToken();

    return apiFetch<AssessmentSubmissionResponse>("/api/v1/assessments/submit", {
      method: "POST",
      body: JSON.stringify({
        quiz_id: request.quiz_id,
        student_id: request.student_id ?? null,
        answers: request.answers,
      }),
      token: activeToken,
    });
  },

  /**
   * Retrieve all historical assessment attempts for a student
   * Endpoint: GET /api/v1/assessments/history/{student_id}
   */
  async getAssessmentHistory(
    studentId: string,
    token?: string | null
  ): Promise<AssessmentHistoryResponse> {
    const activeToken = token ?? getStoredToken();

    return apiFetch<AssessmentHistoryResponse>(
      `/api/v1/assessments/history/${encodeURIComponent(studentId)}`,
      {
        method: "GET",
        token: activeToken,
      }
    );
  },

  /**
   * Retrieve deterministic progress analytics and Progress Agent evaluation
   * Endpoint: GET /api/v1/students/me/progress
   */
  async getProgressReport(token?: string | null): Promise<ProgressReportResponse> {
    const activeToken = token ?? getStoredToken();

    return apiFetch<ProgressReportResponse>("/api/v1/students/me/progress", {
      method: "GET",
      token: activeToken,
    });
  },

  /**
   * Retrieve personalized mentoring guidance and actionable study recommendations
   * Endpoint: GET /api/v1/students/me/mentor-recommendations
   */
  async getMentorRecommendations(
    token?: string | null,
    options?: { signal?: AbortSignal; timeoutMs?: number }
  ): Promise<MentorRecommendationsResponse> {
    const activeToken = token ?? getStoredToken();

    return apiFetch<MentorRecommendationsResponse>(
      "/api/v1/students/me/mentor-recommendations",
      {
        method: "GET",
        token: activeToken,
        signal: options?.signal,
        timeoutMs: options?.timeoutMs ?? 75000,
      }
    );
  },

  /**
   * Consolidated endpoint executing sequential Progress -> Mentor multi-agent workflow
   * Endpoint: GET /api/v1/students/me/progress-mentoring
   */
  async getFullProgressAndMentoring(
    token?: string | null
  ): Promise<FullProgressMentoringResponse> {
    const activeToken = token ?? getStoredToken();

    return apiFetch<FullProgressMentoringResponse>(
      "/api/v1/students/me/progress-mentoring",
      {
        method: "GET",
        token: activeToken,
      }
    );
  },

  // ============================================================================
  // Complete Sequential Chapter Learning Journey Endpoints (8 Agents)
  // ============================================================================

  /**
   * Start or execute complete sequential 8-agent chapter learning journey
   * Endpoint: POST /api/v1/learning-journey/start
   */
  async startLearningJourney(
    data: LearningJourneyStartRequest,
    token?: string | null
  ): Promise<LearningJourneyResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<LearningJourneyResponse>("/api/v1/learning-journey/start", {
      method: "POST",
      body: JSON.stringify(data),
      token: activeToken,
    });
  },

  /**
   * Retrieve learning journey state and outputs by ID
   * Endpoint: GET /api/v1/learning-journey/{journey_id}
   */
  async getLearningJourney(
    journeyId: string,
    token?: string | null
  ): Promise<LearningJourneyResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<LearningJourneyResponse>(`/api/v1/learning-journey/${journeyId}`, {
      method: "GET",
      token: activeToken,
    });
  },

  /**
   * Interact with active learning journey (submit answers, pause, resume, remediation)
   * Endpoint: POST /api/v1/learning-journey/{journey_id}/interact
   */
  async interactLearningJourney(
    journeyId: string,
    data: LearningJourneyInteractRequest,
    token?: string | null
  ): Promise<LearningJourneyResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<LearningJourneyResponse>(`/api/v1/learning-journey/${journeyId}/interact`, {
      method: "POST",
      body: JSON.stringify(data),
      token: activeToken,
    });
  },

  /**
   * List all chapter learning journeys for a student
   * Endpoint: GET /api/v1/learning-journey/student/{student_id}
   */
  async getStudentLearningJourneys(
    studentId: string,
    token?: string | null
  ): Promise<LearningJourneyResponse[]> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<LearningJourneyResponse[]>(`/api/v1/learning-journey/student/${studentId}`, {
      method: "GET",
      token: activeToken,
    });
  },

  // ============================================================================
  // CBSE Class 10 Curriculum System Endpoints
  // ============================================================================

  /**
   * Get official CBSE Class 10 curriculum overview
   * Endpoint: GET /api/v1/curriculum/catalog
   */
  async getCurriculumCatalog(): Promise<{
    board: { code: string; name: string };
    academic_session: string;
    class_code: string;
    official_portal: string;
    total_subjects: number;
    subjects: CurriculumSubjectResponse[];
  }> {
    return apiFetch("/api/v1/curriculum/catalog", { method: "GET" });
  },

  /**
   * List all official CBSE Class 10 subjects
   * Endpoint: GET /api/v1/curriculum/subjects
   */
  async getCurriculumSubjects(
    category?: string,
    isCompulsory?: boolean
  ): Promise<CurriculumSubjectResponse[]> {
    const params: Record<string, string | number | boolean> = {};
    if (category) params.category = category;
    if (isCompulsory !== undefined) params.is_compulsory = isCompulsory;
    return apiFetch<CurriculumSubjectResponse[]>("/api/v1/curriculum/subjects", {
      method: "GET",
      params,
    });
  },

  /**
   * Get subject details by ID
   * Endpoint: GET /api/v1/curriculum/subjects/{subject_id}
   */
  async getCurriculumSubject(subjectId: string): Promise<CurriculumSubjectResponse> {
    return apiFetch<CurriculumSubjectResponse>(`/api/v1/curriculum/subjects/${subjectId}`, {
      method: "GET",
    });
  },

  /**
   * Get full hierarchy (units, chapters, topics) for a subject
   * Endpoint: GET /api/v1/curriculum/subjects/{subject_id}/hierarchy
   */
  async getSubjectHierarchy(subjectId: string): Promise<any> {
    return apiFetch(`/api/v1/curriculum/subjects/${subjectId}/hierarchy`, {
      method: "GET",
    });
  },

  /**
   * List chapters for a curriculum subject
   * Endpoint: GET /api/v1/curriculum/subjects/{subject_id}/chapters
   */
  async getSubjectChapters(
    subjectId: string,
    unitId?: string
  ): Promise<CurriculumChapterSummary[]> {
    const params: Record<string, string | number | boolean> = {};
    if (unitId) params.unit_id = unitId;
    return apiFetch<CurriculumChapterSummary[]>(`/api/v1/curriculum/subjects/${subjectId}/chapters`, {
      method: "GET",
      params,
    });
  },

  /**
   * Get complete chapter details with topics and resources
   * Endpoint: GET /api/v1/curriculum/chapters/{chapter_id}
   */
  async getChapterDetails(chapterId: string): Promise<CurriculumChapterDetail> {
    return apiFetch<CurriculumChapterDetail>(`/api/v1/curriculum/chapters/${chapterId}`, {
      method: "GET",
    });
  },

  /**
   * List topics for a specific chapter
   * Endpoint: GET /api/v1/curriculum/chapters/{chapter_id}/topics
   */
  async getChapterTopics(chapterId: string): Promise<CurriculumTopicSummary[]> {
    return apiFetch<CurriculumTopicSummary[]>(`/api/v1/curriculum/chapters/${chapterId}/topics`, {
      method: "GET",
    });
  },

  /**
   * Get full pedagogical details for a topic
   * Endpoint: GET /api/v1/curriculum/topics/{topic_id}
   */
  async getTopicDetails(topicId: string): Promise<CurriculumTopicDetail> {
    return apiFetch<CurriculumTopicDetail>(`/api/v1/curriculum/topics/${topicId}`, {
      method: "GET",
    });
  },

  /**
   * Search curriculum catalog
   * Endpoint: GET /api/v1/curriculum/search
   */
  async searchCurriculum(
    query: string,
    subjectId?: string,
    limit?: number
  ): Promise<CurriculumSearchResponse> {
    const params: Record<string, string | number | boolean> = { q: query };
    if (subjectId) params.subject_id = subjectId;
    if (limit) params.limit = limit;
    return apiFetch<CurriculumSearchResponse>("/api/v1/curriculum/search", {
      method: "GET",
      params,
    });
  },

  /**
   * Enroll current student in chosen subjects
   * Endpoint: POST /api/v1/students/me/subjects
   */
  async setEnrolledSubjects(
    subjectIds: string[],
    token?: string | null
  ): Promise<StudentEnrolledSubjectResponse[]> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<StudentEnrolledSubjectResponse[]>("/api/v1/students/me/subjects", {
      method: "POST",
      body: JSON.stringify({ subject_ids: subjectIds }),
      token: activeToken,
    });
  },

  /**
   * Get current student's enrolled subjects
   * Endpoint: GET /api/v1/students/me/subjects
   */
  async getEnrolledSubjects(token?: string | null): Promise<StudentEnrolledSubjectResponse[]> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<StudentEnrolledSubjectResponse[]>("/api/v1/students/me/subjects", {
      method: "GET",
      token: activeToken,
    });
  },

  /**
   * Get progress for an enrolled subject
   * Endpoint: GET /api/v1/students/me/curriculum-progress/{subject_id}
   */
  async getSubjectProgress(
    subjectId: string,
    token?: string | null
  ): Promise<SubjectProgressResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<SubjectProgressResponse>(`/api/v1/students/me/curriculum-progress/${subjectId}`, {
      method: "GET",
      token: activeToken,
    });
  },

  /**
   * Update topic progress
   * Endpoint: POST /api/v1/students/me/topic-progress
   */
  async updateTopicProgress(
    data: TopicProgressUpdateRequest,
    token?: string | null
  ): Promise<TopicProgressResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<TopicProgressResponse>("/api/v1/students/me/topic-progress", {
      method: "POST",
      body: JSON.stringify(data),
      token: activeToken,
    });
  },

  /**
   * Start or resume interactive lesson session
   * Endpoint: POST /api/v1/students/me/lesson-sessions
   */
  async startLessonSession(
    data: LessonSessionCreateRequest,
    token?: string | null
  ): Promise<LessonSessionResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<LessonSessionResponse>("/api/v1/students/me/lesson-sessions", {
      method: "POST",
      body: JSON.stringify(data),
      token: activeToken,
    });
  },

  /**
   * Send a message to the AI Teacher within a lesson session
   * Endpoint: POST /api/v1/students/me/lesson-sessions/{session_id}/message
   */
  async sendLessonMessage(
    sessionId: string,
    message: string,
    token?: string | null
  ): Promise<LessonSessionResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<LessonSessionResponse>(`/api/v1/students/me/lesson-sessions/${sessionId}/message`, {
      method: "POST",
      body: JSON.stringify({ message }),
      token: activeToken,
    });
  },

  /**
   * Get active lesson session
   * Endpoint: GET /api/v1/students/me/lesson-sessions/active
   */
  async getActiveLessonSession(
    chapterId?: string,
    token?: string | null
  ): Promise<LessonSessionResponse | null> {
    const activeToken = token ?? getStoredToken();
    const params: Record<string, string> = {};
    if (chapterId) params.chapter_id = chapterId;
    return apiFetch<LessonSessionResponse | null>("/api/v1/students/me/lesson-sessions/active", {
      method: "GET",
      params,
      token: activeToken,
    });
  },

  /**
   * Complete lesson session
   * Endpoint: POST /api/v1/students/me/lesson-sessions/{session_id}/complete
   */
  async completeLessonSession(
    sessionId: string,
    token?: string | null
  ): Promise<LessonSessionResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<LessonSessionResponse>(`/api/v1/students/me/lesson-sessions/${sessionId}/complete`, {
      method: "POST",
      token: activeToken,
    });
  },

  /**
   * Toggle bookmark
   * Endpoint: POST /api/v1/students/me/bookmarks
   */
  async toggleBookmark(
    data: BookmarkToggleRequest,
    token?: string | null
  ): Promise<BookmarkResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<BookmarkResponse>("/api/v1/students/me/bookmarks", {
      method: "POST",
      body: JSON.stringify(data),
      token: activeToken,
    });
  },

  /**
   * Get student bookmarks
   * Endpoint: GET /api/v1/students/me/bookmarks
   */
  async getBookmarks(
    entityType?: string,
    token?: string | null
  ): Promise<any[]> {
    const activeToken = token ?? getStoredToken();
    const params: Record<string, string> = {};
    if (entityType) params.entity_type = entityType;
    return apiFetch<any[]>("/api/v1/students/me/bookmarks", {
      method: "GET",
      params,
      token: activeToken,
    });
  },

  /**
   * Phase Pre-0 2.0: Generate 20-30 Question Topic-Wise Diagnostic Assessment
   * Endpoint: POST /api/v1/diagnostic/generate
   */
  async generateDiagnosticAssessment(
    request: DiagnosticAssessmentGenerateRequest,
    token?: string | null
  ): Promise<DiagnosticAssessmentGenerateResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<DiagnosticAssessmentGenerateResponse>("/api/v1/diagnostic/generate", {
      method: "POST",
      body: JSON.stringify(request),
      token: activeToken,
    });
  },

  /**
   * Phase Pre-0 2.0: Evaluate Submitted Diagnostic Answers
   * Endpoint: POST /api/v1/diagnostic/evaluate
   */
  async evaluateDiagnosticAssessment(
    request: DiagnosticEvaluateRequest,
    token?: string | null
  ): Promise<FullDiagnosticReportResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<FullDiagnosticReportResponse>("/api/v1/diagnostic/evaluate", {
      method: "POST",
      body: JSON.stringify(request),
      token: activeToken,
    });
  },

  /**
   * Phase Pre-0 2.0: Generate Adaptive Remedial Probes for Weak Topics
   * Endpoint: POST /api/v1/diagnostic/adaptive-probes
   */
  async generateAdaptiveProbes(
    request: AdaptiveProbeRequest,
    token?: string | null
  ): Promise<DiagnosticAssessmentGenerateResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<DiagnosticAssessmentGenerateResponse>("/api/v1/diagnostic/adaptive-probes", {
      method: "POST",
      body: JSON.stringify(request),
      token: activeToken,
    });
  },

  /**
   * Phase Pre-0 2.0: Generate Complete Chapter Practice Sets (60 questions: 30 basic, 20 med, 10 hard)
   * Endpoint: POST /api/v1/practice/generate-set
   */
  async generateChapterPracticeSet(
    request: ChapterPracticeSetRequest,
    token?: string | null
  ): Promise<ChapterPracticeSetResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<ChapterPracticeSetResponse>("/api/v1/practice/generate-set", {
      method: "POST",
      body: JSON.stringify(request),
      token: activeToken,
    });
  },

  /**
   * Phase Pre-0 2.0: Save Unfinished Practice Session
   * Endpoint: POST /api/v1/practice/save-session
   */
  async savePracticeSession(
    request: SavePracticeSessionRequest,
    token?: string | null
  ): Promise<SavePracticeSessionResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<SavePracticeSessionResponse>("/api/v1/practice/save-session", {
      method: "POST",
      body: JSON.stringify(request),
      token: activeToken,
    });
  },

  /**
   * Phase Pre-0 2.0: Resume Unfinished Practice Session
   * Endpoint: GET /api/v1/practice/resume-session/{session_id}
   */
  async resumePracticeSession(
    sessionId: string,
    token?: string | null
  ): Promise<SavePracticeSessionRequest> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<SavePracticeSessionRequest>(`/api/v1/practice/resume-session/${sessionId}`, {
      method: "GET",
      token: activeToken,
    });
  },

  /**
   * Phase Pre-0 2.0: Get Comprehensive Multi-Tier Progress Dashboard
   * Endpoint: GET /api/v1/students/me/dashboard-progress
   */
  async getComprehensiveProgressDashboard(
    token?: string | null
  ): Promise<ComprehensiveProgressDashboardResponse> {
    const activeToken = token ?? getStoredToken();
    return apiFetch<ComprehensiveProgressDashboardResponse>("/api/v1/students/me/dashboard-progress", {
      method: "GET",
      token: activeToken,
    });
  },
};
