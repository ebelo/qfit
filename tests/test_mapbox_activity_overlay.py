import unittest

from tests import _path  # noqa: F401

from qfit.validation.mapbox_activity_overlay import (
    ACTIVITY_TYPES,
    PIXELS_PER_MILLIMETER,
    activity_overlay_geojson,
    activity_overlay_mapbox_layers,
    activity_overlay_routes_web_mercator,
)
from qfit.validation.mapbox_outdoors_comparison import (
    LIGHT_CAMERAS,
    build_mapbox_gl_html,
    camera_extent_web_mercator,
)
from qfit.visualization.map_style import resolve_activity_color, resolve_basemap_line_style


class MapboxActivityOverlayTests(unittest.TestCase):
    def test_routes_are_representative_and_stay_inside_each_camera_extent(self):
        for camera in LIGHT_CAMERAS.values():
            with self.subTest(camera=camera.name):
                left, bottom, right, top = camera_extent_web_mercator(camera)
                routes = activity_overlay_routes_web_mercator(camera)

                self.assertEqual(tuple(route.activity_type for route in routes), ACTIVITY_TYPES)
                self.assertTrue(all(len(route.coordinates) >= 5 for route in routes))
                for route in routes:
                    for x, y in route.coordinates:
                        self.assertTrue(left <= x <= right)
                        self.assertTrue(bottom <= y <= top)

    def test_geojson_preserves_activity_type_semantics(self):
        geojson = activity_overlay_geojson(LIGHT_CAMERAS["bern-urban-z12-light"])

        self.assertEqual(geojson["type"], "FeatureCollection")
        features = geojson["features"]
        self.assertEqual(
            [feature["properties"]["sport_type"] for feature in features],
            list(ACTIVITY_TYPES),
        )
        self.assertTrue(
            all(feature["geometry"]["type"] == "LineString" for feature in features)
        )
        for feature in features:
            for longitude, latitude in feature["geometry"]["coordinates"]:
                self.assertTrue(-180.0 <= longitude <= 180.0)
                self.assertTrue(-85.1 <= latitude <= 85.1)

    def test_mapbox_layers_mirror_production_light_line_style(self):
        outline, core = activity_overlay_mapbox_layers()
        line_style = resolve_basemap_line_style("Light")

        self.assertEqual(outline["paint"]["line-color"], line_style.outline_color)
        self.assertAlmostEqual(
            outline["paint"]["line-width"],
            (line_style.line_width + line_style.outline_width * 2.0)
            * PIXELS_PER_MILLIMETER,
        )
        self.assertAlmostEqual(
            core["paint"]["line-width"], line_style.line_width * PIXELS_PER_MILLIMETER
        )
        self.assertEqual(core["paint"]["line-opacity"], line_style.opacity)
        color_match = core["paint"]["line-color"]
        for activity_type in ACTIVITY_TYPES:
            index = color_match.index(activity_type)
            self.assertEqual(
                color_match[index + 1], resolve_activity_color(activity_type, "Light")
            )

    def test_browser_overlay_is_opt_in_and_token_free(self):
        camera = LIGHT_CAMERAS["geneva-urban-z14-light"]

        plain_html = build_mapbox_gl_html(camera=camera)
        overlay_html = build_mapbox_gl_html(camera=camera, activity_overlay=True)

        self.assertNotIn("qfit-activity-overlay-core", plain_html)
        self.assertIn("qfit-activity-overlay-outline", overlay_html)
        self.assertIn("qfit-activity-overlay-core", overlay_html)
        self.assertIn('"sport_type": "Run"', overlay_html)
        self.assertNotIn("pk.", overlay_html)


if __name__ == "__main__":
    unittest.main()
