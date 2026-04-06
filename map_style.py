"""Compatibility shim for visualization map-style helpers.

Prefer importing from ``qfit.visualization.map_style``.
This module remains as a stable forwarding import during the package move.
"""

from .visualization.map_style import (
    DEFAULT_SIMPLE_LINE_HEX,
    BasemapLineStyle,
    adapt_color_for_basemap,
    pick_activity_style_field,
    resolve_activity_color,
    resolve_activity_family,
    resolve_basemap_line_style,
)

__all__ = [
    "DEFAULT_SIMPLE_LINE_HEX",
    "BasemapLineStyle",
    "adapt_color_for_basemap",
    "pick_activity_style_field",
    "resolve_activity_color",
    "resolve_activity_family",
    "resolve_basemap_line_style",
]
