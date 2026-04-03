"""Render atlas elevation profiles as lightweight SVGs."""

from __future__ import annotations

import math
import os
import tempfile

_PAD_LEFT = 14.0
_PAD_RIGHT = 3.0
_PAD_TOP = 2.0
_PAD_BOTTOM = 6.0

_FILL_COLOR = "#b3cde3"
_STROKE_COLOR = "#6497b1"
_STROKE_WIDTH = 0.4
_GRID_COLOR = "#d0d0d0"
_GRID_WIDTH = 0.15
_AXIS_COLOR = "#999999"
_LABEL_COLOR = "#555555"
_LABEL_FONT_SIZE = 2.2


def _nice_step(raw_step: float) -> float:
    if raw_step <= 0:
        return 1.0
    exponent = math.floor(math.log10(raw_step))
    fraction = raw_step / (10 ** exponent)
    if fraction <= 1.5:
        nice = 1.0
    elif fraction <= 3.5:
        nice = 2.0
    elif fraction <= 7.5:
        nice = 5.0
    else:
        nice = 10.0
    return nice * (10 ** exponent)


def _format_altitude(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:.0f}"
    if value == int(value):
        return str(int(value))
    return f"{value:.0f}"


def _format_distance(value_m: float) -> str:
    if value_m >= 1000:
        km = value_m / 1000.0
        if km == int(km):
            return f"{int(km)} km"
        return f"{km:.1f} km"
    return f"{int(value_m)} m"


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_profile_svg(
    points: list[tuple[float, float]],
    width_mm: float = 190.0,
    height_mm: float = 42.0,
) -> str | None:
    if len(points) < 2:
        return None

    distances = [d for d, _ in points]
    altitudes = [a for _, a in points]
    d_min, d_max = distances[0], distances[-1]
    a_min, a_max = min(altitudes), max(altitudes)

    if d_max <= d_min:
        return None

    a_range = a_max - a_min
    if a_range < 1.0:
        a_range = 1.0
        a_min = a_min - 0.5
        a_max = a_max + 0.5
    else:
        pad = a_range * 0.08
        a_min -= pad
        a_max += pad
        a_range = a_max - a_min

    cx = _PAD_LEFT
    cy = _PAD_TOP
    cw = width_mm - _PAD_LEFT - _PAD_RIGHT
    ch = height_mm - _PAD_TOP - _PAD_BOTTOM

    if cw <= 0 or ch <= 0:
        return None

    def map_x(distance: float) -> float:
        return cx + (distance - d_min) / (d_max - d_min) * cw

    def map_y(altitude: float) -> float:
        return cy + ch - (altitude - a_min) / a_range * ch

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width_mm} {height_mm}" '
        f'width="{width_mm}mm" height="{height_mm}mm">'
    )

    raw_step = a_range / 4.0
    step = _nice_step(raw_step)
    grid_start = math.ceil(a_min / step) * step
    grid_val = grid_start
    while grid_val <= a_max:
        gy = map_y(grid_val)
        if cy <= gy <= cy + ch:
            parts.append(
                f'<line x1="{cx:.2f}" y1="{gy:.2f}" '
                f'x2="{cx + cw:.2f}" y2="{gy:.2f}" '
                f'stroke="{_GRID_COLOR}" stroke-width="{_GRID_WIDTH}" />'
            )
            parts.append(
                f'<text x="{cx - 1:.2f}" y="{gy + 0.7:.2f}" '
                f'text-anchor="end" '
                f'font-size="{_LABEL_FONT_SIZE}" fill="{_LABEL_COLOR}" '
                f'font-family="sans-serif">'
                f'{_xml_escape(_format_altitude(grid_val))}</text>'
            )
        grid_val += step

    parts.append(
        f'<text x="{cx - 1:.2f}" y="{cy - 0.3:.2f}" '
        f'text-anchor="end" '
        f'font-size="{_LABEL_FONT_SIZE * 0.85:.2f}" fill="{_LABEL_COLOR}" '
        f'font-family="sans-serif">m</text>'
    )

    poly_points = [f"{map_x(d):.2f},{map_y(a):.2f}" for d, a in points]
    poly_points.append(f"{map_x(d_max):.2f},{map_y(a_min):.2f}")
    poly_points.append(f"{map_x(d_min):.2f},{map_y(a_min):.2f}")
    polygon_points = " ".join(poly_points)
    parts.append(
        f'<polygon points="{polygon_points}" '
        f'fill="{_FILL_COLOR}" stroke="none" />'
    )

    line_points = " ".join(f"{map_x(d):.2f},{map_y(a):.2f}" for d, a in points)
    parts.append(
        f'<polyline points="{line_points}" '
        f'fill="none" stroke="{_STROKE_COLOR}" '
        f'stroke-width="{_STROKE_WIDTH}" stroke-linejoin="round" />'
    )

    parts.append(
        f'<line x1="{cx:.2f}" y1="{cy:.2f}" '
        f'x2="{cx:.2f}" y2="{cy + ch:.2f}" '
        f'stroke="{_AXIS_COLOR}" stroke-width="{_GRID_WIDTH}" />'
    )
    parts.append(
        f'<line x1="{cx:.2f}" y1="{cy + ch:.2f}" '
        f'x2="{cx + cw:.2f}" y2="{cy + ch:.2f}" '
        f'stroke="{_AXIS_COLOR}" stroke-width="{_GRID_WIDTH}" />'
    )

    d_range = d_max - d_min
    d_step = _nice_step(d_range / 5.0)
    d_grid = math.ceil(d_min / d_step) * d_step
    label_y = cy + ch + _PAD_BOTTOM * 0.7
    while d_grid <= d_max:
        dx = map_x(d_grid)
        if cx <= dx <= cx + cw:
            parts.append(
                f'<line x1="{dx:.2f}" y1="{cy + ch:.2f}" '
                f'x2="{dx:.2f}" y2="{cy + ch + 1:.2f}" '
                f'stroke="{_AXIS_COLOR}" stroke-width="{_GRID_WIDTH}" />'
            )
            parts.append(
                f'<text x="{dx:.2f}" y="{label_y:.2f}" '
                f'text-anchor="middle" '
                f'font-size="{_LABEL_FONT_SIZE}" fill="{_LABEL_COLOR}" '
                f'font-family="sans-serif">'
                f'{_xml_escape(_format_distance(d_grid))}</text>'
            )
        d_grid += d_step

    parts.append("</svg>")
    return "\n".join(parts)


def render_profile_to_file(
    points: list[tuple[float, float]],
    width_mm: float = 190.0,
    height_mm: float = 42.0,
    directory: str | None = None,
) -> str | None:
    svg = render_profile_svg(points, width_mm, height_mm)
    if svg is None:
        return None
    fd, path = tempfile.mkstemp(suffix=".svg", prefix="qfit_profile_", dir=directory)
    try:
        os.write(fd, svg.encode("utf-8"))
    finally:
        os.close(fd)
    return path
