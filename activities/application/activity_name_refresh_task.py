"""QGIS background adapter for metadata-only activity name refresh."""

from qfit.ui.qt_enum_compat import qgis_enum_value

import logging

from qgis.core import QgsTask

from .activity_name_refresh import refresh_activity_names

logger = logging.getLogger(__name__)


class ActivityNameRefreshTask(QgsTask):
    is_name_refresh = True

    def __init__(self, provider, output_path, activity_ids=(), *, on_finished=None):
        super().__init__("Refresh Strava activity names", qgis_enum_value(QgsTask, "Flag", "CanCancel"))
        self.provider = provider
        self.output_path = output_path
        self.activity_ids = activity_ids
        self.on_finished = on_finished
        self.result = None
        self.error = None
        self.latest_message = "Refreshing Strava activity names…"

    def run(self):
        try:
            self.result = refresh_activity_names(
                self.provider, self.output_path, self.activity_ids,
                cancelled=self.isCanceled, progress=self._progress,
            )
            return True
        except InterruptedError:
            return False
        except Exception as exc:  # QgsTask thread boundary
            logger.exception("Activity name refresh failed")
            self.error = str(exc)
            return False

    def _progress(self, phase, completed, total):
        self.latest_message = f"Fetched {completed} activity names"
        self.setProgress(80 * completed / total if total else 30)

    def finished(self, ok):
        if self.on_finished is not None:
            self.on_finished(self.result, self.error, not ok and self.isCanceled())
