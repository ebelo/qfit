"""Compatibility shim for qfit GeoPackage point-layer builders.

Prefer importing from ``qfit.activities.infrastructure.geopackage.gpkg_point_layer_builder``.
This module remains as a stable forwarding import during the package move.
"""

from .activities.infrastructure.geopackage.gpkg_point_layer_builder import build_point_layer

__all__ = ["build_point_layer"]
