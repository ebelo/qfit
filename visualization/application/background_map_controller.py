import logging
from dataclasses import dataclass

from ...mapbox_config import preset_defaults, preset_requires_custom_style
from .background_map_messages import (
    build_background_map_result_status,
)
from .layer_gateway import LayerGateway

logger = logging.getLogger(__name__)


@dataclass
class LoadBackgroundRequest:
    """Structured input for the background-map workflow."""

    enabled: bool = False
    preset_name: str = ""
    access_token: str = ""
    style_owner: str = ""
    style_id: str = ""
    tile_mode: str = "raster"


@dataclass
class LoadBackgroundResult:
    """Structured result from loading or clearing a background map."""

    layer: object = None
    status: str = ""


class BackgroundMapController:
    """Orchestrates background map configuration and loading."""

    def __init__(self, layer_gateway: LayerGateway):
        self._layer_gateway = layer_gateway

    def resolve_style_defaults(self, preset_name, current_owner, current_style_id, force=False):
        """Return ``(owner, style_id)`` to apply for *preset_name*.

        Returns ``None`` when the current values should be kept.
        """
        if preset_requires_custom_style(preset_name):
            return None
        if current_owner and current_style_id and not force:
            return None
        return preset_defaults(preset_name)

    @staticmethod
    def build_load_request(
        enabled,
        preset_name,
        access_token,
        style_owner,
        style_id,
        tile_mode,
    ) -> LoadBackgroundRequest:
        return LoadBackgroundRequest(
            enabled=enabled,
            preset_name=preset_name,
            access_token=access_token,
            style_owner=style_owner,
            style_id=style_id,
            tile_mode=tile_mode,
        )

    def load_background(
        self,
        request: LoadBackgroundRequest | None = None,
        **legacy_kwargs,
    ) -> LoadBackgroundResult:
        """Apply the background layer via the layer gateway and return a structured result."""
        if request is None:
            request = self.build_load_request(**legacy_kwargs)

        layer = self._layer_gateway.ensure_background_layer(
            enabled=request.enabled,
            preset_name=request.preset_name,
            access_token=request.access_token,
            style_owner=request.style_owner,
            style_id=request.style_id,
            tile_mode=request.tile_mode,
        )
        status = build_background_map_result_status(
            enabled=request.enabled,
            background_loaded=layer is not None,
        )
        return LoadBackgroundResult(layer=layer, status=status)

    def load_background_request(self, request: LoadBackgroundRequest) -> LoadBackgroundResult:
        return self.load_background(request=request)
