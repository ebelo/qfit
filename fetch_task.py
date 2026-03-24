"""Background task for fetching Strava activities without blocking the QGIS UI.

Uses :class:`qgis.core.QgsTask` so that fetches appear in the QGIS task
manager, show progress in the native progress bar, and can be cancelled.
"""

import logging

from qgis.core import QgsTask

logger = logging.getLogger(__name__)

from .strava_client import StravaClient, StravaClientError


class StravaFetchTask(QgsTask):
    """Wraps :meth:`StravaClient.fetch_activities` in a ``QgsTask``.

    The task runs in a QGIS-managed worker thread so the main thread (and
    therefore the QGIS UI) stays responsive while activities are being
    downloaded from Strava.

    Parameters
    ----------
    client:
        A fully-configured :class:`StravaClient` instance.
    per_page:
        Number of activities to request per API page.
    max_pages:
        Maximum number of pages to fetch.
    before:
        Upper bound epoch timestamp (passed to Strava API).
    after:
        Lower bound epoch timestamp (passed to Strava API).
    use_detailed_streams:
        Whether to enrich activities with per-point stream data.
    max_detailed_activities:
        Maximum number of activities to enrich with streams.
    on_finished:
        Callable invoked **on the main thread** when the task completes.
        It receives keyword arguments:
        ``activities`` (list | None), ``error`` (str | None),
        ``cancelled`` (bool), ``client`` (:class:`StravaClient`).
    """

    def __init__(
        self,
        client,
        per_page,
        max_pages,
        before,
        after,
        use_detailed_streams,
        max_detailed_activities,
        on_finished,
    ):
        super().__init__("Fetch Strava activities", QgsTask.CanCancel)
        self._client = client
        self._per_page = per_page
        self._max_pages = max_pages
        self._before = before
        self._after = after
        self._use_detailed_streams = use_detailed_streams
        self._max_detailed_activities = max_detailed_activities
        self._on_finished = on_finished
        self._activities = []
        self._error = None

    # ------------------------------------------------------------------
    # QgsTask interface
    # ------------------------------------------------------------------

    def run(self):
        """Execute the Strava fetch in the worker thread.

        Returns ``True`` on success, ``False`` on error or cancellation.
        """
        try:
            self._activities = self._client.fetch_activities(
                per_page=self._per_page,
                max_pages=self._max_pages,
                before=self._before,
                after=self._after,
                use_detailed_streams=self._use_detailed_streams,
                max_detailed_activities=self._max_detailed_activities,
            )
        except StravaClientError as exc:
            self._error = str(exc)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.exception("Strava fetch task failed")
            self._error = str(exc)
            return False

        return not self.isCanceled()

    def finished(self, result):
        """Called on the **main thread** after ``run()`` returns.

        Delegates to the ``on_finished`` callback so the dock widget can
        update its UI safely.
        """
        if self._on_finished is not None:
            self._on_finished(
                activities=self._activities if result else None,
                error=self._error,
                cancelled=self.isCanceled(),
                client=self._client,
            )
