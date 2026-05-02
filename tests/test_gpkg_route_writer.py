import os
import sqlite3
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401
from tests.qgis_app import get_shared_qgis_app
from qfit.providers.domain.routes import RouteProfilePoint, SavedRoute

try:
    from qgis.core import QgsApplication
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None

if QgsApplication is not None:
    from qfit.activities.infrastructure.geopackage.gpkg_writer import GeoPackageWriter
else:  # pragma: no cover
    GeoPackageWriter = None


def _ensure_qgis_app():
    return get_shared_qgis_app(QgsApplication)


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class GeoPackageRouteWriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_write_routes_persists_track_metadata_and_profile_samples_idempotently(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "qfit-routes.gpkg")
            writer = GeoPackageWriter(output_path=output_path)
            route = SavedRoute(
                source="strava",
                source_route_id="42",
                name="Swiss gravel loop",
                geometry_source="export_gpx",
                profile_points=[
                    RouteProfilePoint(0, 46.5, 6.6, 0.0, altitude_m=500.0),
                    RouteProfilePoint(1, 46.501, 6.601, 135.4, altitude_m=507.5),
                ],
            )

            first = writer.write_routes([route])
            second = writer.write_routes([route])

            with sqlite3.connect(output_path) as connection:
                route_count = connection.execute("SELECT COUNT(*) FROM route_registry").fetchone()[0]
                point_count = connection.execute("SELECT COUNT(*) FROM route_points").fetchone()[0]
                profile_count = connection.execute("SELECT COUNT(*) FROM route_profile_samples").fetchone()[0]
                z_flag = connection.execute(
                    "SELECT z FROM gpkg_geometry_columns WHERE table_name = 'route_tracks'"
                ).fetchone()[0]

        self.assertEqual(first["route_track_count"], 1)
        self.assertEqual(first["route_point_count"], 2)
        self.assertEqual(first["route_profile_sample_count"], 2)
        self.assertEqual(second["sync"].unchanged, 1)
        self.assertEqual(second["route_track_count"], 1)
        self.assertEqual(route_count, 1)
        self.assertEqual(point_count, 2)
        self.assertEqual(profile_count, 2)
        self.assertEqual(z_flag, 1)


if __name__ == "__main__":
    unittest.main()
