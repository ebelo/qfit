import logging
from dataclasses import dataclass, field

from ...activities.application.activity_selection_state import ActivitySelectionState
from ...activities.domain.activity_query import ActivityQuery
from ...mapbox_config import MapboxConfigError
from .layer_gateway import LayerGateway
from .render_plan import build_render_plan
from .visual_apply_messages import (
    build_visual_apply_background_failure_result_status,
    build_visual_apply_result_status,
)

logger = logging.getLogger(__name__)


@dataclass
class LayerRefs:
    """References to the four qfit output layers."""

    activities: object = None
    starts: object = None
    points: object = None
    atlas: object = None

    def has_any(self):
        return any(
            layer is not None
            for layer in [self.activities, self.starts, self.points, self.atlas]
        )


@dataclass
class BackgroundConfig:
    """Settings needed to manage the background map layer."""

    enabled: bool = False
    preset_name: str = ""
    access_token: str = ""
    style_owner: str = ""
    style_id: str = ""
    tile_mode: str = ""


@dataclass
class ApplyVisualizationRequest:
    """Structured input for the visualization/apply workflow."""

    layers: LayerRefs = field(default_factory=LayerRefs)
    selection_state: ActivitySelectionState = field(default_factory=ActivitySelectionState)
    style_preset: str = ""
    temporal_mode: str = ""
    background_config: BackgroundConfig = field(default_factory=BackgroundConfig)
    apply_subset_filters: bool = False

    @property
    def query(self):
        return self.selection_state.query

    @property
    def filtered_count(self):
        return self.selection_state.filtered_count


# Backward-compatible alias while the request-object migration lands incrementally.
VisualApplyRequest = ApplyVisualizationRequest


@dataclass
class VisualApplyResult:
    """Structured result from a visual-apply operation."""

    status: str = ""
    background_layer: object = None
    background_error: str = ""


class VisualApplyService:
    """Applies filters, styling, temporal config, and background to qfit layers.

    Extracted from ``QfitDockWidget._apply_visual_configuration`` so the
    orchestration logic can be tested without a live UI.
    """

    def __init__(self, layer_gateway: LayerGateway):
        self.layer_gateway = layer_gateway

    @staticmethod
    def should_update_background(apply_subset_filters):
        """Background layer is only updated on initial load, not on filter-only applies."""
        return not apply_subset_filters

    @staticmethod
    def build_request(
        layers,
        style_preset,
        temporal_mode,
        background_config,
        apply_subset_filters,
        selection_state=None,
        query=None,
        filtered_count=0,
    ) -> ApplyVisualizationRequest:
        if selection_state is None:
            selection_state = ActivitySelectionState(
                query=query if query is not None else ActivityQuery(),
                filtered_count=filtered_count,
            )
        return ApplyVisualizationRequest(
            layers=layers,
            selection_state=selection_state,
            style_preset=style_preset,
            temporal_mode=temporal_mode,
            background_config=background_config,
            apply_subset_filters=apply_subset_filters,
        )

    def apply(self, request: ApplyVisualizationRequest | None = None, **legacy_kwargs):
        """Apply visual configuration to layers and return a result."""
        if request is None:
            request = self.build_request(**legacy_kwargs)

        has_layers = request.layers.has_any()
        temporal_note = ""

        if has_layers and request.apply_subset_filters:
            self._apply_filters_to_all_layers(request.layers, request.query)

        if has_layers:
            render_plan = build_render_plan(
                request.style_preset,
                has_start_features=self.layer_gateway.has_features(request.layers.starts),
                has_point_features=self.layer_gateway.has_features(request.layers.points),
                has_points_layer=request.layers.points is not None,
                background_preset_name=(
                    request.background_config.preset_name
                    if request.background_config.enabled
                    else None
                ),
            )
            self.layer_gateway.apply_style(
                request.layers.activities,
                request.layers.starts,
                request.layers.points,
                request.layers.atlas,
                request.style_preset,
                background_preset_name=render_plan.background_preset_name,
                render_plan=render_plan,
            )
            temporal_note = self.layer_gateway.apply_temporal_configuration(
                request.layers.activities,
                request.layers.starts,
                request.layers.points,
                request.layers.atlas,
                request.temporal_mode,
            )

        background_layer = None
        if self.should_update_background(request.apply_subset_filters):
            background_layer, bg_error = self._ensure_background(request.background_config)
            if bg_error is not None:
                failure_status = build_visual_apply_background_failure_result_status(
                    has_layers=has_layers,
                    temporal_note=temporal_note,
                )
                return VisualApplyResult(
                    status=failure_status,
                    background_layer=None,
                    background_error=bg_error,
                )

        status = build_visual_apply_result_status(
            has_layers=has_layers,
            apply_subset_filters=request.apply_subset_filters,
            filtered_count=request.filtered_count,
            wants_background=request.background_config.enabled,
            background_loaded=background_layer is not None,
            temporal_note=temporal_note,
        )
        return VisualApplyResult(status=status, background_layer=background_layer)

    def apply_request(self, request: ApplyVisualizationRequest):
        return self.apply(request=request)

    def _apply_filters_to_all_layers(self, layers, query):
        for layer in [layers.activities, layers.starts, layers.points, layers.atlas]:
            self.layer_gateway.apply_filters(
                layer,
                query.activity_type,
                query.date_from,
                query.date_to,
                query.min_distance_km,
                query.max_distance_km,
                query.search_text,
                query.detailed_only,
                query.detailed_route_filter,
            )

    def _ensure_background(self, config):
        """Try to load/update the background layer.

        Returns ``(layer, None)`` on success or ``(None, error_message)`` on
        failure.
        """
        try:
            layer = self.layer_gateway.ensure_background_layer(
                enabled=config.enabled,
                preset_name=config.preset_name,
                access_token=config.access_token,
                style_owner=config.style_owner,
                style_id=config.style_id,
                tile_mode=config.tile_mode,
            )
            return layer, None
        except (MapboxConfigError, RuntimeError) as exc:
            return None, str(exc)
