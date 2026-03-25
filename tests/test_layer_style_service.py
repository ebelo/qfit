import os
import tempfile
import unittest
from pathlib import Path

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from qgis.core import (
        QgsApplication,
        QgsCategorizedSymbolRenderer,
        QgsHeatmapRenderer,
        QgsProject,
        QgsSingleSymbolRenderer,
    )

    from qfit.gpkg_writer import GeoPackageWriter
    from qfit.layer_manager import LayerManager
    from qfit.layer_style_service import LayerStyleService

    QGIS_AVAILABLE = True
    QGIS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    QgsApplication = None
    QgsProject = None
    QgsCategorizedSymbolRenderer = None
    QgsHeatmapRenderer = None
    QgsSingleSymbolRenderer = None
    GeoPackageWriter = None
    LayerManager = None
    LayerStyleService = None
    QGIS_AVAILABLE = False
    QGIS_IMPORT_ERROR = exc


class _FakeCanvas:
    def __init__(self):
        self.destination_crs_authid = None
        self.last_extent = None
        self.refresh_count = 0

    def setDestinationCrs(self, crs):
        self.destination_crs_authid = crs.authid()

    def setExtent(self, extent):
        self.last_extent = (
            extent.xMinimum(),
            extent.yMinimum(),
            extent.xMaximum(),
            extent.yMaximum(),
        )

    def extent(self):
        return None

    def refresh(self):
        self.refresh_count += 1


class _FakeIface:
    def __init__(self):
        self._canvas = _FakeCanvas()

    def mapCanvas(self):
        return self._canvas


def _sample_activities():
    return [
        {
            "source": "strava",
            "source_activity_id": "2001",
            "external_id": "strava-2001",
            "name": "Test Ride",
            "activity_type": "Ride",
            "sport_type": "Ride",
            "start_date": "2026-03-20T07:00:00+00:00",
            "start_date_local": "2026-03-20T08:00:00+01:00",
            "timezone": "Europe/Zurich",
            "distance_m": 20000,
            "moving_time_s": 3600,
            "elapsed_time_s": 3700,
            "total_elevation_gain_m": 200,
            "start_lat": 46.52,
            "start_lon": 6.62,
            "end_lat": 46.57,
            "end_lon": 6.74,
            "geometry_source": "stream",
            "geometry_points": [(46.52, 6.62), (46.55, 6.68), (46.57, 6.74)],
            "details_json": {
                "stream_metrics": {
                    "time": [0, 1800, 3600],
                    "distance": [0, 10000, 20000],
                    "altitude": [450, 500, 480],
                    "moving": [True, True, True],
                }
            },
        },
        {
            "source": "strava",
            "source_activity_id": "2002",
            "external_id": "strava-2002",
            "name": "Test Run",
            "activity_type": "Run",
            "sport_type": "Run",
            "start_date": "2026-03-21T09:00:00+00:00",
            "start_date_local": "2026-03-21T10:00:00+01:00",
            "timezone": "Europe/Zurich",
            "distance_m": 8000,
            "moving_time_s": 2400,
            "elapsed_time_s": 2500,
            "total_elevation_gain_m": 60,
            "start_lat": 46.51,
            "start_lon": 6.60,
            "end_lat": 46.525,
            "end_lon": 6.63,
            "geometry_source": "stream",
            "geometry_points": [(46.51, 6.60), (46.52, 6.615), (46.525, 6.63)],
            "details_json": {
                "stream_metrics": {
                    "time": [0, 1200, 2400],
                    "distance": [0, 4000, 8000],
                    "altitude": [430, 445, 452],
                    "moving": [True, True, True],
                }
            },
        },
    ]


