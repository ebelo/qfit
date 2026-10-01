import unittest

from tests import _path  # noqa: F401
from qfit.analysis.domain.route_density import (RouteDensityParameters, HeatmapCancelled,
                                                activity_cells, segment_cells, tile_cell)
from qfit.analysis.application.route_heatmap import (heatmap_fingerprint, add_track_fingerprint,
                                                   build_route_heatmap_request)
from qfit.activities.application.activity_selection_state import ActivitySelectionState
from qfit.activities.domain.activity_query import ActivityQuery


class RouteDensityTests(unittest.TestCase):
    def test_vertex_spacing_stops_and_reverse_do_not_change_usage(self):
        parameters = RouteDensityParameters()
        sparse = [(1, 1), (101, 51)]
        dense = [(1 + i, 1 + i / 2) for i in range(101)]
        expected = activity_cells([sparse], parameters)
        self.assertEqual(expected, activity_cells([dense], parameters))
        self.assertEqual(expected, activity_cells([list(reversed(dense))], parameters))
        self.assertEqual(expected, activity_cells([dense + [dense[-1]] * 100, sparse], parameters))

    def test_diagonals_boundaries_and_negative_cells(self):
        self.assertEqual(set(segment_cells((-15, -15), (15, 15), 10)), {(-2, -2), (-1, -1), (0, 0), (1, 1)})
        self.assertEqual(set(segment_cells((0, 0), (20, 0), 10)), {(0, 0), (1, 0), (2, 0)})
        self.assertEqual(list(segment_cells((1, 1), (1, 1), 10)), [(0, 0)])
        self.assertEqual(tile_cell((-1, -1), 256), ((-1, -1), (255, 255)))
        self.assertEqual(activity_cells([[], [(1, 1)]], RouteDensityParameters()), set())

    def test_safe_budgets_cancel_and_invalid_coordinates(self):
        with self.assertRaises(HeatmapCancelled):
            activity_cells([[(1, 1), (50000, 2)]], RouteDensityParameters(), lambda: True)
        with self.assertRaises(ValueError):
            activity_cells([[(0, 0), (100, 10)]], RouteDensityParameters(), max_cells=3)
        with self.assertRaises(ValueError):
            list(segment_cells((float("nan"), 0), (2, 3), 10))
        for kwargs in ({"cell_size": 0}, {"sigma": -1}, {"sigma": 99999}, {"tile_size": 2}, {"cell_size": float("inf")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                RouteDensityParameters(**kwargs)

    def test_geometry_identity_and_parameters_drive_cache_key(self):
        def fingerprint(identity, geometry, cell=10):
            digest = heatmap_fingerprint(RouteDensityParameters(cell_size=cell), "EPSG:4326")
            add_track_fingerprint(digest, identity, geometry)
            return digest.hexdigest()
        original = fingerprint(("strava", "1"), b"geom")
        self.assertEqual(original, fingerprint(("strava", "1"), b"geom"))
        self.assertNotEqual(original, fingerprint(("strava", "2"), b"geom"))
        self.assertNotEqual(original, fingerprint(("strava", "1"), b"changed"))
        self.assertNotEqual(original, fingerprint(("strava", "1"), b"geom", 20))

    def test_selected_filters_are_captured_without_canvas_or_layer_inputs(self):
        query = ActivityQuery(activity_type="Ride", search_text="O'Brien", min_distance_km=2)
        request = build_route_heatmap_request("routes.gpkg", "cache", ActivitySelectionState(query), (1, 2))
        self.assertIn("o''brien", request.subset)
        self.assertIn('"distance_m" >= 2000', request.subset)
        self.assertEqual(request.source_revision, (1, 2))
        query.search_text = "changed"
        self.assertNotIn("changed", request.subset)
        self.assertEqual(build_route_heatmap_request("routes.gpkg", "cache").subset, "")
