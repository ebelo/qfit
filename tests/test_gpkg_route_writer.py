import math
import os
import sqlite3
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: E402,F401
from tests.qgis_app import get_shared_qgis_app  # noqa: E402
from qfit.providers.domain.routes import (  # noqa: E402
    RouteProfilePoint,
    SavedRoute,
)

try:
    from qgis.core import QgsApplication, QgsVectorLayer, QgsWkbTypes
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None
    QgsVectorLayer = None
    QgsWkbTypes = None

if QgsApplication is not None:
    from qfit.activities.infrastructure.geopackage.gpkg_writer import (  # noqa: E501
        GeoPackageWriter,
    )
else:  # pragma: no cover
    GeoPackageWriter = None


def _ensure_qgis_app():
    return get_shared_qgis_app(QgsApplication)


@unittest.skipIf(
    QgsApplication is None,
    "QGIS Python bindings are not available",
)
class GeoPackageRouteWriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_write_routes_persists_metadata_and_samples_idempotently(
        self,
    ):
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
                    RouteProfilePoint(
                        1,
                        46.501,
                        6.601,
                        135.4,
                        altitude_m=507.5,
                    ),
                ],
            )
            route_without_elevation = SavedRoute(
                source="strava",
                source_route_id="43",
                name="Polyline-only loop",
                geometry_source="summary",
                geometry_points=[(46.7, 6.8), (46.8, 6.9)],
            )

            first = writer.write_routes([route, route_without_elevation])
            second = writer.write_routes([route, route_without_elevation])

            with sqlite3.connect(output_path) as connection:
                route_count = connection.execute(
                    "SELECT COUNT(*) FROM route_registry"
                ).fetchone()[0]
                point_count = connection.execute(
                    "SELECT COUNT(*) FROM route_points"
                ).fetchone()[0]
                profile_count = connection.execute(
                    "SELECT COUNT(*) FROM route_profile_samples"
                ).fetchone()[0]
                z_flag = connection.execute(
                    "SELECT z FROM gpkg_geometry_columns "
                    "WHERE table_name = 'route_tracks'"
                ).fetchone()[0]
            track_layer = QgsVectorLayer(
                f"{output_path}|layername=route_tracks",
                "route_tracks",
                "ogr",
            )
            features = {
                feature["source_route_id"]: feature
                for feature in track_layer.getFeatures()
            }

        self.assertEqual(first["route_track_count"], 2)
        self.assertEqual(first["route_point_count"], 2)
        self.assertEqual(first["route_profile_sample_count"], 2)
        self.assertEqual(second["sync"].unchanged, 2)
        self.assertEqual(second["route_track_count"], 2)
        self.assertEqual(route_count, 2)
        self.assertEqual(point_count, 2)
        self.assertEqual(profile_count, 2)
        self.assertEqual(z_flag, 1)
        self.assertTrue(QgsWkbTypes.hasZ(track_layer.wkbType()))
        self.assertTrue(
            QgsWkbTypes.hasZ(features["42"].geometry().wkbType())
        )
        self.assertTrue(
            QgsWkbTypes.hasZ(features["43"].geometry().wkbType())
        )
        self.assertAlmostEqual(
            next(features["42"].geometry().vertices()).z(),
            500.0,
        )
        self.assertTrue(
            math.isnan(next(features["43"].geometry().vertices()).z())
        )


if __name__ == "__main__":
    unittest.main()
