"""Compatibility shim for qfit GeoPackage write orchestration helpers.

Prefer importing from ``qfit.activities.infrastructure.geopackage.gpkg_write_orchestration``.
This module remains as a stable forwarding import during the package move.
"""

from .activities.infrastructure.geopackage.gpkg_write_orchestration import (
    bootstrap_empty_gpkg,
    build_and_write_all_layers,
    ensure_attribute_indexes,
    ensure_spatial_indexes,
)

__all__ = [
    "bootstrap_empty_gpkg",
    "build_and_write_all_layers",
    "ensure_attribute_indexes",
    "ensure_spatial_indexes",
]
