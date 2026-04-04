import unittest

from tests import _path  # noqa: F401
from qfit.visualization.application.temporal_config import (
    DEFAULT_TEMPORAL_MODE_LABEL,
    build_temporal_plan,
    describe_temporal_configuration,
    is_temporal_mode_enabled,
    temporal_mode_labels,
)


class TemporalConfigTests(unittest.TestCase):
    def test_temporal_mode_helpers(self):
        labels = temporal_mode_labels()

        self.assertEqual(labels[0], "Disabled")
        self.assertIn(DEFAULT_TEMPORAL_MODE_LABEL, labels)
        self.assertFalse(is_temporal_mode_enabled("Disabled"))
        self.assertTrue(is_temporal_mode_enabled(DEFAULT_TEMPORAL_MODE_LABEL))

    def test_build_temporal_plan_prefers_local_point_time_when_available(self):
        plan = build_temporal_plan(
            "activity_points",
            ["point_timestamp_utc", "point_timestamp_local", "distance_m"],
            "Local activity time",
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.field_name, "point_timestamp_local")
        self.assertEqual(plan.field_kind, "local")
        self.assertEqual(plan.expression, 'to_datetime("point_timestamp_local")')

    def test_build_temporal_plan_falls_back_to_utc_when_local_is_missing(self):
        plan = build_temporal_plan(
            "activity_tracks",
            ["start_date", "distance_m"],
            "Local activity time",
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.field_name, "start_date")
        self.assertEqual(plan.field_kind, "utc")

    def test_build_temporal_plan_returns_none_when_disabled_or_missing(self):
        self.assertIsNone(build_temporal_plan("activity_points", ["point_timestamp_utc"], "Disabled"))
        self.assertIsNone(build_temporal_plan("activity_points", ["distance_m"], "UTC time"))

    def test_describe_temporal_configuration_is_human_readable(self):
        point_plan = build_temporal_plan("activity_points", ["point_timestamp_utc"], "UTC time")
        message = describe_temporal_configuration([point_plan], "UTC time")

        self.assertIn("Temporal playback wired", message)
        self.assertIn("activity points (UTC)", message)
        self.assertEqual(
            describe_temporal_configuration([], "Disabled"),
            "Temporal playback disabled",
        )


if __name__ == "__main__":
    unittest.main()
