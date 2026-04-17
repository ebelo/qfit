import unittest

from tests import _path  # noqa: F401

from qfit.activities.domain.activity_classification import normalize_activity_type
from qfit.activities.domain.activity_query import ActivityQuery
from qfit.activities.domain.models import Activity


class ActivityDomainSurfaceTests(unittest.TestCase):
    def test_activity_model_exposes_expected_dataclass_shape(self):
        activity = Activity(
            source="strava",
            source_activity_id="123",
            name="Lunch Ride",
            activity_type="Ride",
            start_date="2026-04-01T12:00:00Z",
        )

        self.assertEqual(activity.source, "strava")
        self.assertEqual(activity.source_activity_id, "123")
        self.assertEqual(activity.name, "Lunch Ride")
        self.assertEqual(activity.activity_type, "Ride")

    def test_activity_query_exposes_expected_fields(self):
        query = ActivityQuery(activity_type="Ride", detailed_only=True)

        self.assertEqual(query.activity_type, "Ride")
        self.assertTrue(query.detailed_only)

    def test_domain_classification_helpers_match_expected_behavior(self):
        self.assertEqual(normalize_activity_type("Trail Run"), "trailrun")


if __name__ == "__main__":
    unittest.main()
