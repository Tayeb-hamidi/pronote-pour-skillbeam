import {
  AuthTokenResponse,
  ContentSet,
  ExportFormat,
  Job,
  ProjectAnalytics,
  Project,
  PronoteImportResult,
  QualityPreview,
  QuestionBankVersion,
  SourceDocument,
  SourceInitResponse,
  SourceType,
  ContentType
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";
const POLL_INTERVAL_MS = 1500;

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    cache: "no-store"
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `HTTP ${response.status}`);
  }

  return (await response.json()) as T;
}

export function login(email: string, password: string): Promise<AuthTokenResponse> {
  return request<AuthTokenResponse>("/v1/auth/token", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

export function createProject(token: string, title: string): Promise<Project> {
  return request<Project>(
    "/v1/projects",
    {
      method: "POST",
      body: JSON.stringify({ title })
    },
    token
  );
}

export function initSource(
  token: string,
  projectId: string,
  payload: {
    source_type: SourceType;
    filename?: string;
    mime_type?: string;
    size_bytes?: number;
    raw_text?: string;
    link_url?: string;
    topic?: string;
    subject?: string;
    class_level?: string;
    difficulty_target?: string;
    learning_goal?: string;
    enable_ocr?: boolean;
    enable_table_extraction?: boolean;
    smart_cleaning?: boolean;
  }
): Promise<SourceInitResponse> {
  return request<SourceInitResponse>(
    `/v1/projects/${projectId}/sources`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    token
  );
}

export async function uploadToPresigned(uploadUrl: string, file: File): Promise<void> {
  const response = await fetch(uploadUrl, {
    method: "PUT",
    body: file,
    headers: {
      "Content-Type": file.type
    }
  });
  if (!response.ok) {
    throw new Error(`Upload failed: ${response.status}`);
  }
}

export function launchIngest(token: string, projectId: string, sourceAssetId?: string): Promise<{ job_id: string }> {
  return request<{ job_id: string }>(
    `/v1/projects/${projectId}/ingest`,
    {
      method: "POST",
      body: JSON.stringify({ source_asset_id: sourceAssetId })
    },
    token
  );
}

export function launchGenerate(
  token: string,
  projectId: string,
  payload: {
    content_types: ContentType[];
    instructions?: string;
    max_items?: number;
    language?: string;
    level?: string;
    subject?: string;
    class_level?: string;
    difficulty_target?: string;
  }
): Promise<{ job_id: string }> {
  return request<{ job_id: string }>(
    `/v1/projects/${projectId}/generate`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    token
  );
}

export function getSourceDocument(token: string, projectId: string): Promise<SourceDocument> {
  return request<SourceDocument>(`/v1/projects/${projectId}/document`, { method: "GET" }, token);
}

export function updateSourceDocument(
  token: string,
  projectId: string,
  payload: { plain_text: string }
): Promise<SourceDocument> {
  return request<SourceDocument>(
    `/v1/projects/${projectId}/document`,
    {
      method: "PUT",
      body: JSON.stringify(payload)
    },
    token
  );
}

export function getJob(token: string, jobId: string): Promise<Job> {
  return request<Job>(`/v1/jobs/${jobId}`, { method: "GET" }, token);
}

export function getContent(token: string, projectId: string): Promise<ContentSet> {
  return request<ContentSet>(`/v1/projects/${projectId}/content`, { method: "GET" }, token);
}

export function saveContent(
  token: string,
  projectId: string,
  payload: Pick<ContentSet, "content_set_id" | "items">
): Promise<ContentSet> {
  return request<ContentSet>(
    `/v1/projects/${projectId}/content`,
    {
      method: "PUT",
      body: JSON.stringify(payload)
    },
    token
  );
}

export function getQualityPreview(token: string, projectId: string): Promise<QualityPreview> {
  return request<QualityPreview>(`/v1/projects/${projectId}/quality-preview`, { method: "GET" }, token);
}

export function listQuestionBankVersions(token: string, projectId: string): Promise<QuestionBankVersion[]> {
  return request<QuestionBankVersion[]>(`/v1/projects/${projectId}/question-bank/versions`, { method: "GET" }, token);
}

export function createQuestionBankVersion(
  token: string,
  projectId: string,
  payload: { content_set_id?: string; label?: string }
): Promise<QuestionBankVersion> {
  return request<QuestionBankVersion>(
    `/v1/projects/${projectId}/question-bank/versions`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    token
  );
}

export function restoreQuestionBankVersion(
  token: string,
  projectId: string,
  versionId: string
): Promise<ContentSet> {
  return request<ContentSet>(
    `/v1/projects/${projectId}/question-bank/versions/${versionId}/restore`,
    {
      method: "POST"
    },
    token
  );
}

export function importPronoteXml(
  token: string,
  projectId: string,
  payload: { xml_content: string; source_filename?: string; replace_current_content?: boolean }
): Promise<PronoteImportResult> {
  return request<PronoteImportResult>(
    `/v1/projects/${projectId}/pronote/import`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    token
  );
}

export function getProjectAnalytics(token: string, projectId: string): Promise<ProjectAnalytics> {
  return request<ProjectAnalytics>(`/v1/projects/${projectId}/analytics`, { method: "GET" }, token);
}

export function launchExport(
  token: string,
  projectId: string,
  payload: { format: ExportFormat; options?: Record<string, unknown> }
): Promise<{ job_id: string }> {
  return request<{ job_id: string }>(
    `/v1/projects/${projectId}/export`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    token
  );
}

export function getExportDownload(token: string, exportId: string): Promise<{ export_id: string; url: string }> {
  return request<{ export_id: string; url: string }>(`/v1/exports/${exportId}/download`, { method: "GET" }, token);
}

export async function pollJobUntilDone(
  token: string,
  jobId: string,
  onUpdate?: (job: Job) => void
): Promise<Job> {
  let current = await getJob(token, jobId);
  onUpdate?.(current);
  while (current.status === "queued" || current.status === "running") {
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    current = await getJob(token, jobId);
    onUpdate?.(current);
  }
  if (current.status === "failed") {
    throw new Error(current.error_message ?? "Job failed");
  }
  return current;
}
