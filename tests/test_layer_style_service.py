import importlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Detect real QGIS without relying on sys.modules — test_atlas_export_task.py
# unconditionally replaces qgis.core in sys.modules with a stub, so find_spec
# may raise ValueError.  Fall back to a plain filesystem search.
try:
    _REAL_QGIS_PRESENT = importlib.util.find_spec("qgis") is not None
except ValueError:
    _REAL_QGIS_PRESENT = any(
        os.path.isdir(os.path.join(p, "qgis")) for p in sys.path if p
    )

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


def _load_service_with_mock_qgis():
    """Import LayerStyleService backed by MagicMock QGIS stubs.

    Temporarily replaces every qgis.* entry in sys.modules with a MagicMock
    (regardless of whether real QGIS or a prior stub was there), imports the
    module fresh so all QGIS class references become callable MagicMocks, then
    restores the original sys.modules state before returning.

    This lets the unit-test class below exercise every branch in
    layer_style_service.py without a running QGIS session.
    """
    qstub = MagicMock()
    _QGIS_MODS = ["qgis", "qgis.core", "qgis.PyQt", "qgis.PyQt.QtCore", "qgis.PyQt.QtGui"]

    saved_qgis = {m: sys.modules.get(m) for m in _QGIS_MODS}
    saved_lss = sys.modules.get("qfit.layer_style_service")

    for mod_name in _QGIS_MODS:
        sys.modules[mod_name] = qstub
    sys.modules.pop("qfit.layer_style_service", None)

    try:
        lss = importlib.import_module("qfit.layer_style_service")
        return lss.LayerStyleService
    except Exception:  # pragma: no cover
        return None
    finally:
        for mod_name, original in saved_qgis.items():
            if original is None:
                sys.modules.pop(mod_name, None)
            else:
                sys.modules[mod_name] = original
        if saved_lss is None:
            sys.modules.pop("qfit.layer_style_service", None)
        else:
            sys.modules["qfit.layer_style_service"] = saved_lss


# Build a mock-backed service class when a usable QGIS is absent.
# Use QGIS_AVAILABLE (successful import) rather than _REAL_QGIS_PRESENT
# (package discoverable) so that an incomplete install (package found but
# native libs broken) still triggers the mock suite rather than leaving the
# module uncovered.
_MockedLayerStyleService = (
    None if QGIS_AVAILABLE else _load_service_with_mock_qgis()
)


@unittest.skipIf(
    QGIS_AVAILABLE,
    "QGIS is installed — LayerStyleServiceTests already provides coverage",
)
@unittest.skipIf(
    _MockedLayerStyleService is None,
    "Could not load LayerStyleService with mock QGIS stubs",
)
class LayerStyleServiceUnitTests(unittest.TestCase):
    """Non-QGIS unit tests for LayerStyleService.

    Run in CI environments that lack a QGIS installation (e.g. SonarCloud).
    Every QGIS class is a MagicMock, so all branches in the service execute
    without error and coverage.py can attribute lines to layer_style_service.py.
    """

    def setUp(self):
        self.service = _MockedLayerStyleService()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_layer(self, activity_types=None):
        """Return a mock QGIS vector layer for style tests."""
        field = MagicMock()
        field.name.return_value = "activity_type"

        fields = MagicMock()
        fields.__iter__ = MagicMock(side_effect=lambda: iter([field]))
        fields.indexOf.return_value = 0

        layer = MagicMock()
        layer.fields.return_value = fields
        layer.uniqueValues.return_value = (
            activity_types if activity_types is not None else ["Ride", "Run"]
        )
        return layer

    # ------------------------------------------------------------------
    # apply_style — one test per preset branch
    # ------------------------------------------------------------------

    def test_simple_lines_sets_renderer_and_triggers_repaint(self):
        acts = self._make_layer()
        starts = self._make_layer()
        points = self._make_layer()
        self.service.apply_style(acts, starts, points, None, "Simple lines")
        acts.setRenderer.assert_called_once()
        acts.triggerRepaint.assert_called()

    def test_by_activity_type_sets_renderer_on_tracks(self):
        acts = self._make_layer()
        self.service.apply_style(acts, None, None, None, "By activity type")
        acts.setRenderer.assert_called_once()

    def test_heatmap_hides_tracks_and_starts(self):
        acts = self._make_layer()
        starts = self._make_layer()
        points = self._make_layer()
        self.service.apply_style(acts, starts, points, None, "Heatmap")
        acts.setOpacity.assert_called_with(0.0)
        starts.setOpacity.assert_called_with(0.0)

    def test_heatmap_uses_starts_when_no_points_layer(self):
        acts = self._make_layer()
        starts = self._make_layer()
        self.service.apply_style(acts, starts, None, None, "Heatmap")
        acts.setOpacity.assert_called_with(0.0)
        starts.setRenderer.assert_called_once()

    def test_track_points_sets_renderer_on_tracks_and_points(self):
        acts = self._make_layer()
        starts = self._make_layer()
        points = self._make_layer()
        self.service.apply_style(acts, starts, points, None, "Track points")
        acts.setRenderer.assert_called_once()
        points.setRenderer.assert_called_once()

    def test_clustered_starts_sets_renderer_on_starts(self):
        starts = self._make_layer()
        self.service.apply_style(None, starts, None, None, "Clustered starts")
        starts.setRenderer.assert_called_once()

    def test_start_points_makes_starts_prominent(self):
        starts = self._make_layer()
        self.service.apply_style(None, starts, None, None, "Start points")
        starts.setRenderer.assert_called_once()

    def test_atlas_layer_is_styled(self):
        atlas = self._make_layer()
        self.service.apply_style(None, None, None, atlas, "Simple lines")
        atlas.setRenderer.assert_called_once()

    def test_none_preset_defaults_to_simple_lines(self):
        acts = self._make_layer()
        self.service.apply_style(acts, None, None, None, None)
        acts.setRenderer.assert_called_once()

    def test_all_none_layers_no_error(self):
        self.service.apply_style(None, None, None, None, "Simple lines")

    def test_by_activity_type_unknown_field_falls_back_to_simple(self):
        unknown = MagicMock()
        unknown.name.return_value = "unknown_col"
        fields = MagicMock()
        fields.__iter__ = MagicMock(side_effect=lambda: iter([unknown]))
        fields.indexOf.return_value = 0
        acts = self._make_layer()
        acts.fields.return_value = fields
        self.service.apply_style(acts, None, None, None, "By activity type")
        acts.setRenderer.assert_called_once()

    def test_explicit_background_preset_name_forwarded(self):
        acts = self._make_layer()
        self.service.apply_style(
            acts, None, None, None, "Simple lines", background_preset_name="Outdoor"
        )
        acts.setRenderer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
