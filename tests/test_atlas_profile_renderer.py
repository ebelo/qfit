"""Tests for atlas/profile_renderer.py (lightweight SVG profile chart renderer)."""
import os
import tempfile
import unittest

from qfit.atlas.profile_renderer import (
    _format_altitude,
    _format_distance,
    _nice_step,
    _xml_escape,
    render_profile_svg,
    render_profile_to_file,
)


class TestNiceStep(unittest.TestCase):
    def test_returns_one_for_zero_or_negative(self):
        self.assertEqual(_nice_step(0), 1.0)
        self.assertEqual(_nice_step(-5), 1.0)

    def test_rounds_to_nice_multiples(self):
        self.assertAlmostEqual(_nice_step(1.2), 1.0)
        self.assertAlmostEqual(_nice_step(2.5), 2.0)
        self.assertAlmostEqual(_nice_step(4.0), 5.0)
        self.assertAlmostEqual(_nice_step(8.0), 10.0)
        self.assertAlmostEqual(_nice_step(100.0), 100.0)

    def test_handles_large_values(self):
        step = _nice_step(3000.0)
        self.assertGreater(step, 0)


class TestFormatAltitude(unittest.TestCase):
    def test_formats_integers_cleanly(self):
        self.assertEqual(_format_altitude(800.0), "800")
        self.assertEqual(_format_altitude(0.0), "0")

    def test_formats_large_values(self):
        self.assertEqual(_format_altitude(1234.0), "1234")

    def test_rounds_decimals(self):
        self.assertEqual(_format_altitude(784.8), "785")


class TestFormatDistance(unittest.TestCase):
    def test_formats_meters_below_1km(self):
        self.assertEqual(_format_distance(500.0), "500 m")

    def test_formats_km_for_round_values(self):
        self.assertEqual(_format_distance(1000.0), "1 km")
        self.assertEqual(_format_distance(5000.0), "5 km")

    def test_formats_km_with_decimals(self):
        result = _format_distance(1500.0)
        self.assertIn("km", result)


class TestXmlEscape(unittest.TestCase):
    def test_escapes_ampersand(self):
        self.assertIn("&amp;", _xml_escape("a&b"))

    def test_escapes_angle_brackets(self):
        self.assertIn("&lt;", _xml_escape("<"))
        self.assertIn("&gt;", _xml_escape(">"))

    def test_no_escaping_needed(self):
        self.assertEqual(_xml_escape("hello"), "hello")


class TestRenderProfileSvg(unittest.TestCase):
    def _basic_points(self):
        return [(0.0, 784.8), (1000.0, 795.0), (2000.0, 800.5), (4793.4, 809.4)]

    def test_returns_none_for_single_point(self):
        self.assertIsNone(render_profile_svg([(0.0, 784.8)]))

    def test_returns_none_for_empty_points(self):
        self.assertIsNone(render_profile_svg([]))

    def test_returns_svg_string_for_valid_points(self):
        svg = render_profile_svg(self._basic_points())
        self.assertIsNotNone(svg)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_svg_contains_polygon(self):
        svg = render_profile_svg(self._basic_points())
        self.assertIn("<polygon", svg)

    def test_svg_contains_polyline(self):
        svg = render_profile_svg(self._basic_points())
        self.assertIn("<polyline", svg)

    def test_svg_contains_altitude_labels(self):
        svg = render_profile_svg(self._basic_points())
        # Should contain grid labels in the 785-810 m range
        self.assertIn("785", svg)

    def test_custom_dimensions(self):
        svg = render_profile_svg(self._basic_points(), width_mm=100.0, height_mm=30.0)
        self.assertIn('width="100.0mm"', svg)
        self.assertIn('height="30.0mm"', svg)

    def test_returns_none_when_chart_area_zero(self):
        # Zero usable width/height
        svg = render_profile_svg(self._basic_points(), width_mm=0.0, height_mm=0.0)
        self.assertIsNone(svg)

    def test_returns_none_when_all_distances_equal(self):
        points = [(5.0, 784.8), (5.0, 800.0)]
        self.assertIsNone(render_profile_svg(points))

    def test_flat_profile_widens_altitude_range(self):
        # Flat profile (no altitude variation) should still produce SVG
        points = [(0.0, 800.0), (1000.0, 800.0)]
        svg = render_profile_svg(points)
        self.assertIsNotNone(svg)

    def test_escapes_special_characters_in_labels(self):
        svg = render_profile_svg(self._basic_points())
        self.assertNotIn("&&", svg)


class TestRenderProfileToFile(unittest.TestCase):
    def test_returns_none_for_insufficient_points(self):
        self.assertIsNone(render_profile_to_file([(0.0, 800.0)]))

    def test_returns_svg_file_path(self):
        points = [(0.0, 784.8), (1000.0, 809.4)]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = render_profile_to_file(points, directory=tmpdir)
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".svg"))

    def test_file_is_nonempty_svg(self):
        points = [(0.0, 784.8), (1000.0, 795.0), (4793.4, 809.4)]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = render_profile_to_file(points, directory=tmpdir)
            self.assertIsNotNone(path)
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        self.assertIn("<svg", content)

    def test_uses_default_directory_when_none_provided(self):
        points = [(0.0, 784.8), (4793.4, 809.4)]
        path = render_profile_to_file(points, directory=None)
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        os.unlink(path)


if __name__ == "__main__":
    unittest.main()
