import unittest
from types import SimpleNamespace

from tests import _path  # noqa: F401

from qfit.activities.application.activity_preview import (
    ActivityPreviewRequest,
    build_activity_preview,
    build_activity_preview_query,
    build_activity_preview_request,
    build_activity_preview_selection_state,
    build_activity_query,
    build_activity_selection_state,
)
from qfit.activities.domain.activity_query import DEFAULT_SORT_LABEL, DETAILED_ROUTE_FILTER_MISSING


class ActivityPreviewTests(unittest.TestCase):
    def setUp(self):
        self.activities = [
            SimpleNamespace(
                name="Morning Ride",
                start_date="2026-04-10T08:00:00",
                distance_m=25000,
                moving_time_s=3600,
                geometry_source="stream",
                activity_type="Ride",
                sport_type="Ride",
            ),
            SimpleNamespace(
                name="Lunch Run",
                start_date="2026-04-11T12:00:00",
                distance_m=5000,
                moving_time_s=1500,
                geometry_source="summary",
                activity_type="Run",
                sport_type="Run",
            ),
        ]

    def test_build_activity_query_preserves_filter_inputs(self):
        request = ActivityPreviewRequest(
            activities=self.activities,
            activity_type="Run",
            date_from="2026-04-01",
            date_to="2026-04-30",
            min_distance_km=2,
            max_distance_km=8,
            search_text="lunch",
            detailed_route_filter=DETAILED_ROUTE_FILTER_MISSING,
            sort_label="Name (A–Z)",
        )

        query = build_activity_query(request)

        self.assertEqual(query.activity_type, "Run")
        self.assertEqual(query.date_from, "2026-04-01")
        self.assertEqual(query.date_to, "2026-04-30")
        self.assertEqual(query.min_distance_km, 2.0)
        self.assertEqual(query.max_distance_km, 8.0)
        self.assertEqual(query.search_text, "lunch")
        self.assertEqual(query.detailed_route_filter, DETAILED_ROUTE_FILTER_MISSING)
        self.assertEqual(query.sort_label, "Name (A–Z)")

    def test_build_activity_preview_query_delegates_to_activity_query_builder(self):
        request = ActivityPreviewRequest(
            activities=self.activities,
            activity_type="Run",
            detailed_route_filter=DETAILED_ROUTE_FILTER_MISSING,
        )

        query = build_activity_preview_query(request)

        self.assertEqual(query.activity_type, "Run")
        self.assertEqual(query.detailed_route_filter, DETAILED_ROUTE_FILTER_MISSING)

    def test_build_activity_preview_request_preserves_inputs(self):
        request = build_activity_preview_request(
            activities=self.activities,
            activity_type="Run",
            date_from="2026-04-01",
            date_to="2026-04-30",
            min_distance_km=2,
            max_distance_km=8,
            search_text="lunch",
            detailed_route_filter=DETAILED_ROUTE_FILTER_MISSING,
            sort_label="Name (A–Z)",
            preview_limit=5,
        )

        self.assertIsInstance(request, ActivityPreviewRequest)
        self.assertEqual(request.activities, self.activities)
        self.assertEqual(request.activity_type, "Run")
        self.assertEqual(request.date_from, "2026-04-01")
        self.assertEqual(request.date_to, "2026-04-30")
        self.assertEqual(request.min_distance_km, 2)
        self.assertEqual(request.max_distance_km, 8)
        self.assertEqual(request.search_text, "lunch")
        self.assertEqual(request.detailed_route_filter, DETAILED_ROUTE_FILTER_MISSING)
        self.assertEqual(request.sort_label, "Name (A–Z)")
        self.assertEqual(request.preview_limit, 5)

    def test_build_activity_selection_state_filters_with_query(self):
        request = ActivityPreviewRequest(
            activities=self.activities,
            activity_type="Run",
            detailed_route_filter=DETAILED_ROUTE_FILTER_MISSING,
        )

        selection_state = build_activity_selection_state(request)

        self.assertEqual(selection_state.filtered_count, 1)
        self.assertEqual(selection_state.query.activity_type, "Run")
        self.assertEqual(selection_state.query.detailed_route_filter, DETAILED_ROUTE_FILTER_MISSING)

    def test_build_activity_preview_selection_state_delegates_to_selection_state_builder(self):
        request = ActivityPreviewRequest(activities=self.activities, activity_type="Run")

        selection_state = build_activity_preview_selection_state(request)

        self.assertEqual(selection_state.filtered_count, 1)
        self.assertEqual(selection_state.query.activity_type, "Run")

    def test_build_activity_preview_returns_empty_state_when_no_activities(self):
        result = build_activity_preview(ActivityPreviewRequest(activities=[]))

        self.assertEqual(result.selection_state.filtered_count, 0)
        self.assertEqual(result.fetched_activities, [])
        self.assertEqual(
            result.query_summary_text,
            "Fetch activities to preview your latest synced activities.",
        )
        self.assertEqual(result.preview_text, "")

    def test_build_activity_preview_summarizes_and_formats_preview_lines(self):
        result = build_activity_preview(ActivityPreviewRequest(activities=self.activities))

        self.assertEqual(
            [activity.name for activity in result.fetched_activities],
            ["Lunch Run", "Morning Ride"],
        )
        self.assertIn("2 activities", result.query_summary_text)
        self.assertNotIn("Visualize filters currently match", result.query_summary_text)
        self.assertIn("Lunch Run", result.preview_text)
        self.assertIn("Morning Ride", result.preview_text)

    def test_build_activity_preview_reports_filtered_count_when_subset_is_active(self):
        result = build_activity_preview(
            ActivityPreviewRequest(
                activities=self.activities,
                activity_type="Run",
            )
        )

        self.assertEqual(result.selection_state.filtered_count, 1)
        self.assertIn("Visualize filters currently match 1 activities.", result.query_summary_text)

    def test_build_activity_preview_uses_preview_limit_for_overflow_message(self):
        result = build_activity_preview(
            ActivityPreviewRequest(
                activities=self.activities,
                preview_limit=1,
                sort_label="Name (A–Z)",
            )
        )

        self.assertEqual(result.fetched_activities[0].name, "Lunch Run")
        self.assertEqual(len(result.preview_text.splitlines()), 2)
        self.assertIn("… and 1 more", result.preview_text)
        self.assertEqual(result.selection_state.query.sort_label, "Name (A–Z)")


if __name__ == "__main__":
    unittest.main()
