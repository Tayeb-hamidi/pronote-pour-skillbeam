"""Base exporter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from shared.schemas import ContentSetResponse, ExportArtifact


class BaseExporter(ABC):
    """Exporter contract."""

    format_name: str

    @abstractmethod
    def export(
        self, content_set: ContentSetResponse, options: dict, output_dir: Path
    ) -> ExportArtifact:
        """Generate an artifact from content set."""
