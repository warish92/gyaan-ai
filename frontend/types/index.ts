/**
 * Gyaan AI - Core Frontend TypeScript Definitions
 * Matching backend Pydantic models from backend/app/schemas.py
 */

export interface HealthResponse {
  status: "healthy" | "degraded" | string;
  app: string;
  ollama_connected: boolean;
  model_available: boolean;
  model_name: string;
  details?: string | null;
}

export interface ApiErrorDetail {
  error: string;
  message?: string;
  request_id?: string;
}

export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  status: number;
}

/**
 * Authentication & Student Profile Types (Phase 5 & 8.5)
 */
export interface StudentRegisterRequest {
  display_name: string;
  email: string;
  password: string;
  grade?: string;
  preferred_language?: string;
}

export interface StudentLoginRequest {
  email: string;
  password: string;
}

export interface StudentProfileResponse {
  id: string;
  email?: string | null;
  display_name: string;
  grade: string;
  preferred_language: string;
  created_at: string;
  updated_at?: string | null;
  account_status: string;
}

export interface AuthTokenResponse {
  token: string;
  token_type: string;
  expires_at: string;
  student: StudentProfileResponse;
}

export interface StudentProfileUpdateRequest {
  display_name?: string;
  grade?: string;
  preferred_language?: string;
}

export interface LearningSessionResponse {
  id: string;
  student_id: string;
  subject: string;
  topic: string;
  activity_type: string;
  status: string;
  started_at: string;
  completed_at?: string | null;
  details?: Record<string, unknown> | null;
}

export interface TopicMasteryResponse {
  id: string;
  student_id: string;
  subject: string;
  topic: string;
  latest_score: number;
  max_marks: number;
  percentage: number;
  attempts_count: number;
  mastery_status: string;
  last_assessed_at: string;
  updated_at: string;
}

export interface AssessmentHistoryItem {
  id?: string;
  attempt_id?: string;
  quiz_id: string;
  student_id?: string | null;
  score: number;
  max_marks: number;
  percentage?: number;
  created_at?: string;
  completed_at?: string;
  evaluation_summary?: string | null;
  evaluation_details?: Record<string, any> | null;
  subject?: string;
  topic?: string | null;
  grade?: string;
}

export interface SavedDiagnosticRecord {
  id: string;
  student_id: string;
  subject: string;
  topic: string;
  assessment_input: AssessmentItem[] | string;
  diagnostic_output: string;
  created_at: string;
}

export interface SavedCurriculumPlan {
  plan_id: string;
  student_id: string;
  diagnostic_id: string;
  plan_output: string;
  created_at: string;
  subject: string;
  topic: string;
}

export interface StudentDashboardStats {
  total_sessions: number;
  total_quizzes_taken: number;
  topics_mastered: number;
  topics_in_progress: number;
  topics_needing_revision: number;
}

export interface StudentDashboardResponse {
  profile: StudentProfileResponse;
  recent_learning_sessions: LearningSessionResponse[];
  recent_diagnostics: SavedDiagnosticRecord[];
  recent_curriculum_plans: SavedCurriculumPlan[];
  recent_assessments: AssessmentHistoryItem[];
  topic_mastery: TopicMasteryResponse[];
  stats: StudentDashboardStats;
}

/**
 * Diagnostic & Learning Plan Types (Phase 3 & 8.6)
 */
export interface AssessmentItem {
  question: string;
  student_answer: string;
  expected_answer?: string | null;
}

export interface LearningPlanRequest {
  student_id?: string | null;
  display_name?: string;
  grade?: string;
  subject: string;
  topic: string;
  assessment_items: AssessmentItem[];
}

export interface LearningPlanResponse {
  workflow_id: string;
  student_id: string;
  diagnostic_report: string;
  curriculum_plan: string;
  status: string;
  model: string;
  duration_ms: number;
  persisted: boolean;
  diagnostic_id?: string | null;
  plan_id?: string | null;
}

/**
 * Teacher Agent Request Schema (POST /api/v1/ask)
 */
export interface AskRequest {
  question: string;
  grade?: string;
  subject?: string | null;
  chapter?: string | null;
  topic?: string | null;
  subtopic?: string | null;
  learning_objectives?: string[] | null;
  lesson_mode?: "conceptual" | "simplified" | "real_world" | "practice" | "doubt_clearing" | string;
  language?: string;
  document_ids?: string[] | null;
}

/**
 * Teacher Agent Response Schema
 */
export interface AskResponse {
  answer: string;
  request_id: string;
  model: string;
  status: string;
  duration_ms: number;
  agent_name?: string;
  selected_agents?: string[];
  workflow_executed?: string;
  detected_intent?: string;
  student_documents?: DocumentProvenance[] | null;
}

/**
 * Orchestrator Request Schema (POST /api/v1/orchestrate)
 */
export interface OrchestrationRequest {
  request: string;
  grade?: string;
  subject?: string | null;
  language?: string;
  workflow_preference?: string | null;
  metadata?: Record<string, unknown>;
}

export interface OrchestrationResponse {
  request_id: string;
  workflow_id: string;
  detected_intent: string;
  selected_workflow: string;
  selected_agents: string[];
  routing_reason: string;
  clarification_required: boolean;
  clarification_question?: string | null;
  result?: unknown;
  status: string;
  duration_ms: number;
  model: string;
}

/**
 * Frontend Chat UI State Types
 */
export interface ChatMessage {
  id: string;
  sender: "student" | "teacher";
  text: string;
  timestamp: string;
  metadata?: {
    requestId?: string;
    model?: string;
    durationMs?: number;
    agentName?: string;
    status?: string;
    workflowExecuted?: string;
    detectedIntent?: string;
    studentDocuments?: DocumentProvenance[];
  };
  isError?: boolean;
}

/**
 * Phase 4 & 8.7 Schemas: Resource Agent & Assessment Agent
 */
export interface ResourceRequest {
  grade?: string;
  subject: string;
  topic: string;
  learning_objective?: string | null;
}

export interface ResourceSourceItem {
  source_id?: string;
  title?: string;
  grade?: string;
  subject?: string;
  chapter?: string;
  section?: string;
  page_start?: number;
  page_end?: number;
  is_verified?: boolean;
  keywords?: string[];
  excerpt?: string;
  [key: string]: unknown;
}

export interface ResourceResponse {
  workflow_id: string;
  resource_recommendation: string;
  is_verified: boolean;
  source_type: string;
  sources: ResourceSourceItem[];
  model: string;
  duration_ms: number;
}

export interface StudentQuizQuestion {
  id: string;
  type: string;
  question: string;
  options: string[];
  marks: number;
  difficulty?: string;
}

export interface QuizGenerationRequest {
  student_id?: string | null;
  grade?: string;
  subject: string;
  topic: string;
  num_questions?: number;
  question_types?: string[];
  learning_objectives?: string | null;
}

export interface QuizGenerationResponse {
  quiz_id: string;
  student_id?: string | null;
  subject: string;
  topic: string;
  grade: string;
  questions: StudentQuizQuestion[];
  is_verified_source: boolean;
  source_type: string;
  duration_ms: number;
}

export interface AssessmentSubmissionRequest {
  quiz_id: string;
  student_id?: string | null;
  answers: Record<string, string>;
}

export interface QuestionEvaluation {
  question_id: string;
  score_awarded: number;
  max_marks: number;
  status: string;
  student_answer: string;
  expected_answer: string;
  feedback: string;
  revision_topic?: string | null;
}

export interface AssessmentSubmissionResponse {
  attempt_id: string;
  quiz_id: string;
  student_id?: string | null;
  total_score: number;
  max_marks: number;
  percentage: number;
  evaluations: QuestionEvaluation[];
  overall_feedback: string;
  duration_ms: number;
  persisted: boolean;
}

export interface AssessmentHistoryResponse {
  student_id: string;
  total_attempts: number;
  attempts: AssessmentHistoryItem[];
}

/**
 * Phase 6 & 8.8 Schemas: Progress Agent & Mentor Agent
 */
