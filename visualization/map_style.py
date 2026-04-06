from __future__ import annotations

from dataclasses import dataclass
import colorsys
from typing import Iterable

from ..activities.domain.activity_classification import (
    normalize_activity_type as normalize_activity_value,
    preferred_activity_field,
    resolve_activity_family,
)

DEFAULT_SIMPLE_LINE_HEX = "#2A9D8F"
_DEFAULT_CONTEXT = "Outdoor"

_ACTIVITY_COLORS = {
    "run": "#D62828",
    "trailrun": "#9D0208",
    "virtualrun": "#868E96",
    "ride": "#F77F00",
    "mountainbikeride": "#D95F02",
    "gravelride": "#BC6C25",
    "ebikeride": "#6C757D",
    "walk": "#FFD60A",
    "hike": "#F9C74F",
    "backpacking": "#E9C46A",
    "alpineski": "#0077B6",
    "backcountryski": "#023E8A",
    "nordicski": "#0096C7",
    "snowboard": "#00B4D8",
    "snowshoe": "#48CAE4",
    "swim": "#0077B6",
    "openwaterswim": "#023E8A",
    "kayaking": "#1B9AAA",
    "canoeing": "#2A9D8F",
    "rowing": "#264653",
    "standuppaddling": "#48CAE4",
    "surfing": "#0096C7",
    "rockclimbing": "#8B5E34",
    "mountaineering": "#6B4423",
    "iceclimbing": "#90E0EF",
    "workout": "#7B2CBF",
    "crossfit": "#5A189A",
    "weighttraining": "#3C096C",
    "yoga": "#C77DFF",
    "virtualride": "#6C757D",
    "commute": "#495057",
    "other": "#9E9E9E",
}

_FAMILY_FALLBACKS = {
    "running": "#D62828",
    "cycling": "#F77F00",
    "walking": "#FFD60A",
    "winter": "#0077B6",
    "water": "#00B4D8",
    "mountain": "#8B5E34",
    "fitness": "#7B2CBF",
    "machine": "#6C757D",
}


@dataclass(frozen=True)
class BasemapLineStyle:
    line_width: float
    opacity: float
    outline_color: str | None = None
    outline_width: float = 0.0


_BASEMAP_LINE_STYLES = {
    "Outdoor": BasemapLineStyle(line_width=1.8, opacity=0.85),
    "Light": BasemapLineStyle(line_width=2.1, opacity=0.9, outline_color="#333333", outline_width=0.4),
    "Satellite": BasemapLineStyle(line_width=2.3, opacity=0.95, outline_color="#FFFFFF", outline_width=1.0),
}


def pick_activity_style_field(available_fields: Iterable[str]) -> str | None:
    return preferred_activity_field(available_fields)


def resolve_basemap_line_style(preset_name: str | None) -> BasemapLineStyle:
    return _BASEMAP_LINE_STYLES.get((preset_name or "").strip(), _BASEMAP_LINE_STYLES[_DEFAULT_CONTEXT])


def resolve_activity_color(activity_value: object, basemap_preset_name: str | None = None) -> str:
    normalized = normalize_activity_value(activity_value)
    base_hex = _ACTIVITY_COLORS.get(normalized)
    if base_hex is None:
        base_hex = _FAMILY_FALLBACKS[resolve_activity_family(activity_value)]
    return adapt_color_for_basemap(base_hex, basemap_preset_name)


def adapt_color_for_basemap(color_hex: str, basemap_preset_name: str | None) -> str:
    context = (basemap_preset_name or "").strip() or _DEFAULT_CONTEXT
    if context not in {"Light", "Satellite"}:
        return color_hex.upper()

    red, green, blue = _hex_to_rgb(color_hex)
    hue, lightness, saturation = colorsys.rgb_to_hls(red / 255.0, green / 255.0, blue / 255.0)

    if context == "Light":
        lightness = _clamp(lightness * 0.84)
        saturation = _clamp(saturation * 1.05)
    else:
        lightness = _clamp(lightness * 1.08 + 0.02)
        saturation = _clamp(saturation * 1.03)

    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return _rgb_to_hex(round(red * 255), round(green * 255), round(blue * 255))


def _hex_to_rgb(color_hex: str) -> tuple[int, int, int]:
    value = color_hex.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected a 6-digit hex color, got: {color_hex!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_to_hex(red: int, green: int, blue: int) -> str:
    return f"#{red:02X}{green:02X}{blue:02X}"


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))
