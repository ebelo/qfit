import unittest

from tests import _path  # noqa: F401
from qfit.publish_atlas import (
    DEFAULT_MIN_EXTENT_DEGREES,
    MIN_ALLOWED_ATLAS_MIN_EXTENT_DEGREES,
    MIN_ALLOWED_ATLAS_TARGET_ASPECT_RATIO,
    WEB_MERCATOR_EPSG,
    activity_bounds,
    atlas_sort_key,
    build_atlas_document_summary,
    build_atlas_page_plans,
    build_cover_summary,
    build_date_range_label,
    build_page_name,
    build_page_profile_summary,
    build_page_stats_summary,
    build_page_subtitle,
    build_page_toc_label,
    build_profile_summary,
    ensure_minimum_extent,
    expand_bounds,
    fit_bounds_to_target_aspect_ratio,
    format_altitude_range_label,
    format_distance_label,
    format_duration_label,
    format_elevation_label,
    format_pace_label,
    format_speed_label,
    lonlat_bounds_to_web_mercator,
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
                "total_elevation_gain_m": 640,
                "average_speed_mps": 5.9027777778,
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
        self.assertEqual(plan.page_toc_label, "2026-03-18 · Morning Gravel Ride · 42.5 km · 2h 00m")
        self.assertEqual(plan.page_distance_label, "42.5 km")
        self.assertEqual(plan.page_duration_label, "2h 00m")
        self.assertEqual(plan.page_average_speed_label, "21.3 km/h")
        self.assertIsNone(plan.page_average_pace_label)
        self.assertEqual(plan.page_elevation_gain_label, "640 m")
        self.assertEqual(plan.page_stats_summary, "42.5 km · 2h 00m · 21.3 km/h · ↑ 640 m")
        self.assertEqual(plan.document_activity_count, 1)
        self.assertEqual(plan.document_date_range_label, "2026-03-18")
        self.assertEqual(plan.document_total_distance_label, "42.5 km")
        self.assertEqual(plan.document_total_duration_label, "2h 00m")
        self.assertEqual(plan.document_total_elevation_gain_label, "640 m")
        self.assertEqual(plan.document_activity_types_label, "Ride")
        self.assertEqual(plan.document_cover_summary, "1 activity · 2026-03-18 · 42.5 km · 2h 00m · ↑ 640 m · Ride")
        self.assertFalse(plan.profile_available)
        self.assertEqual(plan.profile_point_count, 0)
        self.assertIsNone(plan.profile_distance_m)
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
        self.assertTrue(all(plan.document_activity_count == 3 for plan in plans))
        self.assertTrue(all(plan.document_date_range_label == "2026-03-18 → 2026-03-19" for plan in plans))

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

    def test_build_atlas_page_plans_can_fit_web_mercator_target_aspect_ratio(self):
        records = [
            {
                "name": "River Ride",
                "activity_type": "Ride",
                "geometry_points": [(46.5000, 6.6000), (46.5080, 6.6030)],
            }
        ]

        plan = build_atlas_page_plans(records, target_aspect_ratio=2.0)[0]

        self.assertAlmostEqual(plan.extent_width_m / plan.extent_height_m, 2.0, places=3)
        self.assertGreater(plan.extent_width_m, 0)
        self.assertGreater(plan.extent_height_m, 0)

    def test_build_atlas_page_plans_formats_run_pace_labels_for_layouts(self):
        records = [
            {
                "name": "Lunch Run",
                "activity_type": "Run",
                "distance_m": 10100,
                "moving_time_s": 3000,
                "average_speed_mps": 3.3666666667,
                "total_elevation_gain_m": 85,
                "geometry_points": [(46.5000, 6.6000), (46.5100, 6.6200)],
            }
        ]

        plan = build_atlas_page_plans(records)[0]

        self.assertEqual(plan.page_toc_label, "Lunch Run · 10.1 km · 50m 00s")
        self.assertEqual(plan.page_average_speed_label, "12.1 km/h")
        self.assertEqual(plan.page_average_pace_label, "4m 57s/km")
        self.assertEqual(plan.page_elevation_gain_label, "85 m")
        self.assertEqual(plan.page_stats_summary, "10.1 km · 50m 00s · 4m 57s/km · ↑ 85 m")

    def test_build_atlas_page_plans_includes_route_profile_metadata_when_stream_metrics_are_available(self):
        records = [
            {
                "name": "Alpine Ride",
                "activity_type": "Ride",
                "distance_m": 34000,
                "geometry_points": [(46.5000, 6.6000), (46.5300, 6.6600)],
                "details_json": {
                    "stream_metrics": {
                        "distance": [0, 1000, 2000, 3000],
                        "altitude": [500, 525, 510, 560],
                    }
                },
            }
        ]

        plan = build_atlas_page_plans(records)[0]

        self.assertTrue(plan.profile_available)
        self.assertEqual(plan.page_profile_summary, "3.0 km · 500–560 m · relief 60 m · ↑ 75 m · ↓ 15 m")
        self.assertEqual(plan.profile_point_count, 4)
        self.assertEqual(plan.profile_distance_m, 3000)
        self.assertEqual(plan.profile_distance_label, "3.0 km")
        self.assertEqual(plan.profile_min_altitude_m, 500)
        self.assertEqual(plan.profile_max_altitude_m, 560)
        self.assertEqual(plan.profile_altitude_range_label, "500–560 m")
        self.assertEqual(plan.profile_relief_m, 60)
        self.assertEqual(plan.profile_elevation_gain_m, 75)
        self.assertEqual(plan.profile_elevation_gain_label, "75 m")
        self.assertEqual(plan.profile_elevation_loss_m, 15)
        self.assertEqual(plan.profile_elevation_loss_label, "15 m")

    def test_build_profile_summary_ignores_invalid_or_incomplete_stream_metrics(self):
        summary = build_profile_summary(
            {
                "details_json": {
                    "stream_metrics": {
                        "distance": [0, None, 500],
                        "altitude": [400, 405, None],
                    }
                }
            }
        )

        self.assertFalse(summary.available)
        self.assertEqual(summary.point_count, 0)
        self.assertIsNone(summary.distance_m)

    def test_build_atlas_document_summary_aggregates_cover_ready_metrics(self):
        summary = build_atlas_document_summary(
            [
                {
                    "activity_type": "Ride",
                    "start_date_local": "2026-03-18T08:10:00+01:00",
                    "distance_m": 42500,
                    "moving_time_s": 7200,
                    "total_elevation_gain_m": 640,
                },
                {
                    "activity_type": "Run",
                    "start_date_local": "2026-03-19T12:00:00+01:00",
                    "distance_m": 10100,
                    "moving_time_s": 3000,
                    "total_elevation_gain_m": 85,
                },
                {
                    "activity_type": "Ride",
                    "start_date_local": "2026-03-20T18:45:00+01:00",
                    "distance_m": 30000,
                    "moving_time_s": 5400,
                    "total_elevation_gain_m": 420,
                },
            ]
        )

        self.assertEqual(summary.activity_count, 3)
        self.assertEqual(summary.activity_date_start, "2026-03-18")
        self.assertEqual(summary.activity_date_end, "2026-03-20")
        self.assertEqual(summary.date_range_label, "2026-03-18 → 2026-03-20")
        self.assertEqual(summary.total_distance_m, 82600)
        self.assertEqual(summary.total_distance_label, "82.6 km")
        self.assertEqual(summary.total_moving_time_s, 15600)
        self.assertEqual(summary.total_duration_label, "4h 20m")
        self.assertEqual(summary.total_elevation_gain_m, 1145)
        self.assertEqual(summary.total_elevation_gain_label, "1145 m")
        self.assertEqual(summary.activity_types_label, "Ride, Run")
        self.assertEqual(
            summary.cover_summary,
            "3 activities · 2026-03-18 → 2026-03-20 · 82.6 km · 4h 20m · ↑ 1145 m · Ride, Run",
        )

    def test_build_cover_summary_handles_minimal_inputs(self):
        summary = build_atlas_document_summary([{}])

        self.assertEqual(summary.activity_count, 1)
        self.assertEqual(summary.cover_summary, "1 activity")
        self.assertEqual(build_date_range_label("2026-03-18", "2026-03-18"), "2026-03-18")
        self.assertEqual(build_date_range_label("2026-03-18", "2026-03-20"), "2026-03-18 → 2026-03-20")
        self.assertIsNone(build_cover_summary(build_atlas_document_summary([])))

    def test_normalize_atlas_page_settings_clamps_invalid_values(self):
        settings = normalize_atlas_page_settings(margin_percent=-5, min_extent_degrees=0, target_aspect_ratio=0.05)

        self.assertEqual(settings.margin_percent, 0.0)
        self.assertEqual(settings.min_extent_degrees, MIN_ALLOWED_ATLAS_MIN_EXTENT_DEGREES)
        self.assertEqual(settings.target_aspect_ratio, MIN_ALLOWED_ATLAS_TARGET_ASPECT_RATIO)

    def test_normalize_atlas_page_settings_uses_defaults_for_missing_values(self):
        settings = normalize_atlas_page_settings(margin_percent=None, min_extent_degrees=None, target_aspect_ratio=None)

        self.assertEqual(settings.margin_percent, 8.0)
        self.assertEqual(settings.min_extent_degrees, DEFAULT_MIN_EXTENT_DEGREES)
        self.assertIsNone(settings.target_aspect_ratio)

    def test_fit_bounds_to_target_aspect_ratio_expands_shorter_dimension_in_web_mercator(self):
        bounds = fit_bounds_to_target_aspect_ratio(6.6, 46.5, 6.61, 46.53, target_aspect_ratio=1.0)
        min_x, min_y, max_x, max_y = lonlat_bounds_to_web_mercator(*bounds)

        self.assertAlmostEqual(max_x - min_x, max_y - min_y, places=3)

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
        self.assertEqual(build_page_toc_label(record), "2026-03-11 · Recovery Walk")
        self.assertIsNone(build_page_stats_summary(record))
        self.assertIsNone(build_page_profile_summary(record))
        self.assertIsNone(format_distance_label(None))
        self.assertIsNone(format_duration_label(None))
        self.assertIsNone(format_elevation_label(None))
        self.assertIsNone(format_altitude_range_label(None, 550))

    def test_profile_label_helpers_round_values_for_layout_text(self):
        self.assertEqual(format_elevation_label(123.6), "124 m")
        self.assertEqual(format_altitude_range_label(501.2, 559.8), "501–560 m")
        self.assertEqual(format_speed_label(5.0), "18.0 km/h")
        self.assertEqual(format_pace_label(10000, 3000, activity_type="Run"), "5m 00s/km")
        self.assertIsNone(format_pace_label(10000, 3000, activity_type="Ride"))
        self.assertEqual(
            build_page_stats_summary({
                "activity_type": "Ride",
                "distance_m": 42500,
                "moving_time_s": 7200,
                "average_speed_mps": 5.9027777778,
                "total_elevation_gain_m": 640,
            }),
            "42.5 km · 2h 00m · 21.3 km/h · ↑ 640 m",
        )
        self.assertEqual(
            build_page_toc_label({
                "name": "Morning Gravel Ride",
                "start_date_local": "2026-03-18T08:10:00+01:00",
                "distance_m": 42500,
                "moving_time_s": 7200,
            }),
            "2026-03-18 · Morning Gravel Ride · 42.5 km · 2h 00m",
        )
        self.assertEqual(
            build_page_profile_summary({
                "details_json": {
                    "stream_metrics": {
                        "distance": [0, 1000, 2000, 3000],
                        "altitude": [500, 525, 510, 560],
                    }
                }
            }),
            "3.0 km · 500–560 m · relief 60 m · ↑ 75 m · ↓ 15 m",
        )

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
