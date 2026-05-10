import unittest

from tests import _path  # noqa: F401
from qfit.visualization.application.temporal_config import (
    DEFAULT_TEMPORAL_MODE_LABEL,
    build_temporal_plan,
    describe_temporal_configuration,
    is_temporal_mode_enabled,
    normalize_temporal_mode,
    temporal_mode_labels,
)


class TemporalConfigTests(unittest.TestCase):
    def test_temporal_mode_helpers(self):
        labels = temporal_mode_labels()

        self.assertEqual(labels, ["Disabled"])
        self.assertEqual(DEFAULT_TEMPORAL_MODE_LABEL, "Disabled")
        self.assertEqual(normalize_temporal_mode("UTC time"), DEFAULT_TEMPORAL_MODE_LABEL)
        self.assertEqual(normalize_temporal_mode("Local activity time"), DEFAULT_TEMPORAL_MODE_LABEL)
        self.assertFalse(is_temporal_mode_enabled(DEFAULT_TEMPORAL_MODE_LABEL))

    def test_build_temporal_plan_returns_none_while_dynamic_temporal_is_disabled(self):
        self.assertIsNone(
            build_temporal_plan(
                "activity_points",
                ["point_timestamp_utc", "point_timestamp_local", "distance_m"],
                "Local activity time",
            )
        )
        self.assertIsNone(
            build_temporal_plan(
                "activity_tracks",
                ["start_date", "distance_m"],
                "UTC time",
            )
        )

    def test_describe_temporal_configuration_is_empty_when_no_temporal_controls_are_active(self):
        self.assertEqual(describe_temporal_configuration([], "Disabled"), "")


if __name__ == "__main__":
    unittest.main()
