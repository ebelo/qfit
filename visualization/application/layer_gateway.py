from __future__ import annotations

from typing import Protocol, runtime_checkable

from .render_plan import RenderPlan


@runtime_checkable
class LayerGateway(Protocol):
    """Application-facing boundary for qfit layer and map operations."""

    def load_output_layers(self, gpkg_path): ...

    def remove_layers(self, layers): ...

    def has_features(self, layer): ...

    def ensure_background_layer(
        self,
        enabled,
        preset_name,
        access_token,
        style_owner="",
        style_id="",
        tile_mode="raster",
    ): ...

    def apply_filters(
        self,
        layer,
        activity_type=None,
        date_from=None,
        date_to=None,
        min_distance_km=None,
        max_distance_km=None,
        search_text=None,
        detailed_only=False,
        detailed_route_filter=None,
    ): ...

    def apply_style(
        self,
        activities_layer,
        starts_layer,
        points_layer,
        atlas_layer,
        preset=None,
        background_preset_name=None,
        render_plan: RenderPlan | None = None,
    ): ...

    def apply_temporal_configuration(
        self,
        activities_layer,
        starts_layer,
        points_layer,
        atlas_layer,
        mode_label,
    ): ...
