from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.tasks import _ensure_link_source_available, _ensure_youtube_transcript_available
from shared.enums import SourceType


def test_guard_accepts_youtube_with_transcript() -> None:
    _ensure_youtube_transcript_available(
        source_type=SourceType.YOUTUBE,
        metadata={"kind": "youtube", "transcript_available": True},
    )


def test_guard_rejects_youtube_without_transcript() -> None:
    with pytest.raises(ValueError) as exc:
        _ensure_youtube_transcript_available(
            source_type=SourceType.YOUTUBE,
            metadata={
                "kind": "youtube",
                "transcript_available": False,
                "transcript_error": "No transcripts found for any language.",
            },
        )

    assert "Transcription YouTube indisponible" in str(exc.value)
    assert "No transcripts found for any language." in str(exc.value)


def test_guard_ignores_generic_links() -> None:
    _ensure_youtube_transcript_available(
        source_type=SourceType.LINK,
        metadata={"kind": "link", "transcript_available": False},
    )


def test_link_guard_accepts_fetched_link() -> None:
    _ensure_link_source_available(
        source_type=SourceType.LINK,
        metadata={"kind": "link", "fetched": True},
    )


def test_link_guard_rejects_blocked_link() -> None:
    with pytest.raises(ValueError) as exc:
        _ensure_link_source_available(
            source_type=SourceType.LINK,
            metadata={
                "kind": "link",
                "fetched": False,
                "error": "Client error '403 Forbidden' for url 'https://example.org'",
            },
        )

    assert "URL inaccessible ou protegee" in str(exc.value)
    assert "403 Forbidden" in str(exc.value)
