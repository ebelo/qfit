import unittest

from qfit.atlas.profile_style import (
    DEFAULT_NATIVE_PROFILE_PLOT_STYLE,
    build_native_profile_plot_style_from_settings,
)


class _FakeSettings:
    def __init__(self, values=None):
        self._values = values or {}

    def get(self, key, default=None):
        return self._values.get(key, default)


class BuildNativeProfilePlotStyleFromSettingsTests(unittest.TestCase):
    def test_returns_default_style_when_no_overrides_exist(self):
        style = build_native_profile_plot_style_from_settings(_FakeSettings())

        self.assertIs(style, DEFAULT_NATIVE_PROFILE_PLOT_STYLE)

    def test_applies_settings_overrides(self):
        style = build_native_profile_plot_style_from_settings(
            _FakeSettings(
                {
                    "atlas_profile_plot_background_fill_color": "1,2,3,255",
                    "atlas_profile_plot_border_color": "4,5,6,255",
                    "atlas_profile_plot_major_grid_color": "7,8,9,255",
                    "atlas_profile_plot_minor_grid_color": "10,11,12,255",
                    "atlas_profile_plot_x_axis_suffix": " mi",
                    "atlas_profile_plot_y_axis_suffix": " ft",
                }
            )
        )

        self.assertEqual(style.background_fill_props["color"], "1,2,3,255")
        self.assertEqual(style.border_fill_props["outline_color"], "4,5,6,255")
        self.assertEqual(style.x_axis.major_grid_props["color"], "7,8,9,255")
        self.assertEqual(style.y_axis.major_grid_props["color"], "7,8,9,255")
        self.assertEqual(style.x_axis.minor_grid_props["color"], "10,11,12,255")
        self.assertEqual(style.y_axis.minor_grid_props["color"], "10,11,12,255")
        self.assertEqual(style.x_axis.suffix, "mi")
        self.assertEqual(style.y_axis.suffix, "ft")

    def test_ignores_blank_string_overrides(self):
        style = build_native_profile_plot_style_from_settings(
            _FakeSettings(
                {
                    "atlas_profile_plot_background_fill_color": "   ",
                    "atlas_profile_plot_x_axis_suffix": "",
                }
            )
        )

        self.assertIs(style, DEFAULT_NATIVE_PROFILE_PLOT_STYLE)
