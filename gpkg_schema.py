"""
GeoPackage schema definitions for qfit.

This module owns:

- Field-definition constants for every layer and table written to the .gpkg
- ``make_qgs_fields`` — converts a field-definition list to a ``QgsFields`` object
- ``GPKG_LAYER_SCHEMA`` — the authoritative description of every layer/table in
  the file (geometry type, kind, field names, primary-key hints)

Nothing in this module performs I/O or builds features; it only declares *what
exists* in the GeoPackage.
"""

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsField, QgsFields

from .sync_repository import REGISTRY_TABLE, SYNC_STATE_TABLE

# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

TRACK_FIELDS = [
    ("source", QVariant.String),
    ("source_activity_id", QVariant.String),
    ("external_id", QVariant.String),
    ("name", QVariant.String),
    ("activity_type", QVariant.String),
    ("sport_type", QVariant.String),
    ("start_date", QVariant.String),
    ("start_date_local", QVariant.String),
    ("timezone", QVariant.String),
    ("distance_m", QVariant.Double),
    ("moving_time_s", QVariant.Int),
    ("elapsed_time_s", QVariant.Int),
    ("total_elevation_gain_m", QVariant.Double),
    ("average_speed_mps", QVariant.Double),
    ("max_speed_mps", QVariant.Double),
    ("average_heartrate", QVariant.Double),
    ("max_heartrate", QVariant.Double),
    ("average_watts", QVariant.Double),
    ("kilojoules", QVariant.Double),
    ("calories", QVariant.Double),
    ("suffer_score", QVariant.Double),
    ("start_lat", QVariant.Double),
    ("start_lon", QVariant.Double),
    ("end_lat", QVariant.Double),
    ("end_lon", QVariant.Double),
    ("summary_polyline", QVariant.String),
    ("geometry_source", QVariant.String),
    ("geometry_point_count", QVariant.Int),
    ("details_json", QVariant.String),
    ("summary_hash", QVariant.String),
    ("first_seen_at", QVariant.String),
    ("last_synced_at", QVariant.String),
]

START_FIELDS = [
    ("activity_fk", QVariant.Int),
    ("source", QVariant.String),
    ("source_activity_id", QVariant.String),
    ("name", QVariant.String),
    ("activity_type", QVariant.String),
    ("start_date", QVariant.String),
    ("distance_m", QVariant.Double),
    ("last_synced_at", QVariant.String),
]

POINT_FIELDS = [
    ("activity_fk", QVariant.Int),
    ("source", QVariant.String),
    ("source_activity_id", QVariant.String),
    ("point_index", QVariant.Int),
    ("point_ratio", QVariant.Double),
    ("stream_time_s", QVariant.Int),
    ("point_timestamp_utc", QVariant.String),
    ("point_timestamp_local", QVariant.String),
    ("stream_distance_m", QVariant.Double),
    ("altitude_m", QVariant.Double),
    ("heartrate_bpm", QVariant.Double),
    ("cadence_rpm", QVariant.Double),
    ("watts", QVariant.Double),
    ("velocity_mps", QVariant.Double),
    ("temp_c", QVariant.Double),
    ("grade_smooth_pct", QVariant.Double),
    ("moving", QVariant.Int),
    ("name", QVariant.String),
    ("activity_type", QVariant.String),
    ("start_date", QVariant.String),
    ("distance_m", QVariant.Double),
    ("geometry_source", QVariant.String),
    ("last_synced_at", QVariant.String),
]

ATLAS_FIELDS = [
    ("activity_fk", QVariant.Int),
    ("source", QVariant.String),
    ("source_activity_id", QVariant.String),
    ("name", QVariant.String),
    ("activity_type", QVariant.String),
    ("sport_type", QVariant.String),
    ("start_date", QVariant.String),
    ("distance_m", QVariant.Double),
    ("moving_time_s", QVariant.Int),
    ("total_elevation_gain_m", QVariant.Double),
    ("geometry_source", QVariant.String),
    ("page_number", QVariant.Int),
    ("page_sort_key", QVariant.String),
    ("page_name", QVariant.String),
    ("page_title", QVariant.String),
    ("page_subtitle", QVariant.String),
    ("page_date", QVariant.String),
    ("page_toc_label", QVariant.String),
    ("page_distance_label", QVariant.String),
    ("page_duration_label", QVariant.String),
    ("page_average_speed_label", QVariant.String),
    ("page_average_pace_label", QVariant.String),
    ("page_elevation_gain_label", QVariant.String),
    ("page_stats_summary", QVariant.String),
    ("page_profile_summary", QVariant.String),
    ("document_activity_count", QVariant.Int),
    ("document_date_range_label", QVariant.String),
    ("document_total_distance_label", QVariant.String),
    ("document_total_duration_label", QVariant.String),
    ("document_total_elevation_gain_label", QVariant.String),
    ("document_activity_types_label", QVariant.String),
    ("document_cover_summary", QVariant.String),
    ("profile_available", QVariant.Int),
    ("profile_point_count", QVariant.Int),
    ("profile_distance_m", QVariant.Double),
    ("profile_distance_label", QVariant.String),
    ("profile_min_altitude_m", QVariant.Double),
    ("profile_max_altitude_m", QVariant.Double),
    ("profile_altitude_range_label", QVariant.String),
    ("profile_relief_m", QVariant.Double),
    ("profile_elevation_gain_m", QVariant.Double),
    ("profile_elevation_gain_label", QVariant.String),
    ("profile_elevation_loss_m", QVariant.Double),
    ("profile_elevation_loss_label", QVariant.String),
    ("center_x_3857", QVariant.Double),
    ("center_y_3857", QVariant.Double),
    ("extent_width_deg", QVariant.Double),
    ("extent_height_deg", QVariant.Double),
    ("extent_width_m", QVariant.Double),
    ("extent_height_m", QVariant.Double),
]

