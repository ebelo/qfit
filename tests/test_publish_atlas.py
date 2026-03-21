import unittest

from tests import _path  # noqa: F401
from qfit.publish_atlas import (
    DEFAULT_MIN_EXTENT_DEGREES,
    MIN_ALLOWED_ATLAS_MIN_EXTENT_DEGREES,
    WEB_MERCATOR_EPSG,
    activity_bounds,
    atlas_sort_key,
    build_atlas_page_plans,
    build_page_name,
    build_page_subtitle,
    ensure_minimum_extent,
    expand_bounds,
    format_distance_label,
    format_duration_label,
    lonlat_to_web_mercator,
    normalize_atlas_page_settings,
    web_mercator_to_lonlat,
)


class PublishAtlasTests(unittest.TestCase):
    def test_build_atlas_page_plans_prefers_stream_geometry_and_formats_labels(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "101",
                "name": "Morning Gravel Ride",
                "activity_type": "Ride",
                "start_date": "2026-03-18T07:10:00+00:00",
                "start_date_local": "2026-03-18T08:10:00+01:00",
                "distance_m": 42500,
                "moving_time_s": 7200,
                "geometry_source": "stream",
                "geometry_points": [(46.52, 6.62), (46.55, 6.7), (46.57, 6.74)],
            }
        ]

        plans = build_atlas_page_plans(records, margin_percent=10, min_extent_degrees=0.01)

        self.assertEqual(len(plans), 1)
        plan = plans[0]
        self.assertEqual(plan.geometry_source, "stream")
        self.assertEqual(plan.page_number, 1)
        self.assertEqual(plan.page_name, "2026-03-18 · Morning Gravel Ride")
        self.assertEqual(plan.page_subtitle, "Ride · 42.5 km · 2h 00m")
        self.assertEqual(plan.page_date, "2026-03-18")
        self.assertEqual(plan.page_distance_label, "42.5 km")
        self.assertEqual(plan.page_duration_label, "2h 00m")
        self.assertTrue(plan.page_sort_key.startswith("2026-03-18T08:10:00+01:00|morning gravel ride|strava|101"))
        self.assertGreater(plan.extent_width_deg, 0.12)
        self.assertGreater(plan.extent_height_deg, 0.05)
        self.assertGreater(plan.extent_width_m, 9000)
        self.assertGreater(plan.extent_height_m, 7000)

    def test_build_atlas_page_plans_sorts_chronologically_and_assigns_page_numbers(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "300",
                "name": "Evening Run",
                "activity_type": "Run",
                "start_date_local": "2026-03-19T18:30:00+01:00",
                "geometry_points": [(46.51, 6.62), (46.52, 6.63)],
            },
            {
                "source": "strava",
                "source_activity_id": "100",
                "name": "Morning Ride",
                "activity_type": "Ride",
                "start_date_local": "2026-03-18T08:10:00+01:00",
                "geometry_points": [(46.52, 6.62), (46.57, 6.74)],
            },
            {
                "source": "strava",
                "source_activity_id": "200",
                "name": "Morning Ride",
                "activity_type": "Ride",
                "start_date_local": "2026-03-18T08:10:00+01:00",
                "geometry_points": [(46.42, 6.52), (46.47, 6.54)],
            },
        ]

        plans = build_atlas_page_plans(records)

        self.assertEqual([plan.page_number for plan in plans], [1, 2, 3])
        self.assertEqual(
            [(plan.source_activity_id, plan.page_name) for plan in plans],
            [
                ("100", "2026-03-18 · Morning Ride"),
                ("200", "2026-03-18 · Morning Ride"),
                ("300", "2026-03-19 · Evening Run"),
            ],
        )

    def test_build_atlas_page_plans_respects_custom_publish_settings(self):
        records = [
            {
                "name": "Lunch Walk",
                "activity_type": "Walk",
                "geometry_points": [(46.5000, 6.6000), (46.5002, 6.6002)],
            }
        ]

        default_plan = build_atlas_page_plans(records)[0]
        custom_plan = build_atlas_page_plans(records, margin_percent=25, min_extent_degrees=0.02)[0]

        self.assertGreater(custom_plan.extent_width_deg, default_plan.extent_width_deg)
        self.assertGreater(custom_plan.extent_height_deg, default_plan.extent_height_deg)
        self.assertAlmostEqual(custom_plan.extent_width_deg, 0.03)
        self.assertAlmostEqual(custom_plan.extent_height_deg, 0.03)
        self.assertGreater(custom_plan.extent_width_m, default_plan.extent_width_m)
        self.assertGreater(custom_plan.extent_height_m, default_plan.extent_height_m)

    def test_normalize_atlas_page_settings_clamps_invalid_values(self):
        settings = normalize_atlas_page_settings(margin_percent=-5, min_extent_degrees=0)

        self.assertEqual(settings.margin_percent, 0.0)
        self.assertEqual(settings.min_extent_degrees, MIN_ALLOWED_ATLAS_MIN_EXTENT_DEGREES)

    def test_normalize_atlas_page_settings_uses_defaults_for_missing_values(self):
        settings = normalize_atlas_page_settings(margin_percent=None, min_extent_degrees=None)

        self.assertEqual(settings.margin_percent, 8.0)
        self.assertEqual(settings.min_extent_degrees, DEFAULT_MIN_EXTENT_DEGREES)

    def test_activity_bounds_falls_back_to_start_end_coordinates(self):
        bounds, geometry_source = activity_bounds(
            {
                "geometry_source": None,
                "start_lat": 46.5,
                "start_lon": 6.6,
                "end_lat": 46.6,
                "end_lon": 6.8,
            }
        )

        self.assertEqual(geometry_source, "start_end")
        self.assertEqual(bounds, (6.6, 46.5, 6.8, 46.6))

    def test_ensure_minimum_extent_expands_tiny_tracks(self):
        bounds = ensure_minimum_extent((6.7, 46.5, 6.7, 46.5), min_extent_degrees=DEFAULT_MIN_EXTENT_DEGREES)

        self.assertAlmostEqual(bounds[2] - bounds[0], DEFAULT_MIN_EXTENT_DEGREES)
        self.assertAlmostEqual(bounds[3] - bounds[1], DEFAULT_MIN_EXTENT_DEGREES)

    def test_expand_bounds_applies_margin_after_minimum_extent(self):
        expanded = expand_bounds((6.7, 46.5, 6.7, 46.5), margin_percent=20, min_extent_degrees=0.01)

        self.assertAlmostEqual(expanded[2] - expanded[0], 0.014)
        self.assertAlmostEqual(expanded[3] - expanded[1], 0.014)

    def test_page_helpers_handle_missing_optional_values(self):
        record = {
            "name": "Recovery Walk",
            "activity_type": "Walk",
            "start_date": "2026-03-11T18:20:00+00:00",
        }

        self.assertEqual(build_page_name(record), "2026-03-11 · Recovery Walk")
        self.assertEqual(build_page_subtitle(record), "Walk")
        self.assertIsNone(format_distance_label(None))
        self.assertIsNone(format_duration_label(None))

    def test_atlas_sort_key_normalizes_missing_values(self):
        key = atlas_sort_key({"name": "  Lunch   Walk  "})

        self.assertEqual(key, "9999-12-31T23:59:59|lunch walk||")

    def test_web_mercator_helpers_round_trip_reasonably(self):
        x, y = lonlat_to_web_mercator(6.6323, 46.5197)
        lon, lat = web_mercator_to_lonlat(x, y)

        self.assertEqual(WEB_MERCATOR_EPSG, "EPSG:3857")
        self.assertAlmostEqual(lon, 6.6323, places=5)
        self.assertAlmostEqual(lat, 46.5197, places=5)

    def test_web_mercator_helpers_clamp_polar_latitudes(self):
        _, y = lonlat_to_web_mercator(0.0, 90.0)
        _, lat = web_mercator_to_lonlat(0.0, y)

        self.assertLessEqual(abs(lat), 85.05112878)


if __name__ == "__main__":
    unittest.main()
