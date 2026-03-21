import tempfile
import unittest
from pathlib import Path

from tests import _path  # noqa: F401
from qfit.models import Activity
from qfit.sync_repository import SyncRepository


class SyncRepositoryTests(unittest.TestCase):
    def _activity(self, **overrides):
        payload = {
            "source": "strava",
            "source_activity_id": "42",
            "name": "Morning Ride",
            "activity_type": "Ride",
            "sport_type": "Ride",
            "start_date": "2026-03-20T06:00:00Z",
            "distance_m": 12345.6,
            "geometry_source": "summary_polyline",
            "geometry_points": [(46.5, 6.6), (46.6, 6.7)],
            "details_json": {"normalized_at": "volatile", "device_name": "Edge"},
        }
        payload.update(overrides)
        return Activity(**payload)

    def test_upsert_and_reload_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            result = repo.upsert_activities([self._activity()], sync_metadata={"provider": "strava"})
            self.assertEqual(result["inserted"], 1)
            self.assertEqual(result["updated"], 0)
            self.assertEqual(result["unchanged"], 0)
            self.assertEqual(result["total_count"], 1)

            activities = repo.load_all_activities()
            self.assertEqual(len(activities), 1)
            self.assertEqual(activities[0].source_activity_id, "42")
            self.assertEqual(activities[0].geometry_points, [[46.5, 6.6], [46.6, 6.7]])
            self.assertEqual(activities[0].details_json["device_name"], "Edge")

    def test_volatile_detail_keys_do_not_force_updates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([self._activity(details_json={"normalized_at": "one", "device_name": "Edge"})])
            result = repo.upsert_activities(
                [self._activity(details_json={"normalized_at": "two", "device_name": "Edge"})]
            )

            self.assertEqual(result["inserted"], 0)
            self.assertEqual(result["updated"], 0)
            self.assertEqual(result["unchanged"], 1)

    def test_meaningful_changes_are_reported_as_updates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()

            repo.upsert_activities([self._activity(distance_m=1000.0)])
            result = repo.upsert_activities([self._activity(distance_m=2000.0)])

            self.assertEqual(result["inserted"], 0)
            self.assertEqual(result["updated"], 1)
            self.assertEqual(result["unchanged"], 0)

    def test_sync_state_is_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SyncRepository(str(Path(tmpdir) / "qfit.sqlite"))
            repo.ensure_schema()
            repo.upsert_activities(
                [self._activity()],
                sync_metadata={
                    "provider": "strava",
                    "fetched_count": 1,
                    "stream_stats": {"downloaded": 1},
                    "rate_limit": {"short_remaining": 100},
                    "is_full_sync": True,
                    "before_epoch": 200,
                    "after_epoch": 100,
                },
            )

            rows = repo._connect().execute("SELECT * FROM sync_state").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], "strava")


if __name__ == "__main__":
    unittest.main()
