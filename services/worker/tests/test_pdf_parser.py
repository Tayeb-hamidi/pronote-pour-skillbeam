"""Tests for PDF extraction behavior."""

from __future__ import annotations

import shared.ingest.parsers as parsers


class _EmptyPage:
    def extract_text(self) -> str:
        return ""


class _EmptyPdfReader:
    def __init__(self, *_args, **_kwargs) -> None:
        self.pages = [_EmptyPage()]


def test_parse_pdf_uses_pdfminer_fallback_when_pypdf_is_sparse(monkeypatch) -> None:
    monkeypatch.setattr(parsers, "PdfReader", _EmptyPdfReader)
    monkeypatch.setattr(
        parsers, "pdfminer_extract_text", lambda _stream: "Contenu extrait via pdfminer fallback."
    )

    extracted = parsers._parse_pdf(b"%PDF-1.4 fake payload")

    assert "pdfminer fallback" in extracted
