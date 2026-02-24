from __future__ import annotations

from shared.ingest.parsers import _select_subtitle_url, _subtitle_payload_to_text


def test_select_subtitle_url_prefers_preferred_language_and_vtt() -> None:
    tracks = {
        "es": [{"ext": "vtt", "url": "https://example.com/es.vtt"}],
        "fr": [
            {"ext": "ttml", "url": "https://example.com/fr.ttml"},
            {"ext": "vtt", "url": "https://example.com/fr.vtt"},
        ],
    }

    assert _select_subtitle_url(tracks) == "https://example.com/fr.vtt"


def test_subtitle_payload_to_text_parses_vtt() -> None:
    payload = """WEBVTT

00:00:00.000 --> 00:00:01.000
Bonjour a tous

00:00:01.000 --> 00:00:02.000
<c>Bienvenue dans ce cours</c>
"""

    text = _subtitle_payload_to_text(payload)
    assert "Bonjour a tous" in text
    assert "Bienvenue dans ce cours" in text
    assert "WEBVTT" not in text
    assert "-->" not in text


def test_subtitle_payload_to_text_parses_json3() -> None:
    payload = (
        '{"events":[{"segs":[{"utf8":"Premiere phrase "},{"utf8":"utile."}]},'
        '{"segs":[{"utf8":"Deuxieme phrase."}]}]}'
    )

    text = _subtitle_payload_to_text(payload)
    assert "Premiere phrase utile." in text
    assert "Deuxieme phrase." in text
