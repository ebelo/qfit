import unittest
from dataclasses import dataclass

from tests import _path  # noqa: F401

from qfit.activities.application.activity_selection_state import ActivitySelectionState
from qfit.activities.domain.activity_query import ActivityQuery


@dataclass
class _Activity:
    name: str
    activity_type: str
    sport_type: str | None = None
    start_date_local: str = "2026-04-07T08:00:00Z"
    distance_km: float = 10.0
    moving_time_s: int = 3600
    geometry_source: str = "stream"


class TestActivitySelectionState(unittest.TestCase):
    def test_from_activities_uses_query_to_count_matching_subset(self):
        activities = [
            _Activity(name="Morning Ride", activity_type="Ride"),
            _Activity(name="Lunch Run", activity_type="Run"),
            _Activity(name="Evening Ride", activity_type="Ride"),
        ]
        query = ActivityQuery(activity_type="Ride", search_text="ride")

        state = ActivitySelectionState.from_activities(activities, query)

        self.assertIs(state.query, query)
        self.assertEqual(state.filtered_count, 2)

    def test_from_activities_defaults_to_empty_query(self):
        activities = [_Activity(name="Morning Ride", activity_type="Ride")]

        state = ActivitySelectionState.from_activities(activities)

        self.assertIsInstance(state.query, ActivityQuery)
        self.assertEqual(state.filtered_count, 1)


if __name__ == "__main__":
    unittest.main()
