import sys
import types
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401


def _ensure_gpkg_schema_qgis_stubs():
    """Provide the tiny QGIS surface needed to import gpkg_writer in pure unit tests."""
    try:
        from qgis.PyQt.QtCore import QVariant  # noqa: F401
        from qgis.core import QgsField, QgsFields  # noqa: F401
        return
    except (ImportError, ModuleNotFoundError):
        pass

    qgis_module = sys.modules.setdefault("qgis", types.ModuleType("qgis"))
    pyqt_module = sys.modules.setdefault("qgis.PyQt", types.ModuleType("qgis.PyQt"))
    qtcore_module = sys.modules.setdefault("qgis.PyQt.QtCore", types.ModuleType("qgis.PyQt.QtCore"))
    core_module = sys.modules.setdefault("qgis.core", types.ModuleType("qgis.core"))

    qgis_module.PyQt = pyqt_module
    pyqt_module.QtCore = qtcore_module
    if not hasattr(qtcore_module, "QVariant"):
        qtcore_module.QVariant = types.SimpleNamespace(String="string", Double="double", Int="int")
    if not hasattr(core_module, "QgsField"):
        core_module.QgsField = lambda name, field_type: (name, field_type)
    if not hasattr(core_module, "QgsFields"):
        core_module.QgsFields = list


def _geo_package_writer_cls():
    _ensure_gpkg_schema_qgis_stubs()
    sys.modules.pop("qfit.activities.infrastructure.geopackage.gpkg_writer", None)
    from qfit.activities.infrastructure.geopackage.gpkg_writer import GeoPackageWriter

    return GeoPackageWriter


class GeoPackageWriterRoutesTests(unittest.TestCase):
    def test_write_routes_requires_output_path(self):
        writer = _geo_package_writer_cls()()

        with self.assertRaises(ValueError):
            writer.write_routes([])

    def test_write_routes_delegates_to_route_store(self):
        module = types.ModuleType("qfit.routes.infrastructure.geopackage.route_storage")

        class FakeRouteStore:
            instances = []

            def __init__(self, output_path):
                self.output_path = output_path
                self.routes = None
                self.instances.append(self)

            def write_routes(self, routes):
                self.routes = routes
                return {"path": self.output_path, "route_count": len(routes)}

        module.GeoPackageRouteStore = FakeRouteStore
        routes = [object(), object()]
        writer = _geo_package_writer_cls()(output_path="/tmp/routes.gpkg")

        with patch.dict(sys.modules, {module.__name__: module}):
            result = writer.write_routes(routes)

        self.assertEqual(FakeRouteStore.instances[0].output_path, "/tmp/routes.gpkg")
        self.assertIs(FakeRouteStore.instances[0].routes, routes)
        self.assertEqual(result["path"], "/tmp/routes.gpkg")
        self.assertEqual(result["route_count"], 2)
        self.assertIn("route_tracks", result["schema"])


if __name__ == "__main__":
    unittest.main()
