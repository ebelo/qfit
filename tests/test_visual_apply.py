import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call

from tests import _path  # noqa: F401
from qfit.visual_apply import (
    BackgroundConfig,
    LayerRefs,
    VisualApplyResult,
    VisualApplyService,
)


def _make_query(**overrides):
    defaults = dict(
        activity_type="All",
        date_from=None,
        date_to=None,
        min_distance_km=0,
        max_distance_km=0,
        search_text="",
        detailed_only=False,
        sort_label="Date (newest first)",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_bg_config(**overrides):
    defaults = dict(
        enabled=False,
        preset_name="Dark",
        access_token="tok",
        style_owner="mapbox",
        style_id="dark-v11",
        tile_mode="raster",
    )
    defaults.update(overrides)
    return BackgroundConfig(**defaults)


class LayerRefsTests(unittest.TestCase):
    def test_has_any_false_when_all_none(self):
        self.assertFalse(LayerRefs().has_any())

    def test_has_any_true_with_one_layer(self):
        self.assertTrue(LayerRefs(activities=MagicMock()).has_any())

    def test_has_any_true_with_atlas_only(self):
        self.assertTrue(LayerRefs(atlas=MagicMock()).has_any())


class ShouldUpdateBackgroundTests(unittest.TestCase):
    def test_returns_true_when_not_applying_subset_filters(self):
        self.assertTrue(VisualApplyService.should_update_background(False))

    def test_returns_false_when_applying_subset_filters(self):
        self.assertFalse(VisualApplyService.should_update_background(True))


class ApplyWithSubsetFiltersTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.layer_manager.apply_temporal_configuration.return_value = ""
        self.service = VisualApplyService(self.layer_manager)
        self.layers = LayerRefs(
            activities=MagicMock(name="activities"),
            starts=MagicMock(name="starts"),
            points=MagicMock(name="points"),
            atlas=MagicMock(name="atlas"),
        )

    def test_applies_filters_to_all_four_layers(self):
        query = _make_query(activity_type="Run", search_text="trail")

        self.service.apply(
            layers=self.layers,
            query=query,
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(),
            apply_subset_filters=True,
            filtered_count=5,
        )

        self.assertEqual(self.layer_manager.apply_filters.call_count, 4)
        for c in self.layer_manager.apply_filters.call_args_list:
            self.assertEqual(c[0][1], "Run")
            self.assertEqual(c[0][6], "trail")

    def test_applies_style_when_layers_present(self):
        self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="Speed gradient",
            temporal_mode="Off",
            background_config=_make_bg_config(),
            apply_subset_filters=True,
            filtered_count=3,
        )

        self.layer_manager.apply_style.assert_called_once()
        args = self.layer_manager.apply_style.call_args
        self.assertEqual(args[0][4], "Speed gradient")

    def test_status_includes_filtered_count(self):
        result = self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(),
            apply_subset_filters=True,
            filtered_count=42,
        )

        self.assertIn("42", result.status)
        self.assertIn("filters", result.status.lower())

    def test_does_not_update_background_on_filter_apply(self):
        self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=True),
            apply_subset_filters=True,
            filtered_count=0,
        )

        self.layer_manager.ensure_background_layer.assert_not_called()


class ApplyWithoutSubsetFiltersTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.layer_manager.apply_temporal_configuration.return_value = ""
        self.layer_manager.ensure_background_layer.return_value = MagicMock(name="bg")
        self.service = VisualApplyService(self.layer_manager)
        self.layers = LayerRefs(
            activities=MagicMock(name="activities"),
            starts=MagicMock(name="starts"),
            points=MagicMock(name="points"),
            atlas=MagicMock(name="atlas"),
        )

    def test_does_not_apply_filters(self):
        self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(),
            apply_subset_filters=False,
            filtered_count=0,
        )

        self.layer_manager.apply_filters.assert_not_called()

    def test_applies_style_and_temporal(self):
        self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Monthly",
            background_config=_make_bg_config(),
            apply_subset_filters=False,
            filtered_count=0,
        )

        self.layer_manager.apply_style.assert_called_once()
        self.layer_manager.apply_temporal_configuration.assert_called_once()
        args = self.layer_manager.apply_temporal_configuration.call_args
        self.assertEqual(args[0][4], "Monthly")

    def test_updates_background_layer(self):
        bg = _make_bg_config(enabled=True)
        result = self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=bg,
            apply_subset_filters=False,
            filtered_count=0,
        )

        self.layer_manager.ensure_background_layer.assert_called_once_with(
            enabled=True,
            preset_name="Dark",
            access_token="tok",
            style_owner="mapbox",
            style_id="dark-v11",
            tile_mode="raster",
        )
        self.assertIsNotNone(result.background_layer)

    def test_status_mentions_styling_and_background(self):
        bg = _make_bg_config(enabled=True)
        result = self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=bg,
            apply_subset_filters=False,
            filtered_count=0,
        )

        self.assertIn("styling", result.status.lower())
        self.assertIn("background", result.status.lower())

    def test_status_without_background(self):
        result = self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=False),
            apply_subset_filters=False,
            filtered_count=0,
        )

        self.assertIn("styling", result.status.lower())


class BackgroundFailureTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.layer_manager.apply_temporal_configuration.return_value = ""
        self.layer_manager.ensure_background_layer.side_effect = RuntimeError("no tiles")
        self.service = VisualApplyService(self.layer_manager)

    def test_returns_error_status_on_background_failure(self):
        layers = LayerRefs(activities=MagicMock())
        result = self.service.apply(
            layers=layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=True),
            apply_subset_filters=False,
            filtered_count=0,
        )

        self.assertIn("could not be updated", result.status.lower())
        self.assertIsNone(result.background_layer)
        self.assertEqual(result.background_error, "no tiles")

    def test_error_status_with_layers(self):
        layers = LayerRefs(activities=MagicMock())
        result = self.service.apply(
            layers=layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=True),
            apply_subset_filters=False,
            filtered_count=0,
        )

        self.assertIn("loaded layers", result.status.lower())

    def test_error_status_without_layers(self):
        layers = LayerRefs()
        result = self.service.apply(
            layers=layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=True),
            apply_subset_filters=False,
            filtered_count=0,
        )

        self.assertNotIn("loaded layers", result.status.lower())
        self.assertIn("could not be updated", result.status.lower())

    def test_unexpected_background_exception_propagates(self):
        self.layer_manager.ensure_background_layer.side_effect = TypeError("boom")
        with self.assertRaises(TypeError):
            self.service.apply(
                layers=LayerRefs(activities=MagicMock()),
                query=_make_query(),
                style_preset="By activity type",
                temporal_mode="Off",
                background_config=_make_bg_config(enabled=True),
                apply_subset_filters=False,
                filtered_count=0,
            )


class NoLayersTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.layer_manager.apply_temporal_configuration.return_value = ""
        self.layer_manager.ensure_background_layer.return_value = None
        self.service = VisualApplyService(self.layer_manager)

    def test_no_filters_or_style_applied(self):
        result = self.service.apply(
            layers=LayerRefs(),
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(),
            apply_subset_filters=True,
            filtered_count=0,
        )

        self.layer_manager.apply_filters.assert_not_called()
        self.layer_manager.apply_style.assert_not_called()
        self.layer_manager.apply_temporal_configuration.assert_not_called()

    def test_background_cleared_status(self):
        result = self.service.apply(
            layers=LayerRefs(),
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=False),
            apply_subset_filters=False,
            filtered_count=0,
        )

        self.assertIn("cleared", result.status.lower())


class TemporalNoteTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.layer_manager.apply_temporal_configuration.return_value = "Temporal mode: Monthly"
        self.layer_manager.ensure_background_layer.return_value = None
        self.service = VisualApplyService(self.layer_manager)
        self.layers = LayerRefs(activities=MagicMock())

    def test_temporal_note_appended_to_status(self):
        result = self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Monthly",
            background_config=_make_bg_config(),
            apply_subset_filters=False,
            filtered_count=0,
        )

        self.assertIn("Temporal mode: Monthly", result.status)

    def test_temporal_note_appended_to_failure_status(self):
        self.layer_manager.ensure_background_layer.side_effect = RuntimeError("fail")
        result = self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Monthly",
            background_config=_make_bg_config(enabled=True),
            apply_subset_filters=False,
            filtered_count=0,
        )

        self.assertIn("Temporal mode: Monthly", result.status)
        self.assertIn("could not be updated", result.status.lower())


class BackgroundPresetPassthroughTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.layer_manager.apply_temporal_configuration.return_value = ""
        self.service = VisualApplyService(self.layer_manager)
        self.layers = LayerRefs(activities=MagicMock())

    def test_passes_preset_name_to_style_when_enabled(self):
        self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=True, preset_name="Satellite"),
            apply_subset_filters=True,
            filtered_count=0,
        )

        kwargs = self.layer_manager.apply_style.call_args[1]
        self.assertEqual(kwargs["background_preset_name"], "Satellite")

    def test_passes_none_to_style_when_disabled(self):
        self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=False),
            apply_subset_filters=True,
            filtered_count=0,
        )

        kwargs = self.layer_manager.apply_style.call_args[1]
        self.assertIsNone(kwargs["background_preset_name"])


class VisualApplyResultTests(unittest.TestCase):
    def test_default_values(self):
        result = VisualApplyResult()
        self.assertEqual(result.status, "")
        self.assertIsNone(result.background_layer)
        self.assertEqual(result.background_error, "")

    def test_custom_values(self):
        result = VisualApplyResult(
            status="ok", background_layer="layer", background_error="err"
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.background_layer, "layer")
        self.assertEqual(result.background_error, "err")
