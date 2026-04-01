"""Configuration helpers for native atlas elevation profile styling."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class NativeProfilePlotAxisStyle:
    """Styling defaults for one axis of a native profile plot."""

    suffix: str
    major_grid_props: Mapping[str, str]
    minor_grid_props: Mapping[str, str]


@dataclass(frozen=True)
class NativeProfilePlotStyle:
    """Styling defaults for native QGIS profile plots."""

    background_fill_props: Mapping[str, str]
    border_fill_props: Mapping[str, str]
    x_axis: NativeProfilePlotAxisStyle
    y_axis: NativeProfilePlotAxisStyle


def _immutable_props(**properties: str) -> Mapping[str, str]:
    return MappingProxyType(dict(properties))


DEFAULT_NATIVE_PROFILE_PLOT_STYLE = NativeProfilePlotStyle(
    background_fill_props=_immutable_props(
        color="255,255,255,230",
        outline_style="no",
    ),
    border_fill_props=_immutable_props(
        color="255,255,255,0",
        outline_color="160,160,160,255",
        outline_width="0.2",
    ),
    x_axis=NativeProfilePlotAxisStyle(
        suffix=" km",
        major_grid_props=_immutable_props(color="210,210,210,255", width="0.25"),
        minor_grid_props=_immutable_props(color="235,235,235,255", width="0.15"),
    ),
    y_axis=NativeProfilePlotAxisStyle(
        suffix=" m",
        major_grid_props=_immutable_props(color="210,210,210,255", width="0.25"),
        minor_grid_props=_immutable_props(color="235,235,235,255", width="0.15"),
    ),
)


def _setting_text(settings, key: str) -> str | None:
    if settings is None or not hasattr(settings, "get"):
        return None

    value = settings.get(key, None)
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def build_native_profile_plot_style_from_settings(
    settings,
    *,
    default_style: NativeProfilePlotStyle = DEFAULT_NATIVE_PROFILE_PLOT_STYLE,
) -> NativeProfilePlotStyle:
    """Build a plot style from optional persisted settings overrides."""
    background_fill_color = _setting_text(settings, "atlas_profile_plot_background_fill_color")
    border_color = _setting_text(settings, "atlas_profile_plot_border_color")
    major_grid_color = _setting_text(settings, "atlas_profile_plot_major_grid_color")
    minor_grid_color = _setting_text(settings, "atlas_profile_plot_minor_grid_color")
    x_axis_suffix = _setting_text(settings, "atlas_profile_plot_x_axis_suffix")
    y_axis_suffix = _setting_text(settings, "atlas_profile_plot_y_axis_suffix")

    if not any(
        [
            background_fill_color,
            border_color,
            major_grid_color,
            minor_grid_color,
            x_axis_suffix,
            y_axis_suffix,
        ]
    ):
        return default_style

    background_fill_props = dict(default_style.background_fill_props)
    border_fill_props = dict(default_style.border_fill_props)
    x_axis_major_props = dict(default_style.x_axis.major_grid_props)
    x_axis_minor_props = dict(default_style.x_axis.minor_grid_props)
    y_axis_major_props = dict(default_style.y_axis.major_grid_props)
    y_axis_minor_props = dict(default_style.y_axis.minor_grid_props)

    if background_fill_color is not None:
        background_fill_props["color"] = background_fill_color
    if border_color is not None:
        border_fill_props["outline_color"] = border_color
    if major_grid_color is not None:
        x_axis_major_props["color"] = major_grid_color
        y_axis_major_props["color"] = major_grid_color
    if minor_grid_color is not None:
        x_axis_minor_props["color"] = minor_grid_color
        y_axis_minor_props["color"] = minor_grid_color

    return NativeProfilePlotStyle(
        background_fill_props=_immutable_props(**background_fill_props),
        border_fill_props=_immutable_props(**border_fill_props),
        x_axis=NativeProfilePlotAxisStyle(
            suffix=x_axis_suffix or default_style.x_axis.suffix,
            major_grid_props=_immutable_props(**x_axis_major_props),
            minor_grid_props=_immutable_props(**x_axis_minor_props),
        ),
        y_axis=NativeProfilePlotAxisStyle(
            suffix=y_axis_suffix or default_style.y_axis.suffix,
            major_grid_props=_immutable_props(**y_axis_major_props),
            minor_grid_props=_immutable_props(**y_axis_minor_props),
        ),
    )
