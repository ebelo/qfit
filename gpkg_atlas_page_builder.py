"""
GeoPackage atlas page-layer builder for qfit.

This module provides the standalone ``build_atlas_layer`` function that turns
atlas page plans into the ``activity_atlas_pages`` polygon layer used by the
QGIS atlas template. It contains no I/O — callers are responsible for writing
the returned layer to disk.

Track and start geometry builders live in :mod:`gpkg_layer_builders`.
"""

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsRectangle,
    QgsVectorLayer,
)

from .gpkg_schema import (
    ATLAS_FIELDS,
    make_qgs_fields,
)
from .atlas.publish_atlas import build_atlas_page_plans


def build_atlas_layer(records, atlas_page_settings, plans=None):
    """Build and return a memory ``QgsVectorLayer`` of atlas page extents.

    Layer CRS is EPSG:3857 (Web Mercator) so that the QGIS atlas map frame
    uses extents as-is without reprojection distortion.
    """
    layer = QgsVectorLayer("Polygon?crs=EPSG:3857", "activity_atlas_pages", "memory")
    provider = layer.dataProvider()
    provider.addAttributes(make_qgs_fields(ATLAS_FIELDS))
    layer.updateFields()

    features = []
    resolved_plans = plans if plans is not None else build_atlas_page_plans(records, settings=atlas_page_settings)
    for plan in resolved_plans:
        half_w = plan.extent_width_m / 2.0
        half_h = plan.extent_height_m / 2.0
        rect = QgsRectangle(
            plan.center_x_3857 - half_w,
            plan.center_y_3857 - half_h,
            plan.center_x_3857 + half_w,
            plan.center_y_3857 + half_h,
        )
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromRect(rect))
        feature["activity_fk"] = plan.page_number
        feature["source"] = plan.source
        feature["source_activity_id"] = plan.source_activity_id
        feature["name"] = plan.name
        feature["activity_type"] = plan.activity_type
        feature["sport_type"] = plan.sport_type
        feature["start_date"] = plan.start_date
        feature["distance_m"] = plan.distance_m
        feature["moving_time_s"] = plan.moving_time_s
        feature["total_elevation_gain_m"] = plan.total_elevation_gain_m
        feature["geometry_source"] = plan.geometry_source
        feature["page_number"] = plan.page_number
        feature["page_sort_key"] = plan.page_sort_key
        feature["page_name"] = plan.page_name
        feature["page_title"] = plan.page_title
        feature["page_subtitle"] = plan.page_subtitle
        feature["page_date"] = plan.page_date
        feature["page_toc_label"] = plan.page_toc_label
        feature["page_distance_label"] = plan.page_distance_label
        feature["page_duration_label"] = plan.page_duration_label
        feature["page_average_speed_label"] = plan.page_average_speed_label
        feature["page_average_pace_label"] = plan.page_average_pace_label
        feature["page_elevation_gain_label"] = plan.page_elevation_gain_label
        feature["page_stats_summary"] = plan.page_stats_summary
        feature["page_profile_summary"] = plan.page_profile_summary
        feature["document_activity_count"] = plan.document_activity_count
        feature["document_date_range_label"] = plan.document_date_range_label
        feature["document_total_distance_label"] = plan.document_total_distance_label
        feature["document_total_duration_label"] = plan.document_total_duration_label
        feature["document_total_elevation_gain_label"] = plan.document_total_elevation_gain_label
        feature["document_activity_types_label"] = plan.document_activity_types_label
        feature["document_cover_summary"] = plan.document_cover_summary
        feature["profile_available"] = int(plan.profile_available)
        feature["profile_point_count"] = plan.profile_point_count
        feature["profile_distance_m"] = plan.profile_distance_m
        feature["profile_distance_label"] = plan.profile_distance_label
        feature["profile_min_altitude_m"] = plan.profile_min_altitude_m
        feature["profile_max_altitude_m"] = plan.profile_max_altitude_m
        feature["profile_altitude_range_label"] = plan.profile_altitude_range_label
        feature["profile_relief_m"] = plan.profile_relief_m
        feature["profile_elevation_gain_m"] = plan.profile_elevation_gain_m
        feature["profile_elevation_gain_label"] = plan.profile_elevation_gain_label
        feature["profile_elevation_loss_m"] = plan.profile_elevation_loss_m
        feature["profile_elevation_loss_label"] = plan.profile_elevation_loss_label
        feature["center_x_3857"] = plan.center_x_3857
        feature["center_y_3857"] = plan.center_y_3857
        feature["extent_width_deg"] = plan.extent_width_deg
        feature["extent_height_deg"] = plan.extent_height_deg
        feature["extent_width_m"] = plan.extent_width_m
        feature["extent_height_m"] = plan.extent_height_m
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer
