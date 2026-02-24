"""Service-level registry wrapper for exporters."""

from shared.exporters.base import BaseExporter
from shared.exporters.registry import get_exporters as get_shared_exporters


def get_exporters() -> dict[str, BaseExporter]:
    """Return available exporters for the export service."""

    return get_shared_exporters()
