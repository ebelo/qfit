"""
GeoPackage atlas helper-table builders for qfit.

This module provides standalone functions that build geometry-less
``QgsVectorLayer`` objects (type ``"None"``) used as helper/lookup tables
by the QGIS atlas template.  It contains no I/O — callers are responsible
for writing the returned layers to disk.

The geometry builders for tracks, starts, points, and atlas pages live in
:mod:`gpkg_layer_builders`.
"""

from qgis.core import (
    QgsFeature,
    QgsVectorLayer,
)

from .gpkg_schema import (
    COVER_HIGHLIGHT_FIELDS,
    DOCUMENT_SUMMARY_FIELDS,
    PAGE_DETAIL_ITEM_FIELDS,
    PROFILE_SAMPLE_FIELDS,
    TOC_FIELDS,
    make_qgs_fields,
)
from ....atlas.publish_atlas import (
    build_atlas_cover_highlights_from_summary,
    build_atlas_document_summary_from_plans,
    build_atlas_page_detail_items,
    build_atlas_page_plans,
    build_atlas_profile_samples,
    build_atlas_toc_entries,
)


def build_document_summary_layer(records=None, atlas_page_settings=None, plans=None):
    """Build and return a memory ``QgsVectorLayer`` with one document-summary row."""
    layer = QgsVectorLayer("None", "atlas_document_summary", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(DOCUMENT_SUMMARY_FIELDS))
    layer.updateFields()

    resolved_plans = plans if plans is not None else build_atlas_page_plans(
        records or [], settings=atlas_page_settings,
    )
    summary = build_atlas_document_summary_from_plans(resolved_plans)
    if summary.activity_count > 0:
        feature = QgsFeature(layer.fields())
        feature["activity_count"] = summary.activity_count
        feature["activity_date_start"] = summary.activity_date_start
        feature["activity_date_end"] = summary.activity_date_end
        feature["date_range_label"] = summary.date_range_label
        feature["total_distance_m"] = summary.total_distance_m
        feature["total_distance_label"] = summary.total_distance_label
        feature["total_moving_time_s"] = summary.total_moving_time_s
        feature["total_duration_label"] = summary.total_duration_label
        feature["total_elevation_gain_m"] = summary.total_elevation_gain_m
        feature["total_elevation_gain_label"] = summary.total_elevation_gain_label
        feature["activity_types_label"] = summary.activity_types_label
        feature["cover_summary"] = summary.cover_summary
        provider.addFeature(feature)

    layer.updateExtents()
    return layer


def build_cover_highlight_layer(records=None, atlas_page_settings=None, plans=None):
    """Build and return a memory ``QgsVectorLayer`` of cover highlight entries."""
    layer = QgsVectorLayer("None", "atlas_cover_highlights", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(COVER_HIGHLIGHT_FIELDS))
    layer.updateFields()

    resolved_plans = plans if plans is not None else build_atlas_page_plans(
        records or [], settings=atlas_page_settings,
    )
    summary = build_atlas_document_summary_from_plans(resolved_plans)

    features = []
    for highlight in build_atlas_cover_highlights_from_summary(summary):
        feature = QgsFeature(layer.fields())
        feature["highlight_order"] = highlight.highlight_order
        feature["highlight_key"] = highlight.highlight_key
        feature["highlight_label"] = highlight.highlight_label
        feature["highlight_value"] = highlight.highlight_value
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def build_page_detail_item_layer(records, atlas_page_settings=None, plans=None):
    """Build and return a memory ``QgsVectorLayer`` of per-page detail items."""
    layer = QgsVectorLayer("None", "atlas_page_detail_items", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(PAGE_DETAIL_ITEM_FIELDS))
    layer.updateFields()

    features = []
    for item in build_atlas_page_detail_items(records, settings=atlas_page_settings, plans=plans):
        feature = QgsFeature(layer.fields())
        feature["page_number"] = item.page_number
        feature["page_sort_key"] = item.page_sort_key
        feature["page_name"] = item.page_name
        feature["page_title"] = item.page_title
        feature["detail_order"] = item.detail_order
        feature["detail_key"] = item.detail_key
        feature["detail_label"] = item.detail_label
        feature["detail_value"] = item.detail_value
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def build_profile_sample_layer(records, atlas_page_settings=None, plans=None):
    """Build and return a memory ``QgsVectorLayer`` of elevation profile samples."""
    layer = QgsVectorLayer("None", "atlas_profile_samples", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(PROFILE_SAMPLE_FIELDS))
    layer.updateFields()

    features = []
    for sample in build_atlas_profile_samples(records, settings=atlas_page_settings, plans=plans):
        feature = QgsFeature(layer.fields())
        feature["page_number"] = sample.page_number
        feature["page_sort_key"] = sample.page_sort_key
        feature["page_name"] = sample.page_name
        feature["page_title"] = sample.page_title
        feature["page_date"] = sample.page_date
        feature["source"] = sample.source
        feature["source_activity_id"] = sample.source_activity_id
        feature["activity_type"] = sample.activity_type
        feature["profile_point_index"] = sample.profile_point_index
        feature["profile_point_count"] = sample.profile_point_count
        feature["profile_point_ratio"] = sample.profile_point_ratio
        feature["distance_m"] = sample.distance_m
        feature["distance_label"] = sample.distance_label
        feature["altitude_m"] = sample.altitude_m
        feature["profile_distance_m"] = sample.profile_distance_m
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def build_toc_layer(records, atlas_page_settings=None, plans=None):
    """Build and return a memory ``QgsVectorLayer`` of table-of-contents entries."""
    layer = QgsVectorLayer("None", "atlas_toc_entries", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(TOC_FIELDS))
    layer.updateFields()

    features = []
    for entry in build_atlas_toc_entries(records, settings=atlas_page_settings, plans=plans):
        feature = QgsFeature(layer.fields())
        feature["page_number"] = entry.page_number
        feature["page_number_label"] = entry.page_number_label
        feature["page_sort_key"] = entry.page_sort_key
        feature["page_name"] = entry.page_name
        feature["page_title"] = entry.page_title
        feature["page_subtitle"] = entry.page_subtitle
        feature["page_date"] = entry.page_date
        feature["page_toc_label"] = entry.page_toc_label
        feature["toc_entry_label"] = entry.toc_entry_label
        feature["page_distance_label"] = entry.page_distance_label
        feature["page_duration_label"] = entry.page_duration_label
        feature["page_stats_summary"] = entry.page_stats_summary
        feature["profile_available"] = int(entry.profile_available)
        feature["page_profile_summary"] = entry.page_profile_summary
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer
