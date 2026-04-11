import os
import sqlite3
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401

try:
    from qgis.core import QgsApplication, QgsVectorLayer
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None
    QgsVectorLayer = None

if QgsApplication is not None:
    from qfit.activities.infrastructure.geopackage.gpkg_write_orchestration import (
        bootstrap_empty_gpkg,
        build_and_write_all_layers,
        ensure_spatial_indexes,
    )
    from qfit.gpkg_write_orchestration import (
        bootstrap_empty_gpkg as legacy_bootstrap_empty_gpkg,
        build_and_write_all_layers as legacy_build_and_write_all_layers,
        ensure_spatial_indexes as legacy_ensure_spatial_indexes,
    )
    from qfit.atlas.publish_atlas import normalize_atlas_page_settings
else:  # pragma: no cover
    bootstrap_empty_gpkg = None
    build_and_write_all_layers = None
    ensure_spatial_indexes = None
    normalize_atlas_page_settings = None


_QGIS_APP = None


def _ensure_qgis_app():
    global _QGIS_APP
    if _QGIS_APP is None:
        _QGIS_APP = QgsApplication([], False)
        _QGIS_APP.initQgis()
    return _QGIS_APP


_EXPECTED_LAYERS = [
    "activity_tracks",
    "activity_starts",
    "activity_points",
    "activity_atlas_pages",
    "atlas_document_summary",
    "atlas_cover_highlights",
    "atlas_page_detail_items",
    "atlas_profile_samples",
    "atlas_toc_entries",
]


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class BootstrapEmptyGpkgTests(unittest.TestCase):
    def test_legacy_gpkg_write_orchestration_shim_exports_same_functions(self):
        self.assertIs(legacy_bootstrap_empty_gpkg, bootstrap_empty_gpkg)
        self.assertIs(legacy_build_and_write_all_layers, build_and_write_all_layers)
        self.assertIs(legacy_ensure_spatial_indexes, ensure_spatial_indexes)

    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()
        cls.settings = normalize_atlas_page_settings()

    def _temp_gpkg(self):
        fd, path = tempfile.mkstemp(suffix=".gpkg")
        os.close(fd)
        os.unlink(path)
        return path

    def test_creates_all_expected_layers(self):
        path = self._temp_gpkg()
        try:
            bootstrap_empty_gpkg(path, self.settings)
            self.assertTrue(os.path.exists(path))
            for layer_name in _EXPECTED_LAYERS:
                lyr = QgsVectorLayer(f"{path}|layername={layer_name}", layer_name, "ogr")
                self.assertTrue(lyr.isValid(), f"layer {layer_name!r} should be valid")
                self.assertEqual(lyr.featureCount(), 0, f"layer {layer_name!r} should be empty")
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_bootstrap_is_idempotent_on_fresh_file(self):
        """Calling bootstrap twice should not raise (second call overwrites)."""
        path = self._temp_gpkg()
        try:
            bootstrap_empty_gpkg(path, self.settings)
            bootstrap_empty_gpkg(path, self.settings)
            self.assertTrue(os.path.exists(path))
        finally:
            if os.path.exists(path):
                os.unlink(path)


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class BuildAndWriteAllLayersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()
        cls.settings = normalize_atlas_page_settings()
        cls.records = [
            {
                "source": "strava",
                "source_activity_id": "100",
                "name": "Morning Ride",
                "activity_type": "Ride",
                "start_date_local": "2026-03-18T08:10:00+01:00",
                "distance_m": 42500,
                "moving_time_s": 7200,
                "total_elevation_gain_m": 640,
                "start_lat": 46.52,
                "start_lon": 6.62,
                "geometry_points": [(46.52, 6.62), (46.57, 6.74)],
            },
        ]

    def _temp_gpkg(self):
        fd, path = tempfile.mkstemp(suffix=".gpkg")
        os.close(fd)
        os.unlink(path)
        return path

    def test_returns_all_expected_layers(self):
        path = self._temp_gpkg()
        try:
            bootstrap_empty_gpkg(path, self.settings)
            layers = build_and_write_all_layers(
                self.records, path, self.settings,
            )
            self.assertEqual(sorted(layers.keys()), sorted(_EXPECTED_LAYERS))
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_written_layers_match_returned_counts(self):
        path = self._temp_gpkg()
        try:
            bootstrap_empty_gpkg(path, self.settings)
            layers = build_and_write_all_layers(
                self.records, path, self.settings,
            )
            for layer_name, mem_layer in layers.items():
                disk_layer = QgsVectorLayer(f"{path}|layername={layer_name}", layer_name, "ogr")
                self.assertTrue(disk_layer.isValid(), f"{layer_name!r} should be valid on disk")
                self.assertEqual(
                    disk_layer.featureCount(),
                    mem_layer.featureCount(),
                    f"{layer_name!r} disk count should match memory count",
                )
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_build_and_write_all_layers_creates_attribute_indexes_for_derived_layers(self):
        path = self._temp_gpkg()
        try:
            bootstrap_empty_gpkg(path, self.settings)
            build_and_write_all_layers(self.records, path, self.settings)

            with sqlite3.connect(path) as connection:
                expected_indexes = {
                    "activity_tracks": {
                        "idx_activity_tracks_source_activity_id",
                        "idx_activity_tracks_activity_type",
                        "idx_activity_tracks_start_date",
                        "idx_activity_tracks_sport_type",
                    },
                    "activity_starts": {
                        "idx_activity_starts_source_activity_id",
                        "idx_activity_starts_activity_type",
                        "idx_activity_starts_start_date",
                    },
                    "activity_points": {
                        "idx_activity_points_source_activity_id",
                        "idx_activity_points_activity_type",
                        "idx_activity_points_start_date",
                        "idx_activity_points_point_timestamp_local",
                        "idx_activity_points_point_timestamp_utc",
                    },
                    "activity_atlas_pages": {
                        "idx_activity_atlas_pages_page_number",
                        "idx_activity_atlas_pages_page_sort_key",
                        "idx_activity_atlas_pages_source_activity_id",
                    },
                }

                for table_name, expected in expected_indexes.items():
                    rows = connection.execute(f"PRAGMA index_list('{table_name}')").fetchall()
                    self.assertTrue(expected.issubset({row[1] for row in rows}), table_name)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_ensure_spatial_indexes_recreates_missing_rtree_metadata(self):
        path = self._temp_gpkg()
        try:
            bootstrap_empty_gpkg(path, self.settings)
            build_and_write_all_layers(self.records, path, self.settings)

            with sqlite3.connect(path) as connection:
                connection.execute(
                    "DELETE FROM gpkg_extensions WHERE table_name='activity_points' AND extension_name='gpkg_rtree_index'"
                )
                for table_name in (
                    "rtree_activity_points_geom",
                    "rtree_activity_points_geom_rowid",
                    "rtree_activity_points_geom_node",
                    "rtree_activity_points_geom_parent",
                ):
                    connection.execute(f"DROP TABLE IF EXISTS {table_name}")
                for trigger_name in (
                    "rtree_activity_points_geom_insert",
                    "rtree_activity_points_geom_update1",
                    "rtree_activity_points_geom_update2",
                    "rtree_activity_points_geom_update3",
                    "rtree_activity_points_geom_update4",
                    "rtree_activity_points_geom_delete",
                ):
                    connection.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
                connection.commit()

            layer = QgsVectorLayer(f"{path}|layername=activity_points", "activity_points", "ogr")
            self.assertTrue(layer.isValid())
            self.assertEqual(layer.dataProvider().hasSpatialIndex(), layer.dataProvider().SpatialIndexNotPresent)

            ensure_spatial_indexes(path)
            ensure_spatial_indexes(path)

            reloaded_layer = QgsVectorLayer(f"{path}|layername=activity_points", "activity_points", "ogr")
            self.assertTrue(reloaded_layer.isValid())
            self.assertEqual(reloaded_layer.dataProvider().hasSpatialIndex(), reloaded_layer.dataProvider().SpatialIndexPresent)

            with sqlite3.connect(path) as connection:
                extension_rows = connection.execute(
                    "SELECT table_name, column_name, extension_name FROM gpkg_extensions WHERE table_name='activity_points'"
                ).fetchall()
                self.assertIn(("activity_points", "geom", "gpkg_rtree_index"), extension_rows)

                rtree_tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'rtree_activity_points_geom%'"
                    ).fetchall()
                }
                self.assertEqual(
                    rtree_tables,
                    {
                        "rtree_activity_points_geom",
                        "rtree_activity_points_geom_rowid",
                        "rtree_activity_points_geom_node",
                        "rtree_activity_points_geom_parent",
                    },
                )
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_track_and_start_counts_match_records(self):
        path = self._temp_gpkg()
        try:
            bootstrap_empty_gpkg(path, self.settings)
            layers = build_and_write_all_layers(
                self.records, path, self.settings,
            )
            self.assertEqual(layers["activity_tracks"].featureCount(), 1)
            self.assertEqual(layers["activity_starts"].featureCount(), 1)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_empty_records_produce_empty_layers(self):
        path = self._temp_gpkg()
        try:
            bootstrap_empty_gpkg(path, self.settings)
            layers = build_and_write_all_layers([], path, self.settings)
            for layer_name, mem_layer in layers.items():
                self.assertEqual(
                    mem_layer.featureCount(), 0,
                    f"{layer_name!r} should be empty for empty records",
                )
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == "__main__":
    unittest.main()
