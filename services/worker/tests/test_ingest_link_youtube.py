"""Tests for link/youtube source parsing."""

from __future__ import annotations

import httpx
from shared.enums import SourceType
import shared.ingest.parsers as parsers
from shared.ingest.parsers import RemotePayload, parse_source


def test_parse_link_extracts_html(monkeypatch) -> None:
    html_payload = (
        b"<html><head><title>Cours Physique</title>"
        b'<meta name="description" content="Resume officiel du chapitre."></head>'
        b"<body><h1>Mecanique</h1><p>Forces et mouvement.</p></body></html>"
    )

    def fake_fetch(_: str) -> RemotePayload:
        return RemotePayload(
            final_url="https://example.org/cours",
            content_type="text/html; charset=utf-8",
            body=html_payload,
            truncated=False,
        )

    monkeypatch.setattr(parsers, "_fetch_remote_payload", fake_fetch)

    parsed = parse_source(
        source_type=SourceType.LINK,
        filename=None,
        mime_type=None,
        payload_bytes=None,
        raw_text=None,
        link_url="https://example.org/cours",
        topic=None,
    )

    assert "Source web: https://example.org/cours" in parsed.text
    assert "Titre: Cours Physique" in parsed.text
    assert "Resume officiel du chapitre." in parsed.text
    assert parsed.metadata["kind"] == "link"
    assert parsed.metadata["parser"] == "html"
    assert parsed.metadata["fetched"] is True


def test_parse_youtube_uses_oembed(monkeypatch) -> None:
    def fake_transcript(_: str | None) -> tuple[str | None, dict[str, str | bool]]:
        return "Cette video explique le calcul des fractions et leurs regles.", {
            "transcript_available": True
        }

    def fake_oembed(_: str) -> dict:
        return {
            "title": "Les fractions en 10 minutes",
            "author_name": "Math Facile",
            "thumbnail_url": "https://img.youtube.com/vi/abc123/hqdefault.jpg",
        }

    monkeypatch.setattr(parsers, "_fetch_youtube_transcript", fake_transcript)
    monkeypatch.setattr(parsers, "_fetch_youtube_oembed", fake_oembed)

    parsed = parse_source(
        source_type=SourceType.YOUTUBE,
        filename=None,
        mime_type=None,
        payload_bytes=None,
        raw_text=None,
        link_url="https://youtu.be/abc123",
        topic=None,
    )

    assert "Titre: Les fractions en 10 minutes" in parsed.text
    assert "Chaine: Math Facile" in parsed.text
    assert "Identifiant video: abc123" in parsed.text
    assert "calcul des fractions" in parsed.text
    assert parsed.metadata["kind"] == "youtube"
    assert parsed.metadata["fetched"] is True
    assert parsed.metadata["transcript_available"] is True
    assert parsed.metadata["video_id"] == "abc123"


def test_parse_link_detects_youtube_url(monkeypatch) -> None:
    def fake_transcript(_: str | None) -> tuple[str | None, dict[str, str | bool]]:
        return "Cette video presente la loi d'Ohm avec des exemples concrets.", {
            "transcript_available": True
        }

    def fake_oembed(_: str) -> dict:
        return {"title": "Loi d'Ohm", "author_name": "Prof Sciences"}

    monkeypatch.setattr(parsers, "_fetch_youtube_transcript", fake_transcript)
    monkeypatch.setattr(parsers, "_fetch_youtube_oembed", fake_oembed)

    parsed = parse_source(
        source_type=SourceType.LINK,
        filename=None,
        mime_type=None,
        payload_bytes=None,
        raw_text=None,
        link_url="https://www.youtube.com/watch?v=xyz987",
        topic=None,
    )

    assert "Titre: Loi d'Ohm" in parsed.text
    assert "Identifiant video: xyz987" in parsed.text
    assert "loi d'Ohm" in parsed.text
    assert parsed.metadata["kind"] == "link_youtube"
    assert parsed.metadata["fetched"] is True


def test_parse_link_uses_reader_fallback_on_blocked_fetch(monkeypatch) -> None:
    def fake_fetch(url: str) -> RemotePayload:
        request = httpx.Request("GET", url)
        response = httpx.Response(403, request=request, text="Forbidden")
        raise httpx.HTTPStatusError("403 Forbidden", request=request, response=response)

    called: list[str] = []

    def fake_reader(url: str, *, cause: Exception) -> RemotePayload | None:
        called.append(url)
        assert isinstance(cause, httpx.HTTPStatusError)
        return RemotePayload(
            final_url=url,
            content_type="text/plain; charset=utf-8",
            body=b"Contenu extrait via reader fallback.",
            truncated=False,
        )

    monkeypatch.setattr(parsers, "_fetch_remote_payload", fake_fetch)
    monkeypatch.setattr(parsers, "_fetch_reader_fallback_payload", fake_reader)

    parsed = parse_source(
        source_type=SourceType.LINK,
        filename=None,
        mime_type=None,
        payload_bytes=None,
        raw_text=None,
        link_url="https://example.org/blocked",
        topic=None,
    )

    assert "Contenu extrait via reader fallback" in parsed.text
    assert parsed.metadata["fetched"] is True
    assert parsed.metadata["parser"] == "reader"
    assert parsed.metadata["reader_fallback"] is True
    assert called == ["https://example.org/blocked"]


def test_parse_link_compacts_http_error_when_fallback_fails(monkeypatch) -> None:
    def fake_fetch(url: str) -> RemotePayload:
        request = httpx.Request("GET", url)
        response = httpx.Response(403, request=request, text="Forbidden")
        raise httpx.HTTPStatusError("403 Forbidden", request=request, response=response)

    monkeypatch.setattr(parsers, "_fetch_remote_payload", fake_fetch)
    monkeypatch.setattr(parsers, "_fetch_reader_fallback_payload", lambda *_args, **_kwargs: None)

    parsed = parse_source(
        source_type=SourceType.LINK,
        filename=None,
        mime_type=None,
        payload_bytes=None,
        raw_text=None,
        link_url="https://example.org/blocked",
        topic=None,
    )

    assert parsed.metadata["fetched"] is False
    assert parsed.metadata["error"] == "HTTP 403 (example.org)"
    assert "Generation impossible en mode fiable" in parsed.text


def test_parse_link_rejects_bot_challenge_payload(monkeypatch) -> None:
    def fake_fetch(_url: str) -> RemotePayload:
        return RemotePayload(
            final_url="https://example.org/protected",
            content_type="text/plain; charset=utf-8",
            body=b"Title: Just a moment... Checking your browser before accessing the site.",
            truncated=False,
        )

    monkeypatch.setattr(parsers, "_fetch_remote_payload", fake_fetch)

    parsed = parse_source(
        source_type=SourceType.LINK,
        filename=None,
        mime_type=None,
        payload_bytes=None,
        raw_text=None,
        link_url="https://example.org/protected",
        topic=None,
    )

    assert parsed.metadata["fetched"] is False
    assert "challenge anti-bot" in str(parsed.metadata["error"])
    assert "Generation impossible en mode fiable" in parsed.text
