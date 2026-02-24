"""PDF exporter plugin (ReportLab)."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from shared.exporters.base import BaseExporter
from shared.exporters.branding import (
    DEFAULT_EXPORT_TITLE,
    bool_option,
    collect_choice_rows,
    label_item_type,
    resolve_skillbeam_logo,
    split_expected_answers,
)
from shared.schemas import ContentSetResponse, ExportArtifact


class PdfExporter(BaseExporter):
    format_name = "pdf"

    def export(
        self, content_set: ContentSetResponse, options: dict, output_dir: Path
    ) -> ExportArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = options.get("filename", f"content_{content_set.project_id}.pdf")
        file_path = output_dir / filename

        c = canvas.Canvas(str(file_path), pagesize=A4)
        c.setPageCompression(0)
        width, height = A4
        margin_x = 42
        margin_top = 40
        margin_bottom = 40
        content_width = width - (margin_x * 2)
        y = height - margin_top

        title = str(options.get("title", DEFAULT_EXPORT_TITLE))
        show_correct_answers = bool_option(options.get("show_correct_answers"), default=False)
        logo_path = resolve_skillbeam_logo(options)

        def draw_header() -> None:
            nonlocal y
            y = height - margin_top
            logo_drawn = False
            if logo_path is not None:
                logo_width = 150
                logo_height = 48
                top = y + 8
                c.drawImage(
                    str(logo_path),
                    margin_x,
                    top - logo_height,
                    width=logo_width,
                    height=logo_height,
                    mask="auto",
                    preserveAspectRatio=True,
                    anchor="sw",
                )
                logo_drawn = True

            header_x = margin_x + 165 if logo_drawn else margin_x
            c.setFillColor(colors.HexColor("#124a52"))
            c.setFont("Helvetica-Bold", 17)
            c.drawString(header_x, y, title)
            y -= 17
            c.setFont("Helvetica", 10)
            c.setFillColor(colors.HexColor("#334155"))
            c.drawString(
                header_x,
                y,
                "Questionnaire QCM - cochez la/les cases correspondantes.",
            )
            y -= 14
            c.setStrokeColor(colors.HexColor("#a8c4e5"))
            c.setLineWidth(1)
            c.line(margin_x, y, width - margin_x, y)
            y -= 15

        def ensure_space(min_height: float) -> None:
            nonlocal y
            if y - min_height < margin_bottom:
                c.showPage()
                draw_header()

        def draw_wrapped(
            text: str,
            *,
            font_name: str = "Helvetica",
            font_size: int = 11,
            leading: int = 15,
            indent: float = 0,
            color: colors.Color = colors.black,
        ) -> None:
            nonlocal y
            value = (text or "").strip()
            if not value:
                return
            lines = simpleSplit(value, font_name, font_size, content_width - indent)
            if not lines:
                return
            ensure_space((len(lines) + 1) * leading)
            c.setFont(font_name, font_size)
            c.setFillColor(color)
            for line in lines:
                c.drawString(margin_x + indent, y, line)
                y -= leading

        draw_header()

        for index, item in enumerate(content_set.items, start=1):
            ensure_space(74)
            item_label = label_item_type(item.item_type.value)
            draw_wrapped(
                f"Question {index} - {item_label}",
                font_name="Helvetica-Bold",
                font_size=12,
                leading=16,
                color=colors.HexColor("#0f2742"),
            )
            draw_wrapped(item.prompt, font_name="Helvetica", font_size=11, leading=15, indent=8)

            if item.item_type.value in {"mcq", "poll"}:
                helper_line = (
                    "Cochez la bonne reponse."
                    if item.item_type.value == "mcq"
                    else "Cochez les bonnes reponses."
                )
                draw_wrapped(
                    helper_line,
                    font_name="Helvetica-Oblique",
                    font_size=10,
                    leading=14,
                    indent=8,
                    color=colors.HexColor("#475569"),
                )

                rows = collect_choice_rows(
                    correct_answer=item.correct_answer,
                    distractors=item.distractors,
                    answer_options=item.answer_options,
                )
                for text, is_correct in rows:
                    checkbox = "[x]" if show_correct_answers and is_correct else "[ ]"
                    draw_wrapped(
                        f"{checkbox} {text}",
                        font_name="Helvetica",
                        font_size=11,
                        leading=15,
                        indent=16,
                        color=colors.HexColor("#1f2937"),
                    )

                if show_correct_answers:
                    answers = split_expected_answers(item.correct_answer)
                    if answers:
                        draw_wrapped(
                            f"Corrige: {' | '.join(answers)}",
                            font_name="Helvetica-Bold",
                            font_size=10,
                            leading=14,
                            indent=16,
                            color=colors.HexColor("#0f6b43"),
                        )
            else:
                if show_correct_answers and item.correct_answer:
                    draw_wrapped(
                        f"Reponse attendue: {item.correct_answer}",
                        font_name="Helvetica-Bold",
                        font_size=10,
                        leading=14,
                        indent=12,
                        color=colors.HexColor("#0f6b43"),
                    )
                else:
                    draw_wrapped(
                        "Reponse: _________________________________",
                        font_name="Helvetica",
                        font_size=11,
                        leading=15,
                        indent=12,
                        color=colors.HexColor("#334155"),
                    )

            y -= 10

        c.save()
        return ExportArtifact(
            artifact_path=str(file_path), mime="application/pdf", filename=filename
        )
