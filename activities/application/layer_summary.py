from __future__ import annotations


def build_loaded_activities_summary(*, total_activities: int, last_sync_date: str) -> str:
    return "{total} activities loaded (last sync: {sync_date})".format(
        total=total_activities,
        sync_date=last_sync_date,
    )
