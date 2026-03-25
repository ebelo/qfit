"""Tests for atlas_profile_renderer — SVG elevation profile generation."""

import os
import tempfile
import unittest

from tests import _path  # noqa: F401
from qfit.atlas.profile_renderer import (
    render_profile_svg,
    render_profile_to_file,
    load_profile_samples_from_gpkg,
    _nice_step,
    _format_altitude,
    _format_distance,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

# Simple ascending profile: 0m → 5000m distance, 500m → 800m altitude
SIMPLE_PROFILE = [
    (0.0, 500.0),
    (1000.0, 550.0),
    (2000.0, 600.0),
    (3000.0, 650.0),
    (4000.0, 700.0),
    (5000.0, 800.0),
]

# Flat profile: same altitude everywhere
FLAT_PROFILE = [
    (0.0, 100.0),
    (1000.0, 100.0),
    (2000.0, 100.0),
]


class TestRenderProfileSvg(unittest.TestCase):
    """Test SVG profile rendering."""

    def test_returns_svg_for_valid_profile(self):
        svg = render_profile_svg(SIMPLE_PROFILE)
        self.assertIsNotNone(svg)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_returns_none_for_empty_points(self):
        self.assertIsNone(render_profile_svg([]))

    def test_returns_none_for_single_point(self):
        self.assertIsNone(render_profile_svg([(0.0, 100.0)]))

    def test_returns_none_for_zero_distance_range(self):
        """Two points at the same distance → None."""
        self.assertIsNone(render_profile_svg([(0.0, 100.0), (0.0, 200.0)]))

    def test_flat_profile_renders(self):
        """A flat profile (all same altitude) should still render."""
        svg = render_profile_svg(FLAT_PROFILE)
        self.assertIsNotNone(svg)
        self.assertIn("<svg", svg)

    def test_svg_contains_polygon(self):
        svg = render_profile_svg(SIMPLE_PROFILE)
        self.assertIn("<polygon", svg)

    def test_svg_contains_polyline(self):
        svg = render_profile_svg(SIMPLE_PROFILE)
        self.assertIn("<polyline", svg)

    def test_svg_viewbox_matches_dimensions(self):
        svg = render_profile_svg(SIMPLE_PROFILE, width_mm=190.0, height_mm=42.0)
        self.assertIn('viewBox="0 0 190.0 42.0"', svg)

    def test_svg_contains_altitude_labels(self):
        """SVG should have altitude text labels."""
        svg = render_profile_svg(SIMPLE_PROFILE)
        self.assertIn("<text", svg)
        # Should contain altitude unit marker
        self.assertIn(">m</text>", svg)

    def test_svg_contains_distance_labels(self):
        """SVG should include distance labels along the bottom axis."""
        svg = render_profile_svg(SIMPLE_PROFILE)
        self.assertIn("km</text>", svg)

    def test_custom_dimensions(self):
        svg = render_profile_svg(SIMPLE_PROFILE, width_mm=100.0, height_mm=30.0)
        self.assertIsNotNone(svg)
        self.assertIn('viewBox="0 0 100.0 30.0"', svg)

    def test_very_small_dimensions_returns_none(self):
        """If chart area is too small, returns None."""
        svg = render_profile_svg(SIMPLE_PROFILE, width_mm=15.0, height_mm=5.0)
        self.assertIsNone(svg)


class TestRenderProfileToFile(unittest.TestCase):
    """Test SVG file writing."""

    def test_writes_svg_file(self):
        path = render_profile_to_file(SIMPLE_PROFILE)
        self.assertIsNotNone(path)
        try:
            self.assertTrue(os.path.isfile(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("<svg", content)
        finally:
            if path:
                os.unlink(path)

    def test_returns_none_for_insufficient_data(self):
        self.assertIsNone(render_profile_to_file([]))
        self.assertIsNone(render_profile_to_file([(0.0, 100.0)]))

    def test_writes_to_specified_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = render_profile_to_file(SIMPLE_PROFILE, directory=tmpdir)
            self.assertIsNotNone(path)
            self.assertTrue(path.startswith(tmpdir))
            os.unlink(path)

    def test_file_is_valid_utf8(self):
        path = render_profile_to_file(SIMPLE_PROFILE)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<svg", content)
        finally:
            if path:
                os.unlink(path)


class TestNiceStep(unittest.TestCase):
    """Test axis step rounding."""

    def test_small_values(self):
        self.assertAlmostEqual(_nice_step(0.3), 0.2)
        self.assertAlmostEqual(_nice_step(0.7), 0.5)

    def test_medium_values(self):
        self.assertAlmostEqual(_nice_step(3.0), 2.0)
        self.assertAlmostEqual(_nice_step(7.0), 5.0)

    def test_large_values(self):
        self.assertAlmostEqual(_nice_step(15.0), 10.0)
        self.assertAlmostEqual(_nice_step(80.0), 100.0)

    def test_zero_returns_one(self):
        self.assertAlmostEqual(_nice_step(0.0), 1.0)

    def test_negative_returns_one(self):
        self.assertAlmostEqual(_nice_step(-5.0), 1.0)


class TestFormatAltitude(unittest.TestCase):
    def test_integer_altitude(self):
        self.assertEqual(_format_altitude(500.0), "500")

    def test_large_altitude(self):
        self.assertEqual(_format_altitude(1234.5), "1234")

    def test_zero(self):
        self.assertEqual(_format_altitude(0.0), "0")


class TestFormatDistance(unittest.TestCase):
    def test_meters(self):
        self.assertEqual(_format_distance(500.0), "500 m")

    def test_kilometers(self):
        self.assertEqual(_format_distance(3000.0), "3 km")

    def test_fractional_km(self):
        self.assertEqual(_format_distance(1500.0), "1.5 km")


class TestLoadProfileSamplesFromGpkg(unittest.TestCase):
    """Test loading profile samples from a GeoPackage database."""

    def test_returns_empty_dict_for_nonexistent_file(self):
        result = load_profile_samples_from_gpkg("/nonexistent/path.gpkg")
        self.assertEqual(result, {})

    def test_returns_empty_dict_for_missing_table(self):
        """A valid SQLite DB without the atlas_profile_samples table → empty."""
        import sqlite3
        with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as f:
            path = f.name
        try:
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE dummy (id INTEGER)")
            conn.close()
            result = load_profile_samples_from_gpkg(path)
            self.assertEqual(result, {})
        finally:
            os.unlink(path)

    def test_loads_samples_grouped_by_page_sort_key(self):
        import sqlite3
        with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as f:
            path = f.name
        try:
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE atlas_profile_samples ("
                "  page_sort_key TEXT,"
                "  profile_point_index INTEGER,"
                "  distance_m REAL,"
                "  altitude_m REAL"
                ")"
            )
            conn.executemany(
                "INSERT INTO atlas_profile_samples VALUES (?, ?, ?, ?)",
                [
                    ("page_a", 0, 0.0, 100.0),
                    ("page_a", 1, 1000.0, 150.0),
                    ("page_a", 2, 2000.0, 120.0),
                    ("page_b", 0, 0.0, 200.0),
                    ("page_b", 1, 500.0, 250.0),
                ],
            )
            conn.commit()
            conn.close()

            result = load_profile_samples_from_gpkg(path)
            self.assertIn("page_a", result)
            self.assertIn("page_b", result)
            self.assertEqual(len(result["page_a"]), 3)
            self.assertEqual(len(result["page_b"]), 2)
            self.assertEqual(result["page_a"][0], (0.0, 100.0))
            self.assertEqual(result["page_a"][2], (2000.0, 120.0))
        finally:
            os.unlink(path)

    def test_skips_null_values(self):
        import sqlite3
        with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as f:
            path = f.name
        try:
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE atlas_profile_samples ("
                "  page_sort_key TEXT,"
                "  profile_point_index INTEGER,"
                "  distance_m REAL,"
                "  altitude_m REAL"
                ")"
            )
            conn.executemany(
                "INSERT INTO atlas_profile_samples VALUES (?, ?, ?, ?)",
                [
                    ("page_a", 0, 0.0, 100.0),
                    ("page_a", 1, None, 150.0),   # null distance
                    ("page_a", 2, 2000.0, None),   # null altitude
                    (None, 3, 3000.0, 200.0),      # null key
                ],
            )
            conn.commit()
            conn.close()

            result = load_profile_samples_from_gpkg(path)
            self.assertEqual(len(result.get("page_a", [])), 1)
            self.assertNotIn(None, result)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
