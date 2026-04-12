import unittest
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401
from qfit.visualization.application.background_map_controller import (
    BackgroundMapController,
    LoadBackgroundRequest,
    LoadBackgroundResult,
)


class ResolveStyleDefaultsTests(unittest.TestCase):
    def test_returns_defaults_when_forced(self):
        lm = MagicMock()
        ctrl = BackgroundMapController(lm)
        result = ctrl.resolve_style_defaults("Mapbox Dark", "existing", "existing", force=True)
        self.assertIsNotNone(result)
        owner, style_id = result
        self.assertTrue(owner)
        self.assertTrue(style_id)

    def test_returns_none_when_current_values_set_and_not_forced(self):
        lm = MagicMock()
        ctrl = BackgroundMapController(lm)
        result = ctrl.resolve_style_defaults("Mapbox Dark", "mapbox", "dark-v11", force=False)
        self.assertIsNone(result)

    def test_returns_defaults_when_current_values_empty(self):
        lm = MagicMock()
        ctrl = BackgroundMapController(lm)
        result = ctrl.resolve_style_defaults("Mapbox Dark", "", "", force=False)
        self.assertIsNotNone(result)

    def test_returns_none_for_custom_style_preset(self):
        lm = MagicMock()
        ctrl = BackgroundMapController(lm)
        result = ctrl.resolve_style_defaults("Custom", "any", "any", force=True)
        self.assertIsNone(result)


class LoadBackgroundTests(unittest.TestCase):
    def test_build_load_request_returns_dataclass(self):
        lm = MagicMock()
        ctrl = BackgroundMapController(lm)

        request = ctrl.build_load_request(
            enabled=True,
            preset_name="Mapbox Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
            tile_mode="raster",
        )

        self.assertIsInstance(request, LoadBackgroundRequest)
        self.assertTrue(request.enabled)
        self.assertEqual(request.style_id, "dark-v11")

    def test_delegates_to_layer_manager(self):
        lm = MagicMock()
        sentinel = object()
        lm.ensure_background_layer.return_value = sentinel
        ctrl = BackgroundMapController(lm)

        with patch(
            "qfit.visualization.application.background_map_controller.build_background_map_loaded_status",
            return_value="Background map loaded below the qfit activity layers",
        ) as build_status:
            result = ctrl.load_background(
                enabled=True,
                preset_name="Mapbox Dark",
                access_token="tok",
                style_owner="mapbox",
                style_id="dark-v11",
                tile_mode="raster",
            )

        self.assertIsInstance(result, LoadBackgroundResult)
        self.assertIs(result.layer, sentinel)
        self.assertEqual(result.status, "Background map loaded below the qfit activity layers")
        build_status.assert_called_once_with()
        lm.ensure_background_layer.assert_called_once_with(
            enabled=True,
            preset_name="Mapbox Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
            tile_mode="raster",
        )

    def test_returns_none_when_disabled(self):
        lm = MagicMock()
        lm.ensure_background_layer.return_value = None
        ctrl = BackgroundMapController(lm)

        with patch(
            "qfit.visualization.application.background_map_controller.build_background_map_cleared_status",
            return_value="Background map cleared",
        ) as build_status:
            result = ctrl.load_background(
                enabled=False,
                preset_name="Mapbox Dark",
                access_token="",
                style_owner="",
                style_id="",
                tile_mode="raster",
            )

        self.assertIsNone(result.layer)
        self.assertEqual(result.status, "Background map cleared")
        build_status.assert_called_once_with()
