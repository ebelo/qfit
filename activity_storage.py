from __future__ import annotations

from typing import Protocol, runtime_checkable

from .sync_repository import SyncRepository, SyncStats


@runtime_checkable
class ActivityStore(Protocol):
    """Application-facing port for persisted qfit activity storage."""

    def ensure_schema(self) -> None:
        """Create or update storage metadata/schema as needed."""

    def upsert_activities(self, activities, sync_metadata=None) -> SyncStats:
        """Persist fetched activities and return sync counters."""

    def load_all_activity_records(self) -> list[dict]:
        """Return all stored activity records in canonical registry form."""

    def load_all_activities(self):
        """Return all stored activities as domain objects."""


class GeoPackageActivityStore(SyncRepository):
    """GeoPackage-backed adapter implementing the ActivityStore port."""
