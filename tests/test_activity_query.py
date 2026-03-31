import unittest

from tests import _path  # noqa: F401
from qfit.activities.domain.activity_query import (
    ActivityQuery,
    build_preview_lines,
    build_subset_string,
    filter_activities,
    format_duration,
    format_summary_text,
    sort_activities,
    summarize_activities,
)
from qfit.activities.domain.models import Activity


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

        self.assertEqual(summary.count, 3)
        self.assertEqual(summary.total_distance_km, 70.7)
        self.assertEqual(summary.detailed_count, 1)
        self.assertEqual(summary.by_type, {"GravelRide": 1, "Ride": 1, "Run": 1})
        self.assertEqual(summary.latest_date, "2026-03-20")
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

        self.assertIn("LOWER(REPLACE(REPLACE(REPLACE(\"activity_type\", ' ', ''), '-', ''), '_', '')) = 'ride'", subset)
        self.assertIn("LOWER(REPLACE(REPLACE(REPLACE(\"sport_type\", ' ', ''), '-', ''), '_', '')) = 'ride'", subset)
        self.assertIn('"distance_m" >= 10000.0', subset)
        self.assertIn('"distance_m" <= 50000.0', subset)
        self.assertIn("lower(coalesce(\"name\", '')) LIKE '%o''brien%'", subset)
        self.assertIn("lower(coalesce(\"activity_type\", '')) LIKE '%o''brien%'", subset)
        self.assertIn("lower(coalesce(\"sport_type\", '')) LIKE '%o''brien%'", subset)
        self.assertIn('"geometry_source" = \'stream\'', subset)

    def test_build_subset_string_search_spans_name_type_sport(self):
        query = ActivityQuery(search_text="ride")
        subset = build_subset_string(query)
        self.assertIn("lower(coalesce(\"name\", ''))", subset)
        self.assertIn("lower(coalesce(\"activity_type\", ''))", subset)
        self.assertIn("lower(coalesce(\"sport_type\", ''))", subset)
        self.assertIn(" OR ", subset)

    def test_build_subset_string_apostrophe_escaping(self):
        query = ActivityQuery(search_text="it's")
        subset = build_subset_string(query)
        self.assertIn("it''s", subset)
        self.assertNotIn("it's", subset)

    def test_summarize_activities_uses_sport_type_when_available(self):
        """sport_type is preferred over activity_type in by_type counts."""
        summary = summarize_activities(self.activities)

        # Activity 1: sport_type="GravelRide" overrides activity_type="Ride"
        self.assertIn("GravelRide", summary.by_type)
        self.assertNotIn("GravelRide", {"Ride": 2, "Run": 1})  # old (wrong) behaviour

    def test_build_preview_lines_uses_sport_type_label(self):
        """Preview lines show canonical (sport_type-preferred) label."""
        lines = build_preview_lines([self.activities[0]])

        self.assertIn("GravelRide", lines[0])
        self.assertNotIn("· Ride ·", lines[0])

    def test_format_helpers_return_human_readable_text(self):
        self.assertEqual(format_duration(3725), "1h 02m")
        self.assertIn("3 activities", format_summary_text(summarize_activities(self.activities)))


