import logging
from dataclasses import dataclass
from datetime import date

from ...detailed_route_strategy import DEFAULT_DETAILED_ROUTE_STRATEGY
from ...providers.application.provider_registry import build_default_provider_registry
from .fetch_task import FetchTask
from .route_sync_task import RouteSyncTask
from ...providers.domain.provider import ProviderError

logger = logging.getLogger(__name__)


@dataclass
class BuildStravaProviderRequest:
    """Structured input for constructing a validated Strava provider."""

    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    cache: object = None
    require_refresh_token: bool = True
    provider_name: str = "strava"


@dataclass
class BuildFetchTaskRequest:
    """Structured input for creating a validated activity-fetch task."""

    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    cache: object = None
    per_page: int = 200
    max_pages: int = 0
    use_detailed_streams: bool = False
    max_detailed_activities: int = 25
    detailed_route_strategy: str = DEFAULT_DETAILED_ROUTE_STRATEGY
    on_finished: object = None
    before: int | None = None
    after: int | None = None


@dataclass
class BuildRouteSyncTaskRequest:
    """Structured input for creating a saved-route sync task."""

    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    cache: object = None
    output_path: str = ""
    per_page: int = 200
    max_pages: int = 0
    use_gpx_geometry: bool = True
    on_finished: object = None


@dataclass
class StravaAuthorizeRequest:
    """Structured input for building a Strava authorization URL."""

    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    cache: object = None
    redirect_uri: str = ""


@dataclass
class ExchangeStravaCodeRequest:
    """Structured input for exchanging a Strava authorization code."""

    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    cache: object = None
    authorization_code: str = ""
    redirect_uri: str = ""


