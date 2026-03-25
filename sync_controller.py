import logging
from datetime import date

from .provider import ProviderError
from .strava_provider import StravaProvider

logger = logging.getLogger(__name__)


class SyncController:
    """Orchestrates provider fetch/sync logic independent of the UI."""

    def build_strava_provider(self, client_id, client_secret, refresh_token, cache=None, require_refresh_token=True):
        """Create and validate a :class:`StravaProvider`."""
        provider = StravaProvider(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            cache=cache,
        )
        if not provider.has_client_credentials():
            raise ProviderError("Enter Strava client ID and client secret first.")
        if require_refresh_token and not provider.has_refresh_token():
            raise ProviderError(
                "Enter a refresh token, or use the built-in authorization flow to generate one."
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
        return (
            "Fetched {activity_count} activities from {source}, detailed tracks: {detailed_count}, "
            "cached streams: {cached}, downloaded streams: {downloaded}, rate-limit skips: {skipped}.{rate_note}"
        ).format(
            activity_count=activity_count,
            source=provider.source_name,
            detailed_count=detailed_count,
            cached=stream_stats.get("cached", 0),
            downloaded=stream_stats.get("downloaded", 0),
            skipped=stream_stats.get("skipped_rate_limit", 0),
            rate_note=rate_limit_note,
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
