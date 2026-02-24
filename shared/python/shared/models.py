"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base
from shared.enums import JobStatus, JobType, ProjectState


class TimestampMixin:
    """Reusable timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    """User account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    projects: Mapped[list[Project]] = relationship(back_populates="user")


class Project(Base, TimestampMixin):
    """Top-level wizard project."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(20), default=ProjectState.DRAFT.value, index=True)

    user: Mapped[User] = relationship(back_populates="projects")
    source_assets: Mapped[list[SourceAsset]] = relationship(back_populates="project")
    normalized_documents: Mapped[list[NormalizedDocument]] = relationship(back_populates="project")
    content_sets: Mapped[list[ContentSet]] = relationship(back_populates="project")
    jobs: Mapped[list[Job]] = relationship(back_populates="project")
    export_jobs: Mapped[list[ExportJob]] = relationship(back_populates="project")
    question_bank_versions: Mapped[list[QuestionBankVersion]] = relationship(
        back_populates="project", cascade="all,delete-orphan"
    )
    pronote_import_runs: Mapped[list[PronoteImportRun]] = relationship(
        back_populates="project", cascade="all,delete-orphan"
    )


class SourceAsset(Base, TimestampMixin):
    """Source payload from one ingestion origin."""

    __tablename__ = "source_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    project: Mapped[Project] = relationship(back_populates="source_assets")


class NormalizedDocument(Base, TimestampMixin):
    """Normalized textual representation of sources."""

    __tablename__ = "normalized_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    plain_text: Mapped[str] = mapped_column(Text)
    sections_json: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    references_json: Mapped[list[dict]] = mapped_column(JSONB, default=list)

    project: Mapped[Project] = relationship(back_populates="normalized_documents")


class ContentSet(Base, TimestampMixin):
    """Generated pedagogical content grouped by run."""

    __tablename__ = "content_sets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    source_document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("normalized_documents.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="generated")
    language: Mapped[str] = mapped_column(String(16), default="fr")
    level: Mapped[str] = mapped_column(String(32), default="intermediate")

    project: Mapped[Project] = relationship(back_populates="content_sets")
    items: Mapped[list[Item]] = relationship(
        back_populates="content_set", cascade="all,delete-orphan"
    )


class Item(Base, TimestampMixin):
    """A single pedagogical item."""

    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    content_set_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("content_sets.id"), index=True
    )
    item_type: Mapped[str] = mapped_column(String(32), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    distractors_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    answer_options_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    tags_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium")
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    content_set: Mapped[ContentSet] = relationship(back_populates="items")


class Job(Base, TimestampMixin):
    """Asynchronous job status entity."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(20), default=JobType.INGEST.value)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.QUEUED.value)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    logs_json: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    result_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="jobs")


class ExportJob(Base, TimestampMixin):
    """Artifact generated by export pipeline."""

    __tablename__ = "export_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    content_set_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("content_sets.id"), nullable=True
    )
    format: Mapped[str] = mapped_column(String(32), index=True)
    options_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.QUEUED.value)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="export_jobs")


class QuestionBankVersion(Base, TimestampMixin):
    """Version snapshot of a generated/edited question set."""

    __tablename__ = "question_bank_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    content_set_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("content_sets.id"), nullable=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    label: Mapped[str] = mapped_column(String(255), default="Version")
    source: Mapped[str] = mapped_column(String(32), default="manual")
    snapshot_json: Mapped[list[dict]] = mapped_column(JSONB, default=list)

    project: Mapped[Project] = relationship(back_populates="question_bank_versions")


class PronoteImportRun(Base, TimestampMixin):
    """Track Pronote XML import runs and aggregated analytics."""

    __tablename__ = "pronote_import_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imported_items_count: Mapped[int] = mapped_column(Integer, default=0)
    stats_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    project: Mapped[Project] = relationship(back_populates="pronote_import_runs")
