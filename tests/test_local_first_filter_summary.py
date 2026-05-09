import unittest
from types import SimpleNamespace

from qfit.activities.domain.activity_query import (
    DETAILED_ROUTE_FILTER_ANY,
    DETAILED_ROUTE_FILTER_MISSING,
    DETAILED_ROUTE_FILTER_PRESENT,
)
from qfit.ui.application.local_first_filter_summary import (
    build_local_first_filter_description,
)


class LocalFirstFilterSummaryTests(unittest.TestCase):
    def test_build_local_first_filter_description_skips_default_controls(self):
        request = SimpleNamespace(
            activity_type="All",
            search_text="  ",
            date_from=None,
            date_to=None,
            min_distance_km=0,
            max_distance_km=None,
            detailed_route_filter=DETAILED_ROUTE_FILTER_ANY,
        )

        self.assertIsNone(build_local_first_filter_description(request))

    def test_build_local_first_filter_description_lists_active_controls_compactly(self):
        request = SimpleNamespace(
            activity_type="Run",
            search_text="alps",
            date_from="2026-04-01",
            date_to="2026-04-30",
            min_distance_km=5,
            max_distance_km=42.5,
            detailed_route_filter=DETAILED_ROUTE_FILTER_PRESENT,
        )

        description = build_local_first_filter_description(request)

        self.assertEqual(
            description,
            "type: Run · search: “alps” · dates: 2026-04-01–2026-04-30 · "
            "distance: 5–42.5 km · routes: detailed only",
        )

    def test_build_local_first_filter_description_handles_open_bounds_and_missing_routes(self):
        request = SimpleNamespace(
            activity_type="Ride",
            search_text=None,
            date_from=None,
            date_to="2026-05-01",
            min_distance_km=None,
            max_distance_km=80,
            detailed_route_filter=DETAILED_ROUTE_FILTER_MISSING,
        )

        description = build_local_first_filter_description(request)

        self.assertEqual(
            description,
            "type: Ride · dates: until 2026-05-01 · distance: ≤ 80 km · "
            "routes: missing details",
        )


if __name__ == "__main__":
    unittest.main()
