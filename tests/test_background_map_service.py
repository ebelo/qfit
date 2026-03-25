import os
import unittest
from unittest.mock import MagicMock, patch, call

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from qfit.background_map_service import BackgroundMapService
    from qfit.mapbox_config import BACKGROUND_LAYER_PREFIX, TILE_MODE_RASTER, TILE_MODE_VECTOR

    QGIS_AVAILABLE = True
    QGIS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    BackgroundMapService = None
    BACKGROUND_LAYER_PREFIX = "qfit background"
    TILE_MODE_RASTER = "Raster"
    TILE_MODE_VECTOR = "Vector"
    QGIS_AVAILABLE = False
    QGIS_IMPORT_ERROR = exc

SKIP_MSG = f"QGIS not available: {QGIS_IMPORT_ERROR}" if not QGIS_AVAILABLE else ""


def _make_project_mock(layers=None):
    """Return a mock QgsProject.instance() with the given layers dict."""
    mock_project = MagicMock()
    mock_project.mapLayers.return_value = layers or {}
    mock_root = MagicMock()
    mock_root.children.return_value = []
    mock_project.layerTreeRoot.return_value = mock_root
    return mock_project


def _make_layer_node(layer_name, layer_class=None):
    """Return a (node, layer) pair whose node.layer() returns the layer mock."""
    layer = MagicMock()
    layer.name.return_value = layer_name
    if layer_class is not None:
        layer.__class__ = layer_class
    node = MagicMock()
    node.layer.return_value = layer
    return node, layer


@unittest.skipUnless(QGIS_AVAILABLE, SKIP_MSG)
class EnsureBackgroundLayerDisabledTests(unittest.TestCase):
    """When enabled=False the service removes existing background layers."""

    def test_returns_none_when_disabled(self):
        service = BackgroundMapService()
        mock_project = _make_project_mock()
        with patch("qfit.background_map_service.QgsProject") as qp:
            qp.instance.return_value = mock_project
            result = service.ensure_background_layer(
                enabled=False, preset_name="Outdoor", access_token="tok"
            )
        self.assertIsNone(result)

    def test_removes_existing_background_layers_when_disabled(self):
        service = BackgroundMapService()

        bg_layer = MagicMock()
        bg_layer.name.return_value = f"{BACKGROUND_LAYER_PREFIX} — Outdoor"
        bg_layer.id.return_value = "bg-id"

        other_layer = MagicMock()
        other_layer.name.return_value = "qfit activities"

        mock_project = _make_project_mock({"bg-id": bg_layer, "act-id": other_layer})
        with patch("qfit.background_map_service.QgsProject") as qp:
            qp.instance.return_value = mock_project
            service.ensure_background_layer(
                enabled=False, preset_name="Outdoor", access_token="tok"
            )

        mock_project.removeMapLayer.assert_called_once_with("bg-id")


@unittest.skipUnless(QGIS_AVAILABLE, SKIP_MSG)
class MoveBackgroundLayersToBottomTests(unittest.TestCase):
    """Background layer nodes must be placed after all other nodes."""

    def test_background_node_moved_to_end(self):
        service = BackgroundMapService()

        bg_node, _ = _make_layer_node(f"{BACKGROUND_LAYER_PREFIX} — Outdoor")
        other_node, _ = _make_layer_node("qfit activities")

        mock_root = MagicMock()
        # Start with background first — should be reordered.
        mock_root.children.return_value = [bg_node, other_node]

        mock_project = _make_project_mock()
        mock_project.layerTreeRoot.return_value = mock_root

        with patch("qfit.background_map_service.QgsProject") as qp:
            qp.instance.return_value = mock_project
            service.move_background_layers_to_bottom()

        mock_root.reorderChildren.assert_called_once_with([other_node, bg_node])

    def test_no_reorder_when_already_at_bottom(self):
        service = BackgroundMapService()

        other_node, _ = _make_layer_node("qfit activities")
        bg_node, _ = _make_layer_node(f"{BACKGROUND_LAYER_PREFIX} — Outdoor")

        mock_root = MagicMock()
        # Background is already last — desired == current, no reorder expected.
        mock_root.children.return_value = [other_node, bg_node]

        mock_project = _make_project_mock()
        mock_project.layerTreeRoot.return_value = mock_root

        with patch("qfit.background_map_service.QgsProject") as qp:
            qp.instance.return_value = mock_project
            service.move_background_layers_to_bottom()

        mock_root.reorderChildren.assert_not_called()

    def test_empty_tree_does_not_raise(self):
        service = BackgroundMapService()

        mock_root = MagicMock()
        mock_root.children.return_value = []

        mock_project = _make_project_mock()
        mock_project.layerTreeRoot.return_value = mock_root

        with patch("qfit.background_map_service.QgsProject") as qp:
            qp.instance.return_value = mock_project
            service.move_background_layers_to_bottom()

        mock_root.reorderChildren.assert_not_called()


