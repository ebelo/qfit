import logging
from dataclasses import dataclass
from datetime import date

from ...providers.domain.provider import ProviderError
from ...providers.infrastructure.strava_provider import StravaProvider

logger = logging.getLogger(__name__)


@dataclass
class BuildStravaProviderRequest:
    """Structured input for constructing a validated Strava provider."""

    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    cache: object = None
    require_refresh_token: bool = True


class SyncController:
    """Orchestrates provider fetch/sync logic independent of the UI."""

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
        """Create and validate a :class:`StravaProvider`."""
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

        provider = StravaProvider(
            client_id=request.client_id,
            client_secret=request.client_secret,
            refresh_token=request.refresh_token,
            cache=request.cache,
        )
        if not provider.has_client_credentials():
            raise ProviderError(
                "Open qfit → Configuration and enter your Strava client ID and client secret first."
            )
        if request.require_refresh_token and not provider.has_refresh_token():
            raise ProviderError(
                "Open qfit → Configuration and enter a Strava refresh token first."
            )
        return provider

    def build_sync_metadata(self, activities, provider):
        """Return a sync-context dict from a completed fetch."""
        detailed_count = sum(1 for a in activities if a.geometry_source == "stream")
        today_str = date.today().isoformat()
        return {
            "provider": provider.source_name,
            "before_epoch": None,
            "after_epoch": None,
            "fetched_count": len(activities),
            "detailed_count": detailed_count,
            "stream_stats": provider.last_stream_enrichment_stats,
            "rate_limit": provider.last_rate_limit,
            "is_full_sync": True,
            "today_str": today_str,
        }

    def fetch_status_text(self, provider, activity_count, detailed_count):
        """Build a human-readable status string for a completed fetch."""
        stream_stats = provider.last_stream_enrichment_stats or {}
        rate_limit_note = self._rate_limit_note(provider.last_rate_limit)
        fetch_notice = self._fetch_notice(provider)
        return (
            "Fetched {activity_count} activities from {source}, detailed tracks: {detailed_count}, "
            "cached streams: {cached}, downloaded streams: {downloaded}, rate-limit skips: {skipped}.{rate_note}{fetch_notice}"
        ).format(
            activity_count=activity_count,
            source=provider.source_name,
            detailed_count=detailed_count,
            cached=stream_stats.get("cached", 0),
            downloaded=stream_stats.get("downloaded", 0),
            skipped=stream_stats.get("skipped_rate_limit", 0),
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
