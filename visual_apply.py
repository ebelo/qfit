import logging
from dataclasses import dataclass

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

    def __init__(self, layer_manager):
        self.layer_manager = layer_manager

    @staticmethod
    def should_update_background(apply_subset_filters):
        """Background layer is only updated on initial load, not on filter-only applies."""
        return not apply_subset_filters

    def apply(
        self,
        layers,
        query,
        style_preset,
        temporal_mode,
        background_config,
        apply_subset_filters,
        filtered_count,
    ):
        """Apply visual configuration to layers and return a result.

        Parameters
        ----------
        layers : LayerRefs
            References to the four qfit output layers.
        query : ActivityQuery
            Current filter/sort query built from UI state.
        style_preset : str
            Name of the selected style preset.
        temporal_mode : str
            Name of the selected temporal mode.
        background_config : BackgroundConfig
            Background map settings.
        apply_subset_filters : bool
            Whether to apply subset filters to layers.
        filtered_count : int
            Number of activities matching the current query (for status text).
        """
        has_layers = layers.has_any()
        temporal_note = ""

        if has_layers and apply_subset_filters:
            self._apply_filters_to_all_layers(layers, query)

        if has_layers:
            self.layer_manager.apply_style(
                layers.activities,
                layers.starts,
                layers.points,
                layers.atlas,
                style_preset,
                background_preset_name=(
                    background_config.preset_name if background_config.enabled else None
                ),
            )
            temporal_note = self.layer_manager.apply_temporal_configuration(
                layers.activities,
                layers.starts,
                layers.points,
                layers.atlas,
                temporal_mode,
            )

        background_layer = None
        if self.should_update_background(apply_subset_filters):
            background_layer, bg_error = self._ensure_background(background_config)
            if bg_error is not None:
                failure_status = self._background_failure_status(
                    has_layers, temporal_note, bg_error
                )
                return VisualApplyResult(
                    status=failure_status,
                    background_layer=None,
                    background_error=bg_error,
                )

        status = self._build_status(
            has_layers=has_layers,
            apply_subset_filters=apply_subset_filters,
            filtered_count=filtered_count,
            wants_background=background_config.enabled,
            background_layer=background_layer,
            temporal_note=temporal_note,
        )
        return VisualApplyResult(status=status, background_layer=background_layer)

    def _apply_filters_to_all_layers(self, layers, query):
        for layer in [layers.activities, layers.starts, layers.points, layers.atlas]:
            self.layer_manager.apply_filters(
                layer,
                query.activity_type,
                query.date_from,
                query.date_to,
                query.min_distance_km,
                query.max_distance_km,
                query.search_text,
                query.detailed_only,
            )

    def _ensure_background(self, config):
        """Try to load/update the background layer.

        Returns ``(layer, None)`` on success or ``(None, error_message)`` on
        failure.
        """
        try:
            layer = self.layer_manager.ensure_background_layer(
                enabled=config.enabled,
                preset_name=config.preset_name,
                access_token=config.access_token,
                style_owner=config.style_owner,
                style_id=config.style_id,
                tile_mode=config.tile_mode,
            )
            return layer, None
        except (RuntimeError, Exception) as exc:
            return None, str(exc)

    @staticmethod
    def _background_failure_status(has_layers, temporal_note, error):
        if not has_layers:
            status = "Background map could not be updated"
        else:
            status = "Loaded layers with styling, but the background map could not be updated"
        if temporal_note:
            status = "{status}. {temporal_note}.".format(
                status=status, temporal_note=temporal_note
            )
        return status

    @staticmethod
    def _build_status(
        has_layers,
        apply_subset_filters,
        filtered_count,
        wants_background,
        background_layer,
        temporal_note,
    ):
        if apply_subset_filters and has_layers:
            status = "Applied filters and styling ({count} matching activities)".format(
                count=filtered_count
            )
        elif has_layers and wants_background and background_layer is not None:
            status = "Applied styling and loaded the background map below the qfit activity layers"
        elif has_layers:
            status = "Applied styling to the loaded qfit layers"
        elif wants_background and background_layer is not None:
            status = "Background map loaded below the qfit activity layers"
        else:
            status = "Background map cleared"

        if temporal_note:
            status = "{status}. {temporal_note}.".format(
                status=status, temporal_note=temporal_note
            )
        return status
