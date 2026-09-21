"""QGIS background tasks for Strava bulk-export preflight and import."""

from __future__ import annotations

from typing import Callable

from qgis.core import QgsTask

from .strava_bulk_import import (
    StravaBulkImportProgress,
    StravaBulkImportRequest,
    StravaBulkImportResult,
    StravaBulkImportWorkflow,
)
from ...providers.infrastructure.strava_bulk_archive import (
    StravaBulkArchiveCancelled,
)

PreflightFinished = Callable[[object | None, str | None, bool], None]
ImportFinished = Callable[[StravaBulkImportResult | None, str | None, bool], None]


class StravaBulkPreflightTask(QgsTask):
    """Validate a potentially large ZIP away from the QGIS UI thread."""

    def __init__(self, workflow, archive_path, on_finished=None):
        super().__init__("Validate Strava bulk export", QgsTask.CanCancel)
        self._workflow = workflow
        self._archive_path = archive_path
        self._on_finished = on_finished
        self._result = None
        self._error_message = None

    def run(self):
        if self.isCanceled():
            return False
        try:
            self._result = self._workflow.preflight(
                self._archive_path,
                cancelled=self.isCanceled,
            )
            return not self.isCanceled()
        except StravaBulkArchiveCancelled:
            return False
        except Exception as exc:  # pragma: no cover - surfaced by finished()
            self._error_message = _safe_task_error(exc)
            return False

    def finished(self, ok):  # pragma: no cover - Qt callback
        cancelled = self.isCanceled() and not ok and self._error_message is None
        if self._on_finished is not None:
            self._on_finished(self._result, self._error_message, cancelled)


class StravaBulkImportTask(QgsTask):
    """Run bounded archive parsing, writes, and one final layer rebuild."""

    def __init__(self, workflow, request, on_finished=None):
        super().__init__("Import Strava bulk export", QgsTask.CanCancel)
        self._workflow = workflow
        self._request = request
        self._on_finished = on_finished
        self._result = None
        self._error_message = None
        self.latest_progress = StravaBulkImportProgress(phase="queued", message="Queued")

    def run(self):
        if self.isCanceled():
            return False
        try:
            self._result = self._workflow.run(
                self._request,
                cancelled=self.isCanceled,
                progress=self._handle_progress,
            )
            return not self._result.cancelled and not self.isCanceled()
        except StravaBulkArchiveCancelled:
            return False
        except Exception as exc:  # pragma: no cover - surfaced by finished()
            self._error_message = _safe_task_error(exc)
            return False

    def _handle_progress(self, progress):
        self.latest_progress = progress
        self.setProgress(progress.percent)

    def finished(self, ok):  # pragma: no cover - Qt callback
        cancelled = bool(self._result is not None and self._result.cancelled)
        if self._result is None and self.isCanceled() and not ok and self._error_message is None:
            cancelled = True
        if self._on_finished is not None:
            self._on_finished(self._result, self._error_message, cancelled)


def build_strava_bulk_preflight_task(workflow, archive_path, on_finished=None):
    return StravaBulkPreflightTask(workflow, archive_path, on_finished=on_finished)


def build_strava_bulk_import_task(workflow, request, on_finished=None):
    return StravaBulkImportTask(workflow, request, on_finished=on_finished)


def _safe_task_error(exc):
    message = str(exc).strip()
    return message if message else type(exc).__name__


__all__ = [
    "StravaBulkImportTask",
    "StravaBulkPreflightTask",
    "build_strava_bulk_import_task",
    "build_strava_bulk_preflight_task",
]