DOCUMENT_SUMMARY_FIELDS = [
    ("activity_count", QVariant.Int),
    ("activity_date_start", QVariant.String),
    ("activity_date_end", QVariant.String),
    ("date_range_label", QVariant.String),
    ("total_distance_m", QVariant.Double),
    ("total_distance_label", QVariant.String),
    ("total_moving_time_s", QVariant.Int),
    ("total_duration_label", QVariant.String),
    ("total_elevation_gain_m", QVariant.Double),
    ("total_elevation_gain_label", QVariant.String),
    ("activity_types_label", QVariant.String),
    ("cover_summary", QVariant.String),
]

COVER_HIGHLIGHT_FIELDS = [
    ("highlight_order", QVariant.Int),
    ("highlight_key", QVariant.String),
    ("highlight_label", QVariant.String),
    ("highlight_value", QVariant.String),
]

PAGE_DETAIL_ITEM_FIELDS = [
    ("page_number", QVariant.Int),
    ("page_sort_key", QVariant.String),
    ("page_name", QVariant.String),
    ("page_title", QVariant.String),
    ("detail_order", QVariant.Int),
    ("detail_key", QVariant.String),
    ("detail_label", QVariant.String),
    ("detail_value", QVariant.String),
]

PROFILE_SAMPLE_FIELDS = [
    ("page_number", QVariant.Int),
    ("page_sort_key", QVariant.String),
    ("page_name", QVariant.String),
    ("page_title", QVariant.String),
    ("page_date", QVariant.String),
    ("source", QVariant.String),
    ("source_activity_id", QVariant.String),
    ("activity_type", QVariant.String),
    ("profile_point_index", QVariant.Int),
    ("profile_point_count", QVariant.Int),
    ("profile_point_ratio", QVariant.Double),
    ("distance_m", QVariant.Double),
    ("distance_label", QVariant.String),
    ("altitude_m", QVariant.Double),
    ("profile_distance_m", QVariant.Double),
]

TOC_FIELDS = [
    ("page_number", QVariant.Int),
    ("page_number_label", QVariant.String),
    ("page_sort_key", QVariant.String),
    ("page_name", QVariant.String),
    ("page_title", QVariant.String),
    ("page_subtitle", QVariant.String),
    ("page_date", QVariant.String),
    ("page_toc_label", QVariant.String),
    ("toc_entry_label", QVariant.String),
    ("page_distance_label", QVariant.String),
    ("page_duration_label", QVariant.String),
    ("page_stats_summary", QVariant.String),
    ("profile_available", QVariant.Int),
    ("page_profile_summary", QVariant.String),
]

# ---------------------------------------------------------------------------
# Layer schema
# ---------------------------------------------------------------------------

#: Authoritative description of every layer and table in the GeoPackage.
#: Keys are layer/table names; values describe geometry type, kind, and fields.
#: ``REGISTRY_TABLE`` and ``SYNC_STATE_TABLE`` are managed by
#: :class:`~qfit.sync_repository.SyncRepository` and do not list fields here.
GPKG_LAYER_SCHEMA = {
    REGISTRY_TABLE: {
        "geometry": None,
        "kind": "table",
        "primary_key": ["source", "source_activity_id"],
    },
    SYNC_STATE_TABLE: {
        "geometry": None,
        "kind": "table",
        "primary_key": ["provider"],
    },
    "activity_tracks": {
        "geometry": "LINESTRING",
        "kind": "layer",
        "fields": [name for name, _ in TRACK_FIELDS],
    },
    "activity_starts": {
        "geometry": "POINT",
        "kind": "layer",
        "fields": [name for name, _ in START_FIELDS],
    },
    "activity_points": {
        "geometry": "POINT",
        "kind": "layer",
        "fields": [name for name, _ in POINT_FIELDS],
    },
    "activity_atlas_pages": {
        "geometry": "POLYGON",
        "kind": "layer",
        "fields": [name for name, _ in ATLAS_FIELDS],
    },
    "atlas_document_summary": {
        "geometry": None,
        "kind": "table",
        "fields": [name for name, _ in DOCUMENT_SUMMARY_FIELDS],
    },
    "atlas_cover_highlights": {
        "geometry": None,
        "kind": "table",
        "fields": [name for name, _ in COVER_HIGHLIGHT_FIELDS],
    },
    "atlas_page_detail_items": {
        "geometry": None,
        "kind": "table",
        "fields": [name for name, _ in PAGE_DETAIL_ITEM_FIELDS],
    },
    "atlas_profile_samples": {
        "geometry": None,
        "kind": "table",
        "fields": [name for name, _ in PROFILE_SAMPLE_FIELDS],
    },
    "atlas_toc_entries": {
        "geometry": None,
        "kind": "table",
        "fields": [name for name, _ in TOC_FIELDS],
    },
}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def make_qgs_fields(field_defs):
    """Return a ``QgsFields`` object built from *field_defs*.

    *field_defs* is a sequence of ``(name, QVariant.Type)`` pairs, matching
    the convention used by the ``*_FIELDS`` constants in this module.
    """
    fields = QgsFields()
    for name, field_type in field_defs:
        fields.append(QgsField(name, field_type))
    return fields
