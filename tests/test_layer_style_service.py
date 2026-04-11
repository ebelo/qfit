import importlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

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
    from qfit.visualization.infrastructure.layer_style_service import LayerStyleService

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
            self.assertIsInstance(starts_layer.renderer(), QgsHeatmapRenderer)
            self.assertAlmostEqual(activities_layer.opacity(), 0.0, places=2)
            self.assertAlmostEqual(points_layer.opacity(), 0.0, places=2)

    def test_heatmap_falls_back_to_starts_when_no_points_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            activities_layer, starts_layer, _points_layer, atlas_layer = self._write_and_load(tmp)
            self.style_service.apply_style(
                activities_layer, starts_layer, None, atlas_layer, "Heatmap"
            )
            self.assertIsInstance(starts_layer.renderer(), QgsHeatmapRenderer)
            self.assertAlmostEqual(activities_layer.opacity(), 0.0, places=2)

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
    saved_lss = sys.modules.get("qfit.visualization.infrastructure.layer_style_service")

    for mod_name in _QGIS_MODS:
        sys.modules[mod_name] = qstub
    sys.modules.pop("qfit.visualization.infrastructure.layer_style_service", None)

    try:
        lss = importlib.import_module("qfit.visualization.infrastructure.layer_style_service")
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
            sys.modules.pop("qfit.visualization.infrastructure.layer_style_service", None)
        else:
            sys.modules["qfit.visualization.infrastructure.layer_style_service"] = saved_lss


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

    def _make_layer(self, activity_types=None, feature_count=2):
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
        layer.featureCount.return_value = feature_count
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

    def test_heatmap_hides_tracks_and_points(self):
        acts = self._make_layer()
        starts = self._make_layer()
        points = self._make_layer()
        self.service.apply_style(acts, starts, points, None, "Heatmap")
        acts.setOpacity.assert_called()
        points.setOpacity.assert_called_with(0.0)

    def test_heatmap_uses_starts_when_no_points_layer(self):
        acts = self._make_layer()
        starts = self._make_layer()
        self.service.apply_style(acts, starts, None, None, "Heatmap")
        acts.setOpacity.assert_called()
        starts.setRenderer.assert_called_once()

    def test_heatmap_uses_starts_when_points_layer_is_empty(self):
        acts = self._make_layer()
        starts = self._make_layer()
        points = self._make_layer(feature_count=0)
        self.service.apply_style(acts, starts, points, None, "Heatmap")
        acts.setOpacity.assert_called()
        starts.setRenderer.assert_called_once()
        starts.setOpacity.assert_called_with(1.0)
        points.setOpacity.assert_called_with(0.0)

    def test_heatmap_falls_back_to_points_when_starts_layer_is_missing(self):
        acts = self._make_layer()
        points = self._make_layer()
        self.service.apply_style(acts, None, points, None, "Heatmap")
        acts.setOpacity.assert_called()
        points.setRenderer.assert_called_once()
        points.setOpacity.assert_called_with(1.0)

    def test_heatmap_falls_back_to_points_when_starts_layer_is_empty(self):
        acts = self._make_layer()
        starts = self._make_layer(feature_count=0)
        points = self._make_layer()
        self.service.apply_style(acts, starts, points, None, "Heatmap")
        acts.setOpacity.assert_called()
        points.setRenderer.assert_called_once()
        points.setOpacity.assert_called_with(1.0)
        starts.setOpacity.assert_called_with(0.0)

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

    def test_private_helpers_cover_track_points_and_clustered_starts_branches(self):
        activities = self._make_layer()
        points = self._make_layer()
        starts = self._make_layer()

        self.service._apply_activities_layer_style(activities, "Track points", None)
        self.service._apply_points_layer_style(points, "Track points", None)
        self.service._apply_starts_layer_style(starts, points, "Clustered starts", None)

        activities.setRenderer.assert_called_once()
        points.setRenderer.assert_called_once()
        starts.setRenderer.assert_called_once()

    def test_private_helpers_fall_back_when_activity_style_field_is_missing(self):
        unknown = MagicMock()
        unknown.name.return_value = "unknown_col"
        fields = MagicMock()
        fields.__iter__ = MagicMock(side_effect=lambda: iter([unknown]))
        fields.indexOf.return_value = 0

        activities = self._make_layer()
        activities.fields.return_value = fields
        points = self._make_layer()
        points.fields.return_value = fields

        self.service._apply_categorized_line_style(activities, None)
        self.service._apply_categorized_point_style(points, None)

        activities.setRenderer.assert_called_once()
        points.setRenderer.assert_called_once()

    def test_build_line_symbol_handles_outline_layers(self):
        line_style = SimpleNamespace(
            outline_color="#123456",
            outline_width=0.5,
            line_width=1.2,
        )

        self.service._build_line_symbol("#abcdef", line_style)

    def test_heatmap_renderer_builders_use_map_units_and_maximum_values(self):
        module_globals = self.service._apply_heatmap_style.__func__.__globals__
        visualize_renderer = MagicMock()
        analysis_renderer = MagicMock()

        with patch.dict(
            module_globals,
            {
                "QgsHeatmapRenderer": MagicMock(side_effect=[visualize_renderer, analysis_renderer]),
            },
            clear=False,
        ):
            module_globals["build_qfit_visualize_heatmap_renderer"](
                radius_map_units=123.0,
                maximum_value=4,
            )
            module_globals["build_qfit_heatmap_renderer"](maximum_value=6)

        visualize_renderer.setRadius.assert_called_once_with(123.0)
        visualize_renderer.setRadiusUnit.assert_called_once_with(
            module_globals["QgsUnitTypes"].RenderMapUnits
        )
        visualize_renderer.setMaximumValue.assert_called_once_with(4.0)
        analysis_renderer.setRadius.assert_called_once_with(
            module_globals["HEATMAP_ANALYSIS_RADIUS_M"]
        )
        analysis_renderer.setRadiusUnit.assert_called_once_with(
            module_globals["QgsUnitTypes"].RenderMapUnits
        )
        analysis_renderer.setMaximumValue.assert_called_once_with(6.0)

    def test_build_metric_start_samples_defaults_invalid_crs_and_skips_empty_geometry(self):
        module_globals = self.service._apply_heatmap_style.__func__.__globals__
        build_samples = module_globals["_build_metric_start_samples"]

        class _Point:
            def __init__(self, x, y):
                self._x = x
                self._y = y

            def x(self):
                return self._x

            def y(self):
                return self._y

        valid_geometry = MagicMock()
        valid_geometry.isEmpty.return_value = False
        valid_geometry.asPoint.return_value = _Point(1.0, 2.0)

        empty_geometry = MagicMock()
        empty_geometry.isEmpty.return_value = True

        valid_feature = MagicMock()
        valid_feature.geometry.return_value = valid_geometry
        valid_feature.fields.return_value.names.return_value = ["source_activity_id"]
        valid_feature.__getitem__.return_value = "42"

        empty_feature = MagicMock()
        empty_feature.geometry.return_value = empty_geometry

        invalid_crs = MagicMock()
        invalid_crs.isValid.return_value = False

        layer = MagicMock()
        layer.crs.return_value = invalid_crs
        layer.getFeatures.return_value = [valid_feature, empty_feature]

        project = MagicMock()
        project.transformContext.return_value = "ctx"
        transform = MagicMock()
        transform.transform.side_effect = lambda point: _Point(point.x() + 10.0, point.y() + 20.0)

        with patch.dict(
            module_globals,
            {
                "QgsCoordinateReferenceSystem": MagicMock(side_effect=lambda authid: f"crs:{authid}"),
                "QgsCoordinateTransform": MagicMock(return_value=transform),
                "QgsPointXY": MagicMock(side_effect=lambda x, y: _Point(x, y)),
                "QgsProject": MagicMock(instance=MagicMock(return_value=project)),
                "HEATMAP_WORKING_CRS": "crs:EPSG:3857",
            },
            clear=False,
        ):
            samples = build_samples(layer)

        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].x, 11.0)
        self.assertEqual(samples[0].y, 22.0)
        self.assertEqual(samples[0].source_activity_id, "42")

    def test_heatmap_settings_return_feature_count_when_no_samples_exist(self):
        module_globals = self.service._apply_heatmap_style.__func__.__globals__
        heatmap_settings = module_globals["_heatmap_settings_from_frequent_starts"]

        layer = MagicMock()
        layer.featureCount.return_value = 3

        with patch.dict(
            module_globals,
            {
                "_build_metric_start_samples": MagicMock(return_value=[]),
            },
            clear=False,
        ):
            radius_map_units, maximum_value = heatmap_settings(layer)

        self.assertEqual(radius_map_units, module_globals["HEATMAP_VISUALIZE_RADIUS_M"])
        self.assertEqual(maximum_value, 3.0)

    def test_heatmap_settings_use_cluster_radius_and_maximum(self):
        module_globals = self.service._apply_heatmap_style.__func__.__globals__
        heatmap_settings = module_globals["_heatmap_settings_from_frequent_starts"]

        layer = MagicMock()
        layer.featureCount.return_value = 2
        clusters = [SimpleNamespace(activity_count=3), SimpleNamespace(activity_count=7)]

        with patch.dict(
            module_globals,
            {
                "_build_metric_start_samples": MagicMock(return_value=[object(), object()]),
                "analyze_frequent_start_points": MagicMock(return_value=(clusters, 120.0)),
            },
            clear=False,
        ):
            radius_map_units, maximum_value = heatmap_settings(layer)

        self.assertEqual(radius_map_units, 120.0)
        self.assertEqual(maximum_value, 7.0)

    def test_heatmap_settings_fall_back_to_feature_count_when_analysis_raises(self):
        module_globals = self.service._apply_heatmap_style.__func__.__globals__
        heatmap_settings = module_globals["_heatmap_settings_from_frequent_starts"]

        layer = MagicMock()
        layer.featureCount.return_value = 5

        with patch.dict(
            module_globals,
            {
                "_build_metric_start_samples": MagicMock(side_effect=RuntimeError("boom")),
            },
            clear=False,
        ):
            radius_map_units, maximum_value = heatmap_settings(layer)

        self.assertEqual(radius_map_units, module_globals["HEATMAP_VISUALIZE_RADIUS_M"])
        self.assertEqual(maximum_value, 5.0)

    def test_infer_background_preset_name_returns_none_for_malformed_name(self):
        layer = MagicMock()
        layer.name.return_value = "qfit background"

        project_instance = MagicMock()
        project_instance.mapLayers.return_value = {"bg": layer}
        self.service._infer_background_preset_name.__func__.__globals__["QgsProject"].instance.return_value = project_instance

        self.assertIsNone(self.service._infer_background_preset_name())


