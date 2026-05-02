import os
from importlib import import_module

from .activity_storage import GeoPackageActivityStore
from .route_storage import GeoPackageRouteStore
from .gpkg_schema import GPKG_LAYER_SCHEMA

gpkg_write_orchestration = import_module(__package__ + ".gpkg_write_orchestration")
from ....atlas.publish_atlas import normalize_atlas_page_settings


class GeoPackageWriter:
    """Persist qfit sync data to a GeoPackage and rebuild derived visualization layers."""

    def __init__(
        self,
        output_path=None,
        write_activity_points=True,
        point_stride=5,
        atlas_margin_percent=None,
        atlas_min_extent_degrees=None,
        atlas_target_aspect_ratio=None,
        activity_store_factory=GeoPackageActivityStore,
        route_store_factory=GeoPackageRouteStore,
    ):
        self.output_path = output_path
        self.write_activity_points = bool(write_activity_points)
        self.point_stride = max(1, int(point_stride or 1))
        self.atlas_page_settings = normalize_atlas_page_settings(
            margin_percent=atlas_margin_percent,
            min_extent_degrees=atlas_min_extent_degrees,
            target_aspect_ratio=atlas_target_aspect_ratio,
        )
        self.activity_store_factory = activity_store_factory
        self.route_store_factory = route_store_factory

    def schema(self):
        return dict(GPKG_LAYER_SCHEMA)

    def write_routes(self, routes, sync_metadata=None):
        if not self.output_path:
            raise ValueError("output_path is required")
        os.makedirs(os.path.dirname(self.output_path) or ".", exist_ok=True)

        route_store = self.route_store_factory(self.output_path)
        new_file = not os.path.exists(self.output_path) or os.path.getsize(self.output_path) == 0
        if new_file:
            gpkg_write_orchestration.bootstrap_empty_route_gpkg(self.output_path)

        route_store.ensure_schema()
        sync_result = route_store.upsert_routes(routes, sync_metadata=sync_metadata)
        records = route_store.load_all_route_records()
        layers = gpkg_write_orchestration.build_and_write_route_layers(records, self.output_path)

        return {
            "schema": self.schema(),
            "path": self.output_path,
            "fetched_count": len(routes),
            "route_track_count": layers["route_tracks"].featureCount(),
            "route_point_count": layers["route_points"].featureCount(),
            "route_profile_sample_count": layers["route_profile_samples"].featureCount(),
            "sync": sync_result,
        }

    def write_activities(self, activities, sync_metadata=None):
        if not self.output_path:
            raise ValueError("output_path is required")
        os.makedirs(os.path.dirname(self.output_path) or ".", exist_ok=True)

        activity_store = self.activity_store_factory(self.output_path)
        new_file = not os.path.exists(self.output_path) or os.path.getsize(self.output_path) == 0
        if new_file:
            gpkg_write_orchestration.bootstrap_empty_gpkg(self.output_path, self.atlas_page_settings)

        activity_store.ensure_schema()
        sync_result = activity_store.upsert_activities(activities, sync_metadata=sync_metadata)
        records = activity_store.load_all_activity_records()

        layers = gpkg_write_orchestration.build_and_write_all_layers(
            records, self.output_path, self.atlas_page_settings,
            write_activity_points=self.write_activity_points,
            point_stride=self.point_stride,
        )

        return {
            "schema": self.schema(),
            "path": self.output_path,
            "fetched_count": len(activities),
            "track_count": layers["activity_tracks"].featureCount(),
            "start_count": layers["activity_starts"].featureCount(),
            "point_count": layers["activity_points"].featureCount(),
            "atlas_count": layers["activity_atlas_pages"].featureCount(),
            "document_summary_count": layers["atlas_document_summary"].featureCount(),
            "cover_highlight_count": layers["atlas_cover_highlights"].featureCount(),
            "page_detail_item_count": layers["atlas_page_detail_items"].featureCount(),
            "profile_sample_count": layers["atlas_profile_samples"].featureCount(),
            "toc_count": layers["atlas_toc_entries"].featureCount(),
            "sync": sync_result,
        }