export interface ObjectiveStatisticsResponse {
  student_id: string;
  has_sufficient_history: boolean;
  total_assessments_completed: number;
  unique_quizzes_taken: number;
  total_questions_answered: number;
  correct_answers_count: number;
  partially_correct_answers_count: number;
  incorrect_answers_count: number;
  average_percentage: number | null;
  performance_trend: string;
  trend_description: string;
  strengths: string[];
  areas_needing_improvement: string[];
  topics_needing_practice: string[];
  total_learning_sessions: number;
  completed_sessions_count: number;
  sessions_by_type: Record<string, number>;
  diagnostic_records_count: number;
  curriculum_plans_count: number;
  most_recent_activity_date: string | null;
}

export interface TopicObservation {
  topic: string;
  observation: string;
  status: "mastered" | "in_progress" | "needs_revision" | string;
}

export interface ProgressReportResponse {
  student_id: string;
  objective_statistics: ObjectiveStatisticsResponse;
  overall_summary: string;
  strengths_analysis: string[];
  weaknesses_analysis: string[];
  topic_observations: TopicObservation[];
  performance_interpretation: string;
  data_limitations?: string | null;
  recommended_priorities: string[];
  model: string;
  duration_ms: number;
}

export interface MentorRecommendationItem {
  title: string;
  topic: string;
  reason: string;
  suggested_action: string;
  priority: "high" | "medium" | "low" | string;
  estimated_minutes?: number;
  supporting_evidence?: string | null;
  resource_reference?: string | null;
}

export interface MentorRecommendationsResponse {
  student_id: string;
  mentor_overview: string;
  recommendations: MentorRecommendationItem[];
  study_tip?: string | null;
  next_milestone?: string | null;
  model: string;
  duration_ms: number;
}

export interface FullProgressMentoringResponse {
  student_id: string;
  progress: ProgressReportResponse;
  mentoring: MentorRecommendationsResponse;
  duration_ms: number;
}

/**
 * Sequential Chapter Learning Journey Schemas (8 Canonical Agents)
 */
export interface LearningJourneyStartRequest {
  subject: string;
  chapter: string;
  learning_goal?: string | null;
  grade?: string;
  language?: string;
  student_id?: string | null;
  student_input_evidence?: string | null;
  student_answers?: Record<string, string> | null;
  is_remediation?: boolean;
  max_retries?: number;
}

export interface LearningJourneyInteractRequest {
  action: "submit_answers" | "acknowledge_lesson" | "pause" | "resume" | "request_remediation" | string;
  student_answers?: Record<string, string> | null;
  feedback?: string | null;
}

export interface LearningJourneyResponse {
  journey_id: string;
  student_id?: string | null;
  subject: string;
  chapter: string;
  learning_goal?: string | null;
  current_step: string;
  status: "active" | "needs_student_input" | "completed" | "paused" | string;
  loop_iteration: number;
  max_retries: number;
  mastery_score: number;
  mastery_achieved: boolean;
  step_outputs?: Record<string, string | unknown>;
  adaptive_action?: string | null;
  duration_seconds?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
}





/**
 * CBSE Class 10 Curriculum System Types
 */
export interface CurriculumSubjectResponse {
  id: string;
  class_id: string;
  code: string;
  name: string;
  short_name?: string | null;
  category: string;
  is_compulsory: boolean;
  description?: string | null;
  official_syllabus_url?: string | null;
  verification_status: string;
  unit_count?: number;
  chapter_count?: number;
}

export interface CurriculumUnitResponse {
  id: string;
  subject_id: string;
  unit_number: number;
  title: string;
  section_tag?: string | null;
  description?: string | null;
  weightage_marks: number;
}

export interface CurriculumChapterSummary {
  id: string;
  subject_id: string;
  unit_id?: string | null;
  chapter_number: number;
  title: string;
  slug?: string | null;
  section_tag?: string | null;
  description?: string | null;
  estimated_minutes: number;
  is_prescribed: boolean;
  topic_count: number;
  unit_title?: string | null;
}

export interface CurriculumTopicSummary {
  id: string;
  chapter_id: string;
  topic_number: number;
  title: string;
  slug?: string | null;
  summary?: string | null;
  importance: string;
  difficulty_level: string;
}

