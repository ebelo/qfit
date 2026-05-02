import importlib
import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, call, patch

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    _REAL_QGIS_PRESENT = importlib.util.find_spec("qgis") is not None
except ValueError:
    _REAL_QGIS_PRESENT = any(
        os.path.isdir(os.path.join(p, "qgis")) for p in sys.path if p
    )

try:
    from qfit.visualization.infrastructure.project_layer_loader import ProjectLayerLoader

    QGIS_AVAILABLE = True
    QGIS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    ProjectLayerLoader = None
    QGIS_AVAILABLE = False
    QGIS_IMPORT_ERROR = exc

SKIP_REAL = f"QGIS not available: {QGIS_IMPORT_ERROR}" if not QGIS_AVAILABLE else ""


_def_loader_cls = None
_def_loader_mod = None


def _load_service_with_mock_qgis():
    qstub = MagicMock()
    qgis_modules = ["qgis", "qgis.core"]

    saved_qgis = {name: sys.modules.get(name) for name in qgis_modules}
    saved_module = sys.modules.get("qfit.visualization.infrastructure.project_layer_loader")

    for name in qgis_modules:
        sys.modules[name] = qstub
    sys.modules.pop("qfit.visualization.infrastructure.project_layer_loader", None)

    try:
        module = importlib.import_module("qfit.visualization.infrastructure.project_layer_loader")
        return module.ProjectLayerLoader, module
    except Exception:  # pragma: no cover
        return None, None
    finally:
        for name, original in saved_qgis.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        if saved_module is None:
            sys.modules.pop("qfit.visualization.infrastructure.project_layer_loader", None)
        else:
            sys.modules["qfit.visualization.infrastructure.project_layer_loader"] = saved_module


if not QGIS_AVAILABLE:
    _def_loader_cls, _def_loader_mod = _load_service_with_mock_qgis()

SKIP_MOCK = "QGIS is installed — real-QGIS suite provides coverage" if QGIS_AVAILABLE else ""
SKIP_MOCK_LOAD = (
    "Could not load ProjectLayerLoader with mock QGIS"
    if (_def_loader_cls is None and not _REAL_QGIS_PRESENT)
    else ""
)


