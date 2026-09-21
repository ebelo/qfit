import json
import os
import sqlite3
from importlib import import_module

from .activity_storage import GeoPackageActivityStore
from .route_storage import GeoPackageRouteStore
from .gpkg_schema import GPKG_LAYER_SCHEMA

gpkg_write_orchestration = import_module(__package__ + ".gpkg_write_orchestration")
from ....atlas.publish_atlas import normalize_atlas_page_settings


def _incremental_publication_module():
    return import_module(__package__ + ".gpkg_incremental_publication")


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

    def write_activities(
        self,
        activities,
        sync_metadata=None,
        *,
        progress=None,
        cancelled=None,
    ):
        if cancelled is not None and cancelled():
            raise InterruptedError("activity publication cancelled")
        self._report_progress(progress, "reconcile", 0, 4)
        activity_store = self.prepare_activity_storage()
        sync_result = activity_store.upsert_activities(activities, sync_metadata=sync_metadata)
        if hasattr(activity_store, "with_pending_derived_changes") and hasattr(
            sync_result,
            "changed_keys",
        ):
            sync_result = activity_store.with_pending_derived_changes(sync_result)
        publication_signature = self._publication_signature()
        signature_matches = (
            not hasattr(activity_store, "load_derived_publication_signature")
            or activity_store.load_derived_publication_signature()
            == publication_signature
        )
        self._report_progress(progress, "reconcile", 1, 4)
        if self._can_skip_derived_publication(sync_result, signature_matches):
            self._report_progress(progress, "complete", 4, 4)
            return {
                "schema": self.schema(),
                "path": self.output_path,
                "fetched_count": len(activities),
                **self._existing_activity_layer_counts(),
                "sync": sync_result,
                "publication_mode": "unchanged",
            }
        publication_mode = "incremental"
        fallback_reason = None
        rebuilt_layers = None
        if not signature_matches:
            publication_mode = "full_rebuild"
            fallback_reason = "derived publication settings changed"
            rebuilt_layers = self._rebuild_activity_layers_fallback(
                activity_store,
                getattr(sync_result, "total_count", 0),
                progress=progress,
                cancelled=cancelled,
            )
        elif not hasattr(sync_result, "changed_keys"):
            publication_mode = "full_rebuild"
            fallback_reason = "activity store does not report mutation keys"
            rebuilt_layers = self._rebuild_activity_layers_fallback(
                activity_store,
                getattr(sync_result, "total_count", 0),
                progress=progress,
                cancelled=cancelled,
            )
        else:
            incremental = _incremental_publication_module()
            try:
                changed_records = activity_store.load_activity_records(
                    sync_result.changed_keys
                )
                incremental.publish_incremental_activity_layers(
                    changed_records,
                    self.output_path,
                    self.atlas_page_settings,
                    sync_result,
                    write_activity_points=self.write_activity_points,
                    point_stride=self.point_stride,
                    progress=progress,
                    cancelled=cancelled,
                )
                gpkg_write_orchestration.ensure_attribute_indexes(
                    self.output_path
                )
                self._mark_activity_layers_published(activity_store)
            except incremental.IncrementalPublicationNotEligible as exc:
                publication_mode = "full_rebuild"
                fallback_reason = str(exc)
                rebuilt_layers = self._rebuild_activity_layers_fallback(
                    activity_store,
                    sync_result.total_count,
                    progress=progress,
                    cancelled=cancelled,
                )

        counts = (
            self._activity_layer_counts(rebuilt_layers)
            if rebuilt_layers is not None
            else self._existing_activity_layer_counts()
        )
        self._report_progress(progress, "complete", 4, 4)

        return {
            "schema": self.schema(),
            "path": self.output_path,
            "fetched_count": len(activities),
            **counts,
            "sync": sync_result,
            "publication_mode": publication_mode,
            "publication_fallback_reason": fallback_reason,
        }

    def _rebuild_activity_layers_fallback(
        self,
        activity_store,
        total_count,
        *,
        progress=None,
        cancelled=None,
    ):
        """Use the bounded path when a large registry needs full publication."""

        if int(total_count or 0) >= 200:
            def report(layer_name, completed, total, layer_index, layer_count):
                if cancelled is not None and cancelled():
                    raise InterruptedError("activity publication cancelled")
                if progress is not None:
                    progress(
                        "full_rebuild",
                        layer_index + (completed / max(total, 1)),
                        layer_count,
                    )

            return self.rebuild_activity_layers_bounded(
                activity_store=activity_store,
                progress=report,
            )
        self._report_progress(progress, "full_rebuild", 1, 2)
        return self.rebuild_activity_layers(activity_store=activity_store)

    @staticmethod
    def _report_progress(progress, phase, completed, total):
        if progress is not None:
            progress(phase, completed, total)

    @staticmethod
    def _activity_layer_counts(layers):
        return {
            "track_count": layers["activity_tracks"].featureCount(),
            "start_count": layers["activity_starts"].featureCount(),
            "point_count": layers["activity_points"].featureCount(),
            "atlas_count": layers["activity_atlas_pages"].featureCount(),
            "document_summary_count": layers["atlas_document_summary"].featureCount(),
            "cover_highlight_count": layers["atlas_cover_highlights"].featureCount(),
            "page_detail_item_count": layers["atlas_page_detail_items"].featureCount(),
            "profile_sample_count": layers["atlas_profile_samples"].featureCount(),
            "toc_count": layers["atlas_toc_entries"].featureCount(),
        }

    def _can_skip_derived_publication(self, sync_result, signature_matches=True):
        if not signature_matches:
            return False
        if not hasattr(sync_result, "has_derived_changes"):
            return False
        if sync_result.has_derived_changes:
            return False
        required = {
            "activity_tracks",
            "activity_starts",
            "activity_points",
            "activity_atlas_pages",
            "atlas_document_summary",
            "atlas_cover_highlights",
            "atlas_page_detail_items",
            "atlas_profile_samples",
            "atlas_toc_entries",
        }
        with sqlite3.connect(self.output_path) as connection:
            existing = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        return required.issubset(existing)

    def _publication_signature(self):
        settings = self.atlas_page_settings
        payload = {
            "version": 1,
            "write_activity_points": self.write_activity_points,
            "point_stride": self.point_stride,
            "atlas_margin_percent": getattr(settings, "margin_percent", None),
            "atlas_min_extent_degrees": getattr(
                settings,
                "min_extent_degrees",
                None,
            ),
            "atlas_target_aspect_ratio": getattr(
                settings,
                "target_aspect_ratio",
                None,
            ),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _mark_activity_layers_published(self, store):
        if hasattr(store, "record_derived_publication_signature"):
            store.record_derived_publication_signature(
                self._publication_signature()
            )
        if hasattr(store, "clear_derived_dirty"):
            store.clear_derived_dirty()

    def _existing_activity_layer_counts(self):
        result_keys = {
            "activity_tracks": "track_count",
            "activity_starts": "start_count",
            "activity_points": "point_count",
            "activity_atlas_pages": "atlas_count",
            "atlas_document_summary": "document_summary_count",
            "atlas_cover_highlights": "cover_highlight_count",
            "atlas_page_detail_items": "page_detail_item_count",
            "atlas_profile_samples": "profile_sample_count",
            "atlas_toc_entries": "toc_count",
        }
        with sqlite3.connect(self.output_path) as connection:
            try:
                ogr_counts = {
                    row[0]: int(row[1])
                    for row in connection.execute(
                        "SELECT table_name, feature_count FROM gpkg_ogr_contents "
                        "WHERE feature_count IS NOT NULL"
                    )
                }
            except sqlite3.OperationalError:
                ogr_counts = {}
            counts = {}
            for layer_name, result_key in result_keys.items():
                if layer_name in ogr_counts:
                    counts[result_key] = ogr_counts[layer_name]
                    continue
                quoted_name = layer_name.replace('"', '""')
                counts[result_key] = int(
                    connection.execute(
                        f'SELECT COUNT(*) FROM "{quoted_name}"'
                    ).fetchone()[0]
                )
        return counts

    def prepare_activity_storage(self):
        """Create the GeoPackage and registry schema without rebuilding layers."""

        if not self.output_path:
            raise ValueError("output_path is required")
        os.makedirs(os.path.dirname(self.output_path) or ".", exist_ok=True)
        activity_store = self.activity_store_factory(self.output_path)
        new_file = not os.path.exists(self.output_path) or os.path.getsize(self.output_path) == 0
        if new_file:
            gpkg_write_orchestration.bootstrap_empty_gpkg(
                self.output_path,
                self.atlas_page_settings,
            )
        activity_store.ensure_schema()
        return activity_store

    def upsert_activity_batch(self, activity_store, activities, *, compress_detail_payloads=False):
        """Commit one coherent registry batch without touching visible layers."""

        return activity_store.upsert_activities(
            activities,
            sync_metadata={"provider": "strava", "suppress_sync_state": True},
            compress_detail_payloads=compress_detail_payloads,
            reconcile_existing=True,
        )

    def rebuild_activity_layers(self, *, activity_store=None):
        """Atomically replace derived activity layers from canonical registry rows."""

        store = activity_store or self.prepare_activity_storage()
        records = store.load_all_activity_records()
        layers = gpkg_write_orchestration.build_and_write_all_layers(
            records,
            self.output_path,
            self.atlas_page_settings,
            write_activity_points=self.write_activity_points,
            point_stride=self.point_stride,
        )
        self._mark_activity_layers_published(store)
        return layers

    def rebuild_activity_layers_bounded(
        self,
        *,
        activity_store=None,
        batch_size=25,
        progress=None,
    ):
        """Rebuild detail-heavy layers from repeatable bounded record batches."""

        store = activity_store or self.prepare_activity_storage()
        layers = gpkg_write_orchestration.build_and_write_all_layers_bounded(
            lambda: store.iter_activity_record_batches(batch_size=batch_size),
            self.output_path,
            self.atlas_page_settings,
            write_activity_points=self.write_activity_points,
            point_stride=self.point_stride,
            progress=progress,
        )
        self._mark_activity_layers_published(store)
        return layers
