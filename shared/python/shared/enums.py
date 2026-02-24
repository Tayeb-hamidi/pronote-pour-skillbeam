"""Domain enumerations."""

from enum import StrEnum


class ProjectState(StrEnum):
    DRAFT = "DRAFT"
    INGESTED = "INGESTED"
    GENERATED = "GENERATED"
    REVIEWED = "REVIEWED"
    EXPORTED = "EXPORTED"


class SourceType(StrEnum):
    DOCUMENT = "document"
    TEXT = "text"
    THEME = "theme"
    YOUTUBE = "youtube"
    LINK = "link"
    AUDIO_VIDEO = "audio_video"


class ContentType(StrEnum):
    COURSE_STRUCTURE = "course_structure"
    MCQ = "mcq"
    POLL = "poll"
    OPEN_QUESTION = "open_question"
    CLOZE = "cloze"
    MATCHING = "matching"
    BRAINSTORMING = "brainstorming"
    FLASHCARDS = "flashcards"


class ItemType(StrEnum):
    MCQ = "mcq"
    POLL = "poll"
    OPEN_QUESTION = "open_question"
    CLOZE = "cloze"
    MATCHING = "matching"
    BRAINSTORMING = "brainstorming"
    FLASHCARD = "flashcard"
    COURSE_STRUCTURE = "course_structure"


class JobType(StrEnum):
    INGEST = "ingest"
    GENERATE = "generate"
    EXPORT = "export"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExportFormat(StrEnum):
    DOCX = "docx"
    PDF = "pdf"
    XLSX = "xlsx"
    MOODLE_XML = "moodle_xml"
    PRONOTE_XML = "pronote_xml"
    QTI = "qti"
    H5P = "h5p"
    ANKI = "anki"
