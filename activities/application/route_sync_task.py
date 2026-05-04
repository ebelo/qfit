"""Background task for syncing saved Strava routes into the GeoPackage."""

from __future__ import annotations

import logging
from copy import copy
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Callable

from qgis.core import QgsTask

from ...providers.domain.provider import ProviderError

logger = logging.getLogger(__name__)

RouteSyncTaskFinishedCallback = Callable[[dict | None, str | None, bool, object], None]
ROUTE_DETAIL_REQUESTS_PER_ROUTE = 2
ROUTE_SYNC_MIN_SHORT_REMAINING = 10
ROUTE_SYNC_MIN_LONG_REMAINING = 50
ROUTE_SYNC_SHORT_WINDOW_RESERVE_FRACTION = 0.5
ROUTE_SYNC_LONG_WINDOW_RESERVE_FRACTION = 0.05


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
        self._fetch_notice: str | None = None

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
            fetch_notice = self._current_fetch_notice()
            if fetch_notice and isinstance(self._result, dict):
                self._result["fetch_notice"] = fetch_notice
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
        for index, route in enumerate(routes):
            if self.isCanceled():
                break
            if self._should_pause_route_enrichment_for_rate_limit():
                skipped_routes = self._mark_routes_skipped_for_rate_limit(routes[index:])
                enriched_routes.extend(skipped_routes)
                self._fetch_notice = self._route_rate_limit_pause_notice(len(skipped_routes))
                break
            route_id = getattr(route, "source_route_id", None)
            if route_id in (None, ""):
                enriched_routes.append(route)
                continue
            try:
                enriched_routes.append(
                    self._provider.fetch_route_detail(
                        route_id,
                        use_gpx_geometry=True,
                    )
                )
            except ProviderError as exc:
                if not _is_rate_limit_error(exc):
                    raise
                skipped_routes = self._mark_routes_skipped_for_rate_limit(routes[index:])
                enriched_routes.extend(skipped_routes)
                self._fetch_notice = self._route_rate_limit_pause_notice(
                    len(skipped_routes),
                    error_message=str(exc),
                )
                break
        return enriched_routes

    def _build_sync_metadata(self, routes):
        provider_name = getattr(self._provider, "source_name", "strava")
        fetch_notice = self._current_fetch_notice()
        is_full_sync = self._max_pages == 0 and not fetch_notice
        return {
            "provider": provider_name,
            "fetched_count": len(routes),
            "detailed_count": sum(1 for route in routes if _route_has_gpx_geometry(route)),
            "rate_limit": getattr(self._provider, "last_rate_limit", None),
            "fetch_notice": fetch_notice,
            "is_full_sync": is_full_sync,
            "today_str": date.today().isoformat(),
            "synced_at": datetime.now(UTC).isoformat(),
        }

    def _current_fetch_notice(self) -> str | None:
        notices = []
        for notice in (getattr(self._provider, "last_fetch_notice", None), self._fetch_notice):
            if notice and notice not in notices:
                notices.append(notice)
        if not notices:
            return None
        return " ".join(notices)

    def _should_pause_route_enrichment_for_rate_limit(self) -> bool:
        budget = _route_detail_enrichment_budget(getattr(self._provider, "last_rate_limit", None))
        return budget is not None and budget <= 0

    def _route_rate_limit_pause_notice(self, skipped_count: int, *, error_message: str | None = None) -> str:
        rate_limit = getattr(self._provider, "last_rate_limit", None) or {}
        short_remaining = rate_limit.get("short_remaining")
        long_remaining = rate_limit.get("long_remaining")
        detail = (
            "Stopped route GPX enrichment early to preserve Strava API headroom. "
            "Skipped GPX enrichment for {skipped_count} saved routes; summary route metadata was still stored. "
            "Remaining read quota: short={short}, long={long}."
        ).format(
            skipped_count=skipped_count,
            short=short_remaining if short_remaining is not None else "?",
            long=long_remaining if long_remaining is not None else "?",
        )
        if error_message:
            return "{detail} Last Strava response: {error_message}".format(
                detail=detail,
                error_message=error_message,
            )
        return detail

    def _mark_routes_skipped_for_rate_limit(self, routes):
        skipped_routes = []
        for route in routes:
            route, details = _route_with_mutable_details(route)
            if details is None:
                continue
            details["gpx_geometry_status"] = "skipped_rate_limit"
            details["gpx_skipped_reason"] = "rate_limit_guard"
            skipped_routes.append(route)
        return skipped_routes


def _route_has_gpx_geometry(route) -> bool:
    details = getattr(route, "details_json", None) or {}
    return details.get("gpx_geometry_status") == "downloaded"


def _is_rate_limit_error(exc: Exception) -> bool:
    return bool(getattr(exc, "is_rate_limit", False))


def _route_with_mutable_details(route):
    details = getattr(route, "details_json", None)
    if isinstance(details, dict):
        return route, details

    details = {}
    try:
        route.details_json = details
        return route, details
    except AttributeError:
        pass

    try:
        replaced_route = replace(route, details_json=details)
        return replaced_route, details
    except (TypeError, ValueError):
        pass

    try:
        copied_route = copy(route)
        copied_route.details_json = details
        return copied_route, details
    except AttributeError:
        return route, None


def _route_detail_enrichment_budget(rate_limit) -> int | None:
    if not rate_limit:
        return None
    budgets = []
    short_budget = _remaining_request_budget(
        rate_limit,
        remaining_key="short_remaining",
        limit_key="short_limit",
        minimum_reserve=ROUTE_SYNC_MIN_SHORT_REMAINING,
        reserve_fraction=ROUTE_SYNC_SHORT_WINDOW_RESERVE_FRACTION,
    )
    if short_budget is not None:
        budgets.append(short_budget // ROUTE_DETAIL_REQUESTS_PER_ROUTE)
    long_budget = _remaining_request_budget(
        rate_limit,
        remaining_key="long_remaining",
        limit_key="long_limit",
        minimum_reserve=ROUTE_SYNC_MIN_LONG_REMAINING,
        reserve_fraction=ROUTE_SYNC_LONG_WINDOW_RESERVE_FRACTION,
    )
    if long_budget is not None:
        budgets.append(long_budget // ROUTE_DETAIL_REQUESTS_PER_ROUTE)
    if not budgets:
        return None
    return min(budgets)


def _remaining_request_budget(
    rate_limit,
    *,
    remaining_key: str,
    limit_key: str,
    minimum_reserve: int,
    reserve_fraction: float,
) -> int | None:
    remaining = rate_limit.get(remaining_key)
    if remaining is None:
        return None
    reserve = minimum_reserve
    limit = rate_limit.get(limit_key)
    if limit is not None:
        reserve = max(reserve, int(limit * reserve_fraction))
    return max(0, int(remaining) - reserve)


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
