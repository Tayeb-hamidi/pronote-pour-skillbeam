"""Pydantic schemas for API contracts and internal payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from shared.enums import (
    ContentType,
    ExportFormat,
    ItemType,
    JobStatus,
    JobType,
    ProjectState,
    SourceType,
)


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    state: ProjectState
    created_at: datetime
    updated_at: datetime


class SourceInitRequest(BaseModel):
    source_type: SourceType
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    raw_text: str | None = None
    link_url: str | None = None
    topic: str | None = None
    subject: str | None = None
    class_level: str | None = None
    difficulty_target: str | None = None
    learning_goal: str | None = None
    enable_ocr: bool | None = None
    enable_table_extraction: bool | None = None
    smart_cleaning: bool | None = None


class SourceInitResponse(BaseModel):
    asset_id: str
    upload_url: str | None = None
    object_key: str | None = None


class IngestRequest(BaseModel):
    source_asset_id: str | None = None


class GenerateRequest(BaseModel):
    content_types: list[ContentType]
    instructions: str | None = None
    max_items: int = Field(default=12, ge=1, le=100)
    language: str = "fr"
    level: str = "intermediate"
    subject: str | None = None
    class_level: str | None = None
    difficulty_target: str | None = None


class ExportRequest(BaseModel):
    format: ExportFormat
    options: dict[str, Any] = Field(default_factory=dict)


class QualityIssue(BaseModel):
    code: str
    severity: str
    message: str
    item_id: str | None = None
    item_index: int | None = None


class QualityPreviewResponse(BaseModel):
    project_id: str
    content_set_id: str | None = None
    overall_score: int
    readiness: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    issues: list[QualityIssue] = Field(default_factory=list)


class QuestionBankVersionCreateRequest(BaseModel):
    content_set_id: str | None = None
    label: str | None = None


class QuestionBankVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    content_set_id: str | None = None
    version_number: int
    label: str
    source: str
    created_at: datetime


class PronoteImportRequest(BaseModel):
    xml_content: str = Field(min_length=1)
    source_filename: str | None = None
    replace_current_content: bool = True


class PronoteImportResponse(BaseModel):
    project_id: str
    imported_items_count: int
    content_set_id: str | None = None
    type_breakdown: dict[str, int] = Field(default_factory=dict)
    import_run_id: str


class AnalyticsResponse(BaseModel):
    project_id: str
    total_items: int
    latest_content_set_id: str | None = None
    by_item_type: dict[str, int] = Field(default_factory=dict)
    by_difficulty: dict[str, int] = Field(default_factory=dict)
    jobs_by_status: dict[str, int] = Field(default_factory=dict)
    export_by_format: dict[str, int] = Field(default_factory=dict)
    question_bank_versions: int = 0
    pronote_import_runs: int = 0


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    job_type: JobType
    status: JobStatus
    progress: int
    logs_json: list[dict[str, Any]]
    result_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ContentItemIn(BaseModel):
    id: str | None = None
    item_type: ItemType
    prompt: str
    correct_answer: str | None = None
    distractors: list[str] = Field(default_factory=list)
    answer_options: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    difficulty: str = "medium"
    feedback: str | None = None
    source_reference: str | None = None
    position: int = 0


class ContentItemOut(ContentItemIn):
    id: str


class ContentSetResponse(BaseModel):
    content_set_id: str
    project_id: str
    status: str
    language: str
    level: str
    items: list[ContentItemOut]


class ContentSetUpdateRequest(BaseModel):
    content_set_id: str | None = None
    items: list[ContentItemIn]


class DownloadResponse(BaseModel):
    export_id: str
    url: str


class InternalIngestRequest(BaseModel):
    project_id: str
    source_asset_id: str | None = None


class InternalGenerateRequest(BaseModel):
    project_id: str
    content_types: list[ContentType]
    instructions: str | None = None
    max_items: int = 12
    language: str = "fr"
    level: str = "intermediate"
    subject: str | None = None
    class_level: str | None = None
    difficulty_target: str | None = None


class SourceDocumentResponse(BaseModel):
    document_id: str
    project_id: str
    plain_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime


class SourceDocumentUpdateRequest(BaseModel):
    plain_text: str = Field(min_length=1)


class InternalExportRequest(BaseModel):
    project_id: str
    format: ExportFormat
    options: dict[str, Any] = Field(default_factory=dict)


class GeneratedItem(BaseModel):
    item_type: ItemType
    prompt: str
    correct_answer: str | None = None
    distractors: list[str] = Field(default_factory=list)
    answer_options: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    difficulty: str = "medium"
    feedback: str | None = None
    source_reference: str | None = None


class ExportArtifact(BaseModel):
    artifact_path: str
    mime: str
    filename: str
