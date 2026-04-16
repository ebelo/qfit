from __future__ import annotations

from ....sync_repository import SyncRepository


class GeoPackageActivityStore(SyncRepository):
    """GeoPackage-backed adapter implementing the ActivityStore port."""


__all__ = ["GeoPackageActivityStore"]
