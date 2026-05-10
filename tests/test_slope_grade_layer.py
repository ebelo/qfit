import importlib
import sys
import unittest
from types import ModuleType

from tests import _path  # noqa: F401


class _FeatureSample:
    def __init__(self, values, *, geometry=None):
        self._values = values
        self._geometry = geometry

    def __getitem__(self, key):
        return self._values[key]

    def geometry(self):
        return self._geometry


class _FeatureLayer:
    def __init__(self, features, *, crs_authid="EPSG:4326"):
        self._features = tuple(features)
        self._crs = _Crs(crs_authid)

    def getFeatures(self):
        return iter(self._features)

    def crs(self):
        return self._crs


class _Crs:
    def __init__(self, authid):
        self._authid = authid

    def isValid(self):
        return bool(self._authid)

    def authid(self):
        return self._authid


class _Point:
    def __init__(self, x, y):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


class _Geometry:
    def __init__(self, x, y):
        self._point = _Point(x, y)

    def isEmpty(self):
        return False

    def asPoint(self):
        return self._point


class SlopeGradeLayerTests(unittest.TestCase):
    def test_builds_styled_memory_layer_from_activity_line_segments(self):
        module = _load_slope_grade_layer_with_qgis_stub()
        points_layer = _FeatureLayer(
            (
                _FeatureSample(
                    {
                        "source": "strava",
                        "source_activity_id": "a-1",
                        "stream_distance_m": 0,
                        "grade_smooth_pct": 0.0,
                    },
                    geometry=_Geometry(6.6, 46.5),
                ),
                _FeatureSample(
                    {
                        "source": "strava",
                        "source_activity_id": "a-1",
                        "stream_distance_m": 100,
                        "grade_smooth_pct": 4.0,
                    },
                    geometry=_Geometry(6.7, 46.6),
                ),
            ),
            crs_authid="EPSG:2056",
        )

        layer, segments = module.build_slope_grade_layer(
            activities_layer=object(),
            points_layer=points_layer,
        )

        self.assertEqual(layer.name, module.SLOPE_GRADE_LAYER_NAME)
        self.assertEqual(layer.crs_authid, "EPSG:2056")
        self.assertEqual(len(segments), 1)
        self.assertEqual(len(layer.features), 1)
        self.assertEqual(layer.features[0].attrs["grade_class"], "climb")
        self.assertEqual(layer.features[0].attrs["source_id"], "a-1")
        self.assertEqual(
            layer.features[0].geometry,
            ((6.6, 46.5), (6.7, 46.6)),
        )
        self.assertEqual(layer.renderer.field_name, "grade_class")
        self.assertEqual(len(layer.renderer.categories), 5)
        self.assertAlmostEqual(layer.opacity, 0.95)
        self.assertEqual(layer.repaint_count, 1)

    def test_builds_memory_layer_from_route_profile_lat_lon_segments(self):
        module = _load_slope_grade_layer_with_qgis_stub()
        profile_layer = _FeatureLayer(
            (
                _FeatureSample(
                    {
                        "sample_group_index": 1,
                        "source": "strava",
                        "source_route_id": "r-1",
                        "lat": 46.5,
                        "lon": 6.6,
                        "distance_m": 0,
                        "altitude_m": 100,
                    }
                ),
                _FeatureSample(
                    {
                        "sample_group_index": 1,
                        "source": "strava",
                        "source_route_id": "r-1",
                        "lat": 46.6,
                        "lon": 6.7,
                        "distance_m": 100,
                        "altitude_m": 91,
                    }
                ),
            )
        )

        layer, segments = module.build_slope_grade_layer(
            route_tracks_layer=object(),
            route_profile_samples_layer=profile_layer,
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(layer.features[0].attrs["layer_key"], "saved_route_tracks")
        self.assertEqual(layer.features[0].attrs["grade_class"], "steep_descent")
        self.assertEqual(
            layer.features[0].geometry,
            ((6.6, 46.5), (6.7, 46.6)),
        )

    def test_returns_empty_result_when_no_line_segments_are_available(self):
        module = _load_slope_grade_layer_with_qgis_stub()

        layer, segments = module.build_slope_grade_layer(
            activities_layer=object(),
            points_layer=_FeatureLayer(()),
        )

        self.assertIsNone(layer)
        self.assertEqual(segments, ())


class _QVariant:
    String = "String"
    Double = "Double"


class _QColor:
    def __init__(self, value):
        self.value = value


class _QgsField:
    def __init__(self, name, field_type):
        self.name = name
        self.field_type = field_type


class _QgsFeature:
    def __init__(self, fields=None):
        self.fields = fields
        self.attrs = {}
        self.geometry = None

    def setGeometry(self, geometry):
        self.geometry = geometry

    def __setitem__(self, key, value):
        self.attrs[key] = value


class _QgsGeometry:
    @staticmethod
    def fromPolylineXY(points):
        return tuple((point.x, point.y) for point in points)


class _QgsPointXY:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class _Provider:
    def __init__(self, layer):
        self.layer = layer

    def addAttributes(self, fields):
        self.layer.field_defs.extend(fields)

    def addFeatures(self, features):
        self.layer.features.extend(features)


class _QgsVectorLayer:
    def __init__(self, uri, name, provider_name):
        self.uri = uri
        self.name = name
        self.provider_name = provider_name
        self.crs_authid = uri.split("crs=", 1)[1]
        self.field_defs = []
        self.features = []
        self.renderer = None
        self.opacity = None
        self.repaint_count = 0

    def dataProvider(self):
        return _Provider(self)

    def updateFields(self):
        pass

    def fields(self):
        return self.field_defs

    def updateExtents(self):
        pass

    def setRenderer(self, renderer):
        self.renderer = renderer

    def setOpacity(self, opacity):
        self.opacity = opacity

    def triggerRepaint(self):
        self.repaint_count += 1


class _QgsCategorizedSymbolRenderer:
    def __init__(self, field_name, categories):
        self.field_name = field_name
        self.categories = categories


class _QgsRendererCategory:
    def __init__(self, value, symbol, label):
        self.value = value
        self.symbol = symbol
        self.label = label


class _QgsLineSymbol:
    def __init__(self):
        self.layers = []

    def deleteSymbolLayer(self, _index):
        self.layers.clear()

    def appendSymbolLayer(self, layer):
        self.layers.append(layer)


class _QgsSimpleLineSymbolLayer:
    def __init__(self):
        self.color = None
        self.width = None

    def setColor(self, color):
        self.color = color

    def setWidth(self, width):
        self.width = width


class _QgsCoordinateReferenceSystem:
    pass


def _load_slope_grade_layer_with_qgis_stub():
    target = "qfit.analysis.infrastructure.slope_grade_layer"
    qgis_modules = (
        "qgis",
        "qgis.core",
        "qgis.PyQt",
        "qgis.PyQt.QtCore",
        "qgis.PyQt.QtGui",
    )
    saved = {name: sys.modules.get(name) for name in qgis_modules + (target,)}

    qgis = ModuleType("qgis")
    core = ModuleType("qgis.core")
    pyqt = ModuleType("qgis.PyQt")
    qtcore = ModuleType("qgis.PyQt.QtCore")
    qtgui = ModuleType("qgis.PyQt.QtGui")

    qtcore.QVariant = _QVariant
    qtgui.QColor = _QColor
    core.QgsCategorizedSymbolRenderer = _QgsCategorizedSymbolRenderer
    core.QgsCoordinateReferenceSystem = _QgsCoordinateReferenceSystem
    core.QgsFeature = _QgsFeature
    core.QgsField = _QgsField
    core.QgsGeometry = _QgsGeometry
    core.QgsLineSymbol = _QgsLineSymbol
    core.QgsPointXY = _QgsPointXY
    core.QgsRendererCategory = _QgsRendererCategory
    core.QgsSimpleLineSymbolLayer = _QgsSimpleLineSymbolLayer
    core.QgsVectorLayer = _QgsVectorLayer

    sys.modules.update(
        {
            "qgis": qgis,
            "qgis.core": core,
            "qgis.PyQt": pyqt,
            "qgis.PyQt.QtCore": qtcore,
            "qgis.PyQt.QtGui": qtgui,
        }
    )
    sys.modules.pop(target, None)
    try:
        return importlib.import_module(target)
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


if __name__ == "__main__":
    unittest.main()
