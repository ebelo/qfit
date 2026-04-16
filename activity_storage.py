"""Deprecated compatibility shim for qfit's activity storage helpers.

Use :mod:`qfit.activities.application.activity_storage` for the
application-facing port and
:mod:`qfit.activities.infrastructure.geopackage.activity_storage` for the
GeoPackage adapter. Do not add new in-repo imports here.
"""

from .activities.application.activity_storage import ActivityStore
from .activities.infrastructure.geopackage.activity_storage import GeoPackageActivityStore

__all__ = ["ActivityStore", "GeoPackageActivityStore"]
