import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401

from qfit.analysis.application.analysis_models import RunAnalysisRequest
from qfit.analysis.application.power_output_analysis import (
    POWER_OUTPUT_CLASSES,
    POWER_OUTPUT_LEGEND,
    POWER_OUTPUT_MODE,
    PowerOutputAnalysisPlan,
    PowerOutputLayerPlan,
    build_activity_power_output_line_segments,
    build_activity_power_output_segments,
    build_power_output_analysis_result,
    build_power_output_analysis_plan,
    build_power_output_segments,
    build_power_output_status,
    power_output_class_for_watts,
    run_power_output_analysis,
)


class _Field:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _Layer:
    def __init__(self, *, geometry="LineString", fields=()):
        self._geometry = geometry
        self._fields = tuple(_Field(name) for name in fields)

    def geometryType(self):
        return self._geometry

    def fields(self):
        return self._fields


class _FeatureSample:
    def __init__(self, values, *, geometry=None):
        self._values = values
        self._geometry = geometry

    def __getitem__(self, key):
        return self._values[key]

    def geometry(self):
        return self._geometry


class _Point:
    def __init__(self, x, y):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


class _Geometry:
    def __init__(self, x, y):
        self._point = _Point(x, y)

    def isEmpty(self):
        return False

    def asPoint(self):
        return self._point


class _FeatureLayer:
    def __init__(self, features, *, fields=()):
        self._features = tuple(features)
        self._fields = tuple(_Field(name) for name in fields)

    def getFeatures(self):
        return iter(self._features)

    def fields(self):
        return self._fields


