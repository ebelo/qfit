import importlib
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


class _FakePoint:
    def __init__(self, x, y):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


class _FakeGeometry:
    def __init__(self, point=None, empty=False):
        self._point = point or _FakePoint(0.0, 0.0)
        self._empty = empty

    def isEmpty(self):
        return self._empty

    def asPoint(self):
        return self._point

    @staticmethod
    def fromPointXY(point):
        return _FakeGeometry(point=point)


class _FakeFields:
    def __init__(self, names=None):
        self._names = list(names or [])

    def names(self):
        return list(self._names)


class _FakeSourceFeature:
    def __init__(self, x, y, source_activity_id=None, empty=False, field_names=None):
        self._geometry = _FakeGeometry(_FakePoint(x, y), empty=empty)
        self._values = {"source_activity_id": source_activity_id}
        self._fields = _FakeFields(field_names or ["source_activity_id"])

    def geometry(self):
        return self._geometry

    def fields(self):
        return self._fields

    def __getitem__(self, key):
        return self._values[key]


class _FakeOutputFeature:
    def __init__(self, fields):
        self._fields = fields
        self.geometry = None
        self.values = {}

    def setGeometry(self, geometry):
        self.geometry = geometry

    def __setitem__(self, key, value):
        self.values[key] = value


class _FakeField:
    def __init__(self, name, _variant):
        self.name = name


class _FakeProvider:
    def __init__(self, layer):
        self._layer = layer

    def addAttributes(self, attributes):
        self._layer._field_names.extend(attribute.name for attribute in attributes)

    def addFeatures(self, features):
        self._layer.features.extend(features)


class _FakeVectorLayer:
    def __init__(self, spec, name, provider_key):
        self.spec = spec
        self._name = name
        self.provider_key = provider_key
        self._field_names = []
        self.features = []
        self.renderer = None
        self.opacity = None
        self.repainted = False

    def dataProvider(self):
        return _FakeProvider(self)

    def updateFields(self):
        return None

    def fields(self):
        return _FakeFields(self._field_names)

    def updateExtents(self):
        return None

    def setRenderer(self, renderer):
        self.renderer = renderer

    def setOpacity(self, opacity):
        self.opacity = opacity

    def triggerRepaint(self):
        self.repainted = True


class _FakeSymbolLayer:
    PropertySize = "size"

    def __init__(self):
        self.data_defined = {}

    def setDataDefinedProperty(self, key, value):
        self.data_defined[key] = value


class _FakeMarkerSymbol:
    def __init__(self, options):
        self.options = options
        self._symbol_layer = _FakeSymbolLayer()

    def symbolLayer(self, _index):
        return self._symbol_layer

    @classmethod
    def createSimple(cls, options):
        return cls(options)


class _FakeSingleSymbolRenderer:
    def __init__(self, symbol):
        self.symbol = symbol


class _FakeCRS:
    def __init__(self, authid):
        self._authid = authid

    def isValid(self):
        return bool(self._authid)

    def authid(self):
        return self._authid


class _FakeCoordinateTransform:
    def __init__(self, _source, _dest, _context):
        pass

    def transform(self, point):
        return point


class _FakeStartsLayer:
    def __init__(self, features, authid="EPSG:4326", valid=True):
        self._features = list(features)
        self._crs = _FakeCRS(authid)
        self._valid = valid

    def isValid(self):
        return self._valid

    def crs(self):
        return self._crs

    def getFeatures(self):
        return list(self._features)


class _FakeProjectSingleton:
    def transformContext(self):
        return object()


class TestFrequentStartPointsLayerPure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._module = cls._import_module_with_stubs()

    @staticmethod
    def _import_module_with_stubs():
        qgis_mod = ModuleType("qgis")
        qgis_core = ModuleType("qgis.core")
        qtcore = ModuleType("qgis.PyQt.QtCore")

        qgis_core.QgsCoordinateReferenceSystem = _FakeCRS
        qgis_core.QgsCoordinateTransform = _FakeCoordinateTransform
        qgis_core.QgsFeature = _FakeOutputFeature
        qgis_core.QgsField = _FakeField
        qgis_core.QgsGeometry = _FakeGeometry
        qgis_core.QgsMarkerSymbol = _FakeMarkerSymbol
        qgis_core.QgsPointXY = _FakePoint
        qgis_core.QgsProject = SimpleNamespace(instance=lambda: _FakeProjectSingleton())
        qgis_core.QgsProperty = SimpleNamespace(fromField=lambda name: f"field:{name}")
        qgis_core.QgsSingleSymbolRenderer = _FakeSingleSymbolRenderer
        qgis_core.QgsSymbolLayer = _FakeSymbolLayer
        qgis_core.QgsVectorLayer = _FakeVectorLayer

        qtcore.QVariant = SimpleNamespace(Int="int", Double="double")

        qgis_mod.core = qgis_core

        with patch.dict(
            sys.modules,
            {
                "qgis": qgis_mod,
                "qgis.core": qgis_core,
                "qgis.PyQt": ModuleType("qgis.PyQt"),
                "qgis.PyQt.QtCore": qtcore,
            },
            clear=False,
        ):
            sys.modules.pop(
                "qfit.analysis.infrastructure.frequent_start_points_layer", None
            )
            return importlib.import_module(
                "qfit.analysis.infrastructure.frequent_start_points_layer"
            )

    def test_returns_none_for_missing_or_invalid_starts_layer(self):
        layer, clusters = self._module.build_frequent_start_points_layer(None)
        self.assertIsNone(layer)
        self.assertEqual(clusters, [])

        invalid_layer = _FakeStartsLayer([], valid=False)
        layer, clusters = self._module.build_frequent_start_points_layer(invalid_layer)
        self.assertIsNone(layer)
        self.assertEqual(clusters, [])

    def test_builds_styled_memory_layer_from_valid_start_features(self):
        starts_layer = _FakeStartsLayer(
            [
                _FakeSourceFeature(6200.0, 46520.0, source_activity_id="a1"),
                _FakeSourceFeature(6205.0, 46524.0, source_activity_id="a2"),
                _FakeSourceFeature(6800.0, 46700.0, source_activity_id="b1"),
                _FakeSourceFeature(0.0, 0.0, source_activity_id="skip", empty=True),
            ],
            authid="",
        )

        layer, clusters = self._module.build_frequent_start_points_layer(starts_layer)

        self.assertIsNotNone(layer)
        self.assertEqual(layer.spec, "Point?crs=EPSG:4326")
        self.assertEqual(layer._name, self._module.FREQUENT_STARTING_POINTS_LAYER_NAME)
        self.assertEqual([cluster.activity_count for cluster in clusters], [2, 1])
        self.assertEqual(len(layer.features), 2)
        self.assertEqual(layer.features[0].values["rank"], 1)
        self.assertEqual(layer.features[0].values["activity_count"], 2)
        self.assertIn("marker_size", layer.features[0].values)
        self.assertIsInstance(layer.renderer, _FakeSingleSymbolRenderer)
        self.assertEqual(layer.opacity, 0.95)
        self.assertTrue(layer.repainted)
        symbol_layer = layer.renderer.symbol.symbolLayer(0)
        self.assertEqual(
            symbol_layer.data_defined[_FakeSymbolLayer.PropertySize],
            "field:marker_size",
        )


if __name__ == "__main__":
    unittest.main()
