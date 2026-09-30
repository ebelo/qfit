"""Name-only metadata refresh independent from incremental activity sync."""

from pathlib import Path

from ...providers.domain.provider import ProviderError
from ...sync_repository import SyncRepository


def parse_activity_ids(text):
    """An empty selection means history; otherwise accept positive numeric IDs."""
    if not text.strip():
        return ()
    ids = tuple(dict.fromkeys(part.strip() for part in text.split(",")))
    if any(not value.isascii() or not value.isdecimal() or int(value) <= 0 for value in ids):
        raise ValueError("Enter positive Strava activity IDs separated by commas.")
    return tuple(dict.fromkeys(str(int(value)) for value in ids))


def refresh_activity_names(provider, output_path, activity_ids=(), *, cancelled=None, progress=None):
    """Fetch first, then publish names in one transaction; never mutate on partial fetch."""
    if not Path(output_path).is_file():
        raise ValueError("Select a GeoPackage containing stored Strava activities first.")
    repository = SyncRepository(output_path)
    if repository.load_activity_count(provider="strava") == 0:
        raise ValueError("Select a GeoPackage containing stored Strava activities first.")
    names = {}
    if activity_ids:
        for index, activity_id in enumerate(activity_ids):
            _check_cancelled(cancelled)
            names[activity_id] = provider.fetch_activity_name(activity_id)
            if progress is not None:
                progress("names", index + 1, len(activity_ids))
    else:
        activities = provider.fetch_activities(
            per_page=200, max_pages=0, before=None, after=None,
            use_detailed_streams=False, cancelled=cancelled, progress=progress,
        )
        _check_cancelled(cancelled)
        if provider.last_fetch_notice:
            raise ProviderError(
                "Historical name refresh was incomplete. No names were changed. "
                "Retry later or refresh specific activity IDs. " + provider.last_fetch_notice
            )
        names = {str(activity.source_activity_id): activity.name for activity in activities}
    _check_cancelled(cancelled)
    return repository.refresh_activity_names(names, cancelled=cancelled)


def _check_cancelled(cancelled):
    if cancelled is not None and cancelled():
        raise InterruptedError("Activity name refresh cancelled")
