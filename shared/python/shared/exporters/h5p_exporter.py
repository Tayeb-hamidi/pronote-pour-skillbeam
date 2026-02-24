"""H5P QuestionSet best-effort exporter."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from shared.exporters.base import BaseExporter
from shared.schemas import ContentSetResponse, ExportArtifact


class H5pExporter(BaseExporter):
    """Generate lightweight H5P package.

    TODO: enrich semantics and libraries metadata for production-grade compatibility.
    """

    format_name = "h5p"

    def export(
        self, content_set: ContentSetResponse, options: dict, output_dir: Path
    ) -> ExportArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = options.get("filename", f"content_{content_set.project_id}.h5p")
        output_path = output_dir / filename

        h5p_manifest = {
            "title": options.get("title", "SkillBeam QuestionSet"),
            "language": "fr",
            "mainLibrary": "H5P.QuestionSet",
            "embedTypes": ["div"],
            "license": "U",
            "preloadedDependencies": [
                {"machineName": "H5P.QuestionSet", "majorVersion": 1, "minorVersion": 17}
            ],
        }

        questions = []
        for item in content_set.items:
            if item.item_type.value != "mcq":
                continue
            answers = [{"text": item.correct_answer or "", "correct": True}]
            answers.extend({"text": d, "correct": False} for d in item.distractors)
            questions.append({"question": item.prompt, "answers": answers})

        content_json = {
            "introPage": {"showIntroPage": False},
            "questions": questions,
        }

        with TemporaryDirectory(prefix="h5p_") as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "content").mkdir(parents=True, exist_ok=True)
            (temp_path / "h5p.json").write_text(
                json.dumps(h5p_manifest, ensure_ascii=True, indent=2), encoding="utf-8"
            )
            (temp_path / "content" / "content.json").write_text(
                json.dumps(content_json, ensure_ascii=True, indent=2), encoding="utf-8"
            )

            with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as zipf:
                zipf.write(temp_path / "h5p.json", arcname="h5p.json")
                zipf.write(temp_path / "content" / "content.json", arcname="content/content.json")

        return ExportArtifact(
            artifact_path=str(output_path), mime="application/zip", filename=filename
        )
