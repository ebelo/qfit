"""Compatibility shim for qfit GeoPackage atlas page builders.

Prefer importing from ``qfit.activities.infrastructure.geopackage.gpkg_atlas_page_builder``.
This module remains as a stable forwarding import during the package move.
"""

from .activities.infrastructure.geopackage.gpkg_atlas_page_builder import build_atlas_layer

__all__ = ["build_atlas_layer"]
