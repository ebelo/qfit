from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AtlasExportRuntime(Protocol):
    """Application-facing runtime adapter for atlas export task details.

    Keeps QGIS-heavy task construction and dependency probing behind a small
    seam so atlas export orchestration can describe intent without directly
    owning lazy imports into ``export_task``.
    """

    def check_pdf_export_prerequisites(self) -> str | None:
        """Return a user-facing error when atlas PDF export cannot run."""

    def build_task(self, request, *, layer_gateway):
        """Build the runtime task object for a prepared atlas export request."""
