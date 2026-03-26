import os
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
    from qfit.gpkg_write_orchestration import (
        bootstrap_empty_gpkg,
        build_and_write_all_layers,
    )
    from qfit.atlas.publish_atlas import normalize_atlas_page_settings
else:  # pragma: no cover
    bootstrap_empty_gpkg = None
    build_and_write_all_layers = None
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
