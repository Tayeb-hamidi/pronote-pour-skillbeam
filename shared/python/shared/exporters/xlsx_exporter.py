"""XLSX exporter plugin."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from shared.exporters.base import BaseExporter
from shared.schemas import ContentSetResponse, ExportArtifact


class XlsxExporter(BaseExporter):
    format_name = "xlsx"

    def export(
        self, content_set: ContentSetResponse, options: dict, output_dir: Path
    ) -> ExportArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = options.get("filename", f"content_{content_set.project_id}.xlsx")
        file_path = output_dir / filename

        wb = Workbook()
        ws = wb.active
        ws.title = "Items"
        ws.append(
            ["Type", "Prompt", "Correct Answer", "Distractors", "Tags", "Difficulty", "Feedback"]
        )

        for item in content_set.items:
            ws.append(
                [
                    item.item_type.value,
                    item.prompt,
                    item.correct_answer or "",
                    " | ".join(item.distractors),
                    " | ".join(item.tags),
                    item.difficulty,
                    item.feedback or "",
                ]
            )

        wb.save(file_path)
        return ExportArtifact(
            artifact_path=str(file_path),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
        )
