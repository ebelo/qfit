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

    def run(self) -> bool:
        if self.isCanceled():
            return False
        try:
            self._result = self._workflow.write_database_request(self._request)
            return not self.isCanceled()
        except Exception as exc:  # pragma: no cover, exercised via finished()
            self._error_message = "".join(
                traceback.format_exception_only(type(exc), exc)
            ).strip()
            return False

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
