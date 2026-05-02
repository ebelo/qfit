import sys
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from tests import _path  # noqa: F401

_GPKG_WRITER_MODULE = "qfit.activities.infrastructure.geopackage.gpkg_writer"


@contextmanager
def _patched_gpkg_writer_import(route_store_cls=None):
    """Import gpkg_writer with GeoPackage/QGIS-heavy collaborators replaced."""
    schema = types.ModuleType("qfit.activities.infrastructure.geopackage.gpkg_schema")
    schema.GPKG_LAYER_SCHEMA = {"route_tracks": {"kind": "layer"}}

    orchestration = types.ModuleType(
        "qfit.activities.infrastructure.geopackage.gpkg_write_orchestration"
    )
    orchestration.bootstrap_empty_gpkg = lambda *args, **kwargs: None
    orchestration.build_and_write_all_layers = lambda *args, **kwargs: {}

    atlas = types.ModuleType("qfit.atlas.publish_atlas")
    atlas.normalize_atlas_page_settings = lambda **kwargs: dict(kwargs)

    modules = {
        schema.__name__: schema,
        orchestration.__name__: orchestration,
        atlas.__name__: atlas,
    }
    if route_store_cls is not None:
        route_storage = types.ModuleType("qfit.routes.infrastructure.geopackage.route_storage")
        route_storage.GeoPackageRouteStore = route_store_cls
        modules[route_storage.__name__] = route_storage

    original_writer_module = sys.modules.get(_GPKG_WRITER_MODULE)
    writer_was_loaded = _GPKG_WRITER_MODULE in sys.modules
    sys.modules.pop(_GPKG_WRITER_MODULE, None)
    try:
        with patch.dict(sys.modules, modules):
            from qfit.activities.infrastructure.geopackage.gpkg_writer import GeoPackageWriter

            yield GeoPackageWriter
    finally:
        if writer_was_loaded:
            sys.modules[_GPKG_WRITER_MODULE] = original_writer_module
        else:
            sys.modules.pop(_GPKG_WRITER_MODULE, None)


class GeoPackageWriterRoutesTests(unittest.TestCase):
    def test_write_routes_requires_output_path(self):
        with _patched_gpkg_writer_import() as GeoPackageWriter:
            writer = GeoPackageWriter()

            with self.assertRaises(ValueError):
                writer.write_routes([])

    def test_write_routes_delegates_to_route_store(self):
        class FakeRouteStore:
            instances = []

            def __init__(self, output_path):
                self.output_path = output_path
                self.routes = None
                self.instances.append(self)

            def write_routes(self, routes):
                self.routes = routes
                return {"path": self.output_path, "route_count": len(routes)}

        routes = [object(), object()]
        with _patched_gpkg_writer_import(FakeRouteStore) as GeoPackageWriter:
            writer = GeoPackageWriter(output_path="/tmp/routes.gpkg")
            result = writer.write_routes(routes)

        self.assertEqual(FakeRouteStore.instances[0].output_path, "/tmp/routes.gpkg")
        self.assertIs(FakeRouteStore.instances[0].routes, routes)
        self.assertEqual(result["path"], "/tmp/routes.gpkg")
        self.assertEqual(result["route_count"], 2)
        self.assertIn("route_tracks", result["schema"])


if __name__ == "__main__":
    unittest.main()