class PowerOutputAnalysisTests(unittest.TestCase):
    def test_legend_uses_documented_deterministic_watts_classes(self):
        self.assertEqual(POWER_OUTPUT_MODE, "Power output lines")
        self.assertEqual(
            POWER_OUTPUT_LEGEND,
            (
                "Recovery (< 100 W)",
                "Endurance (100 W to 180 W)",
                "Tempo (180 W to 260 W)",
                "Threshold (260 W to 340 W)",
                "Anaerobic (>= 340 W)",
            ),
        )
        self.assertEqual(
            [power_class.color_hex for power_class in POWER_OUTPUT_CLASSES],
            ["#2c7fb8", "#1a9850", "#fee08b", "#f46d43", "#d73027"],
        )

    def test_classifies_watts_boundaries_deterministically(self):
        self.assertEqual(power_output_class_for_watts(99.9).key, "recovery")
        self.assertEqual(power_output_class_for_watts(100.0).key, "endurance")
        self.assertEqual(power_output_class_for_watts(180.0).key, "tempo")
        self.assertEqual(power_output_class_for_watts(260.0).key, "threshold")
        self.assertEqual(power_output_class_for_watts(340.0).key, "anaerobic")

    def test_builds_power_segments_from_ordered_samples(self):
        segments = build_power_output_segments(
            (
                {"stream_distance_m": 0, "watts": 80},
                {"stream_distance_m": 100, "watts": 210},
                {"stream_distance_m": 200, "watts": 355},
            )
        )

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].start_distance_m, 0.0)
        self.assertEqual(segments[0].end_distance_m, 100.0)
        self.assertEqual(segments[0].watts, 210.0)
        self.assertEqual(segments[0].power_class.key, "tempo")
        self.assertEqual(segments[1].power_class.key, "anaerobic")

    def test_builds_activity_segments_per_activity_key(self):
        segments = build_activity_power_output_segments(
            _FeatureLayer(
                (
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 0,
                            "watts": 90,
                        }
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 100,
                            "watts": 220,
                        }
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-2",
                            "stream_distance_m": 0,
                            "watts": 120,
                        }
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-2",
                            "stream_distance_m": 100,
                            "watts": 300,
                        }
                    ),
                )
            )
        )

        self.assertEqual(
            tuple(segment.power_class.key for segment in segments),
            ("tempo", "threshold"),
        )

    def test_builds_activity_line_segments_from_point_sample_geometry(self):
        segments = build_activity_power_output_line_segments(
            _FeatureLayer(
                (
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 0,
                            "watts": 80,
                        },
                        geometry=_Geometry(6.6, 46.5),
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 100,
                            "watts": 210,
                        },
                        geometry=_Geometry(6.7, 46.6),
                    ),
                )
            )
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].layer_key, "activity_tracks")
        self.assertEqual(segments[0].source_id, "a-1")
        self.assertEqual(segments[0].start_xy, (6.6, 46.5))
        self.assertEqual(segments[0].end_xy, (6.7, 46.6))
        self.assertEqual(segments[0].power_class.key, "tempo")

    def test_line_segment_builders_do_not_connect_across_sample_groups(self):
        segments = build_activity_power_output_line_segments(
            _FeatureLayer(
                (
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 0,
                            "watts": 110,
                        },
                        geometry=_Geometry(6.6, 46.5),
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-2",
                            "stream_distance_m": 100,
                            "watts": 250,
                        },
                        geometry=_Geometry(6.7, 46.6),
                    ),
                )
            )
        )

        self.assertEqual(segments, ())

    def test_result_classifies_segments_for_eligible_activity_tracks(self):
        result = build_power_output_analysis_result(
            activities_layer=_Layer(fields=("name",)),
            points_layer=_FeatureLayer(
                (
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 0,
                            "watts": 90,
                        }
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 100,
                            "watts": 210,
                        }
                    ),
                ),
                fields=("stream_distance_m", "watts"),
            ),
        )

        self.assertEqual(result.segment_count, 1)
        self.assertEqual(result.layers[0].segments[0].power_class.key, "tempo")
        self.assertEqual(
            build_power_output_status(result),
            (
                "Power output line analysis classified activity tracks "
                "(1 segment)."
            ),
        )

    def test_result_reports_when_eligible_layers_have_no_segments(self):
        result = build_power_output_analysis_result(
            activities_layer=_Layer(fields=("name",)),
            points_layer=_FeatureLayer(
                (),
                fields=("stream_distance_m", "watts"),
            ),
        )

        self.assertEqual(result.segment_count, 0)
        self.assertEqual(
            build_power_output_status(result),
            (
                "Power output line analysis found eligible activity tracks, "
                "but no "
                "power segments could be classified."
            ),
        )

    def test_analysis_result_rejects_unhandled_plan_layer_keys(self):
        with patch(
            "qfit.analysis.application.power_output_analysis."
            "build_power_output_analysis_plan",
            return_value=PowerOutputAnalysisPlan(
                layers=(
                    PowerOutputLayerPlan(
                        key="future_layer",
                        label="future layer",
                        enabled=True,
                    ),
                )
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Unsupported power-output layer key: future_layer",
            ):
                build_power_output_analysis_result()

    def test_segments_skip_invalid_or_non_forward_samples_and_recover(self):
        segments = build_power_output_segments(
            (
                {"stream_distance_m": 0, "watts": 90},
                {"stream_distance_m": 0, "watts": 120},
                {"stream_distance_m": "bad", "watts": 180},
                {"stream_distance_m": 100, "watts": None},
                {"stream_distance_m": 200, "watts": 260},
            )
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].start_distance_m, 0.0)
        self.assertEqual(segments[0].end_distance_m, 200.0)
        self.assertEqual(segments[0].power_class.key, "threshold")

    def test_plan_targets_only_eligible_activity_line_layers(self):
        plan = build_power_output_analysis_plan(
            activities_layer=_Layer(fields=("name",)),
            points_layer=_Layer(fields=("watts", "stream_distance_m")),
        )

        self.assertEqual(
            tuple(layer.key for layer in plan.enabled_layers),
            ("activity_tracks",),
        )
        self.assertEqual(
            plan.layers[0].source_fields,
            ("watts", "stream_distance_m"),
        )
        self.assertEqual(
            build_power_output_status(plan),
            "Power output line analysis ready for activity tracks.",
        )

    def test_plan_reports_missing_power_point_samples(self):
        plan = build_power_output_analysis_plan(
            activities_layer=_Layer(fields=("name",)),
            points_layer=_Layer(fields=("stream_distance_m",)),
        )

        self.assertEqual(plan.enabled_layers, ())
        self.assertIn(
            "watts and stream_distance_m",
            plan.layers[0].blocked_reason,
        )

    def test_plan_rejects_non_line_targets(self):
        plan = build_power_output_analysis_plan(
            activities_layer=_Layer(geometry="Polygon", fields=("name",)),
            points_layer=_Layer(fields=("watts", "stream_distance_m")),
        )

        self.assertEqual(plan.enabled_layers, ())
        self.assertIn(
            "activity track target is not a line layer",
            plan.layers[0].blocked_reason,
        )

    def test_route_layer_kwargs_are_accepted_but_ignored(self):
        plan = build_power_output_analysis_plan(
            activities_layer=None,
            route_tracks_layer=object(),
            route_points_layer=object(),
            route_profile_samples_layer=object(),
        )

        self.assertEqual(plan.enabled_layers, ())

    def test_unexpected_kwargs_are_rejected(self):
        with self.assertRaisesRegex(
            TypeError,
            "Unexpected power-output layer kwargs",
        ):
            build_power_output_analysis_plan(extra_layer=object())

    def test_run_power_output_analysis_builds_status_and_layer(self):
        request = RunAnalysisRequest(
            analysis_mode=POWER_OUTPUT_MODE,
            activities_layer=_Layer(fields=("name",)),
            points_layer=_FeatureLayer(
                (
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 0,
                            "watts": 90,
                        }
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 100,
                            "watts": 210,
                        }
                    ),
                ),
                fields=("watts", "stream_distance_m"),
            ),
        )

        with patch(
            "qfit.analysis.application.power_output_analysis."
            "_build_power_output_layer",
            return_value=("power-layer", ("segment",)),
        ):
            result = run_power_output_analysis(request)

        self.assertEqual(
            result.status,
            (
                "Power output line analysis classified activity tracks "
                "(1 segment)."
            ),
        )
        self.assertEqual(result.layer, "power-layer")


if __name__ == "__main__":
    unittest.main()
