"""Compatibility shim for qfit GeoPackage activity geometry-layer builders.

Prefer importing from ``qfit.activities.infrastructure.geopackage.gpkg_layer_builders``.
This module remains as a stable forwarding import during the package move.
"""

from .activities.infrastructure.geopackage.gpkg_layer_builders import (
    build_atlas_layer,
    build_start_layer,
    build_track_layer,
)

__all__ = ["build_atlas_layer", "build_start_layer", "build_track_layer"]
