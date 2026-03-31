import logging

from .mapbox_config import preset_defaults, preset_requires_custom_style
from .visualization.application.layer_gateway import LayerGateway

logger = logging.getLogger(__name__)


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

    def load_background(self, enabled, preset_name, access_token, style_owner, style_id, tile_mode):
        """Apply the background layer via the layer gateway and return the layer (or *None*)."""
        layer = self._layer_gateway.ensure_background_layer(
            enabled=enabled,
            preset_name=preset_name,
            access_token=access_token,
            style_owner=style_owner,
            style_id=style_id,
            tile_mode=tile_mode,
        )
        return layer
