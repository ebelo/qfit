import importlib
import sys
import types
import unittest
from unittest.mock import patch, sentinel

from tests import _path  # noqa: F401


class _FakePoint:
    def __init__(self, x=0.0, y=0.0, empty=False):
        self._x = x
        self._y = y
        self._empty = empty

    def x(self):
        return self._x

    def y(self):
        return self._y

    def isEmpty(self):
        return self._empty


class _FakeGeometry:
    def __init__(self, point=None, vertices=None, empty=False):
        self._point = point
        self._vertices = list(vertices or [])
        self._empty = empty

    def isEmpty(self):
        return self._empty

    def asPoint(self):
        return self._point or _FakePoint(empty=True)

    def vertices(self):
        return iter(self._vertices)

    @staticmethod
    def fromPointXY(point):
        return _FakeGeometry(point=_FakePoint(point.x(), point.y()))


class _FakeFeature:
    def __init__(self, geometry=None):
        self._geometry = geometry

    def geometry(self):
        return self._geometry

    def setGeometry(self, geometry):
        self._geometry = geometry


class _FakeProvider:
    def __init__(self):
        self.added = []

    def addFeatures(self, features):
        self.added.extend(features)


class _FakeCrs:
    def __init__(self, authid="EPSG:4326", valid=True):
        self._authid = authid
        self._valid = valid

    def authid(self):
        return self._authid

    def isValid(self):
        return self._valid


class _FakeMemoryLayer:
    def __init__(self, spec, name, provider_key):
        self.spec = spec
        self._name = name
        self.provider_key = provider_key
        self._provider = _FakeProvider()
        self.renderer = None
        self.opacity = None
        self.repainted = False
        self.extents_updated = False

    def dataProvider(self):
        return self._provider

    def updateExtents(self):
        self.extents_updated = True

    def setRenderer(self, renderer):
        self.renderer = renderer

    def setOpacity(self, opacity):
        self.opacity = opacity

    def triggerRepaint(self):
        self.repainted = True

    def name(self):
        return self._name

    def featureCount(self):
        return len(self._provider.added)


class _FakeSourceLayer:
    def __init__(self, features=None, valid=True, crs=None):
        self._features = list(features or [])
        self._valid = valid
        self._crs = crs if crs is not None else _FakeCrs()

    def isValid(self):
        return self._valid

    def featureCount(self):
        return len(self._features)

    def getFeatures(self):
        return iter(self._features)

    def crs(self):
        return self._crs


class ActivityHeatmapLayerPureTests(unittest.TestCase):
    def setUp(self):
        qgis_mod = types.ModuleType("qgis")
        qgis_core = types.ModuleType("qgis.core")
        qgis_core.QgsFeature = _FakeFeature
        qgis_core.QgsGeometry = _FakeGeometry
        qgis_core.QgsPointXY = _FakePoint
        qgis_core.QgsVectorLayer = _FakeMemoryLayer

        layer_style_service = types.ModuleType(
            "qfit.visualization.infrastructure.layer_style_service"
        )
        layer_style_service.build_qfit_visualize_heatmap_renderer = (
            lambda: sentinel.heatmap_renderer
        )

        self._modules = {
            "qgis": qgis_mod,
            "qgis.core": qgis_core,
            "qfit.visualization.infrastructure.layer_style_service": layer_style_service,
        }
        self._patcher = patch.dict(sys.modules, self._modules, clear=False)
        self._patcher.start()
        sys.modules.pop("qfit.analysis.infrastructure.activity_heatmap_layer", None)
        self.module = importlib.import_module(
            "qfit.analysis.infrastructure.activity_heatmap_layer"
        )

    def tearDown(self):
        self._patcher.stop()
        sys.modules.pop("qfit.analysis.infrastructure.activity_heatmap_layer", None)

    def test_returns_none_without_valid_source_layers(self):
        layer, count = self.module.build_activity_heatmap_layer(None, None)

        self.assertIsNone(layer)
        self.assertEqual(count, 0)

    def test_prefers_existing_points_layer(self):
        points_layer = _FakeSourceLayer(
            features=[
                _FakeFeature(_FakeGeometry(point=_FakePoint(6.62, 46.52))),
                _FakeFeature(_FakeGeometry(point=_FakePoint(6.63, 46.53))),
            ]
        )
        activities_layer = _FakeSourceLayer(
            features=[
                _FakeFeature(
                    _FakeGeometry(vertices=[_FakePoint(6.60, 46.50), _FakePoint(6.70, 46.60)])
                )
            ]
        )

        layer, count = self.module.build_activity_heatmap_layer(
            activities_layer=activities_layer,
            points_layer=points_layer,
        )

        self.assertIsNotNone(layer)
        self.assertEqual(layer.name(), self.module.ACTIVITY_HEATMAP_LAYER_NAME)
        self.assertEqual(layer.spec, "Point?crs=EPSG:4326")
        self.assertEqual(count, 2)
        self.assertEqual(layer.featureCount(), 2)
        self.assertIs(layer.renderer, sentinel.heatmap_renderer)
        self.assertEqual(layer.opacity, 1.0)
        self.assertTrue(layer.repainted)

    def test_falls_back_to_activity_vertices_when_points_layer_missing(self):
        activities_layer = _FakeSourceLayer(
            features=[
                _FakeFeature(
                    _FakeGeometry(
                        vertices=[
                            _FakePoint(6.60, 46.50),
                            _FakePoint(6.65, 46.55),
                            _FakePoint(6.70, 46.60),
                        ]
                    )
                )
            ]
        )

        layer, count = self.module.build_activity_heatmap_layer(
            activities_layer=activities_layer,
            points_layer=None,
        )

        self.assertIsNotNone(layer)
        self.assertEqual(count, 3)
        self.assertEqual(layer.featureCount(), 3)

    def test_skips_empty_point_geometries(self):
        points_layer = _FakeSourceLayer(
            features=[
                _FakeFeature(_FakeGeometry(empty=True)),
                _FakeFeature(_FakeGeometry(point=_FakePoint(empty=True))),
            ]
        )

        layer, count = self.module.build_activity_heatmap_layer(
            activities_layer=None,
            points_layer=points_layer,
        )

        self.assertIsNone(layer)
        self.assertEqual(count, 0)

    def test_defaults_output_crs_when_source_crs_is_invalid(self):
        activities_layer = _FakeSourceLayer(
            features=[_FakeFeature(_FakeGeometry(vertices=[_FakePoint(6.60, 46.50)]))],
            crs=_FakeCrs(authid="", valid=False),
        )

        layer, count = self.module.build_activity_heatmap_layer(
            activities_layer=activities_layer,
            points_layer=None,
        )

        self.assertIsNotNone(layer)
        self.assertEqual(layer.spec, "Point?crs=EPSG:3857")
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
