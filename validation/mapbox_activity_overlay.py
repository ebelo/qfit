from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from qfit.visualization.map_style import resolve_activity_color, resolve_basemap_line_style

WEB_MERCATOR_HALF_WORLD = 20037508.342789244
WEB_MERCATOR_TILE_SIZE = 512
PIXELS_PER_MILLIMETER = 96.0 / 25.4
ACTIVITY_TYPE_FIELD = "sport_type"
ACTIVITY_TYPES = ("Run", "Ride", "Hike")


class OverlayCamera(Protocol):
    longitude: float
    latitude: float
    zoom: float
    width: int
    height: int


@dataclass(frozen=True)
class ActivityOverlayRoute:
    activity_type: str
    coordinates: tuple[tuple[float, float], ...]


_ROUTE_SCREEN_POINTS = (
    ("Run", ((0.08, 0.24), (0.25, 0.34), (0.43, 0.27), (0.62, 0.43), (0.88, 0.35))),
    ("Ride", ((0.07, 0.74), (0.26, 0.61), (0.45, 0.70), (0.65, 0.55), (0.90, 0.67))),
    ("Hike", ((0.18, 0.49), (0.34, 0.42), (0.50, 0.52), (0.67, 0.46), (0.82, 0.51))),
)


def _camera_extent_web_mercator(camera: OverlayCamera) -> tuple[float, float, float, float]:
    clamped_latitude = min(85.05112878, max(-85.05112878, camera.latitude))
    center_x = camera.longitude * WEB_MERCATOR_HALF_WORLD / 180.0
    center_y = math.log(math.tan((90.0 + clamped_latitude) * math.pi / 360.0))
    center_y *= WEB_MERCATOR_HALF_WORLD / math.pi
    world_pixels = WEB_MERCATOR_TILE_SIZE * (2**camera.zoom)
    meters_per_pixel = (WEB_MERCATOR_HALF_WORLD * 2.0) / world_pixels
    half_width = camera.width * meters_per_pixel / 2.0
    half_height = camera.height * meters_per_pixel / 2.0
    return (
        center_x - half_width,
        center_y - half_height,
        center_x + half_width,
        center_y + half_height,
    )


def activity_overlay_routes_web_mercator(
    camera: OverlayCamera,
) -> tuple[ActivityOverlayRoute, ...]:
    left, bottom, right, top = _camera_extent_web_mercator(camera)
    width = right - left
    height = top - bottom
    return tuple(
        ActivityOverlayRoute(
            activity_type=activity_type,
            coordinates=tuple((left + x * width, top - y * height) for x, y in screen_points),
        )
        for activity_type, screen_points in _ROUTE_SCREEN_POINTS
    )


def _web_mercator_to_lon_lat(x: float, y: float) -> tuple[float, float]:
    longitude = x * 180.0 / WEB_MERCATOR_HALF_WORLD
    latitude = math.degrees(
        2.0 * math.atan(math.exp(y / WEB_MERCATOR_HALF_WORLD * math.pi)) - math.pi / 2.0
    )
    return longitude, latitude


def activity_overlay_geojson(camera: OverlayCamera) -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {ACTIVITY_TYPE_FIELD: route.activity_type},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        list(_web_mercator_to_lon_lat(x, y)) for x, y in route.coordinates
                    ],
                },
            }
            for route in activity_overlay_routes_web_mercator(camera)
        ],
    }


def activity_overlay_mapbox_layers(
    *, basemap_preset_name: str = "Light"
) -> list[dict[str, object]]:
    line_style = resolve_basemap_line_style(basemap_preset_name)
    match_expression: list[object] = ["match", ["get", ACTIVITY_TYPE_FIELD]]
    for activity_type in ACTIVITY_TYPES:
        match_expression.extend(
            [activity_type, resolve_activity_color(activity_type, basemap_preset_name)]
        )
    match_expression.append(resolve_activity_color("Other", basemap_preset_name))

    layers: list[dict[str, object]] = []
    if line_style.outline_color and line_style.outline_width > 0:
        layers.append(
            {
                "id": "qfit-activity-overlay-outline",
                "type": "line",
                "source": "qfit-activity-overlay",
                "paint": {
                    "line-color": line_style.outline_color,
                    "line-width": (
                        line_style.line_width + line_style.outline_width * 2.0
                    )
                    * PIXELS_PER_MILLIMETER,
                    "line-opacity": line_style.opacity,
                },
                "layout": {"line-cap": "round", "line-join": "round"},
            }
        )
    layers.append(
        {
            "id": "qfit-activity-overlay-core",
            "type": "line",
            "source": "qfit-activity-overlay",
            "paint": {
                "line-color": match_expression,
                "line-width": line_style.line_width * PIXELS_PER_MILLIMETER,
                "line-opacity": line_style.opacity,
            },
            "layout": {"line-cap": "round", "line-join": "round"},
        }
    )
    return layers
