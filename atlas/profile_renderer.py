"""Render a route elevation profile as an SVG image.

Produces a lightweight SVG string (no external dependencies) that can be
written to a temporary file and embedded in a QGIS print layout via
:class:`QgsLayoutItemPicture`.
"""

from __future__ import annotations

import math
import os
import tempfile


# Layout constants for the chart within the SVG (all in viewBox units = mm)
_PAD_LEFT = 14.0    # space for altitude labels
_PAD_RIGHT = 3.0
_PAD_TOP = 2.0
_PAD_BOTTOM = 6.0   # space for distance labels

# Styling
_FILL_COLOR = "#b3cde3"       # light blue fill
_STROKE_COLOR = "#6497b1"     # darker blue stroke
_STROKE_WIDTH = 0.4
_GRID_COLOR = "#d0d0d0"
_GRID_WIDTH = 0.15
_AXIS_COLOR = "#999999"
_LABEL_COLOR = "#555555"
_LABEL_FONT_SIZE = 2.2        # mm


def _nice_step(raw_step: float) -> float:
    """Round *raw_step* to a 'nice' interval (1, 2, 5, 10, 20, 50, …)."""
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
    """Format altitude for axis label."""
    if abs(value) >= 1000:
        return f"{value:.0f}"
    if value == int(value):
        return str(int(value))
    return f"{value:.0f}"


def _format_distance(value_m: float) -> str:
    """Format distance for axis label."""
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
    """Render an elevation profile as an SVG string.

    Parameters
    ----------
    points:
        List of ``(distance_m, altitude_m)`` tuples, ordered by distance.
    width_mm:
        SVG width in millimetres (matches layout item width).
    height_mm:
        SVG height in millimetres (matches layout item height).

    Returns
    -------
    str | None
        SVG markup string, or ``None`` if *points* has fewer than 2 entries.
    """
    if len(points) < 2:
        return None

    # Data range
    distances = [d for d, _ in points]
    altitudes = [a for _, a in points]
    d_min, d_max = distances[0], distances[-1]
    a_min, a_max = min(altitudes), max(altitudes)

    if d_max <= d_min:
        return None

    # Add small padding to altitude range so the line doesn't touch edges
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

    # Chart drawing area
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

    # Build SVG parts
    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width_mm} {height_mm}" '
        f'width="{width_mm}mm" height="{height_mm}mm">'
    )

    # Horizontal grid lines (altitude)
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

    # Altitude unit label
    parts.append(
        f'<text x="{cx - 1:.2f}" y="{cy - 0.3:.2f}" '
        f'text-anchor="end" '
        f'font-size="{_LABEL_FONT_SIZE * 0.85:.2f}" fill="{_LABEL_COLOR}" '
        f'font-family="sans-serif">m</text>'
    )

    # Filled area polygon
    poly_points = []
    for d, a in points:
        poly_points.append(f"{map_x(d):.2f},{map_y(a):.2f}")
    # Close polygon at baseline
    poly_points.append(f"{map_x(d_max):.2f},{map_y(a_min):.2f}")
    poly_points.append(f"{map_x(d_min):.2f},{map_y(a_min):.2f}")
    parts.append(
        f'<polygon points="{" ".join(poly_points)}" '
        f'fill="{_FILL_COLOR}" stroke="none" />'
    )

    # Profile line on top of fill
    line_points = " ".join(
        f"{map_x(d):.2f},{map_y(a):.2f}" for d, a in points
    )
    parts.append(
        f'<polyline points="{line_points}" '
        f'fill="none" stroke="{_STROKE_COLOR}" '
        f'stroke-width="{_STROKE_WIDTH}" stroke-linejoin="round" />'
    )

    # Chart border (left + bottom axis lines)
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

    # Distance labels along bottom axis
    d_range = d_max - d_min
    d_step = _nice_step(d_range / 5.0)
    d_grid = math.ceil(d_min / d_step) * d_step
    label_y = cy + ch + _PAD_BOTTOM * 0.7
    while d_grid <= d_max:
        dx = map_x(d_grid)
        if cx <= dx <= cx + cw:
            # Tick mark
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
    """Render profile SVG to a temporary file and return the path.

    Returns ``None`` if the profile cannot be rendered (too few points).
    The caller is responsible for cleaning up the file.
    """
    svg = render_profile_svg(points, width_mm, height_mm)
    if svg is None:
        return None
    fd, path = tempfile.mkstemp(suffix=".svg", prefix="qfit_profile_", dir=directory)
    try:
        os.write(fd, svg.encode("utf-8"))
    finally:
        os.close(fd)
    return path


def load_profile_samples_from_gpkg(
    gpkg_path: str,
) -> dict[str, list[tuple[float, float]]]:
    """Load atlas profile samples from a GeoPackage, grouped by page_sort_key.

    Returns a dict mapping ``page_sort_key`` to a list of
    ``(distance_m, altitude_m)`` tuples ordered by ``profile_point_index``.

    Returns an empty dict if the table does not exist or cannot be read.
    """
    import sqlite3  # noqa: PLC0415

    result: dict[str, list[tuple[float, float]]] = {}
    try:
        conn = sqlite3.connect(gpkg_path)
        try:
            cursor = conn.execute(
                "SELECT page_sort_key, distance_m, altitude_m "
                "FROM atlas_profile_samples "
                "ORDER BY page_sort_key, profile_point_index"
            )
            for page_sort_key, distance_m, altitude_m in cursor:
                if page_sort_key is None:
                    continue
                if distance_m is None or altitude_m is None:
                    continue
                result.setdefault(page_sort_key, []).append(
                    (float(distance_m), float(altitude_m))
                )
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        pass
    return result
