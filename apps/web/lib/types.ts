export type SourceType = "document" | "text" | "theme" | "youtube" | "link";

export type ContentType =
  | "course_structure"
  | "mcq"
  | "poll"
  | "open_question"
  | "cloze"
  | "matching"
  | "brainstorming"
  | "flashcards";

export type ExportFormat = "docx" | "pdf" | "xlsx" | "moodle_xml" | "pronote_xml" | "qti" | "h5p" | "anki";

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Project {
  id: string;
  title: string;
  state: string;
}

export interface SourceInitResponse {
  asset_id: string;
  upload_url?: string;
  object_key?: string;
}

export interface SourceDocument {
  document_id: string;
  project_id: string;
  plain_text: string;
  metadata: Record<string, unknown>;
  updated_at: string;
}

export interface Job {
  id: string;
  project_id: string;
  status: JobStatus;
  progress: number;
  logs_json: Array<{ at: string; message: string }>;
  error_message?: string;
  result_id?: string;
}

export interface ContentItem {
  id: string;
  item_type: string;
  prompt: string;
  correct_answer?: string;
  distractors: string[];
  answer_options: string[];
  tags: string[];
  difficulty: string;
  feedback?: string;
  source_reference?: string;
  position: number;
}

export interface ContentSet {
  content_set_id: string;
  project_id: string;
  status: string;
  language: string;
  level: string;
  items: ContentItem[];
}

export interface QualityIssue {
  code: string;
  severity: "critical" | "major" | "minor" | string;
  message: string;
  item_id?: string;
  item_index?: number;
}

export interface QualityPreview {
  project_id: string;
  content_set_id?: string;
  overall_score: number;
  readiness: "ready" | "review_needed" | "blocked" | string;
  metrics: Record<string, unknown>;
  issues: QualityIssue[];
}

export interface QuestionBankVersion {
  id: string;
  project_id: string;
  content_set_id?: string;
  version_number: number;
  label: string;
  source: string;
  created_at: string;
}

export interface PronoteImportResult {
  project_id: string;
  imported_items_count: number;
  content_set_id?: string;
  type_breakdown: Record<string, number>;
  import_run_id: string;
}

export interface ProjectAnalytics {
  project_id: string;
  total_items: number;
  latest_content_set_id?: string;
  by_item_type: Record<string, number>;
  by_difficulty: Record<string, number>;
  jobs_by_status: Record<string, number>;
  export_by_format: Record<string, number>;
  question_bank_versions: number;
  pronote_import_runs: number;
}
