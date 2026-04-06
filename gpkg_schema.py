"""Compatibility shim for qfit GeoPackage schema helpers.

Prefer importing from ``qfit.activities.infrastructure.geopackage.gpkg_schema``.
This module remains as a stable forwarding import during the package move.
"""

from .activities.infrastructure.geopackage import gpkg_schema as _schema

TRACK_FIELDS = _schema.TRACK_FIELDS
START_FIELDS = _schema.START_FIELDS
POINT_FIELDS = _schema.POINT_FIELDS
ATLAS_FIELDS = _schema.ATLAS_FIELDS
DOCUMENT_SUMMARY_FIELDS = _schema.DOCUMENT_SUMMARY_FIELDS
COVER_HIGHLIGHT_FIELDS = _schema.COVER_HIGHLIGHT_FIELDS
PAGE_DETAIL_ITEM_FIELDS = _schema.PAGE_DETAIL_ITEM_FIELDS
PROFILE_SAMPLE_FIELDS = _schema.PROFILE_SAMPLE_FIELDS
TOC_FIELDS = _schema.TOC_FIELDS
GPKG_LAYER_SCHEMA = _schema.GPKG_LAYER_SCHEMA
make_qgs_fields = _schema.make_qgs_fields

__all__ = [
    "TRACK_FIELDS",
    "START_FIELDS",
    "POINT_FIELDS",
    "ATLAS_FIELDS",
    "DOCUMENT_SUMMARY_FIELDS",
    "COVER_HIGHLIGHT_FIELDS",
    "PAGE_DETAIL_ITEM_FIELDS",
    "PROFILE_SAMPLE_FIELDS",
    "TOC_FIELDS",
    "GPKG_LAYER_SCHEMA",
    "make_qgs_fields",
]
