"""QTI exporter placeholder plugin."""

from __future__ import annotations

from pathlib import Path

from shared.exporters.base import BaseExporter
from shared.schemas import ContentSetResponse, ExportArtifact


class QtiExporter(BaseExporter):
    """Minimal valid QTI-like XML placeholder.

    TODO: support full IMS QTI packaging and item-level metadata.
    """

    format_name = "qti"

    def export(
        self, content_set: ContentSetResponse, options: dict, output_dir: Path
    ) -> ExportArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = options.get("filename", f"content_{content_set.project_id}_qti.xml")
        file_path = output_dir / filename

        xml = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<assessmentTest xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0" identifier="skillbeam-test" title="SkillBeam QTI">',
            '  <testPart identifier="P1" navigationMode="linear" submissionMode="individual">',
            '    <assessmentSection identifier="S1" title="Generated" visible="true">',
            "      <!-- TODO: add complete QTI item definitions -->",
            "    </assessmentSection>",
            "  </testPart>",
            "</assessmentTest>",
        ]
        file_path.write_text("\n".join(xml), encoding="utf-8")
        return ExportArtifact(
            artifact_path=str(file_path), mime="application/xml", filename=filename
        )
