import unittest

from tests import _path  # noqa: F401
from qfit.providers.domain import RouteGpxParseError, parse_route_gpx


class RouteGpxParserTests(unittest.TestCase):
    def test_parses_track_points_with_elevation_and_distance(self):
        points = parse_route_gpx(
            """
            <gpx xmlns="http://www.topografix.com/GPX/1/1">
              <trk><trkseg>
                <trkpt lat="46.5000" lon="6.6000"><ele>400.5</ele></trkpt>
                <trkpt lat="46.5009" lon="6.6000"><ele>410.0</ele></trkpt>
              </trkseg></trk>
            </gpx>
            """
        )

        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].point_index, 0)
        self.assertEqual(points[0].lat, 46.5)
        self.assertEqual(points[0].lon, 6.6)
        self.assertEqual(points[0].altitude_m, 400.5)
        self.assertEqual(points[0].segment_index, 0)
        self.assertEqual(points[0].distance_m, 0.0)
        self.assertGreater(points[1].distance_m, 90.0)
        self.assertLess(points[1].distance_m, 110.0)
        self.assertEqual(points[1].altitude_m, 410.0)

    def test_does_not_add_synthetic_distance_between_track_segments(self):
        points = parse_route_gpx(
            """
            <gpx><trk>
              <trkseg>
                <trkpt lat="46.0" lon="6.0" />
                <trkpt lat="46.001" lon="6.0" />
              </trkseg>
              <trkseg>
                <trkpt lat="47.0" lon="7.0" />
                <trkpt lat="47.001" lon="7.0" />
              </trkseg>
            </trk></gpx>
            """
        )

        self.assertEqual([point.segment_index for point in points], [0, 0, 1, 1])
        self.assertAlmostEqual(points[2].distance_m, points[1].distance_m)
        self.assertGreater(points[3].distance_m, points[2].distance_m)

    def test_parses_route_points_without_namespace_or_elevation(self):
        points = parse_route_gpx(
            """
            <gpx>
              <rte>
                <rtept lat="46.5" lon="6.6" />
                <rtept lat="46.6" lon="6.7" />
              </rte>
            </gpx>
            """
        )

        self.assertEqual(
            [(point.lat, point.lon) for point in points],
            [(46.5, 6.6), (46.6, 6.7)],
        )
        self.assertIsNone(points[0].altitude_m)

    def test_empty_gpx_returns_no_points(self):
        self.assertEqual(parse_route_gpx(""), [])

    def test_invalid_gpx_raises_parse_error(self):
        with self.assertRaises(RouteGpxParseError):
            parse_route_gpx("<gpx><trkpt lat='bad' lon='6.6' /></gpx>")

    def test_missing_coordinate_keeps_specific_parse_error(self):
        with self.assertRaisesRegex(RouteGpxParseError, "missing lat"):
            parse_route_gpx("<gpx><trkpt lon='6.6' /></gpx>")


if __name__ == "__main__":
    unittest.main()