class SyncController:
    """Orchestrates provider fetch/sync logic independent of the UI."""

    def __init__(self, provider_registry=None):
        self.provider_registry = provider_registry or build_default_provider_registry()

    @staticmethod
    def build_provider_request(
        client_id,
        client_secret,
        refresh_token,
        cache=None,
        require_refresh_token=True,
    ) -> BuildStravaProviderRequest:
        """Build a structured request for Strava-provider creation."""
        return BuildStravaProviderRequest(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            cache=cache,
            require_refresh_token=require_refresh_token,
        )

    def build_strava_provider(
        self,
        request: BuildStravaProviderRequest | str | None = None,
        client_secret=None,
        refresh_token=None,
        **legacy_kwargs,
    ):
        """Create and validate the configured activity provider."""
        if isinstance(request, BuildStravaProviderRequest):
            pass
        elif request is None:
            request = self.build_provider_request(**legacy_kwargs)
        else:
            request = self.build_provider_request(
                client_id=request,
                client_secret=client_secret,
                refresh_token=refresh_token,
                **legacy_kwargs,
            )

        return self.provider_registry.build_provider(request)

    @staticmethod
    def build_fetch_task_request(
        client_id,
        client_secret,
        refresh_token,
        cache,
        per_page,
        max_pages,
        use_detailed_streams,
        max_detailed_activities,
        on_finished=None,
        detailed_route_strategy=DEFAULT_DETAILED_ROUTE_STRATEGY,
        before=None,
        after=None,
    ) -> BuildFetchTaskRequest:
        """Build a structured request for creating a fetch task."""
        return BuildFetchTaskRequest(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            cache=cache,
            per_page=per_page,
            max_pages=max_pages,
            use_detailed_streams=use_detailed_streams,
            max_detailed_activities=max_detailed_activities,
            detailed_route_strategy=detailed_route_strategy,
            on_finished=on_finished,
            before=before,
            after=after,
        )

    def build_fetch_task(
        self,
        request: BuildFetchTaskRequest | None = None,
        **legacy_kwargs,
    ) -> FetchTask:
        """Create a validated :class:`FetchTask` for background activity import."""
        if request is None:
            request = self.build_fetch_task_request(**legacy_kwargs)

        provider_request = self.build_provider_request(
            client_id=request.client_id,
            client_secret=request.client_secret,
            refresh_token=request.refresh_token,
            cache=request.cache,
            require_refresh_token=True,
        )
        provider = self.build_strava_provider(provider_request)

        return FetchTask(
            provider=provider,
            per_page=request.per_page,
            max_pages=request.max_pages,
            before=request.before,
            after=request.after,
            use_detailed_streams=request.use_detailed_streams,
            max_detailed_activities=request.max_detailed_activities,
            detailed_route_strategy=request.detailed_route_strategy,
            on_finished=request.on_finished,
        )

    @staticmethod
    def build_route_sync_task_request(
        client_id,
        client_secret,
        refresh_token,
        cache,
        output_path,
        per_page=200,
        max_pages=0,
        use_gpx_geometry=True,
        on_finished=None,
    ) -> BuildRouteSyncTaskRequest:
        """Build a structured request for syncing saved Strava routes."""

        return BuildRouteSyncTaskRequest(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            cache=cache,
            output_path=output_path,
            per_page=per_page,
            max_pages=max_pages,
            use_gpx_geometry=use_gpx_geometry,
            on_finished=on_finished,
        )

    def build_route_sync_task(
        self,
        request: BuildRouteSyncTaskRequest | None = None,
        **legacy_kwargs,
    ) -> RouteSyncTask:
        """Create a validated :class:`RouteSyncTask` for route-catalog sync."""

        if request is None:
            request = self.build_route_sync_task_request(**legacy_kwargs)

        if not request.output_path:
            raise ProviderError("Choose a GeoPackage output path first.")

        provider_request = self.build_provider_request(
            client_id=request.client_id,
            client_secret=request.client_secret,
            refresh_token=request.refresh_token,
            cache=request.cache,
            require_refresh_token=True,
        )
        provider = self.build_strava_provider(provider_request)

        return RouteSyncTask(
            provider=provider,
            output_path=request.output_path,
            per_page=request.per_page,
            max_pages=request.max_pages,
            use_gpx_geometry=request.use_gpx_geometry,
            on_finished=request.on_finished,
        )

    @staticmethod
    def build_authorize_request(
        client_id,
        client_secret,
        refresh_token,
        cache,
        redirect_uri,
    ) -> StravaAuthorizeRequest:
        return StravaAuthorizeRequest(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            cache=cache,
            redirect_uri=redirect_uri,
        )

    def build_authorize_url(
        self,
        request: StravaAuthorizeRequest | None = None,
        **legacy_kwargs,
    ) -> str:
        if request is None:
            request = self.build_authorize_request(**legacy_kwargs)

        provider_request = self.build_provider_request(
            client_id=request.client_id,
            client_secret=request.client_secret,
            refresh_token=request.refresh_token,
            cache=request.cache,
            require_refresh_token=False,
        )
        provider = self.build_strava_provider(provider_request)
        return provider.build_authorize_url(redirect_uri=request.redirect_uri)

    @staticmethod
    def build_exchange_code_request(
        client_id,
        client_secret,
        refresh_token,
        cache,
        authorization_code,
        redirect_uri,
    ) -> ExchangeStravaCodeRequest:
        return ExchangeStravaCodeRequest(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            cache=cache,
            authorization_code=authorization_code,
            redirect_uri=redirect_uri,
        )

    def exchange_code_for_tokens(
        self,
        request: ExchangeStravaCodeRequest | None = None,
        **legacy_kwargs,
    ):
        if request is None:
            request = self.build_exchange_code_request(**legacy_kwargs)

        provider_request = self.build_provider_request(
            client_id=request.client_id,
            client_secret=request.client_secret,
            refresh_token=request.refresh_token,
            cache=request.cache,
            require_refresh_token=False,
        )
        provider = self.build_strava_provider(provider_request)
        payload = provider.exchange_code_for_tokens(
            authorization_code=request.authorization_code,
            redirect_uri=request.redirect_uri,
        )
        refresh_token = payload.get("refresh_token")
        if not refresh_token:
            raise ProviderError("Strava returned no refresh token")
        return payload

    def build_sync_metadata(self, activities, provider):
        """Return a sync-context dict from a completed fetch."""
        detailed_count = sum(1 for a in activities if a.geometry_source == "stream")
        today_str = date.today().isoformat()
        fetch_context = getattr(provider, "last_fetch_context", {}) or {}
        is_unbounded_fetch = int(fetch_context.get("max_pages") or 0) == 0
        uses_default_bounds = fetch_context.get("before") is None and fetch_context.get("after") is None
        is_full_sync = is_unbounded_fetch and uses_default_bounds and not getattr(provider, "last_fetch_notice", None)
        return {
            "provider": provider.source_name,
            "before_epoch": fetch_context.get("before"),
            "after_epoch": fetch_context.get("after"),
            "fetched_count": len(activities),
            "detailed_count": detailed_count,
            "stream_stats": provider.last_stream_enrichment_stats,
            "rate_limit": provider.last_rate_limit,
            "is_full_sync": is_full_sync,
            "today_str": today_str,
        }

    def fetch_status_text(self, provider, activity_count, detailed_count):
        """Build a human-readable status string for a completed fetch."""
        stream_stats = provider.last_stream_enrichment_stats or {}
        rate_limit_note = self._rate_limit_note(provider.last_rate_limit)
        fetch_notice = self._fetch_notice(provider)
        progress_note = ""
        if "missing_before" in stream_stats or "remaining_missing" in stream_stats:
            progress_note = (
                ", already detailed before run: {already}, missing detailed routes before run: {before}, "
                "remaining missing: {after}, empty detailed-route responses: {empty}, errors: {errors}"
            ).format(
                already=stream_stats.get("already_detailed", 0),
                before=stream_stats.get("missing_before", 0),
                after=stream_stats.get("remaining_missing", 0),
                empty=stream_stats.get("empty", 0),
                errors=stream_stats.get("errors", 0),
            )
        return (
            "Fetched {activity_count} activities from {source}, detailed tracks: {detailed_count}, "
            "cached streams: {cached}, downloaded streams: {downloaded}, rate-limit skips: {skipped}{progress}.{rate_note}{fetch_notice}"
        ).format(
            activity_count=activity_count,
            source=provider.source_name,
            detailed_count=detailed_count,
            cached=stream_stats.get("cached", 0),
            downloaded=stream_stats.get("downloaded", 0),
            skipped=stream_stats.get("skipped_rate_limit", 0),
            progress=progress_note,
            rate_note=rate_limit_note,
            fetch_notice=fetch_notice,
        )

    @staticmethod
    def _rate_limit_note(rate_limit):
        if not rate_limit:
            return ""
        short_remaining = rate_limit.get("short_remaining")
        long_remaining = rate_limit.get("long_remaining")
        if short_remaining is None and long_remaining is None:
            return ""
        return " Remaining rate limit: short={short}, long={long}.".format(
            short=short_remaining if short_remaining is not None else "?",
            long=long_remaining if long_remaining is not None else "?",
        )

    @staticmethod
    def _fetch_notice(provider):
        notice = getattr(provider, "last_fetch_notice", None)
        if not notice:
            return ""
        return " {notice}".format(notice=notice)
