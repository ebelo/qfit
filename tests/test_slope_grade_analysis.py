import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401

from qfit.analysis.application.analysis_models import RunAnalysisRequest
from qfit.analysis.application.slope_grade_analysis import (
    SLOPE_GRADE_CLASSES,
    SLOPE_GRADE_LEGEND,
    SLOPE_GRADE_MODE,
    SlopeGradeAnalysisPlan,
    SlopeGradeAnalysisResult,
    SlopeGradeLayerPlan,
    SlopeGradeLayerResult,
    build_activity_slope_grade_line_segments,
    build_activity_slope_grade_segments,
    build_slope_grade_analysis_result,
    build_slope_grade_analysis_plan,
    build_slope_grade_segments,
    build_slope_grade_status,
    run_slope_grade_analysis,
    slope_grade_class_for_percent,
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


class _WkbLayer(_Layer):
    def __init__(self, *, wkb_type, fields=()):
        super().__init__(geometry=None, fields=fields)
        self._wkb_type = wkb_type

    def wkbType(self):
        return self._wkb_type


class _Sample:
    def __init__(self, *, stream_distance_m, altitude_m=None, grade_smooth_pct=None):
        self.stream_distance_m = stream_distance_m
        self.altitude_m = altitude_m
        self.grade_smooth_pct = grade_smooth_pct


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


class SlopeGradeAnalysisTests(unittest.TestCase):
    def test_legend_uses_documented_deterministic_percent_grade_classes(self):
        self.assertEqual(SLOPE_GRADE_MODE, "Slope grade lines")
        self.assertEqual(
            SLOPE_GRADE_LEGEND,
            (
                "Steep descent (< -8%)",
                "Descent (-8% to -3%)",
                "Flat / rolling (-3% to +3%)",
                "Climb (+3% to +8%)",
                "Steep climb (≥ +8%)",
            ),
        )
        self.assertEqual(
            [grade_class.color_hex for grade_class in SLOPE_GRADE_CLASSES],
            ["#2c7fb8", "#7fcdbb", "#f0f0f0", "#fdae61", "#d7191c"],
        )

    def test_classifies_percent_grade_boundaries_deterministically(self):
        self.assertEqual(slope_grade_class_for_percent(-9.0).key, "steep_descent")
        self.assertEqual(slope_grade_class_for_percent(-8.0).key, "descent")
        self.assertEqual(slope_grade_class_for_percent(-3.0).key, "flat")
        self.assertEqual(slope_grade_class_for_percent(3.0).key, "climb")
        self.assertEqual(slope_grade_class_for_percent(8.0).key, "steep_climb")

    def test_builds_route_segments_from_elevation_distance_samples(self):
        segments = build_slope_grade_segments(
            (
                {"distance_m": 0, "altitude_m": 100},
                {"distance_m": 100, "altitude_m": 104},
                {"distance_m": 200, "altitude_m": 94},
            )
        )

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].start_distance_m, 0.0)
        self.assertEqual(segments[0].end_distance_m, 100.0)
        self.assertAlmostEqual(segments[0].grade_percent, 4.0)
        self.assertEqual(segments[0].grade_class.key, "climb")
        self.assertAlmostEqual(segments[1].grade_percent, -10.0)
        self.assertEqual(segments[1].grade_class.key, "steep_descent")

    def test_builds_activity_segments_from_existing_smoothed_grade_samples(self):
        segments = build_slope_grade_segments(
            (
                _Sample(stream_distance_m=0, grade_smooth_pct=0.0),
                _Sample(stream_distance_m=20, grade_smooth_pct="2.5"),
                _Sample(stream_distance_m=40, grade_smooth_pct="9.1"),
            ),
            distance_field="stream_distance_m",
            elevation_field=None,
            grade_field="grade_smooth_pct",
        )

        self.assertEqual(
            tuple(segment.grade_class.key for segment in segments),
            ("flat", "steep_climb"),
        )
        self.assertEqual(segments[0].grade_percent, 2.5)
        self.assertEqual(segments[1].grade_percent, 9.1)

    def test_builds_segments_from_feature_item_access_rows(self):
        segments = build_slope_grade_segments(
            (
                _FeatureSample({"distance_m": 0, "altitude_m": 100}),
                _FeatureSample({"distance_m": 50, "altitude_m": 95}),
            )
        )

        self.assertEqual(len(segments), 1)
        self.assertAlmostEqual(segments[0].grade_percent, -10.0)
        self.assertEqual(segments[0].grade_class.key, "steep_descent")

    def test_builds_activity_segments_from_point_layer_features(self):
        segments = build_activity_slope_grade_segments(
            _FeatureLayer(
                (
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 0,
                            "grade_smooth_pct": 0.0,
                        }
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 50,
                            "grade_smooth_pct": -4.0,
                        }
                    ),
                )
            )
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].grade_class.key, "descent")

    def test_builds_activity_segments_per_activity_key(self):
        segments = build_activity_slope_grade_segments(
            _FeatureLayer(
                (
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 0,
                            "grade_smooth_pct": 4.0,
                        }
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 100,
                            "grade_smooth_pct": 4.0,
                        }
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-2",
                            "stream_distance_m": 0,
                            "grade_smooth_pct": -4.0,
                        }
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-2",
                            "stream_distance_m": 100,
                            "grade_smooth_pct": -4.0,
                        }
                    ),
                )
            )
        )

        self.assertEqual(
            tuple(segment.grade_class.key for segment in segments),
            ("climb", "descent"),
        )

    def test_layer_segment_builders_ignore_missing_layers(self):
        self.assertEqual(build_activity_slope_grade_segments(None), ())

    def test_builds_activity_line_segments_from_point_sample_geometry(self):
        segments = build_activity_slope_grade_line_segments(
            _FeatureLayer(
                (
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 0,
                            "grade_smooth_pct": 0.0,
                        },
                        geometry=_Geometry(6.6, 46.5),
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 100,
                            "grade_smooth_pct": 4.0,
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
        self.assertEqual(segments[0].grade_class.key, "climb")

    def test_line_segment_builders_do_not_connect_across_sample_groups(self):
        segments = build_activity_slope_grade_line_segments(
            _FeatureLayer(
                (
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 0,
                            "grade_smooth_pct": 4.0,
                        },
                        geometry=_Geometry(6.6, 46.5),
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-2",
                            "stream_distance_m": 100,
                            "grade_smooth_pct": -4.0,
                        },
                        geometry=_Geometry(6.7, 46.6),
                    ),
                )
            )
        )

        self.assertEqual(segments, ())

    def test_analysis_result_classifies_segments_for_eligible_activity_line_targets(self):
        result = build_slope_grade_analysis_result(
            activities_layer=_Layer(fields=("name",)),
            route_tracks_layer=_Layer(fields=("name",)),
            route_profile_samples_layer=_FeatureLayer(
                (
                    _FeatureSample(
                        {"sample_group_index": 1, "distance_m": 0, "altitude_m": 100}
                    ),
                    _FeatureSample(
                        {"sample_group_index": 1, "distance_m": 100, "altitude_m": 91}
                    ),
                ),
                fields=("distance_m", "altitude_m"),
            ),
            points_layer=_FeatureLayer(
                (
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 0,
                            "grade_smooth_pct": 0,
                        }
                    ),
                    _FeatureSample(
                        {
                            "source": "strava",
                            "source_activity_id": "a-1",
                            "stream_distance_m": 100,
                            "grade_smooth_pct": 4,
                        }
                    ),
                ),
                fields=("stream_distance_m", "grade_smooth_pct"),
            ),
        )

        self.assertEqual(result.segment_count, 1)
        self.assertEqual(
            tuple(layer.segment_count for layer in result.layers),
            (1,),
        )
        self.assertEqual(
            tuple(layer.segments[0].grade_class.key for layer in result.layers),
            ("climb",),
        )
        self.assertEqual(
            build_slope_grade_status(result),
            "Slope grade line analysis classified activity tracks (1 segment).",
        )

    def test_analysis_result_reports_when_eligible_layers_have_no_segments(self):
        result = build_slope_grade_analysis_result(
            activities_layer=_Layer(fields=("name",)),
            points_layer=_FeatureLayer(
                (),
                fields=("stream_distance_m", "grade_smooth_pct"),
            ),
        )

        self.assertEqual(result.segment_count, 0)
        self.assertEqual(
            build_slope_grade_status(result),
            (
                "Slope grade line analysis found eligible activity tracks, but no "
                "grade segments could be classified."
            ),
        )

    def test_status_only_reports_layers_with_classified_segments(self):
        result = SlopeGradeAnalysisResult(
            plan=SlopeGradeAnalysisPlan(layers=()),
            layers=(
                SlopeGradeLayerResult(
                    key="activity_tracks",
                    label="activity tracks",
                    segments=(
                        build_slope_grade_segments(
                            (
                                {"distance_m": 0, "altitude_m": 100},
                                {"distance_m": 100, "altitude_m": 104},
                            )
                        )[0],
                    ),
                ),
                SlopeGradeLayerResult(
                    key="empty_layer",
                    label="empty layer",
                    segments=(),
                ),
            ),
        )

        self.assertEqual(
            build_slope_grade_status(result),
            "Slope grade line analysis classified activity tracks (1 segment).",
        )

    def test_analysis_result_rejects_unhandled_plan_layer_keys(self):
        with patch(
            "qfit.analysis.application.slope_grade_analysis.build_slope_grade_analysis_plan",
            return_value=SlopeGradeAnalysisPlan(
                layers=(
                    SlopeGradeLayerPlan(
                        key="future_layer",
                        label="future layer",
                        enabled=True,
                    ),
                )
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Unsupported slope-grade layer key: future_layer",
            ):
                build_slope_grade_analysis_result()

    def test_segments_skip_invalid_or_non_forward_samples_and_recover(self):
        segments = build_slope_grade_segments(
            (
                {"distance_m": 0, "altitude_m": 100},
                {"distance_m": 0, "altitude_m": 101},
                {"distance_m": "bad", "altitude_m": 102},
                {"distance_m": 100, "altitude_m": None},
                {"distance_m": 200, "altitude_m": 104},
            )
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].start_distance_m, 0.0)
        self.assertEqual(segments[0].end_distance_m, 200.0)
        self.assertAlmostEqual(segments[0].grade_percent, 2.0)

    def test_segments_recover_after_missing_midstream_elevation_sample(self):
        segments = build_slope_grade_segments(
            (
                {"distance_m": 0, "altitude_m": 100},
                {"distance_m": 50, "altitude_m": None},
                {"distance_m": 100, "altitude_m": 104},
            )
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].start_distance_m, 0.0)
        self.assertEqual(segments[0].end_distance_m, 100.0)
        self.assertAlmostEqual(segments[0].grade_percent, 4.0)
        self.assertEqual(segments[0].grade_class.key, "climb")

    def test_plan_targets_only_eligible_activity_line_layers(self):
        activity_tracks = _Layer(fields=("name",))
        activity_points = _Layer(
            fields=("grade_smooth_pct", "stream_distance_m", "altitude_m")
        )
        plan = build_slope_grade_analysis_plan(
            activities_layer=activity_tracks,
            points_layer=activity_points,
            route_tracks_layer=_Layer(fields=("name", "has_elevation")),
            route_profile_samples_layer=_Layer(fields=("distance_m", "altitude_m")),
        )

        self.assertEqual(
            tuple(layer.key for layer in plan.enabled_layers),
            ("activity_tracks",),
        )
        self.assertEqual(
            plan.layers[0].source_fields,
            ("grade_smooth_pct", "stream_distance_m"),
        )
        self.assertEqual(len(plan.layers), 1)
        self.assertEqual(
            build_slope_grade_status(plan),
            "Slope grade line analysis ready for activity tracks.",
        )

    def test_plan_rejects_non_line_targets_without_touching_other_layers(self):
        polygon_layer = _Layer(geometry="Polygon", fields=("grade_smooth_pct",))
        plan = build_slope_grade_analysis_plan(
            activities_layer=polygon_layer,
            points_layer=polygon_layer,
        )

        self.assertEqual(plan.enabled_layers, ())
        self.assertEqual(len(plan.layers), 1)
        self.assertIn("activity track target is not a line layer", plan.layers[0].blocked_reason)

    def test_plan_uses_wkb_type_fallback_without_confusing_point_and_line_codes(self):
        point_wkb_layer = _WkbLayer(
            wkb_type=1,
            fields=("grade_smooth_pct", "stream_distance_m"),
        )
        line_wkb_layer = _WkbLayer(wkb_type=2, fields=("name",))
        plan = build_slope_grade_analysis_plan(
            activities_layer=line_wkb_layer,
            points_layer=point_wkb_layer,
        )

        self.assertEqual(
            tuple(layer.key for layer in plan.enabled_layers),
            ("activity_tracks",),
        )

        rejected_plan = build_slope_grade_analysis_plan(
            activities_layer=point_wkb_layer,
            points_layer=point_wkb_layer,
        )

        self.assertEqual(rejected_plan.enabled_layers, ())
        self.assertIn(
            "activity track target is not a line layer",
            rejected_plan.layers[0].blocked_reason,
        )

    def test_plan_reports_missing_activity_grade_sources_gracefully(self):
        plan = build_slope_grade_analysis_plan(
            activities_layer=_Layer(fields=("name",)),
            points_layer=_Layer(fields=("stream_distance_m",)),
        )

        self.assertEqual(plan.enabled_layers, ())
        status = build_slope_grade_status(plan)
        self.assertIn("activity tracks need point samples", status)
        self.assertNotIn("saved routes", status)

    def test_plan_rejects_unexpected_layer_kwargs(self):
        with self.assertRaisesRegex(
            TypeError,
            "Unexpected slope-grade layer kwargs: future_layer",
        ):
            build_slope_grade_analysis_plan(future_layer=object())

    def test_run_slope_grade_analysis_ignores_saved_route_layers(self):
        result = run_slope_grade_analysis(
            RunAnalysisRequest(
                analysis_mode=SLOPE_GRADE_MODE,
                route_tracks_layer=_Layer(fields=("name",)),
                route_profile_samples_layer=_FeatureLayer(
                    (
                        _FeatureSample(
                            {
                                "sample_group_index": 1,
                                "distance_m": 0,
                                "altitude_m": 100,
                            }
                        ),
                        _FeatureSample(
                            {
                                "sample_group_index": 1,
                                "distance_m": 100,
                                "altitude_m": 91,
                            }
                        ),
                    ),
                    fields=("distance_m", "altitude_m"),
                ),
            )
        )

        self.assertIsNone(result.layer)
        self.assertIn("activity track lines are not loaded", result.status)
        self.assertNotIn("saved route", result.status)

    def test_run_slope_grade_analysis_returns_status_without_creating_overlay_layer(self):
        result = run_slope_grade_analysis(
            RunAnalysisRequest(
                analysis_mode=SLOPE_GRADE_MODE,
                activities_layer=_Layer(fields=("name",)),
                points_layer=_FeatureLayer(
                    (
                        _FeatureSample(
                            {
                                "source": "strava",
                                "source_activity_id": "a-1",
                                "stream_distance_m": 0,
                                "grade_smooth_pct": 0,
                            }
                        ),
                        _FeatureSample(
                            {
                                "source": "strava",
                                "source_activity_id": "a-1",
                                "stream_distance_m": 100,
                                "grade_smooth_pct": 4,
                            }
                        ),
                    ),
                    fields=("grade_smooth_pct", "stream_distance_m"),
                ),
            )
        )

        self.assertEqual(
            result.status,
            "Slope grade line analysis classified activity tracks (1 segment).",
        )
        self.assertIsNone(result.layer)

    def test_run_slope_grade_analysis_returns_overlay_layer_when_available(self):
        overlay_layer = object()
        with patch(
            "qfit.analysis.application.slope_grade_analysis._build_slope_grade_layer",
            return_value=(overlay_layer, (object(),)),
        ):
            result = run_slope_grade_analysis(
                RunAnalysisRequest(
                    analysis_mode=SLOPE_GRADE_MODE,
                    activities_layer=_Layer(fields=("name",)),
                    points_layer=_FeatureLayer(
                        (
                            _FeatureSample(
                                {
                                    "source": "strava",
                                    "source_activity_id": "a-1",
                                    "stream_distance_m": 0,
                                    "grade_smooth_pct": 0,
                                }
                            ),
                            _FeatureSample(
                                {
                                    "source": "strava",
                                    "source_activity_id": "a-1",
                                    "stream_distance_m": 100,
                                    "grade_smooth_pct": 4,
                                }
                            ),
                        ),
                        fields=("grade_smooth_pct", "stream_distance_m"),
                    ),
                )
            )

        self.assertIs(result.layer, overlay_layer)
        self.assertEqual(
            result.status,
            "Slope grade line analysis classified activity tracks (1 segment).",
        )


if __name__ == "__main__":
    unittest.main()
