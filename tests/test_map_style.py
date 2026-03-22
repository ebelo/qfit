import unittest

import tests._path  # noqa: F401,E402

from map_style import (  # noqa: E402
    DEFAULT_SIMPLE_LINE_HEX,
    adapt_color_for_basemap,
    pick_activity_style_field,
    resolve_activity_color,
    resolve_activity_family,
    resolve_basemap_line_style,
)


class MapStyleTests(unittest.TestCase):
    def test_activity_color_mapping_uses_semantic_reference_palette(self):
        self.assertEqual(resolve_activity_color("Run"), "#D62828")
        self.assertEqual(resolve_activity_color("TrailRun"), "#9D0208")
        self.assertEqual(resolve_activity_color("Ride"), "#F77F00")
        self.assertEqual(resolve_activity_color("Snowshoe"), "#48CAE4")
        self.assertEqual(resolve_activity_color("VirtualRide"), "#6C757D")

    def test_unknown_activity_types_fall_back_by_semantic_family(self):
        self.assertEqual(resolve_activity_family("EveningJog"), "running")
        self.assertEqual(resolve_activity_family("BikeCommute"), "machine")
        self.assertEqual(resolve_activity_family("Kitesurf"), "water")
        self.assertEqual(resolve_activity_color("Kitesurf"), "#00B4D8")
        self.assertEqual(resolve_activity_color(None), "#6C757D")

    def test_light_and_satellite_contexts_adjust_luminance_without_changing_mapping(self):
        self.assertEqual(resolve_activity_color("Run", "Outdoor"), "#D62828")
        self.assertEqual(resolve_activity_color("Run", "Light"), "#B71E1E")
        self.assertEqual(resolve_activity_color("Run", "Satellite"), "#DE3F3F")
        self.assertEqual(adapt_color_for_basemap(DEFAULT_SIMPLE_LINE_HEX, "Light"), "#21867A")
        self.assertEqual(adapt_color_for_basemap(DEFAULT_SIMPLE_LINE_HEX, "Satellite"), "#2EB4A3")

    def test_basemap_line_profiles_follow_style_guide_ranges(self):
        outdoor = resolve_basemap_line_style("Outdoor")
        light = resolve_basemap_line_style("Light")
        satellite = resolve_basemap_line_style("Satellite")
        fallback = resolve_basemap_line_style("Winter (custom style)")

        self.assertEqual((outdoor.line_width, outdoor.opacity, outdoor.outline_color), (1.8, 0.85, None))
        self.assertEqual((light.line_width, light.opacity, light.outline_color, light.outline_width), (2.1, 0.9, "#333333", 0.4))
        self.assertEqual((satellite.line_width, satellite.opacity, satellite.outline_color, satellite.outline_width), (2.3, 0.95, "#FFFFFF", 1.0))
        self.assertEqual(fallback, outdoor)

    def test_pick_activity_style_field_prefers_sport_type(self):
        self.assertEqual(pick_activity_style_field(["name", "sport_type", "activity_type"]), "sport_type")
        self.assertEqual(pick_activity_style_field(["name", "activity_type"]), "activity_type")
        self.assertIsNone(pick_activity_style_field(["name", "distance_m"]))


if __name__ == "__main__":
    unittest.main()
