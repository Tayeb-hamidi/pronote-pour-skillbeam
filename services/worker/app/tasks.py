"""Background tasks for ingest, generation and export pipelines."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import time

from shared.db import SessionLocal
from shared.enums import ContentType, JobStatus, ProjectState, SourceType
from shared.exporters.registry import get_exporters
from shared.generation.templates import generate_items
from shared.ingest.parsers import parse_source
from shared.jobs import update_job
from shared.llm.providers import get_provider
from shared.logging import configure_logging
from shared.models import ContentSet, ExportJob, Item, NormalizedDocument, Project, SourceAsset
from shared.schemas import ContentItemOut, ContentSetResponse
from shared.storage import ObjectStorage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.worker import celery_app

configure_logging()
logger = logging.getLogger(__name__)
storage = ObjectStorage()
DEFAULT_PRONOTE_CATEGORY_NAME = "SkillBeam"
PRONOTE_PLACEHOLDER_NAMES = {"skillbeam", "skillbeam wizard"}
GENERIC_PROJECT_TITLES = {"projet wizard", "wizard project", "project wizard"}


@celery_app.task(name="worker.tasks.parse_source")
def parse_source_task(job_id: str, project_id: str, source_asset_id: str | None = None) -> None:
    """Parse source and save normalized document."""

    try:
        _ensure_storage_ready()
        with SessionLocal() as db:
            update_job(
                db, job_id, status=JobStatus.RUNNING, progress=5, message="Ingestion started"
            )

            source = _select_source_asset(
                db=db, project_id=project_id, source_asset_id=source_asset_id
            )
            if source is None:
                raise ValueError("No source asset available for ingestion")

            payload_bytes = storage.get_bytes(source.object_key) if source.object_key else None
            # TODO(security): run ClamAV scan on payload_bytes before parsing document sources.
            parsed = parse_source(
                source_type=SourceType(source.source_type),
                filename=source.filename,
                mime_type=source.mime_type,
                payload_bytes=payload_bytes,
                raw_text=source.raw_text,
                link_url=(source.metadata_json or {}).get("link_url"),
                topic=(source.metadata_json or {}).get("topic"),
                source_metadata=source.metadata_json or {},
            )
            _ensure_youtube_transcript_available(
                source_type=SourceType(source.source_type),
                metadata=parsed.metadata,
            )
            _ensure_link_source_available(
                source_type=SourceType(source.source_type),
                metadata=parsed.metadata,
            )

            source.status = "ingested"
            source.source_hash = parsed.source_hash
            db.add(source)

            normalized_doc = NormalizedDocument(
                project_id=project_id,
                plain_text=parsed.text,
                sections_json=parsed.sections,
                metadata_json=parsed.metadata,
                references_json=parsed.references,
            )
            db.add(normalized_doc)

            project = db.get(Project, project_id)
            if project:
                project.state = ProjectState.INGESTED.value
                db.add(project)

            db.commit()
            db.refresh(normalized_doc)
            update_job(
                db,
                job_id,
                status=JobStatus.SUCCEEDED,
                progress=100,
                message="Ingestion completed",
                result_id=normalized_doc.id,
            )
    except Exception as exc:
        logger.exception("ingestion task failed")
        _mark_job_failed(job_id=job_id, error_message=str(exc))


@celery_app.task(name="worker.tasks.generate_content")
def generate_content_task(
    job_id: str,
    project_id: str,
    content_types: list[str],
    instructions: str | None,
    max_items: int,
    language: str,
    level: str,
    subject: str | None = None,
    class_level: str | None = None,
    difficulty_target: str | None = None,
) -> None:
    """Generate pedagogical content from latest normalized document."""

    try:
        _update_job_running(job_id, progress=10, message="Generation started")
        with SessionLocal() as db:
            normalized_doc = db.scalar(
                select(NormalizedDocument)
                .where(NormalizedDocument.project_id == project_id)
                .order_by(NormalizedDocument.created_at.desc())
            )
            if normalized_doc is None:
                raise ValueError("No normalized document found. Run ingest first.")

            _update_job_running(job_id, progress=20, message="Source loaded")
            parsed_types = [ContentType(ct) for ct in content_types]
            _update_job_running(job_id, progress=35, message="Model initialization")
            provider = get_provider()
            _update_job_running(job_id, progress=45, message="Generation LLM en cours")
            items = generate_items(
                provider=provider,
                source_text=normalized_doc.plain_text,
                content_types=parsed_types,
                instructions=instructions,
                max_items=max_items,
                language=language,
                level=level,
                subject=subject,
                class_level=class_level,
                difficulty_target=difficulty_target,
            )
            _update_job_running(job_id, progress=68, message=f"{len(items)} items generated")

            content_set = ContentSet(
                project_id=project_id,
                source_document_id=normalized_doc.id,
                status="generated",
                language=language,
                level=level,
            )
            db.add(content_set)
            db.flush()

            checkpoint = max(1, len(items) // 6) if items else 1
            for index, generated_item in enumerate(items):
                db.add(
                    Item(
                        content_set_id=content_set.id,
                        item_type=generated_item.item_type.value,
                        prompt=generated_item.prompt,
                        correct_answer=generated_item.correct_answer,
                        distractors_json=generated_item.distractors,
                        answer_options_json=generated_item.answer_options,
                        tags_json=generated_item.tags,
                        difficulty=generated_item.difficulty,
                        feedback=generated_item.feedback,
                        source_reference=generated_item.source_reference,
                        position=index,
                    )
                )
                persisted = index + 1
                if persisted % checkpoint == 0 or persisted == len(items):
                    progress = 70 + int((persisted / max(1, len(items))) * 25)
                    _update_job_running(
                        job_id,
                        progress=progress,
                        message=f"Sauvegarde des items {persisted}/{len(items)}",
                    )

            project = db.get(Project, project_id)
            if project:
                project.state = ProjectState.GENERATED.value
                db.add(project)

            db.commit()
            db.refresh(content_set)
            update_job(
                db,
                job_id,
                status=JobStatus.SUCCEEDED,
                progress=100,
                message="Generation completed",
                result_id=content_set.id,
            )
    except Exception as exc:
        logger.exception("generation task failed")
        _mark_job_failed(job_id=job_id, error_message=str(exc))


@celery_app.task(name="worker.tasks.export_content")
def export_content_task(job_id: str, project_id: str, format_name: str, options: dict) -> None:
    """Export latest content set through plugin registry."""

    try:
        _ensure_storage_ready()
        with SessionLocal() as db:
            update_job(db, job_id, status=JobStatus.RUNNING, progress=10, message="Export started")

            content_set = db.scalar(
                select(ContentSet)
                .where(ContentSet.project_id == project_id)
                .order_by(ContentSet.created_at.desc())
            )
            if content_set is None:
                raise ValueError("No content set found. Run generate first.")

            items = db.scalars(
                select(Item)
                .where(Item.content_set_id == content_set.id)
                .order_by(Item.position.asc())
            ).all()
            payload = ContentSetResponse(
                content_set_id=content_set.id,
                project_id=project_id,
                status=content_set.status,
                language=content_set.language,
                level=content_set.level,
                items=[
                    ContentItemOut(
                        id=item.id,
                        item_type=item.item_type,
                        prompt=item.prompt,
                        correct_answer=item.correct_answer,
                        distractors=item.distractors_json,
                        answer_options=item.answer_options_json,
                        tags=item.tags_json,
                        difficulty=item.difficulty,
                        feedback=item.feedback,
                        source_reference=item.source_reference,
                        position=item.position,
                    )
                    for item in items
                ],
            )

            exporters = get_exporters()
            exporter = exporters.get(format_name)
            if exporter is None:
                raise ValueError(f"Unsupported export format: {format_name}")

            resolved_options = _prepare_export_options(
                db=db,
                project_id=project_id,
                content_set=content_set,
                format_name=format_name,
                options=options,
            )

            with TemporaryDirectory(prefix="skillbeam_export_") as output_dir:
                artifact = exporter.export(payload, resolved_options, output_dir=Path(output_dir))
                with open(artifact.artifact_path, "rb") as artifact_file:
                    artifact_bytes = artifact_file.read()

                object_key = f"exports/{project_id}/{job_id}/{artifact.filename}"
                storage.put_bytes(
                    object_key=object_key, data=artifact_bytes, content_type=artifact.mime
                )

            export_row = ExportJob(
                project_id=project_id,
                content_set_id=content_set.id,
                format=format_name,
                options_json=resolved_options,
                object_key=object_key,
                mime_type=artifact.mime,
                filename=artifact.filename,
                status=JobStatus.SUCCEEDED.value,
                completed_at=datetime.now(timezone.utc),
            )
            db.add(export_row)

            project = db.get(Project, project_id)
            if project:
                project.state = ProjectState.EXPORTED.value
                db.add(project)

            db.commit()
            db.refresh(export_row)
            update_job(
                db,
                job_id,
                status=JobStatus.SUCCEEDED,
                progress=100,
                message="Export completed",
                result_id=export_row.id,
            )
    except Exception as exc:
        logger.exception("export task failed")
        _mark_job_failed(job_id=job_id, error_message=str(exc))


def _select_source_asset(
    db: Session, project_id: str, source_asset_id: str | None
) -> SourceAsset | None:
    if source_asset_id:
        return db.get(SourceAsset, source_asset_id)
    return db.scalar(
        select(SourceAsset)
        .where(SourceAsset.project_id == project_id)
        .order_by(SourceAsset.created_at.desc())
    )


def _prepare_export_options(
    *,
    db: Session,
    project_id: str,
    content_set: ContentSet,
    format_name: str,
    options: dict | None,
) -> dict:
    resolved = dict(options or {})
    if format_name != "pronote_xml":
        return resolved

    raw_name = str(resolved.get("name", "")).strip()
    if _is_placeholder_pronote_name(raw_name):
        resolved["name"] = _derive_pronote_category_name(
            db=db, project_id=project_id, content_set=content_set
        )
    return resolved


def _derive_pronote_category_name(*, db: Session, project_id: str, content_set: ContentSet) -> str:
    candidates: list[object] = []

    source_asset = db.scalar(
        select(SourceAsset)
        .where(SourceAsset.project_id == project_id)
        .order_by(SourceAsset.created_at.desc())
    )
    if source_asset is not None:
        source_meta = source_asset.metadata_json or {}
        candidates.extend(
            [
                source_meta.get("topic"),
                source_meta.get("title"),
                source_meta.get("learning_goal"),
                source_asset.filename,
            ]
        )

    normalized_document = None
    if content_set.source_document_id:
        normalized_document = db.get(NormalizedDocument, content_set.source_document_id)
    if normalized_document is None:
        normalized_document = db.scalar(
            select(NormalizedDocument)
            .where(NormalizedDocument.project_id == project_id)
            .order_by(NormalizedDocument.created_at.desc())
        )
    if normalized_document is not None:
        normalized_meta = normalized_document.metadata_json or {}
        candidates.extend(
            [
                normalized_meta.get("topic"),
                normalized_meta.get("title"),
                normalized_meta.get("filename"),
            ]
        )

    project = db.get(Project, project_id)
    if project is not None:
        candidates.append(project.title)

    return _select_pronote_category_name(candidates)


def _select_pronote_category_name(candidates: list[object]) -> str:
    for candidate in candidates:
        normalized = _normalize_pronote_name(candidate)
        if normalized:
            return normalized
    return DEFAULT_PRONOTE_CATEGORY_NAME


def _normalize_pronote_name(value: object) -> str | None:
    if value is None:
        return None

    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return None

    if " " not in text and "/" not in text and re.search(r"\.[A-Za-z0-9]{2,6}$", text):
        text = Path(text).stem.strip()
    if not text:
        return None

    lowered = text.lower()
    if lowered in PRONOTE_PLACEHOLDER_NAMES or lowered in GENERIC_PROJECT_TITLES:
        return None

    return text[:120].strip()


def _is_placeholder_pronote_name(value: str) -> bool:
    return not value or value.strip().lower() in PRONOTE_PLACEHOLDER_NAMES


def _mark_job_failed(job_id: str, error_message: str) -> None:
    with SessionLocal() as db:
        update_job(
            db,
            job_id,
            status=JobStatus.FAILED,
            progress=100,
            message="Job failed",
            error_message=error_message,
        )


def _update_job_running(job_id: str, *, progress: int, message: str) -> None:
    """Update running job progress in an isolated transaction."""

    with SessionLocal() as db:
        update_job(
            db,
            job_id,
            status=JobStatus.RUNNING,
            progress=progress,
            message=message,
        )


def _ensure_storage_ready(max_attempts: int = 20, delay_seconds: float = 1.0) -> None:
    """Ensure bucket exists before storage operations."""

    for _ in range(max_attempts):
        try:
            storage.ensure_bucket()
            return
        except Exception:
            time.sleep(delay_seconds)
    raise RuntimeError("Object storage is not ready")


def _ensure_youtube_transcript_available(*, source_type: SourceType, metadata: dict) -> None:
    """Fail ingestion early for YouTube sources without transcript to avoid irrelevant generation."""

    if source_type not in {SourceType.YOUTUBE, SourceType.LINK}:
        return

    kind = str(metadata.get("kind", ""))
    if kind not in {"youtube", "link_youtube"}:
        return
    if bool(metadata.get("transcript_available")):
        return

    detail = str(metadata.get("transcript_error", "transcription unavailable"))
    raise ValueError(
        "Transcription YouTube indisponible pour cette video. "
        "Activez des sous-titres/captions ou utilisez une autre source. "
        f"Detail: {detail}"
    )


def _ensure_link_source_available(*, source_type: SourceType, metadata: dict) -> None:
    """Fail ingestion when a generic web link cannot be fetched."""

    if source_type != SourceType.LINK:
        return

    kind = str(metadata.get("kind", ""))
    if kind != "link":
        return
    if bool(metadata.get("fetched")):
        return

    detail = str(metadata.get("error", "source inaccessible"))
    raise ValueError(
        "URL inaccessible ou protegee (ex: 403/Cloudflare). "
        "Essayez une autre URL, collez le texte en mode 'Texte' ou uploadez un document. "
        f"Detail: {detail}"
    )