export interface CurriculumSubtopicResponse {
  id: string;
  topic_id: string;
  subtopic_number: number;
  title: string;
  explanation?: string | null;
}

export interface CurriculumObjectiveResponse {
  id: string;
  topic_id: string;
  objective_code?: string | null;
  description: string;
  bloom_level: string;
}

export interface CurriculumResourceResponse {
  id: string;
  chapter_id?: string | null;
  topic_id?: string | null;
  title: string;
  resource_type: string;
  url?: string | null;
  notes?: string | null;
}

export interface CurriculumTopicDetail {
  id: string;
  chapter_id: string;
  topic_number: number;
  title: string;
  slug?: string | null;
  summary?: string | null;
  importance: string;
  difficulty_level: string;
  key_concepts: string[];
  definitions: Record<string, string>;
  formulas: string[];
  common_misconceptions: string[];
  practice_questions: Array<{
    id?: string;
    question: string;
    type?: string;
    expected_answer?: string;
  }>;
  subtopics: CurriculumSubtopicResponse[];
  learning_objectives: CurriculumObjectiveResponse[];
  resources: CurriculumResourceResponse[];
  chapter_title?: string | null;
  subject_name?: string | null;
}

export interface CurriculumChapterDetail {
  id: string;
  subject_id: string;
  unit_id?: string | null;
  chapter_number: number;
  title: string;
  slug?: string | null;
  section_tag?: string | null;
  description?: string | null;
  estimated_minutes: number;
  prerequisites?: string[];
  is_prescribed: boolean;
  excluded_topics?: string | null;
  source_reference?: string | null;
  verification_status: string;
  unit_title?: string | null;
  subject_name?: string | null;
  subject_code?: string | null;
  topics: CurriculumTopicDetail[];
  resources: CurriculumResourceResponse[];
}

export interface EnrollSubjectsRequest {
  subject_ids: string[];
}

export interface StudentEnrolledSubjectResponse {
  id: string;
  code: string;
  name: string;
  short_name?: string | null;
  category: string;
  is_compulsory: boolean;
  description?: string | null;
  chapter_count: number;
  total_topics: number;
  completed_topics: number;
  progress_percentage: number;
  enrolled_at?: string;
}

export interface TopicProgressUpdateRequest {
  topic_id: string;
  status: "not_started" | "in_progress" | "completed" | "mastered" | string;
  time_spent_seconds?: number;
  notes?: string | null;
}

export interface TopicProgressResponse {
  id: string;
  student_id: string;
  topic_id: string;
  status: string;
  time_spent_seconds: number;
  last_studied_at?: string | null;
  notes?: string | null;
  updated_at: string;
}

export interface SubjectProgressResponse {
  student_id: string;
  subject_id: string;
  total_topics: number;
  completed_topics: number;
  in_progress_topics: number;
  mastered_topics: number;
  progress_percentage: number;
  total_study_time_seconds: number;
}

export interface LessonSessionCreateRequest {
  subject_id: string;
  chapter_id: string;
  topic_id?: string | null;
  subtopic_id?: string | null;
  lesson_mode?: "conceptual" | "simplified" | "real_world" | "practice" | "doubt_clearing" | string;
}

export interface LessonMessageRequest {
  message: string;
}

