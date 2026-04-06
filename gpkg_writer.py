"""Compatibility shim for qfit GeoPackage writer helpers.

Prefer importing from ``qfit.activities.infrastructure.geopackage.gpkg_writer``.
This module remains as a stable forwarding import during the package move.
"""

from .activities.infrastructure.geopackage.gpkg_writer import GeoPackageWriter

__all__ = ["GeoPackageWriter"]