@unittest.skipUnless(
    QGIS_AVAILABLE,
    "PyQGIS is not available in this environment: {error}".format(error=QGIS_IMPORT_ERROR),
)
class LayerStyleServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QgsApplication.setPrefixPath("/usr", True)
        cls.qgs = QgsApplication([], False)
        cls.qgs.initQgis()

    @classmethod
    def tearDownClass(cls):
        QgsProject.instance().clear()
        cls.qgs.exitQgis()

    def setUp(self):
        QgsProject.instance().clear()
        self.iface = _FakeIface()
        self.layer_manager = LayerManager(self.iface)
        self.style_service = LayerStyleService()

    def tearDown(self):
        QgsProject.instance().clear()

    def _write_and_load(self, temp_dir, write_points=True):
        output_path = str(Path(temp_dir) / "style-test.gpkg")
        GeoPackageWriter(
            output_path,
            write_activity_points=write_points,
            point_stride=1,
            atlas_margin_percent=10,
            atlas_min_extent_degrees=0.01,
            atlas_target_aspect_ratio=1.5,
        ).write_activities(_sample_activities(), sync_metadata={"provider": "strava"})
        return self.layer_manager.load_output_layers(output_path)

    def test_style_service_is_distinct_from_layer_manager(self):
        """LayerStyleService must be a standalone class, not nested inside LayerManager."""
        self.assertIsInstance(self.style_service, LayerStyleService)
        self.assertIsNot(self.style_service, self.layer_manager)

    def test_simple_lines_applies_single_symbol_renderer(self):
        with tempfile.TemporaryDirectory() as tmp:
            activities_layer, starts_layer, points_layer, atlas_layer = self._write_and_load(tmp)
            self.style_service.apply_style(
                activities_layer, starts_layer, points_layer, atlas_layer, "Simple lines"
            )
            self.assertIsInstance(activities_layer.renderer(), QgsSingleSymbolRenderer)
            self.assertGreater(activities_layer.opacity(), 0.0)

    def test_by_activity_type_applies_categorized_renderer(self):
        with tempfile.TemporaryDirectory() as tmp:
            activities_layer, starts_layer, points_layer, atlas_layer = self._write_and_load(tmp)
            self.style_service.apply_style(
                activities_layer, starts_layer, points_layer, atlas_layer, "By activity type"
            )
            renderer = activities_layer.renderer()
            self.assertIsInstance(renderer, QgsCategorizedSymbolRenderer)
            categories = {cat.value() for cat in renderer.categories()}
            self.assertEqual(categories, {"Ride", "Run"})

    def test_heatmap_applies_heatmap_renderer_and_hides_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            activities_layer, starts_layer, points_layer, atlas_layer = self._write_and_load(tmp)
            self.style_service.apply_style(
                activities_layer, starts_layer, points_layer, atlas_layer, "Heatmap"
            )
            self.assertIsInstance(points_layer.renderer(), QgsHeatmapRenderer)
            self.assertEqual(round(activities_layer.opacity(), 2), 0.0)
            self.assertEqual(round(starts_layer.opacity(), 2), 0.0)

    def test_heatmap_falls_back_to_starts_when_no_points_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            activities_layer, starts_layer, _points_layer, atlas_layer = self._write_and_load(tmp)
            self.style_service.apply_style(
                activities_layer, starts_layer, None, atlas_layer, "Heatmap"
            )
            self.assertIsInstance(starts_layer.renderer(), QgsHeatmapRenderer)
            self.assertEqual(round(activities_layer.opacity(), 2), 0.0)

    def test_start_points_preset_makes_starts_prominent(self):
        with tempfile.TemporaryDirectory() as tmp:
            activities_layer, starts_layer, points_layer, atlas_layer = self._write_and_load(tmp)
            self.style_service.apply_style(
                activities_layer, starts_layer, points_layer, atlas_layer, "Start points"
            )
            self.assertIsInstance(starts_layer.renderer(), QgsSingleSymbolRenderer)
            self.assertGreaterEqual(starts_layer.opacity(), 0.8)

    def test_apply_style_via_layer_manager_delegates_to_service(self):
        """LayerManager.apply_style must produce the same result as calling LayerStyleService directly."""
        with tempfile.TemporaryDirectory() as tmp:
            activities_layer, starts_layer, points_layer, atlas_layer = self._write_and_load(tmp)
            self.layer_manager.apply_style(
                activities_layer, starts_layer, points_layer, atlas_layer, "By activity type"
            )
            self.assertIsInstance(activities_layer.renderer(), QgsCategorizedSymbolRenderer)

    def test_none_layers_are_skipped_gracefully(self):
        """apply_style must not raise when optional layers are None."""
        with tempfile.TemporaryDirectory() as tmp:
            activities_layer, _starts, _points, _atlas = self._write_and_load(tmp)
            # Should not raise
            self.style_service.apply_style(activities_layer, None, None, None, "Simple lines")
            self.assertIsInstance(activities_layer.renderer(), QgsSingleSymbolRenderer)

    def test_none_preset_defaults_to_simple_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            activities_layer, starts_layer, points_layer, atlas_layer = self._write_and_load(tmp)
            self.style_service.apply_style(
                activities_layer, starts_layer, points_layer, atlas_layer, None
            )
            self.assertIsInstance(activities_layer.renderer(), QgsSingleSymbolRenderer)


if __name__ == "__main__":
    unittest.main()
