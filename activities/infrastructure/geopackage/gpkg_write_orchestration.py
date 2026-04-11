"""
GeoPackage bootstrap and layer-write sequencing for qfit.

This module owns the two write-orchestration steps that were previously
inlined in :class:`~qfit.gpkg_writer.GeoPackageWriter`:

- :func:`bootstrap_empty_gpkg` — create a fresh GeoPackage with empty layers
  in the canonical order.
- :func:`build_and_write_all_layers` — rebuild every visualization layer from
  activity records and write them to disk, returning the built layers for
  result summarization.

It depends on :mod:`gpkg_io` (disk writes), :mod:`gpkg_layer_builders`
(layer construction), and :mod:`atlas.publish_atlas` (plan computation)
but contains no schema definitions or repository logic.
"""

import sqlite3

from .gpkg_io import write_layer_to_gpkg
from .gpkg_atlas_page_builder import build_atlas_layer
from .gpkg_layer_builders import (
    build_start_layer,
    build_track_layer,
)
from .gpkg_point_layer_builder import build_point_layer
from .gpkg_atlas_table_builders import (
    build_cover_highlight_layer,
    build_document_summary_layer,
    build_page_detail_item_layer,
    build_profile_sample_layer,
    build_toc_layer,
)
from ....atlas.publish_atlas import build_atlas_page_plans


DERIVED_LAYER_ATTRIBUTE_INDEXES = {
    "activity_tracks": (
        "CREATE INDEX IF NOT EXISTS idx_activity_tracks_source_activity_id ON activity_tracks(source, source_activity_id)",
        "CREATE INDEX IF NOT EXISTS idx_activity_tracks_activity_type ON activity_tracks(activity_type)",
        "CREATE INDEX IF NOT EXISTS idx_activity_tracks_start_date ON activity_tracks(start_date)",
        "CREATE INDEX IF NOT EXISTS idx_activity_tracks_sport_type ON activity_tracks(sport_type)",
    ),
    "activity_starts": (
        "CREATE INDEX IF NOT EXISTS idx_activity_starts_source_activity_id ON activity_starts(source, source_activity_id)",
        "CREATE INDEX IF NOT EXISTS idx_activity_starts_activity_type ON activity_starts(activity_type)",
        "CREATE INDEX IF NOT EXISTS idx_activity_starts_start_date ON activity_starts(start_date)",
    ),
    "activity_points": (
        "CREATE INDEX IF NOT EXISTS idx_activity_points_source_activity_id ON activity_points(source, source_activity_id)",
        "CREATE INDEX IF NOT EXISTS idx_activity_points_activity_type ON activity_points(activity_type)",
        "CREATE INDEX IF NOT EXISTS idx_activity_points_start_date ON activity_points(start_date)",
        "CREATE INDEX IF NOT EXISTS idx_activity_points_point_timestamp_local ON activity_points(point_timestamp_local)",
        "CREATE INDEX IF NOT EXISTS idx_activity_points_point_timestamp_utc ON activity_points(point_timestamp_utc)",
    ),
    "activity_atlas_pages": (
        "CREATE INDEX IF NOT EXISTS idx_activity_atlas_pages_page_number ON activity_atlas_pages(page_number)",
        "CREATE INDEX IF NOT EXISTS idx_activity_atlas_pages_page_sort_key ON activity_atlas_pages(page_sort_key)",
        "CREATE INDEX IF NOT EXISTS idx_activity_atlas_pages_source_activity_id ON activity_atlas_pages(source, source_activity_id)",
    ),
}


def ensure_attribute_indexes(output_path):
    """Create derived-layer attribute indexes inside *output_path* if missing."""
    with sqlite3.connect(output_path) as connection:
        cursor = connection.cursor()
        for statements in DERIVED_LAYER_ATTRIBUTE_INDEXES.values():
            for statement in statements:
                cursor.execute(statement)
        connection.commit()


