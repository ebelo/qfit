import unittest

from tests import _path  # noqa: F401

from qfit.analysis.application.analysis_models import RunAnalysisRequest
from qfit.analysis.application.slope_grade_analysis import (
    SLOPE_GRADE_CLASSES,
    SLOPE_GRADE_LEGEND,
    SLOPE_GRADE_MODE,
    build_slope_grade_analysis_plan,
    build_slope_grade_status,
    run_slope_grade_analysis,
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


class SlopeGradeAnalysisTests(unittest.TestCase):
    def test_legend_uses_documented_deterministic_percent_grade_classes(self):
        self.assertEqual(SLOPE_GRADE_MODE, "Slope grade lines")
        self.assertEqual(
            SLOPE_GRADE_LEGEND,
            (
                "Steep descent (≤ -8%)",
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

    def test_plan_targets_only_eligible_activity_and_route_line_layers(self):
        activity_tracks = _Layer(fields=("name",))
        activity_points = _Layer(
            fields=("grade_smooth_pct", "stream_distance_m", "altitude_m")
        )
        route_tracks = _Layer(fields=("name", "has_elevation"))
        route_samples = _Layer(fields=("distance_m", "altitude_m"))

        plan = build_slope_grade_analysis_plan(
            activities_layer=activity_tracks,
            points_layer=activity_points,
            route_tracks_layer=route_tracks,
            route_profile_samples_layer=route_samples,
        )

        self.assertEqual(
            tuple(layer.key for layer in plan.enabled_layers),
            ("activity_tracks", "saved_route_tracks"),
        )
        self.assertEqual(
            plan.layers[0].source_fields,
            ("grade_smooth_pct", "stream_distance_m"),
        )
        self.assertEqual(plan.layers[1].source_fields, ("distance_m", "altitude_m"))
        self.assertEqual(
            build_slope_grade_status(plan),
            "Slope grade line analysis ready for activity tracks, saved route tracks.",
        )

    def test_plan_rejects_non_line_targets_without_touching_other_layers(self):
        polygon_layer = _Layer(geometry="Polygon", fields=("grade_smooth_pct",))
        route_samples = _Layer(fields=("distance_m", "altitude_m"))

        plan = build_slope_grade_analysis_plan(
            activities_layer=polygon_layer,
            points_layer=polygon_layer,
            route_tracks_layer=polygon_layer,
            route_profile_samples_layer=route_samples,
        )

        self.assertEqual(plan.enabled_layers, ())
        self.assertIn("activity track target is not a line layer", plan.layers[0].blocked_reason)
        self.assertIn("saved route target is not a line layer", plan.layers[1].blocked_reason)

    def test_plan_uses_wkb_type_fallback_without_confusing_point_and_line_codes(self):
        point_wkb_layer = _WkbLayer(
            wkb_type=1,
            fields=("grade_smooth_pct", "stream_distance_m"),
        )
        line_wkb_layer = _WkbLayer(wkb_type=2, fields=("name",))
        multi_line_wkb_layer = _WkbLayer(wkb_type=5, fields=("name",))
        route_samples = _Layer(fields=("distance_m", "altitude_m"))

        plan = build_slope_grade_analysis_plan(
            activities_layer=line_wkb_layer,
            points_layer=point_wkb_layer,
            route_tracks_layer=multi_line_wkb_layer,
            route_profile_samples_layer=route_samples,
        )

        self.assertEqual(
            tuple(layer.key for layer in plan.enabled_layers),
            ("activity_tracks", "saved_route_tracks"),
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

    def test_plan_reports_missing_elevation_distance_sources_gracefully(self):
        plan = build_slope_grade_analysis_plan(
            activities_layer=_Layer(fields=("name",)),
            points_layer=_Layer(fields=("stream_distance_m",)),
            route_tracks_layer=_Layer(fields=("name",)),
            route_points_layer=_Layer(fields=("distance_m",)),
        )

        self.assertEqual(plan.enabled_layers, ())
        status = build_slope_grade_status(plan)
        self.assertIn("activity tracks need point samples", status)
        self.assertIn("saved routes need profile or route point samples", status)

    def test_run_slope_grade_analysis_returns_status_without_creating_overlay_layer(self):
        result = run_slope_grade_analysis(
            RunAnalysisRequest(
                analysis_mode=SLOPE_GRADE_MODE,
                activities_layer=_Layer(fields=("name",)),
                points_layer=_Layer(fields=("grade_smooth_pct", "stream_distance_m")),
            )
        )

        self.assertEqual(
            result.status,
            "Slope grade line analysis ready for activity tracks.",
        )
        self.assertIsNone(result.layer)


if __name__ == "__main__":
    unittest.main()
