"""Background task for syncing saved Strava routes into the GeoPackage."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Callable

from qgis.core import QgsTask

from ...providers.domain.provider import ProviderError

logger = logging.getLogger(__name__)

RouteSyncTaskFinishedCallback = Callable[[dict | None, str | None, bool, object], None]


def _default_writer_factory(**kwargs):
    from ..infrastructure.geopackage.gpkg_writer import GeoPackageWriter

    return GeoPackageWriter(**kwargs)


class RouteSyncTask(QgsTask):
    """Fetch saved routes, enrich them with GPX geometry, and persist route layers."""

    def __init__(
        self,
        *,
        provider,
        output_path: str,
        per_page: int = 200,
        max_pages: int = 0,
        use_gpx_geometry: bool = True,
        writer_factory=None,
        on_finished: RouteSyncTaskFinishedCallback | None = None,
    ):
        super().__init__("Sync saved Strava routes", QgsTask.CanCancel)
        self._provider = provider
        self._output_path = output_path
        self._per_page = max(1, int(per_page or 1))
        self._max_pages = max(0, int(max_pages or 0))
        self._use_gpx_geometry = bool(use_gpx_geometry)
        self._writer_factory = writer_factory or _default_writer_factory
        self._on_finished = on_finished
        self._result: dict | None = None
        self._error: str | None = None

    def run(self) -> bool:
        """Run the route sync in a QGIS worker thread."""

        try:
            routes = self._fetch_routes()
            if self.isCanceled():
                return False

            writer = self._writer_factory(output_path=self._output_path)
            self._result = writer.write_routes(
                routes,
                sync_metadata=self._build_sync_metadata(routes),
            )
            return True
        except ProviderError as exc:
            self._error = str(exc)
            return False
        except Exception as exc:  # noqa: BLE001 – worker-thread safety net
            logger.exception("Route sync task failed")
            self._error = str(exc)
            return False

    def finished(self, result: bool) -> None:  # pragma: no cover - Qt callback shape
        cancelled = self.isCanceled() and self._error is None
        if self._on_finished is not None:
            self._on_finished(
                self._result if (result or self._result is not None) else None,
                self._error,
                cancelled,
                self._provider,
            )

    def _fetch_routes(self):
        if not hasattr(self._provider, "fetch_routes"):
            raise ProviderError("The configured provider does not support saved routes")

        self._provider.last_fetch_context = {
            "route_max_pages": self._max_pages,
            "route_per_page": self._per_page,
        }
        routes = list(
            self._provider.fetch_routes(
                per_page=self._per_page,
                max_pages=self._max_pages,
            )
        )
        if not self._use_gpx_geometry or not hasattr(self._provider, "fetch_route_detail"):
            return routes

        enriched_routes = []
        for route in routes:
            if self.isCanceled():
                break
            route_id = getattr(route, "source_route_id", None)
            if route_id in (None, ""):
                enriched_routes.append(route)
                continue
            enriched_routes.append(
                self._provider.fetch_route_detail(
                    route_id,
                    use_gpx_geometry=True,
                )
            )
        return enriched_routes

    def _build_sync_metadata(self, routes):
        provider_name = getattr(self._provider, "source_name", "strava")
        fetch_notice = getattr(self._provider, "last_fetch_notice", None)
        is_full_sync = self._max_pages == 0 and not fetch_notice
        return {
            "provider": provider_name,
            "fetched_count": len(routes),
            "detailed_count": sum(1 for route in routes if _route_has_gpx_geometry(route)),
            "rate_limit": getattr(self._provider, "last_rate_limit", None),
            "is_full_sync": is_full_sync,
            "today_str": date.today().isoformat(),
            "synced_at": datetime.now(UTC).isoformat(),
        }


def _route_has_gpx_geometry(route) -> bool:
    details = getattr(route, "details_json", None) or {}
    return details.get("gpx_geometry_status") == "downloaded"


def build_route_sync_task(
    *,
    provider,
    output_path: str,
    per_page: int = 200,
    max_pages: int = 0,
    use_gpx_geometry: bool = True,
    writer_factory=None,
    on_finished: RouteSyncTaskFinishedCallback | None = None,
) -> RouteSyncTask:
    return RouteSyncTask(
        provider=provider,
        output_path=output_path,
        per_page=per_page,
        max_pages=max_pages,
        use_gpx_geometry=use_gpx_geometry,
        writer_factory=writer_factory,
        on_finished=on_finished,
    )


__all__ = [
    "RouteSyncTask",
    "RouteSyncTaskFinishedCallback",
    "build_route_sync_task",
]
