"""Export plugin registry."""

from __future__ import annotations

from shared.exporters.anki_exporter import AnkiExporter
from shared.exporters.base import BaseExporter
from shared.exporters.docx_exporter import DocxExporter
from shared.exporters.h5p_exporter import H5pExporter
from shared.exporters.moodle_xml_exporter import MoodleXmlExporter
from shared.exporters.pdf_exporter import PdfExporter
from shared.exporters.pronote_xml_exporter import PronoteXmlExporter
from shared.exporters.qti_exporter import QtiExporter
from shared.exporters.xlsx_exporter import XlsxExporter


def get_exporters() -> dict[str, BaseExporter]:
    """Return exporter map by format."""

    exporters = [
        DocxExporter(),
        PdfExporter(),
        XlsxExporter(),
        MoodleXmlExporter(),
        PronoteXmlExporter(),
        QtiExporter(),
        H5pExporter(),
        AnkiExporter(),
    ]
    return {exp.format_name: exp for exp in exporters}
