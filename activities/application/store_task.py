"""Background task for storing activities without blocking the QGIS UI."""

from __future__ import annotations

import traceback
from typing import Callable

from qgis.core import QgsTask

from .load_workflow import LoadResult, LoadWorkflowService, StoreActivitiesRequest

StoreTaskFinishedCallback = Callable[[LoadResult | None, str | None, bool], None]


class StoreActivitiesTask(QgsTask):
    """Run the GeoPackage store workflow in a background QGIS task."""

    def __init__(
        self,
        workflow: LoadWorkflowService,
        request: StoreActivitiesRequest,
        on_finished: StoreTaskFinishedCallback | None = None,
    ):
        super().__init__("Store qfit activities", QgsTask.CanCancel)
        self._workflow = workflow
        self._request = request
        self._on_finished = on_finished
        self._result: LoadResult | None = None
        self._error_message: str | None = None
        self.latest_phase = "queued"
        self.latest_message = "Store queued"

    def run(self) -> bool:
        if self.isCanceled():
            return False
        try:
            self._result = self._workflow.write_database_request(
                self._request,
                progress=self._handle_progress,
                cancelled=self.isCanceled,
            )
            return not self.isCanceled()
        except Exception as exc:  # pragma: no cover, exercised via finished()
            if self.isCanceled():
                return False
            self._error_message = "".join(
                traceback.format_exception_only(type(exc), exc)
            ).strip()
            return False

    def _handle_progress(self, phase, completed, total):
        self.latest_phase = phase
        messages = {
            "reconcile": "Reconciling fetched activities…",
            "plan": "Planning changed map rows…",
            "stage": "Staging changed map rows…",
            "commit": "Publishing changed map rows…",
            "full_rebuild": "Rebuilding derived map layers…",
            "complete": "Activity store complete",
        }
        self.latest_message = messages.get(phase, "Updating activity store…")
        fraction = float(completed) / max(float(total), 1.0)
        ranges = {
            "reconcile": (0.0, 20.0),
            "plan": (20.0, 35.0),
            "stage": (35.0, 65.0),
            "commit": (65.0, 95.0),
            "full_rebuild": (20.0, 95.0),
            "complete": (100.0, 100.0),
        }
        start, end = ranges.get(phase, (0.0, 95.0))
        self.setProgress(min(100.0, max(0.0, start + ((end - start) * fraction))))

    def finished(self, ok: bool) -> None:  # pragma: no cover, Qt callback
        cancelled = self.isCanceled() and not ok and self._error_message is None
        if self._on_finished is not None:
            self._on_finished(self._result, self._error_message, cancelled)


def build_store_task(
    workflow: LoadWorkflowService,
    request: StoreActivitiesRequest,
    on_finished: StoreTaskFinishedCallback | None = None,
) -> StoreActivitiesTask:
    return StoreActivitiesTask(workflow=workflow, request=request, on_finished=on_finished)