export interface LessonSessionResponse {
  id: string;
  student_id: string;
  subject_id: string;
  chapter_id: string;
  topic_id?: string | null;
  subtopic_id?: string | null;
  lesson_mode: string;
  messages: Array<{
    role: "student" | "teacher";
    content: string;
    timestamp?: string;
  }>;
  status: "active" | "completed" | string;
  started_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface BookmarkToggleRequest {
  entity_type: "chapter" | "topic" | "resource" | "question" | string;
  entity_id: string;
  note?: string | null;
}

export interface BookmarkResponse {
  action: "created" | "removed";
  entity_type: string;
  entity_id: string;
  note?: string | null;
  id?: string | null;
}

export interface CurriculumSearchResponse {
  query: string;
  chapters: Array<{
    id: string;
    subject_id: string;
    chapter_number: number;
    title: string;
    description?: string;
    section_tag?: string;
    subject_name?: string;
    subject_code?: string;
  }>;
  topics: Array<{
    id: string;
    chapter_id: string;
    topic_number: number;
    title: string;
    summary?: string;
    importance?: string;
    chapter_title?: string;
    chapter_number?: number;
    subject_id?: string;
    subject_name?: string;
  }>;
  total_matches: number;
}

// ==============================================================================
// Agent Arena & Canonical Multi-Agent Registry Types
// ==============================================================================

export interface AgentMetadataResponse {
  id: string;
  name: string;
  title: string;
  role: string;
  goal: string;
  backstory: string;
  model: string;
  llm_provider: string;
  temperature: number;
  phase: string;
  status: "idle" | "running" | "completed" | "error";
  registration_status: "registered" | "error";
  associated_workflows: string[];
  total_executions: number;
  last_execution_time?: string | null;
  last_duration_seconds?: number | null;
  last_workflow?: string | null;
  last_error?: string | null;
}

export interface ArenaStatusResponse {
  total_agents: number;
  registered_agents: number;
  running_agents: number;
  idle_agents: number;
  error_agents: number;
  model: string;
  provider: string;
  base_url: string;
  status: "healthy" | "degraded";
  canonical_roster: string[];
}

export interface WorkflowDescriptorResponse {
  workflow_id: string;
  name: string;
  description: string;
  agents: string[];
  requires_auth: boolean;
}

// ==============================================================================
// Phase Pre-0 2.0 Types: Diagnostic Assessment (25q), Practice Sets (60q),
// Multi-Difficulty Distribution, and Enhanced Progress Reporting
// ==============================================================================

export interface DiagnosticQuestionItem {
  id: string;
  subject_id?: string | null;
  chapter_id?: string | null;
  topic_id?: string | null;
  topic: string;
  learning_objective_id?: string | null;
  difficulty: "basic" | "medium" | "hard" | string;
  question_type: "mcq" | "true_false" | "fill_blank" | "short_answer" | "conceptual" | "numerical" | "assertion_reason" | "case_based" | string;
  question: string;
  options: string[];
  marks: number;
  expected_answer?: string | null;
  marking_rubric?: string | null;
  explanation?: string | null;
  source_reference?: string | null;
}

export interface DiagnosticAssessmentGenerateRequest {
  student_id?: string | null;
  grade?: string;
  subject: string;
  chapter: string;
  chapter_id?: string | null;
  topics?: string[] | null;
  prerequisite_topics?: string[] | null;
  num_questions?: number;
  question_formats?: string[] | null;
}

export interface DiagnosticAssessmentGenerateResponse {
  assessment_id: string;
  student_id?: string | null;
  grade: string;
  subject: string;
  chapter: string;
  target_topics: string[];
  total_questions: number;
  questions: DiagnosticQuestionItem[];
  duration_ms: number;
  is_cached?: boolean;
}

export interface DiagnosticEvaluateRequest {
  assessment_id: string;
  student_id?: string | null;
  subject: string;
  chapter: string;
  answers: Record<string, string>;
}

export interface TopicDiagnosticResult {
  topic: string;
  total_questions: number;
  correct_count: number;
  partially_correct_count: number;
  incorrect_count: number;
  score: number;
  max_marks: number;
  percentage: number;
  mastery_status: "mastered" | "in_progress" | "needs_revision" | "prerequisite_gap" | string;
  misconceptions: string[];
  knowledge_gaps: string[];
}

export interface FullDiagnosticReportResponse {
  report_id: string;
  assessment_id: string;
  student_id?: string | null;
  subject: string;
  chapter: string;
  total_questions: number;
  correct_answers: number;
  partially_correct_answers: number;
  incorrect_answers: number;
  total_score: number;
  max_marks: number;
  percentage: number;
  overall_classification: string;
  topic_results: TopicDiagnosticResult[];
  demonstrated_understanding: string[];
  evidenced_knowledge_gaps: string[];
  uncovered_misconceptions: string[];
  prerequisite_gaps: string[];
  recommended_remediation: string[];
  recommended_focus_topics: string[];
  adaptive_probes_recommended: boolean;
  overall_summary: string;
  duration_ms: number;
  persisted: boolean;
}

export interface AdaptiveProbeRequest {
  student_id?: string | null;
  subject: string;
  chapter: string;
  weak_topic: string;
  previous_misconception?: string | null;
  num_probes?: number;
}

export interface PracticeQuestionItem {
  id: string;
  subject_id?: string | null;
  chapter_id?: string | null;
  topic_id?: string | null;
  topic: string;
  learning_objective_id?: string | null;
  difficulty: "basic" | "medium" | "hard" | string;
  question_type: "mcq" | "true_false" | "fill_blank" | "short_answer" | "long_answer" | "numerical" | "conceptual" | "assertion_reason" | "case_based" | "application" | string;
  question: string;
  options: string[];
  marks: number;
  expected_answer?: string | null;
  marking_rubric?: string | null;
  explanation?: string | null;
  source_reference?: string | null;
}

export interface ChapterPracticeSetRequest {
  student_id?: string | null;
  grade?: string;
  subject: string;
  chapter: string;
  topic?: string | null;
  difficulty_tier?: "basic" | "medium" | "hard" | "all" | string;
  question_types?: string[] | null;
}

export interface ChapterPracticeSetResponse {
  practice_set_id: string;
  student_id?: string | null;
  grade: string;
  subject: string;
  chapter: string;
  difficulty_tier: string;
  total_questions: number;
  basic_count: number;
  medium_count: number;
  hard_count: number;
  questions: PracticeQuestionItem[];
  duration_ms: number;
  is_cached?: boolean;
}

export interface SavePracticeSessionRequest {
  session_id: string;
  student_id?: string | null;
  practice_set_id: string;
  chapter: string;
  answers: Record<string, string>;
  current_index?: number;
  time_spent_seconds?: number;
}

export interface SavePracticeSessionResponse {
  session_id: string;
  status: string;
  saved_at: string;
}

export interface SubjectProgressItem {
  subject: string;
  quizzes_taken: number;
  average_score?: number | null;
  topics_mastered: number;
  topics_in_progress: number;
  topics_needing_revision: number;
}

export interface ChapterCompletionItem {
  chapter_id: string;
  title: string;
  subject: string;
  status: "not_started" | "in_progress" | "completed" | string;
  mastery_percentage: number;
  objectives_completed: number;
  total_objectives: number;
}

export interface ComprehensiveProgressDashboardResponse {
  student_id: string;
  student_name: string;
  grade: string;
  has_sufficient_history: boolean;
  overall_accuracy?: number | null;
  total_assessments: number;
  total_questions_answered: number;
  performance_trend: string;
  trend_description: string;
  subject_progress: SubjectProgressItem[];
  chapter_completion: ChapterCompletionItem[];
  topic_mastery: TopicObservation[];
  strengths: string[];
  weaknesses: string[];
  recent_attempts: AssessmentHistoryItem[];
  recommended_priorities: string[];
  empty_state_guide?: string | null;
  duration_ms: number;
}

/**
 * Phase 5D: Student Document Management & RAG Schemas
 */
export interface DocumentProvenance {
  document_id: string;
  filename: string;
  chunk_id: string;
  page_number: number;
  chunk_index: number;
  similarity_score: number;
  text: string;
}

export interface DocumentMetadataResponse {
  id: string;
  student_id: string;
  filename: string;
  file_size: number;
  content_type: string;
  page_count: number;
  chunk_count: number;
  indexing_status: "INDEXED" | "PROCESSING" | "FAILED" | string;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentSearchRequest {
  query: string;
  document_ids?: string[] | null;
  max_results?: number;
  min_score?: number;
}

export interface DocumentSearchResultItem {
  chunk_id: string;
  document_id: string;
  student_id: string;
  page_number: number;
  chunk_index: number;
  text: string;
  similarity_score: number;
}

export interface DocumentSearchResponse {
  query: string;
  results_count: number;
  results: DocumentSearchResultItem[];
}

export interface DocumentDeleteResponse {
  success: boolean;
  message: string;
  document_id: string;
}

