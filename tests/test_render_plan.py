import unittest

from tests import _path  # noqa: F401
from qfit.visualization.application.render_plan import (
    HEATMAP_PRESET,
    RENDERER_HEATMAP,
    RENDERER_START_POINTS,
    RENDERER_TRACK_POINTS,
    SOURCE_ROLE_POINTS,
    SOURCE_ROLE_STARTS,
    START_POINTS_PRESET,
    TRACK_POINTS_PRESET,
    build_render_plan,
)


class RenderPlanTests(unittest.TestCase):
    def test_heatmap_prefers_starts_when_starts_and_points_have_features(self):
        plan = build_render_plan(
            HEATMAP_PRESET,
            has_start_features=True,
            has_point_features=True,
            has_points_layer=True,
        )

        self.assertEqual(plan.selected_source_role, SOURCE_ROLE_STARTS)
        self.assertEqual(plan.starts.renderer_family, RENDERER_HEATMAP)
        self.assertTrue(plan.starts.visible)
        self.assertEqual(plan.points.renderer_family, RENDERER_TRACK_POINTS)
        self.assertFalse(plan.points.visible)

    def test_heatmap_falls_back_to_points_when_starts_are_missing(self):
        plan = build_render_plan(
            HEATMAP_PRESET,
            has_start_features=False,
            has_point_features=True,
            has_points_layer=True,
        )

        self.assertEqual(plan.selected_source_role, SOURCE_ROLE_POINTS)
        self.assertEqual(plan.points.renderer_family, RENDERER_HEATMAP)
        self.assertTrue(plan.points.visible)
        self.assertEqual(plan.starts.renderer_family, RENDERER_START_POINTS)
        self.assertFalse(plan.starts.visible)
        self.assertTrue(plan.starts.subtle)

    def test_heatmap_falls_back_to_points_when_starts_are_empty(self):
        plan = build_render_plan(
            HEATMAP_PRESET,
            has_start_features=False,
            has_point_features=True,
            has_points_layer=True,
        )

        self.assertEqual(plan.selected_source_role, SOURCE_ROLE_POINTS)
        self.assertEqual(plan.points.renderer_family, RENDERER_HEATMAP)

    def test_track_points_preset_keeps_points_prominent(self):
        plan = build_render_plan(
            TRACK_POINTS_PRESET,
            has_start_features=True,
            has_point_features=True,
            has_points_layer=True,
        )

        self.assertEqual(plan.points.renderer_family, RENDERER_TRACK_POINTS)
        self.assertTrue(plan.points.visible)
        self.assertFalse(plan.points.subtle)
        self.assertEqual(plan.starts.renderer_family, RENDERER_START_POINTS)
        self.assertTrue(plan.starts.subtle)

    def test_start_points_preset_keeps_starts_prominent(self):
        plan = build_render_plan(
            START_POINTS_PRESET,
            has_start_features=True,
            has_point_features=True,
            has_points_layer=True,
        )

        self.assertEqual(plan.starts.renderer_family, RENDERER_START_POINTS)
        self.assertTrue(plan.starts.visible)
        self.assertFalse(plan.starts.subtle)
        self.assertEqual(plan.points.renderer_family, RENDERER_TRACK_POINTS)
        self.assertTrue(plan.points.subtle)


if __name__ == "__main__":
    unittest.main()
