"""Tests for advanced source quality metadata."""

from __future__ import annotations

from shared.enums import SourceType
from shared.ingest.parsers import parse_source


def test_parse_text_builds_quality_report_with_tables_and_cleaning() -> None:
    raw_text = """
Header Cours
Header Cours
Header Cours
Header Cours

Chapitre 1 | Definition | Exemple
Memoire de travail | Stockage court terme | Rappel oral
Attention selective | Filtrer les stimuli | Activite en classe
"""

    parsed = parse_source(
        source_type=SourceType.TEXT,
        filename=None,
        mime_type=None,
        payload_bytes=None,
        raw_text=raw_text,
        link_url=None,
        topic=None,
        source_metadata={"smart_cleaning": True, "enable_table_extraction": True},
    )

    quality = parsed.metadata.get("source_quality") or {}
    assert isinstance(quality, dict)
    assert quality.get("table_candidates", 0) >= 1
    cleaning = quality.get("smart_cleaning") or {}
    assert isinstance(cleaning, dict)
    assert cleaning.get("removed_repeated_headers", 0) >= 1
