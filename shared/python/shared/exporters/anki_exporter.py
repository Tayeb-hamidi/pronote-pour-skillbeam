"""Anki exporter plugin (CSV format)."""

from __future__ import annotations

import csv
from pathlib import Path

from shared.exporters.base import BaseExporter
from shared.schemas import ContentSetResponse, ExportArtifact


class AnkiExporter(BaseExporter):
    """Export as Anki-compatible CSV.

    TODO: add .apkg generation using genanki for richer deck metadata.
    """

    format_name = "anki"

    def export(
        self, content_set: ContentSetResponse, options: dict, output_dir: Path
    ) -> ExportArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = options.get("filename", f"content_{content_set.project_id}_anki.csv")
        file_path = output_dir / filename

        with file_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["Front", "Back", "Tags"])
            for item in content_set.items:
                back = item.correct_answer or ""
                if item.distractors:
                    back = back + "\nDistracteurs: " + " | ".join(item.distractors)
                writer.writerow([item.prompt, back, " ".join(item.tags)])

        return ExportArtifact(artifact_path=str(file_path), mime="text/csv", filename=filename)
