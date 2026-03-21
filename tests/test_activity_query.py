import unittest

from tests import _path  # noqa: F401
from qfit.activity_query import (
    ActivityQuery,
    build_preview_lines,
    build_subset_string,
    filter_activities,
    format_duration,
    format_summary_text,
    sort_activities,
    summarize_activities,
)
from qfit.models import Activity


class ActivityQueryTests(unittest.TestCase):
    def setUp(self):
        self.activities = [
            Activity(
                source="strava",
                source_activity_id="1",
                name="Morning Gravel Ride",
                activity_type="Ride",
                sport_type="GravelRide",
                start_date="2026-03-18T07:10:00+00:00",
                start_date_local="2026-03-18T08:10:00+01:00",
                distance_m=42500,
                moving_time_s=7200,
                geometry_source="stream",
            ),
            Activity(
                source="strava",
                source_activity_id="2",
                name="Lunch Run",
                activity_type="Run",
                sport_type="Run",
                start_date="2026-03-19T11:30:00+00:00",
                start_date_local="2026-03-19T12:30:00+01:00",
                distance_m=10200,
                moving_time_s=3100,
                geometry_source="summary_polyline",
            ),
            Activity(
                source="strava",
                source_activity_id="3",
                name="Easy Evening Ride",
                activity_type="Ride",
                sport_type="Ride",
                start_date="2026-03-20T17:45:00+00:00",
                start_date_local="2026-03-20T18:45:00+01:00",
                distance_m=18000,
                moving_time_s=2800,
                geometry_source="summary_polyline",
            ),
        ]

    def test_filter_activities_supports_text_distance_and_detailed_filters(self):
        query = ActivityQuery(
            activity_type="Ride",
            min_distance_km=20,
            search_text="gravel",
            detailed_only=True,
        )

        results = filter_activities(self.activities, query)

        self.assertEqual([activity.source_activity_id for activity in results], ["1"])

    def test_filter_activities_applies_date_window(self):
        query = ActivityQuery(date_from="2026-03-19", date_to="2026-03-20")

        results = filter_activities(self.activities, query)

        self.assertEqual([activity.source_activity_id for activity in results], ["2", "3"])

    def test_sort_activities_supports_distance_and_name(self):
        by_distance = sort_activities(self.activities, "Distance (longest first)")
        by_name = sort_activities(self.activities, "Name (A–Z)")

        self.assertEqual([activity.source_activity_id for activity in by_distance], ["1", "3", "2"])
        self.assertEqual([activity.source_activity_id for activity in by_name], ["3", "2", "1"])

    def test_summarize_activities_and_preview_lines(self):
        summary = summarize_activities(self.activities)
        lines = build_preview_lines(sort_activities(self.activities, None), limit=2)

        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["total_distance_km"], 70.7)
        self.assertEqual(summary["detailed_count"], 1)
        self.assertEqual(summary["by_type"], {"Ride": 2, "Run": 1})
        self.assertEqual(summary["latest_date"], "2026-03-20")
        self.assertEqual(len(lines), 2)
        self.assertIn("Easy Evening Ride", lines[0])
        self.assertIn("detailed", build_preview_lines([self.activities[0]])[0])

    def test_build_subset_string_covers_new_filter_fields(self):
        query = ActivityQuery(
            activity_type="Ride",
            date_from="2026-03-01",
            date_to="2026-03-31",
            min_distance_km=10,
            max_distance_km=50,
            search_text="O'Brien",
            detailed_only=True,
        )

        subset = build_subset_string(query)

        self.assertIn('"activity_type" = \'Ride\'', subset)
        self.assertIn('"distance_m" >= 10000.0', subset)
        self.assertIn('"distance_m" <= 50000.0', subset)
        self.assertIn("lower(coalesce(\"name\", '')) LIKE '%o''brien%'", subset)
        self.assertIn('"geometry_source" = \'stream\'', subset)

    def test_format_helpers_return_human_readable_text(self):
        self.assertEqual(format_duration(3725), "1h 02m")
        self.assertIn("3 activities", format_summary_text(summarize_activities(self.activities)))


if __name__ == "__main__":
    unittest.main()
