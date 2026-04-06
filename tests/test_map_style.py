import colorsys
import unittest

from tests import _path  # noqa: F401

from qfit.map_style import (
    DEFAULT_SIMPLE_LINE_HEX,
    adapt_color_for_basemap,
    pick_activity_style_field,
    resolve_activity_color,
    resolve_activity_family,
    resolve_basemap_line_style,
)
from qfit.visualization.map_style import (
    DEFAULT_SIMPLE_LINE_HEX as PACKAGE_DEFAULT_SIMPLE_LINE_HEX,
    adapt_color_for_basemap as package_adapt_color_for_basemap,
    pick_activity_style_field as package_pick_activity_style_field,
    resolve_activity_color as package_resolve_activity_color,
    resolve_activity_family as package_resolve_activity_family,
    resolve_basemap_line_style as package_resolve_basemap_line_style,
)


class MapStyleTests(unittest.TestCase):
    def test_root_shim_exports_visualization_map_style_helpers(self):
        self.assertIs(DEFAULT_SIMPLE_LINE_HEX, PACKAGE_DEFAULT_SIMPLE_LINE_HEX)
        self.assertIs(adapt_color_for_basemap, package_adapt_color_for_basemap)
        self.assertIs(pick_activity_style_field, package_pick_activity_style_field)
        self.assertIs(resolve_activity_color, package_resolve_activity_color)
        self.assertIs(resolve_activity_family, package_resolve_activity_family)
        self.assertIs(resolve_basemap_line_style, package_resolve_basemap_line_style)

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

    def test_truly_unknown_types_fall_back_to_grey(self):
        # A type with no recognizable token should land in the 'machine' family (grey).
        grey_hex = resolve_activity_color("SomeRandomSport")
        r, g, b = int(grey_hex[1:3], 16), int(grey_hex[3:5], 16), int(grey_hex[5:7], 16)
        _hue, _lightness, saturation = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
        # Grey family means very low saturation.
        self.assertLess(saturation, 0.15, f"Expected grey-ish color for unknown type, got {grey_hex}")

    def test_light_and_satellite_contexts_adjust_luminance_without_changing_mapping(self):
        self.assertEqual(resolve_activity_color("Run", "Outdoor"), "#D62828")
        self.assertEqual(resolve_activity_color("Run", "Light"), "#B71E1E")
        self.assertEqual(resolve_activity_color("Run", "Satellite"), "#DE3F3F")
        self.assertEqual(adapt_color_for_basemap(DEFAULT_SIMPLE_LINE_HEX, "Light"), "#21867A")
        self.assertEqual(adapt_color_for_basemap(DEFAULT_SIMPLE_LINE_HEX, "Satellite"), "#2EB4A3")

    def test_basemap_adaptation_does_not_change_hue(self):
        # Hue must be stable across basemap presets (only lightness/saturation may shift).
        def hex_hue(hex_color):
            r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            hue, _l, _s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
            return round(hue, 2)

        for activity in ("Run", "Ride", "Hike", "AlpineSki"):
            base_hue = hex_hue(resolve_activity_color(activity, "Outdoor"))
            light_hue = hex_hue(resolve_activity_color(activity, "Light"))
            satellite_hue = hex_hue(resolve_activity_color(activity, "Satellite"))
            self.assertAlmostEqual(base_hue, light_hue, places=2, msg=f"{activity}: hue changed on Light basemap")
            self.assertAlmostEqual(base_hue, satellite_hue, places=2, msg=f"{activity}: hue changed on Satellite basemap")

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