class FilterParityTests(unittest.TestCase):
    """Verify that filter_activities (Python) and build_subset_string (SQL) agree."""

    ACTIVITIES = [
        Activity(
            source="strava", source_activity_id="A",
            name="Morning Gravel Ride", activity_type="Ride", sport_type="GravelRide",
            start_date="2026-03-15T07:00:00Z", start_date_local="2026-03-15T08:00:00+01:00",
            distance_m=45000.0, geometry_source="stream",
        ),
        Activity(
            source="strava", source_activity_id="B",
            name="Lunch Run", activity_type="Run", sport_type="Run",
            start_date="2026-03-18T11:00:00Z", start_date_local="2026-03-18T12:00:00+01:00",
            distance_m=8000.0, geometry_source="summary_polyline",
        ),
        Activity(
            source="strava", source_activity_id="C",
            name="Evening Ride", activity_type="Ride", sport_type="Ride",
            start_date="2026-03-20T17:00:00Z", start_date_local="2026-03-20T18:00:00+01:00",
            distance_m=20000.0, geometry_source="stream",
        ),
        Activity(
            source="strava", source_activity_id="D",
            name="O'Brien's Trail Hike", activity_type="Hike", sport_type="Hike",
            start_date="2026-03-22T09:00:00Z", start_date_local="2026-03-22T10:00:00+01:00",
            distance_m=12000.0, geometry_source="summary_polyline",
        ),
    ]

    def _sql_filter(self, query):
        """Run build_subset_string against an in-memory SQLite table and return matching IDs."""
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE t ("
            "  source_activity_id TEXT, name TEXT, activity_type TEXT, sport_type TEXT,"
            "  start_date TEXT, start_date_local TEXT, distance_m REAL, geometry_source TEXT"
            ")"
        )
        for a in self.ACTIVITIES:
            conn.execute(
                "INSERT INTO t VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (a.source_activity_id, a.name, a.activity_type, a.sport_type,
                 a.start_date, a.start_date_local, a.distance_m, a.geometry_source),
            )
        subset = build_subset_string(query)
        sql = "SELECT source_activity_id FROM t"
        if subset:
            sql += f" WHERE {subset}"
        sql += " ORDER BY source_activity_id"
        rows = conn.execute(sql).fetchall()
        conn.close()
        return [r[0] for r in rows]

    def _python_filter(self, query):
        """Run filter_activities and return matching IDs."""
        results = filter_activities(self.ACTIVITIES, query)
        return sorted(a.source_activity_id for a in results)

    def test_parity_activity_type_filter(self):
        query = ActivityQuery(activity_type="Ride")
        self.assertEqual(self._python_filter(query), self._sql_filter(query))

    def test_parity_sport_type_filter(self):
        """Filtering by a sport_type value (e.g. 'GravelRide') works in both paths."""
        query = ActivityQuery(activity_type="GravelRide")
        python_ids = self._python_filter(query)
        sql_ids = self._sql_filter(query)
        self.assertEqual(python_ids, sql_ids)
        # Only activity A has sport_type="GravelRide"
        self.assertEqual(python_ids, ["A"])

    def test_parity_date_range_filter(self):
        query = ActivityQuery(date_from="2026-03-18", date_to="2026-03-20")
        self.assertEqual(self._python_filter(query), self._sql_filter(query))

    def test_parity_distance_range_filter(self):
        query = ActivityQuery(min_distance_km=10, max_distance_km=25)
        self.assertEqual(self._python_filter(query), self._sql_filter(query))

    def test_parity_search_text_across_name(self):
        query = ActivityQuery(search_text="gravel")
        self.assertEqual(self._python_filter(query), self._sql_filter(query))

    def test_parity_search_text_across_sport_type(self):
        query = ActivityQuery(search_text="GravelRide")
        self.assertEqual(self._python_filter(query), self._sql_filter(query))

    def test_parity_search_text_across_activity_type(self):
        query = ActivityQuery(search_text="Hike")
        self.assertEqual(self._python_filter(query), self._sql_filter(query))

    def test_parity_search_case_insensitive(self):
        query = ActivityQuery(search_text="LUNCH")
        self.assertEqual(self._python_filter(query), self._sql_filter(query))

    def test_parity_detailed_only(self):
        query = ActivityQuery(detailed_only=True)
        self.assertEqual(self._python_filter(query), self._sql_filter(query))

    def test_parity_combined_filters(self):
        query = ActivityQuery(
            activity_type="Ride",
            min_distance_km=20,
            search_text="ride",
            detailed_only=True,
        )
        self.assertEqual(self._python_filter(query), self._sql_filter(query))

    def test_parity_no_filters(self):
        query = ActivityQuery()
        self.assertEqual(self._python_filter(query), self._sql_filter(query))

    def test_sql_escaping_single_quote_in_search(self):
        """Apostrophe in search text is safely escaped in SQL."""
        query = ActivityQuery(search_text="O'Brien")
        # Should not raise and should match the hike activity
        sql_ids = self._sql_filter(query)
        python_ids = self._python_filter(query)
        self.assertEqual(python_ids, sql_ids)
        self.assertIn("D", sql_ids)

    def test_sql_escaping_single_quote_in_activity_type(self):
        """Apostrophe in activity_type filter is safely escaped and normalized."""
        query = ActivityQuery(activity_type="Rock'n'Roll")
        subset = build_subset_string(query)
        # normalize_activity_type strips apostrophes, so no escaping needed
        self.assertIn("rocknroll", subset)

    def test_sql_escaping_percent_in_search(self):
        """Percent sign in search text is passed through (LIKE wildcard)."""
        query = ActivityQuery(search_text="100%")
        subset = build_subset_string(query)
        self.assertIn("100%", subset)

    def test_empty_search_returns_all(self):
        """Empty search text matches everything."""
        query = ActivityQuery(search_text="")
        python_ids = self._python_filter(query)
        sql_ids = self._sql_filter(query)
        self.assertEqual(len(python_ids), 4)
        self.assertEqual(python_ids, sql_ids)

    def test_search_matches_partial_name(self):
        """Partial name match works in both Python and SQL."""
        query = ActivityQuery(search_text="Even")
        python_ids = self._python_filter(query)
        sql_ids = self._sql_filter(query)
        self.assertEqual(python_ids, sql_ids)
        self.assertIn("C", sql_ids)

    def test_deterministic_results(self):
        """Same query always returns the same results."""
        query = ActivityQuery(activity_type="Ride", search_text="ride")
        first = self._python_filter(query)
        second = self._python_filter(query)
        self.assertEqual(first, second)

    def test_parity_normalized_activity_type_variants(self):
        """Selecting a canonical label matches records whose raw labels differ only in formatting.

        Regression test: ordered_canonical_activity_labels collapses 'Trail Run'
        and 'TrailRun' via normalize_activity_type, but filter_activities and
        build_subset_string must also use normalized comparison so the surviving
        UI option still matches all equivalent records.
        """
        activities = [
            Activity(
                source="strava", source_activity_id="X",
                name="Morning trail", activity_type="Run", sport_type="Trail Run",
                start_date="2026-03-15T07:00:00Z", start_date_local="2026-03-15T08:00:00+01:00",
                distance_m=10000.0, geometry_source="stream",
            ),
            Activity(
                source="strava", source_activity_id="Y",
                name="Afternoon trail", activity_type="Run", sport_type="TrailRun",
                start_date="2026-03-16T14:00:00Z", start_date_local="2026-03-16T15:00:00+01:00",
                distance_m=12000.0, geometry_source="stream",
            ),
            Activity(
                source="strava", source_activity_id="Z",
                name="Dashed trail", activity_type="Run", sport_type="trail-run",
                start_date="2026-03-17T08:00:00Z", start_date_local="2026-03-17T09:00:00+01:00",
                distance_m=8000.0, geometry_source="summary_polyline",
            ),
        ]

        # The UI would show one of the variants (e.g. "Trail Run") after dedup.
        # All three must match regardless of which variant the user selects.
        for label in ("Trail Run", "TrailRun", "trail-run"):
            query = ActivityQuery(activity_type=label)
            py_ids = sorted(a.source_activity_id for a in filter_activities(activities, query))
            self.assertEqual(py_ids, ["X", "Y", "Z"], f"Python filter failed for label={label!r}")

        # SQL parity — use inline activities list for _sql_filter
        import sqlite3
        for label in ("Trail Run", "TrailRun", "trail-run"):
            query = ActivityQuery(activity_type=label)
            conn = sqlite3.connect(":memory:")
            conn.execute(
                "CREATE TABLE t ("
                "  source_activity_id TEXT, name TEXT, activity_type TEXT, sport_type TEXT,"
                "  start_date TEXT, start_date_local TEXT, distance_m REAL, geometry_source TEXT"
                ")"
            )
            for a in activities:
                conn.execute(
                    "INSERT INTO t VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (a.source_activity_id, a.name, a.activity_type, a.sport_type,
                     a.start_date, a.start_date_local, a.distance_m, a.geometry_source),
                )
            subset = build_subset_string(query)
            rows = conn.execute(
                f"SELECT source_activity_id FROM t WHERE {subset} ORDER BY source_activity_id"
            ).fetchall()
            conn.close()
            sql_ids = [r[0] for r in rows]
            self.assertEqual(sql_ids, ["X", "Y", "Z"], f"SQL filter failed for label={label!r}")
            self.assertEqual(py_ids, sql_ids, f"Python/SQL parity failed for label={label!r}")


if __name__ == "__main__":
    unittest.main()