class VisualizationInfrastructureExportTests(unittest.TestCase):
    def test_layer_style_service_alias_is_exported_from_visualization_infrastructure(self):
        if QGIS_AVAILABLE:
            from qfit.visualization.infrastructure import LayerStyleService as exported
            from qfit.visualization.infrastructure.layer_style_service import LayerStyleService

            self.assertIs(exported, LayerStyleService)
            return

        service_cls = _load_service_with_mock_qgis()
        self.assertIsNotNone(service_cls)

    def test_visualization_infrastructure_lazy_exports_cover_supported_names(self):
        package_name = "qfit.visualization.infrastructure"
        module_specs = {
            f"{package_name}.background_map_service": ("BackgroundMapService", type("BackgroundMapService", (), {})),
            f"{package_name}.layer_filter_service": ("LayerFilterService", type("LayerFilterService", (), {})),
            f"{package_name}.map_canvas_service": ("MapCanvasService", type("MapCanvasService", (), {})),
            f"{package_name}.project_hygiene_service": ("ProjectHygieneService", type("ProjectHygieneService", (), {})),
            f"{package_name}.project_layer_loader": ("ProjectLayerLoader", type("ProjectLayerLoader", (), {})),
            f"{package_name}.qgis_layer_gateway": ("QgisLayerGateway", type("QgisLayerGateway", (), {})),
            f"{package_name}.layer_style_service": ("LayerStyleService", type("LayerStyleService", (), {})),
            f"{package_name}.temporal_service": ("TemporalService", type("TemporalService", (), {})),
        }
        saved_modules = {name: sys.modules.get(name) for name in [package_name, *module_specs]}

        try:
            for name, (class_name, cls) in module_specs.items():
                module = ModuleType(name)
                setattr(module, class_name, cls)
                sys.modules[name] = module

            sys.modules.pop(package_name, None)
            package = importlib.import_module(package_name)
            package = importlib.reload(package)

            self.assertIs(package.BackgroundMapService, module_specs[f"{package_name}.background_map_service"][1])
            self.assertIs(package.LayerFilterService, module_specs[f"{package_name}.layer_filter_service"][1])
            self.assertIs(package.LayerManager, module_specs[f"{package_name}.qgis_layer_gateway"][1])
            self.assertIs(package.MapCanvasService, module_specs[f"{package_name}.map_canvas_service"][1])
            self.assertIs(package.ProjectHygieneService, module_specs[f"{package_name}.project_hygiene_service"][1])
            self.assertIs(package.ProjectLayerLoader, module_specs[f"{package_name}.project_layer_loader"][1])
            self.assertIs(package.QgisLayerGateway, module_specs[f"{package_name}.qgis_layer_gateway"][1])
            self.assertIs(package.LayerStyleService, module_specs[f"{package_name}.layer_style_service"][1])
            self.assertIs(package.TemporalService, module_specs[f"{package_name}.temporal_service"][1])
            with self.assertRaises(AttributeError):
                _ = package.NotReal
        finally:
            for name, original in saved_modules.items():
                if original is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = original


if __name__ == "__main__":
    unittest.main()