@unittest.skipUnless(QGIS_AVAILABLE, SKIP_MSG)
class SnapExtentToBackgroundTileZoomTests(unittest.TestCase):
    """snap_extent_to_background_tile_zoom delegates to pure math only when conditions are met."""

    def _make_extent(self, xmin, ymin, xmax, ymax):
        extent = MagicMock()
        extent.isEmpty.return_value = False
        extent.xMinimum.return_value = float(xmin)
        extent.yMinimum.return_value = float(ymin)
        extent.xMaximum.return_value = float(xmax)
        extent.yMaximum.return_value = float(ymax)
        return extent

    def test_returns_extent_unchanged_when_empty(self):
        service = BackgroundMapService()
        extent = MagicMock()
        extent.isEmpty.return_value = True
        canvas = MagicMock()

        with patch("qfit.background_map_service.QgsProject"):
            result = service.snap_extent_to_background_tile_zoom(extent, canvas)

        self.assertIs(result, extent)

    def test_returns_extent_unchanged_when_none(self):
        service = BackgroundMapService()
        canvas = MagicMock()

        with patch("qfit.background_map_service.QgsProject"):
            result = service.snap_extent_to_background_tile_zoom(None, canvas)

        self.assertIsNone(result)

    def test_returns_extent_unchanged_when_crs_not_web_mercator(self):
        service = BackgroundMapService()
        extent = self._make_extent(0, 0, 1000, 1000)
        canvas = MagicMock()

        mock_project = _make_project_mock()
        mock_crs = MagicMock()
        mock_crs.authid.return_value = "EPSG:4326"
        mock_project.crs.return_value = mock_crs

        with patch("qfit.background_map_service.QgsProject") as qp:
            qp.instance.return_value = mock_project
            result = service.snap_extent_to_background_tile_zoom(extent, canvas)

        self.assertIs(result, extent)

    def test_returns_extent_unchanged_when_no_raster_background(self):
        service = BackgroundMapService()
        extent = self._make_extent(0, 0, 1_000_000, 1_000_000)
        canvas = MagicMock()
        canvas.width.return_value = 1024
        canvas.height.return_value = 768

        mock_project = _make_project_mock()
        mock_crs = MagicMock()
        mock_crs.authid.return_value = "EPSG:3857"
        mock_project.crs.return_value = mock_crs
        # No raster background layers
        mock_project.mapLayers.return_value = {}

        with patch("qfit.background_map_service.QgsProject") as qp:
            qp.instance.return_value = mock_project
            result = service.snap_extent_to_background_tile_zoom(extent, canvas)

        self.assertIs(result, extent)

    def test_snaps_extent_when_raster_background_present(self):
        """When a raster background exists in EPSG:3857, extent is snapped."""
        try:
            from qgis.core import QgsRasterLayer  # noqa: PLC0415
        except ImportError:  # pragma: no cover
            self.skipTest("QgsRasterLayer not importable")

        service = BackgroundMapService()

        # Use a realistic Web Mercator bounding box (roughly Switzerland)
        extent = self._make_extent(700_000, 5_700_000, 1_100_000, 5_980_000)
        canvas = MagicMock()
        canvas.width.return_value = 1024
        canvas.height.return_value = 768

        mock_crs = MagicMock()
        mock_crs.authid.return_value = "EPSG:3857"

        raster_layer = MagicMock(spec=QgsRasterLayer)
        raster_layer.name.return_value = f"{BACKGROUND_LAYER_PREFIX} — Outdoor"

        mock_project = _make_project_mock({"bg-id": raster_layer})
        mock_project.crs.return_value = mock_crs

        with patch("qfit.background_map_service.QgsProject") as qp, \
             patch("qfit.background_map_service.QgsRectangle") as mock_rect:
            qp.instance.return_value = mock_project
            mock_rect.return_value = MagicMock()
            result = service.snap_extent_to_background_tile_zoom(extent, canvas)

        # Snapping was attempted: QgsRectangle was called with snapped coords.
        mock_rect.assert_called_once()
        args = mock_rect.call_args[0]
        self.assertEqual(len(args), 4)


@unittest.skipUnless(QGIS_AVAILABLE, SKIP_MSG)
class RemoveBackgroundLayersTests(unittest.TestCase):
    """_remove_background_layers removes only background-prefixed layers."""

    def test_removes_background_layers_only(self):
        service = BackgroundMapService()

        bg_layer = MagicMock()
        bg_layer.name.return_value = f"{BACKGROUND_LAYER_PREFIX} — Outdoor"
        bg_layer.id.return_value = "bg-1"

        other_layer = MagicMock()
        other_layer.name.return_value = "qfit activities"
        other_layer.id.return_value = "act-1"

        mock_project = _make_project_mock({"bg-1": bg_layer, "act-1": other_layer})

        with patch("qfit.background_map_service.QgsProject") as qp:
            qp.instance.return_value = mock_project
            service._remove_background_layers()

        mock_project.removeMapLayer.assert_called_once_with("bg-1")

    def test_no_removal_when_no_background_layers(self):
        service = BackgroundMapService()

        layer = MagicMock()
        layer.name.return_value = "qfit activities"
        mock_project = _make_project_mock({"act-1": layer})

        with patch("qfit.background_map_service.QgsProject") as qp:
            qp.instance.return_value = mock_project
            service._remove_background_layers()

        mock_project.removeMapLayer.assert_not_called()
