"""Compatibility shim for qfit GeoPackage atlas helper-table builders.

Prefer importing from ``qfit.activities.infrastructure.geopackage.gpkg_atlas_table_builders``.
This module remains as a stable forwarding import during the package move.
"""

from .activities.infrastructure.geopackage.gpkg_atlas_table_builders import (
    build_cover_highlight_layer,
    build_document_summary_layer,
    build_page_detail_item_layer,
    build_profile_sample_layer,
    build_toc_layer,
)

__all__ = [
    "build_cover_highlight_layer",
    "build_document_summary_layer",
    "build_page_detail_item_layer",
    "build_profile_sample_layer",
    "build_toc_layer",
]
