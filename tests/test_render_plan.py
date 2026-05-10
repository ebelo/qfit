import unittest

from tests import _path  # noqa: F401
from qfit.visualization.application.render_plan import (
    DEFAULT_RENDER_PRESET,
    REMOVED_ANALYSIS_PRESETS,
    RENDERER_SIMPLE_LINES,
    RENDERER_START_POINTS,
    RENDERER_TRACK_POINTS,
    TRACK_POINTS_PRESET,
    build_render_plan,
    normalize_render_preset,
)


class RenderPlanTests(unittest.TestCase):
    def test_removed_analysis_presets_normalize_to_default_map_style(self):
        for preset in REMOVED_ANALYSIS_PRESETS:
            with self.subTest(preset=preset):
                self.assertEqual(normalize_render_preset(preset), DEFAULT_RENDER_PRESET)
                plan = build_render_plan(preset, has_points_layer=True)
                self.assertEqual(plan.preset_name, DEFAULT_RENDER_PRESET)
                self.assertEqual(plan.activities.renderer_family, RENDERER_SIMPLE_LINES)
                self.assertEqual(plan.starts.renderer_family, RENDERER_START_POINTS)
                self.assertEqual(plan.points.renderer_family, RENDERER_TRACK_POINTS)

    def test_track_points_preset_keeps_points_prominent(self):
        plan = build_render_plan(TRACK_POINTS_PRESET, has_points_layer=True)

        self.assertEqual(plan.points.renderer_family, RENDERER_TRACK_POINTS)
        self.assertTrue(plan.points.visible)
        self.assertFalse(plan.points.subtle)
        self.assertEqual(plan.starts.renderer_family, RENDERER_START_POINTS)
        self.assertTrue(plan.starts.subtle)


if __name__ == "__main__":
    unittest.main()
