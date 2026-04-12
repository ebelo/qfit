import unittest
from types import SimpleNamespace

from tests import _path  # noqa: F401

from qfit.activities.application.activity_type_options import (
    ActivityTypeOptionsResult,
    build_activity_type_options,
    build_activity_type_options_from_activities,
    build_activity_type_options_from_records,
)


class ActivityTypeOptionsTests(unittest.TestCase):
    def test_build_activity_type_options_sorts_and_preserves_all_option(self):
        result = build_activity_type_options(
            [
                ("Ride", "GravelRide"),
                ("Run", "Trail Run"),
                ("Ride", None),
            ],
            current_value="Trail Run",
        )

        self.assertEqual(
            result,
            ActivityTypeOptionsResult(
                options=["All", "GravelRide", "Ride", "Trail Run"],
                selected_value="Trail Run",
            ),
        )

    def test_build_activity_type_options_falls_back_to_all_when_current_missing(self):
        result = build_activity_type_options([(None, "Run")], current_value="Swim")

        self.assertEqual(result.options, ["All", "Run"])
        self.assertEqual(result.selected_value, "All")

    def test_build_activity_type_options_from_activities_reads_activity_and_sport_type(self):
        activities = [
            SimpleNamespace(activity_type="Ride", sport_type="GravelRide"),
            SimpleNamespace(activity_type="Run", sport_type=None),
        ]

        result = build_activity_type_options_from_activities(activities, current_value="Ride")

        self.assertEqual(result.options, ["All", "GravelRide", "Run"])
        self.assertEqual(result.selected_value, "All")

    def test_build_activity_type_options_from_records_returns_none_without_label_fields(self):
        records = [{"name": "Morning Ride"}]

        result = build_activity_type_options_from_records(records, ["name"], current_value="All")

        self.assertIsNone(result)

    def test_build_activity_type_options_from_records_uses_available_fields(self):
        records = [
            {"activity_type": "Ride", "sport_type": "GravelRide"},
            {"activity_type": "Run", "sport_type": "TrailRun"},
        ]

        result = build_activity_type_options_from_records(
            records,
            ["sport_type", "activity_type"],
            current_value="TrailRun",
        )

        self.assertEqual(result.options, ["All", "GravelRide", "TrailRun"])
        self.assertEqual(result.selected_value, "TrailRun")


if __name__ == "__main__":
    unittest.main()
