import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401
from qfit.visualization.application.render_plan import (
    DEFAULT_RENDER_PRESET,
    RENDERER_SIMPLE_LINES,
)
from qfit.visualization.application.visual_apply import (
    BackgroundConfig,
    LayerRefs,
    VisualApplyRequest,
    VisualApplyResult,
    VisualApplyService,
)
from qfit.visualization.application.visual_apply_messages import (
    build_visual_apply_background_failure_result_status,
    build_visual_apply_result_status,
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
        detailed_route_filter="any",
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


class BuildRequestTests(unittest.TestCase):
    def test_build_request_returns_structured_request(self):
        request = VisualApplyService.build_request(
            layers=LayerRefs(activities=MagicMock()),
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(),
            apply_subset_filters=True,
            filtered_count=7,
        )

        self.assertIsInstance(request, VisualApplyRequest)
        self.assertEqual(request.style_preset, "By activity type")
        self.assertTrue(request.apply_subset_filters)


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
        query = _make_query(activity_type="Run", search_text="trail", detailed_route_filter="missing")

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
            self.assertEqual(c[0][8], "missing")

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

    def test_builds_and_passes_render_plan(self):
        self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="Heatmap",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=True, preset_name="Satellite"),
            apply_subset_filters=True,
            filtered_count=3,
        )

        kwargs = self.layer_manager.apply_style.call_args[1]
        render_plan = kwargs["render_plan"]
        self.assertEqual(render_plan.preset_name, DEFAULT_RENDER_PRESET)
        self.assertEqual(render_plan.activities.renderer_family, RENDERER_SIMPLE_LINES)
        self.assertEqual(render_plan.background_preset_name, "Satellite")
        self.layer_manager.has_features.assert_not_called()

    def test_render_plan_tolerates_layers_without_feature_count(self):
        self.layers.starts = SimpleNamespace(name="starts")
        self.layers.points = SimpleNamespace(name="points")

        self.service.apply(
            layers=self.layers,
            query=_make_query(),
            style_preset="Track points",
            temporal_mode="Off",
            background_config=_make_bg_config(),
            apply_subset_filters=True,
            filtered_count=3,
        )

        kwargs = self.layer_manager.apply_style.call_args[1]
        render_plan = kwargs["render_plan"]
        self.assertEqual(render_plan.points.renderer_family, "track_points")
        self.layer_manager.has_features.assert_not_called()

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

    def test_status_selection_uses_helper(self):
        with patch(
            "qfit.visualization.application.visual_apply.build_visual_apply_result_status",
            return_value="Applied filters and styling (42 matching activities)",
        ) as build_status:
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
        build_status.assert_called_once_with(
            has_layers=True,
            apply_subset_filters=True,
            filtered_count=42,
            wants_background=False,
            background_loaded=False,
            temporal_note="",
        )

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

    def test_apply_request_accepts_structured_request(self):
        request = self.service.build_request(
            layers=self.layers,
            query=_make_query(activity_type="Run"),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=True),
            apply_subset_filters=True,
            filtered_count=2,
        )

        result = self.service.apply_request(request)

        self.assertIn("Applied filters and styling", result.status)


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

    def test_returns_cleared_status_via_helper_when_background_is_not_loaded(self):
        self.layer_manager.ensure_background_layer.return_value = None

        with patch(
            "qfit.visualization.application.visual_apply.build_visual_apply_result_status",
            return_value="Background map cleared",
        ) as build_status:
            result = self.service.apply(
                layers=LayerRefs(),
                query=_make_query(),
                style_preset="By activity type",
                temporal_mode="Off",
                background_config=_make_bg_config(enabled=False),
                apply_subset_filters=False,
                filtered_count=0,
            )

        self.assertEqual(result.status, "Background map cleared")
        build_status.assert_called_once_with(
            has_layers=False,
            apply_subset_filters=False,
            filtered_count=0,
            wants_background=False,
            background_loaded=False,
            temporal_note="",
        )

    def test_returns_loaded_background_status_via_helper_when_only_background_is_loaded(self):
        with patch(
            "qfit.visualization.application.visual_apply.build_visual_apply_result_status",
            return_value="Background map loaded below the qfit activity layers",
        ) as build_status:
            result = self.service.apply(
                layers=LayerRefs(),
                query=_make_query(),
                style_preset="By activity type",
                temporal_mode="Off",
                background_config=_make_bg_config(enabled=True),
                apply_subset_filters=False,
                filtered_count=0,
            )

        self.assertEqual(result.status, "Background map loaded below the qfit activity layers")
        build_status.assert_called_once_with(
            has_layers=False,
            apply_subset_filters=False,
            filtered_count=0,
            wants_background=True,
            background_loaded=True,
            temporal_note="",
        )

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

    def test_returns_styled_background_loaded_status_via_helper(self):
        bg = _make_bg_config(enabled=True)

        with patch(
            "qfit.visualization.application.visual_apply.build_visual_apply_result_status",
            return_value="Applied styling and loaded the background map below the qfit activity layers",
        ) as build_status:
            result = self.service.apply(
                layers=self.layers,
                query=_make_query(),
                style_preset="By activity type",
                temporal_mode="Off",
                background_config=bg,
                apply_subset_filters=False,
                filtered_count=0,
            )

        self.assertEqual(
            result.status,
            "Applied styling and loaded the background map below the qfit activity layers",
        )
        build_status.assert_called_once_with(
            has_layers=True,
            apply_subset_filters=False,
            filtered_count=0,
            wants_background=True,
            background_loaded=True,
            temporal_note="",
        )

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

        with patch(
            "qfit.visualization.application.visual_apply.build_visual_apply_background_failure_result_status",
            return_value="Loaded layers with styling, but the background map could not be updated",
        ) as build_status:
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
        build_status.assert_called_once_with(
            has_layers=True,
            temporal_note="",
        )

    def test_error_status_without_layers(self):
        layers = LayerRefs()

        with patch(
            "qfit.visualization.application.visual_apply.build_visual_apply_background_failure_result_status",
            return_value="Background map could not be updated",
        ) as build_status:
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
        build_status.assert_called_once_with(
            has_layers=False,
            temporal_note="",
        )

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

    def test_styled_only_status_uses_helper(self):
        layers = LayerRefs(activities=MagicMock())

        with patch(
            "qfit.visualization.application.visual_apply.build_visual_apply_result_status",
            return_value="Applied styling to the loaded qfit layers",
        ) as build_status:
            result = self.service.apply(
                layers=layers,
                query=_make_query(),
                style_preset="By activity type",
                temporal_mode="Off",
                background_config=_make_bg_config(enabled=False),
                apply_subset_filters=False,
                filtered_count=0,
            )

        self.assertIn("applied styling", result.status.lower())
        build_status.assert_called_once_with(
            has_layers=True,
            apply_subset_filters=False,
            filtered_count=0,
            wants_background=False,
            background_loaded=False,
            temporal_note="",
        )


class TemporalNoteTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.layer_manager.apply_temporal_configuration.return_value = "Temporal mode: Monthly"
        self.layer_manager.ensure_background_layer.return_value = None
        self.service = VisualApplyService(self.layer_manager)
        self.layers = LayerRefs(activities=MagicMock())

    def test_temporal_note_appended_to_status(self):
        with patch(
            "qfit.visualization.application.visual_apply.build_visual_apply_result_status",
            wraps=build_visual_apply_result_status,
        ) as build_status:
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
        build_status.assert_called_once_with(
            has_layers=True,
            apply_subset_filters=False,
            filtered_count=0,
            wants_background=False,
            background_loaded=False,
            temporal_note="Temporal mode: Monthly",
        )

    def test_temporal_note_appended_to_failure_status(self):
        self.layer_manager.ensure_background_layer.side_effect = RuntimeError("fail")
        with patch(
            "qfit.visualization.application.visual_apply.build_visual_apply_background_failure_result_status",
            wraps=build_visual_apply_background_failure_result_status,
        ) as build_status:
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
        build_status.assert_called_once_with(
            has_layers=True,
            temporal_note="Temporal mode: Monthly",
        )


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


class VisualApplyRequestContractTests(unittest.TestCase):
    def test_build_request_returns_dataclass(self):
        request = VisualApplyService.build_request(
            layers=LayerRefs(activities=MagicMock()),
            query=_make_query(activity_type="Ride"),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=True),
            apply_subset_filters=True,
            filtered_count=7,
        )

        self.assertIsInstance(request, VisualApplyRequest)
        self.assertTrue(request.apply_subset_filters)
        self.assertEqual(request.filtered_count, 7)
        self.assertEqual(request.query.activity_type, "Ride")

    def test_apply_request_matches_legacy_wrapper(self):
        layer_manager = MagicMock()
        layer_manager.apply_temporal_configuration.return_value = ""
        layer_manager.ensure_background_layer.return_value = None
        service = VisualApplyService(layer_manager)
        layers = LayerRefs(activities=MagicMock())
        request = service.build_request(
            layers=layers,
            query=_make_query(),
            style_preset="By activity type",
            temporal_mode="Off",
            background_config=_make_bg_config(enabled=False),
            apply_subset_filters=False,
            filtered_count=0,
        )

        via_request = service.apply_request(request)
        via_wrapper = service.apply(
            layers=layers,
            query=request.query,
            style_preset=request.style_preset,
            temporal_mode=request.temporal_mode,
            background_config=request.background_config,
            apply_subset_filters=request.apply_subset_filters,
            filtered_count=request.filtered_count,
        )

        self.assertEqual(via_request.status, via_wrapper.status)
        self.assertEqual(via_request.background_error, via_wrapper.background_error)
