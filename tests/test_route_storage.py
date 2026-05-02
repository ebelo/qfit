import os
import tempfile
import unittest

from tests import _path  # noqa: F401
from qfit.activities.infrastructure.geopackage.route_storage import GeoPackageRouteStore
from qfit.providers.domain.routes import RouteProfilePoint, SavedRoute


class RouteStorageTests(unittest.TestCase):
    def test_route_store_is_idempotent_and_preserves_profile_samples(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GeoPackageRouteStore(os.path.join(tmpdir, "routes.gpkg"))
            store.ensure_schema()
            route = SavedRoute(
                source="strava",
                source_route_id="42",
                name="Swiss gravel loop",
                distance_m=12345.6,
                elevation_gain_m=789.0,
                geometry_source="export_gpx",
                geometry_points=[(46.5, 6.6), (46.501, 6.601)],
                profile_points=[
                    RouteProfilePoint(
                        point_index=0,
                        lat=46.5,
                        lon=6.6,
                        distance_m=0.0,
                        altitude_m=500.0,
                    ),
                    RouteProfilePoint(
                        point_index=1,
                        lat=46.501,
                        lon=6.601,
                        distance_m=135.4,
                        altitude_m=507.5,
                    ),
                ],
                details_json={"gpx_enriched_at": "volatile", "gpx_point_count": 2},
            )

            first = store.upsert_routes([route])
            second = store.upsert_routes([route])
            records = store.load_all_route_records()

        self.assertEqual(first.inserted, 1)
        self.assertEqual(first.updated, 0)
        self.assertEqual(first.unchanged, 0)
        self.assertEqual(second.inserted, 0)
        self.assertEqual(second.updated, 0)
        self.assertEqual(second.unchanged, 1)
        self.assertEqual(second.total_count, 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source"], "strava")
        self.assertEqual(records[0]["source_route_id"], "42")
        self.assertEqual(records[0]["profile_points"][1]["distance_m"], 135.4)
        self.assertEqual(records[0]["profile_points"][1]["altitude_m"], 507.5)

    def test_route_store_updates_existing_route_without_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GeoPackageRouteStore(os.path.join(tmpdir, "routes.gpkg"))
            store.ensure_schema()
            route = SavedRoute(source="strava", source_route_id="42", name="Old name")
            updated_route = SavedRoute(source="strava", source_route_id="42", name="New name")

            first = store.upsert_routes([route])
            second = store.upsert_routes([updated_route])
            records = store.load_all_route_records()

        self.assertEqual(first.inserted, 1)
        self.assertEqual(second.updated, 1)
        self.assertEqual(second.total_count, 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "New name")

    def test_full_sync_pruning_infers_provider_from_dict_routes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GeoPackageRouteStore(os.path.join(tmpdir, "routes.gpkg"))
            store.ensure_schema()
            store.upsert_routes([
                SavedRoute(source="strava", source_route_id="keep", name="Keep"),
                SavedRoute(source="strava", source_route_id="drop", name="Drop"),
                SavedRoute(source="komoot", source_route_id="other", name="Other provider"),
            ])

            stats = store.upsert_routes(
                [{"source": "strava", "source_route_id": "keep", "name": "Keep"}],
                sync_metadata={"is_full_sync": True},
            )
            records = store.load_all_route_records()

        self.assertEqual(stats.unchanged, 1)
        self.assertEqual(stats.total_count, 2)
        self.assertEqual(
            {(record["source"], record["source_route_id"]) for record in records},
            {("strava", "keep"), ("komoot", "other")},
        )

    def test_empty_full_sync_without_provider_does_not_prune_any_provider(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GeoPackageRouteStore(os.path.join(tmpdir, "routes.gpkg"))
            store.ensure_schema()
            store.upsert_routes([SavedRoute(source="strava", source_route_id="42", name="Swiss loop")])

            stats = store.upsert_routes([], sync_metadata={"is_full_sync": True})
            records = store.load_all_route_records()

        self.assertEqual(stats.total_count, 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source_route_id"], "42")

    def test_empty_full_sync_with_explicit_provider_prunes_that_provider(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GeoPackageRouteStore(os.path.join(tmpdir, "routes.gpkg"))
            store.ensure_schema()
            store.upsert_routes([
                SavedRoute(source="strava", source_route_id="42", name="Swiss loop"),
                SavedRoute(source="komoot", source_route_id="99", name="Other loop"),
            ])

            stats = store.upsert_routes(
                [],
                sync_metadata={"is_full_sync": True, "provider": "strava"},
            )
            records = store.load_all_route_records()

        self.assertEqual(stats.total_count, 1)
        self.assertEqual([(record["source"], record["source_route_id"]) for record in records], [("komoot", "99")])


if __name__ == "__main__":
    unittest.main()