@unittest.skipUnless(QGIS_AVAILABLE, SKIP_REAL)
class ProjectLayerLoaderRealTests(unittest.TestCase):
    def test_load_output_layers_uses_current_and_legacy_activity_names(self):
        loader = ProjectLayerLoader()

        primary = MagicMock()
        primary.isValid.return_value = False
        legacy = MagicMock()
        legacy.isValid.return_value = True
        starts = MagicMock()
        starts.isValid.return_value = True
        points = MagicMock()
        points.isValid.return_value = False
        atlas = MagicMock()
        atlas.isValid.return_value = True

        project = MagicMock()
        project.mapLayersByName.return_value = []

        with patch("qfit.visualization.infrastructure.project_layer_loader.QgsVectorLayer", side_effect=[primary, legacy, starts, points, atlas]) as vector_layer, \
             patch("qfit.visualization.infrastructure.project_layer_loader.QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            layers = loader.load_output_layers("/tmp/out.gpkg")

        self.assertEqual(layers, (legacy, starts, None, atlas))
        self.assertEqual(
            vector_layer.call_args_list,
            [
                call("/tmp/out.gpkg|layername=activity_tracks", "qfit activities", "ogr"),
                call("/tmp/out.gpkg|layername=activities", "qfit activities", "ogr"),
                call("/tmp/out.gpkg|layername=activity_starts", "qfit activity starts", "ogr"),
                call("/tmp/out.gpkg|layername=activity_points", "qfit activity points", "ogr"),
                call("/tmp/out.gpkg|layername=activity_atlas_pages", "qfit atlas pages", "ogr"),
            ],
        )

    def test_load_layer_replaces_existing_display_name(self):
        loader = ProjectLayerLoader()

        old_layer = MagicMock()
        old_layer.id.return_value = "old-id"
        new_layer = MagicMock()
        new_layer.isValid.return_value = True

        project = MagicMock()
        project.mapLayersByName.return_value = [old_layer]

        with patch("qfit.visualization.infrastructure.project_layer_loader.QgsVectorLayer", return_value=new_layer), \
             patch("qfit.visualization.infrastructure.project_layer_loader.QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            loaded = loader._load_layer("/tmp/out.gpkg", "activity_tracks", "qfit activities")

        self.assertIs(loaded, new_layer)
        project.removeMapLayer.assert_called_once_with("old-id")
        project.addMapLayer.assert_called_once_with(new_layer, True)

    def test_load_layer_defaults_geometry_layers_to_wgs84_when_crs_is_missing(self):
        loader = ProjectLayerLoader()

        invalid_crs = MagicMock()
        invalid_crs.isValid.return_value = False

        new_layer = MagicMock()
        new_layer.isValid.return_value = True
        new_layer.crs.return_value = invalid_crs

        project = MagicMock()
        project.mapLayersByName.return_value = []

        with patch("qfit.visualization.infrastructure.project_layer_loader.QgsVectorLayer", return_value=new_layer), \
             patch("qfit.visualization.infrastructure.project_layer_loader.QgsCoordinateReferenceSystem", side_effect=lambda authid: authid), \
             patch("qfit.visualization.infrastructure.project_layer_loader.QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            loader._load_layer("/tmp/out.gpkg", "activity_tracks", "qfit activities")

        new_layer.setCrs.assert_called_once_with("EPSG:4326")

    def test_load_layer_preserves_metric_crs_for_atlas_pages_when_crs_is_missing(self):
        loader = ProjectLayerLoader()

        invalid_crs = MagicMock()
        invalid_crs.isValid.return_value = False

        new_layer = MagicMock()
        new_layer.isValid.return_value = True
        new_layer.crs.return_value = invalid_crs

        project = MagicMock()
        project.mapLayersByName.return_value = []

        with patch("qfit.visualization.infrastructure.project_layer_loader.QgsVectorLayer", return_value=new_layer), \
             patch("qfit.visualization.infrastructure.project_layer_loader.QgsCoordinateReferenceSystem", side_effect=lambda authid: authid), \
             patch("qfit.visualization.infrastructure.project_layer_loader.QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            loader._load_layer("/tmp/out.gpkg", "activity_atlas_pages", "qfit atlas pages")

        new_layer.setCrs.assert_called_once_with("EPSG:3857")
        project.addMapLayer.assert_called_once_with(new_layer, False)

    def test_load_route_layers_adds_saved_routes_to_dedicated_group(self):
        loader = ProjectLayerLoader()

        route_tracks = MagicMock()
        route_tracks.isValid.return_value = True
        route_points = MagicMock()
        route_points.isValid.return_value = True
        group = MagicMock()
        root = MagicMock()
        root.findGroup.return_value = group
        project = MagicMock()
        project.mapLayersByName.return_value = []
        project.layerTreeRoot.return_value = root

        with patch("qfit.visualization.infrastructure.project_layer_loader.QgsVectorLayer", side_effect=[route_tracks, route_points]) as vector_layer, \
             patch("qfit.visualization.infrastructure.project_layer_loader.QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            layers = loader.load_route_layers("/tmp/out.gpkg")

        self.assertEqual(layers, (route_tracks, route_points))
        self.assertEqual(
            vector_layer.call_args_list,
            [
                call("/tmp/out.gpkg|layername=route_tracks", "qfit saved routes", "ogr"),
                call("/tmp/out.gpkg|layername=route_points", "qfit route profile samples", "ogr"),
            ],
        )
        project.addMapLayer.assert_has_calls([call(route_tracks, False), call(route_points, False)])
        group.addLayer.assert_has_calls([call(route_tracks), call(route_points)])


@unittest.skipIf(QGIS_AVAILABLE, SKIP_MOCK)
@unittest.skipIf(_def_loader_cls is None, SKIP_MOCK_LOAD)
class ProjectLayerLoaderMockTests(unittest.TestCase):
    def setUp(self):
        self.loader = _def_loader_cls()
        self.module = _def_loader_mod

    def test_load_output_layers_returns_optional_nones_for_invalid_layers(self):
        activities = MagicMock()
        activities.isValid.return_value = True
        starts = MagicMock()
        starts.isValid.return_value = False
        points = MagicMock()
        points.isValid.return_value = True
        atlas = MagicMock()
        atlas.isValid.return_value = False

        project = MagicMock()
        project.mapLayersByName.return_value = []

        with patch.object(self.module, "QgsVectorLayer", side_effect=[activities, starts, points, atlas]), \
             patch.object(self.module, "QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            layers = self.loader.load_output_layers("/tmp/out.gpkg")

        self.assertEqual(layers, (activities, None, points, None))

    def test_load_output_layers_raises_last_error_when_no_activity_layer_can_be_loaded(self):
        invalid_primary = MagicMock()
        invalid_primary.isValid.return_value = False
        invalid_legacy = MagicMock()
        invalid_legacy.isValid.return_value = False

        project = MagicMock()
        project.mapLayersByName.return_value = []

        with patch.object(self.module, "QgsVectorLayer", side_effect=[invalid_primary, invalid_legacy]), \
             patch.object(self.module, "QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            with self.assertRaises(RuntimeError) as ctx:
                self.loader._load_first_available(
                    "/tmp/out.gpkg",
                    [("activity_tracks", "qfit activities"), ("activities", "qfit activities")],
                )

        self.assertIn("activities", str(ctx.exception))

    def test_load_layer_defaults_geometry_layers_to_wgs84_when_crs_is_missing(self):
        invalid_crs = MagicMock()
        invalid_crs.isValid.return_value = False

        new_layer = MagicMock()
        new_layer.isValid.return_value = True
        new_layer.crs.return_value = invalid_crs

        project = MagicMock()
        project.mapLayersByName.return_value = []

        with patch.object(self.module, "QgsVectorLayer", return_value=new_layer), \
             patch.object(self.module, "QgsCoordinateReferenceSystem", side_effect=lambda authid: authid), \
             patch.object(self.module, "QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            self.loader._load_layer("/tmp/out.gpkg", "activity_tracks", "qfit activities")

        new_layer.setCrs.assert_called_once_with("EPSG:4326")

    def test_load_layer_preserves_metric_crs_for_atlas_pages_when_crs_is_missing(self):
        invalid_crs = MagicMock()
        invalid_crs.isValid.return_value = False

        new_layer = MagicMock()
        new_layer.isValid.return_value = True
        new_layer.crs.return_value = invalid_crs

        project = MagicMock()
        project.mapLayersByName.return_value = []

        with patch.object(self.module, "QgsVectorLayer", return_value=new_layer), \
             patch.object(self.module, "QgsCoordinateReferenceSystem", side_effect=lambda authid: authid), \
             patch.object(self.module, "QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            self.loader._load_layer("/tmp/out.gpkg", "activity_atlas_pages", "qfit atlas pages")

        new_layer.setCrs.assert_called_once_with("EPSG:3857")
        project.addMapLayer.assert_called_once_with(new_layer, False)

    def test_load_route_layers_adds_saved_routes_to_dedicated_group(self):
        route_tracks = MagicMock()
        route_tracks.isValid.return_value = True
        route_points = MagicMock()
        route_points.isValid.return_value = True
        group = MagicMock()
        root = MagicMock()
        root.findGroup.return_value = group
        project = MagicMock()
        project.mapLayersByName.return_value = []
        project.layerTreeRoot.return_value = root

        with patch.object(self.module, "QgsVectorLayer", side_effect=[route_tracks, route_points]), \
             patch.object(self.module, "QgsProject") as qgs_project:
            qgs_project.instance.return_value = project
            layers = self.loader.load_route_layers("/tmp/out.gpkg")

        self.assertEqual(layers, (route_tracks, route_points))
        project.addMapLayer.assert_has_calls([call(route_tracks, False), call(route_points, False)])
        group.addLayer.assert_has_calls([call(route_tracks), call(route_points)])
