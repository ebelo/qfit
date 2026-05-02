import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401
from tests.qgis_app import get_shared_qgis_app
from qfit.providers.domain.routes import SavedRoute, RouteProfilePoint

try:
    _REAL_QGIS_PRESENT = importlib.util.find_spec("qgis") is not None
except ValueError:
    _REAL_QGIS_PRESENT = any(os.path.isdir(os.path.join(p, "qgis")) for p in sys.path if p)

try:
    from qgis.core import QgsApplication
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None

if QgsApplication is not None and _REAL_QGIS_PRESENT:
    from qfit.routes.infrastructure.geopackage.route_storage import GeoPackageRouteStore
else:  # pragma: no cover
    GeoPackageRouteStore = None


def _ensure_qgis_app():
    if not _REAL_QGIS_PRESENT:
        raise unittest.SkipTest("QGIS Python bindings are not available")
    return get_shared_qgis_app(QgsApplication)


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class RouteStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_write_routes_persists_registry_points_and_linestring_z_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "routes.gpkg")
            store = GeoPackageRouteStore(path)
            route = SavedRoute(
                source="strava",
                source_route_id="733",
                name="Saved route",
                route_type="Ride",
                geometry_source="export_gpx",
                profile_points=[
                    RouteProfilePoint(point_index=0, lat=46.1, lon=7.1, altitude_m=500.0, distance_m=0.0),
                    RouteProfilePoint(point_index=1, lat=46.2, lon=7.2, altitude_m=550.0, distance_m=1000.0),
                ],
            )

            result = store.write_routes([route])

            self.assertEqual(result["route_count"], 1)
            self.assertEqual(result["route_point_count"], 2)
            with sqlite3.connect(path) as connection:
                route_rows = connection.execute("SELECT source_route_id, name FROM route_registry").fetchall()
                point_count = connection.execute("SELECT COUNT(*) FROM route_points").fetchone()[0]
                metadata = connection.execute(
                    "SELECT geometry_type_name, z, m FROM gpkg_geometry_columns WHERE table_name = 'route_tracks'"
                ).fetchone()

            self.assertEqual(route_rows, [("733", "Saved route")])
            self.assertEqual(point_count, 2)
            self.assertEqual(metadata, ("LINESTRING", 1, 0))


if __name__ == "__main__":
    unittest.main()
