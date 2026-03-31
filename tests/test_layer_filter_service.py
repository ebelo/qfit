import importlib
import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.activities.domain.activity_query import ActivityQuery, build_subset_string
from qfit.layer_filter_service import LayerFilterService

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    _REAL_QGIS_PRESENT = importlib.util.find_spec("qgis") is not None
except ValueError:
    _REAL_QGIS_PRESENT = any(
        os.path.isdir(os.path.join(p, "qgis")) for p in sys.path if p
    )

try:
    from qfit.layer_manager import LayerManager

    QGIS_AVAILABLE = True
    QGIS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    LayerManager = None
    QGIS_AVAILABLE = False
    QGIS_IMPORT_ERROR = exc

SKIP_REAL = f"QGIS not available: {QGIS_IMPORT_ERROR}" if not QGIS_AVAILABLE else ""


class LayerFilterServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = LayerFilterService()

    def test_apply_filters_sets_subset_string_and_repaints(self):
        layer = MagicMock()
        layer.isValid.return_value = True

        self.service.apply_filters(
            layer,
            activity_type="Ride",
            date_from="2026-03-01",
            date_to="2026-03-31",
            min_distance_km=10,
            max_distance_km=50,
            search_text="alps",
            detailed_only=True,
        )

        expected = build_subset_string(
            ActivityQuery(
                activity_type="Ride",
                date_from="2026-03-01",
                date_to="2026-03-31",
                min_distance_km=10,
                max_distance_km=50,
                search_text="alps",
                detailed_only=True,
            )
        )
        layer.setSubsetString.assert_called_once_with(expected)
        layer.triggerRepaint.assert_called_once_with()

    def test_apply_filters_ignores_none_layer(self):
        self.service.apply_filters(None, activity_type="Ride")

    def test_apply_filters_ignores_invalid_layer(self):
        layer = MagicMock()
        layer.isValid.return_value = False

        self.service.apply_filters(layer, activity_type="Ride")

        layer.setSubsetString.assert_not_called()
        layer.triggerRepaint.assert_not_called()


@unittest.skipUnless(QGIS_AVAILABLE, SKIP_REAL)
class LayerManagerFilterDelegationTests(unittest.TestCase):
    def test_apply_filters_delegates_to_filter_service(self):
        manager = LayerManager(iface=MagicMock())
        manager._filter_service = MagicMock()
        layer = MagicMock()

        manager.apply_filters(
            layer,
            activity_type="Run",
            date_from="2026-01-01",
            date_to="2026-01-31",
            min_distance_km=5,
            max_distance_km=15,
            search_text="tempo",
            detailed_only=True,
        )

        manager._filter_service.apply_filters.assert_called_once_with(
            layer,
            activity_type="Run",
            date_from="2026-01-01",
            date_to="2026-01-31",
            min_distance_km=5,
            max_distance_km=15,
            search_text="tempo",
            detailed_only=True,
        )


if __name__ == "__main__":
    unittest.main()