def _import_qgis_spatial_index_api():
    try:
        from qgis.core import QgsFeatureSource, QgsVectorDataProvider, QgsVectorLayer
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("QGIS Python bindings are required to create GeoPackage spatial indexes") from exc

    return QgsFeatureSource, QgsVectorDataProvider, QgsVectorLayer


def ensure_spatial_indexes(output_path):
    """Create derived-layer spatial indexes inside *output_path* if missing."""
    qgs_feature_source, qgs_vector_data_provider, qgs_vector_layer = _import_qgis_spatial_index_api()

    for layer_name in DERIVED_LAYER_ATTRIBUTE_INDEXES:
        layer = qgs_vector_layer(f"{output_path}|layername={layer_name}", layer_name, "ogr")
        if not layer.isValid():
            raise RuntimeError(f"Failed to load GeoPackage layer {layer_name!r} from {output_path}")

        provider = layer.dataProvider()
        if not provider.capabilities() & qgs_vector_data_provider.CreateSpatialIndex:
            raise RuntimeError(f"Layer {layer_name!r} does not support spatial index creation")

        if provider.hasSpatialIndex() == qgs_feature_source.SpatialIndexPresent:
            continue

        if not provider.createSpatialIndex():
            raise RuntimeError(f"Failed to create spatial index for layer {layer_name!r}")


def bootstrap_empty_gpkg(output_path, atlas_page_settings):
    """Create a new GeoPackage with empty layers in the canonical order.

    The first layer (``activity_tracks``) overwrites any existing file;
    subsequent layers are appended.
    """
    write_layer_to_gpkg(build_track_layer([]), output_path, "activity_tracks", overwrite_file=True)
    write_layer_to_gpkg(build_start_layer([]), output_path, "activity_starts", overwrite_file=False)
    write_layer_to_gpkg(build_point_layer([]), output_path, "activity_points", overwrite_file=False)
    write_layer_to_gpkg(
        build_atlas_layer([], atlas_page_settings),
        output_path, "activity_atlas_pages", overwrite_file=False,
    )
    write_layer_to_gpkg(build_document_summary_layer(), output_path, "atlas_document_summary", overwrite_file=False)
    write_layer_to_gpkg(build_cover_highlight_layer(), output_path, "atlas_cover_highlights", overwrite_file=False)
    write_layer_to_gpkg(build_page_detail_item_layer([]), output_path, "atlas_page_detail_items", overwrite_file=False)
    write_layer_to_gpkg(build_profile_sample_layer([]), output_path, "atlas_profile_samples", overwrite_file=False)
    write_layer_to_gpkg(build_toc_layer([]), output_path, "atlas_toc_entries", overwrite_file=False)


def build_and_write_all_layers(
    records, output_path, atlas_page_settings,
    write_activity_points=True, point_stride=5,
):
    """Build all visualization layers from *records* and write them to *output_path*.

    Returns an ``OrderedDict``-style dict mapping layer names to the built
    ``QgsVectorLayer`` objects so callers can inspect feature counts without
    re-reading the file.
    """
    plans = build_atlas_page_plans(records, settings=atlas_page_settings)

    layers = {
        "activity_tracks": build_track_layer(records),
        "activity_starts": build_start_layer(records),
        "activity_points": build_point_layer(records, write_activity_points, point_stride),
        "activity_atlas_pages": build_atlas_layer(records, atlas_page_settings, plans=plans),
        "atlas_document_summary": build_document_summary_layer(plans=plans),
        "atlas_cover_highlights": build_cover_highlight_layer(plans=plans),
        "atlas_page_detail_items": build_page_detail_item_layer(records, atlas_page_settings, plans=plans),
        "atlas_profile_samples": build_profile_sample_layer(records, atlas_page_settings, plans=plans),
        "atlas_toc_entries": build_toc_layer(records, atlas_page_settings, plans=plans),
    }

    for layer_name, layer in layers.items():
        write_layer_to_gpkg(layer, output_path, layer_name, overwrite_file=False)

    ensure_attribute_indexes(output_path)
    ensure_spatial_indexes(output_path)

    return layers
