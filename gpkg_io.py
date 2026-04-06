"""Compatibility shim for qfit GeoPackage I/O helpers.

Prefer importing from ``qfit.activities.infrastructure.geopackage.gpkg_io``.
This module remains as a stable forwarding import during the package move.
"""

from .activities.infrastructure.geopackage.gpkg_io import write_layer_to_gpkg

__all__ = ["write_layer_to_gpkg"]
