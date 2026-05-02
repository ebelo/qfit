from math import atan2, cos, radians, sin, sqrt
from typing import Optional
from xml.parsers import expat

from .routes import RouteProfilePoint


class RouteGpxParseError(ValueError):
    pass


def parse_route_gpx(gpx_text: str) -> list[RouteProfilePoint]:
    if not gpx_text:
        return []

    raw_points: list[tuple[float, float, Optional[float], int]] = []
    current_point: dict[str, object] | None = None
    current_segment_index = 0
    seen_track_segment = False
    element_stack: list[str] = []
    elevation_chunks: list[str] = []

    def start_element(name, attrs):
        nonlocal current_point, current_segment_index, elevation_chunks
        nonlocal seen_track_segment
        local_name = _local_name(name)
        element_stack.append(local_name)
        if local_name == "trkseg":
            if seen_track_segment:
                current_segment_index += 1
            else:
                seen_track_segment = True
        elif local_name in {"trkpt", "rtept"}:
            current_point = {
                "lat": _parse_required_float(attrs.get("lat"), "lat"),
                "lon": _parse_required_float(attrs.get("lon"), "lon"),
                "ele": None,
                "segment_index": current_segment_index,
            }
            elevation_chunks = []
        elif current_point is not None and local_name == "ele":
            elevation_chunks = []

    def character_data(data):
        if (
            current_point is not None
            and element_stack
            and element_stack[-1] == "ele"
        ):
            elevation_chunks.append(data)

    def end_element(name):
        nonlocal current_point, elevation_chunks
        local_name = _local_name(name)
        if current_point is not None and local_name == "ele":
            elevation_text = "".join(elevation_chunks).strip()
            current_point["ele"] = (
                float(elevation_text) if elevation_text else None
            )
        elif current_point is not None and local_name in {"trkpt", "rtept"}:
            raw_points.append(
                (
                    float(current_point["lat"]),
                    float(current_point["lon"]),
                    current_point["ele"],
                    int(current_point["segment_index"]),
                )
            )
            current_point = None
            elevation_chunks = []
        if element_stack:
            element_stack.pop()

    parser = expat.ParserCreate(namespace_separator=" ")
    parser.StartElementHandler = start_element
    parser.CharacterDataHandler = character_data
    parser.EndElementHandler = end_element

    try:
        parser.Parse(gpx_text, True)
    except RouteGpxParseError:
        raise
    except (expat.ExpatError, TypeError, ValueError) as exc:
        raise RouteGpxParseError("Invalid route GPX") from exc

    return _profile_points(raw_points)


def _profile_points(
    raw_points: list[tuple[float, float, Optional[float], int]],
) -> list[RouteProfilePoint]:
    profile_points: list[RouteProfilePoint] = []
    previous: tuple[float, float] | None = None
    previous_segment_index: int | None = None
    cumulative_distance_m = 0.0

    for index, (lat, lon, altitude_m, segment_index) in enumerate(raw_points):
        if previous is not None and previous_segment_index == segment_index:
            cumulative_distance_m += _haversine_distance_m(
                previous[0],
                previous[1],
                lat,
                lon,
            )
        profile_points.append(
            RouteProfilePoint(
                point_index=index,
                lat=lat,
                lon=lon,
                distance_m=cumulative_distance_m,
                segment_index=segment_index,
                altitude_m=altitude_m,
            )
        )
        previous = (lat, lon)
        previous_segment_index = segment_index

    return profile_points


def _parse_required_float(value, field_name):
    if value is None:
        raise RouteGpxParseError(
            "GPX point missing {field_name}".format(field_name=field_name)
        )
    return float(value)


def _local_name(name):
    return str(name).split(" ")[-1]


def _haversine_distance_m(lat_a, lon_a, lat_b, lon_b):
    earth_radius_m = 6371000.0
    lat_a_rad = radians(lat_a)
    lat_b_rad = radians(lat_b)
    delta_lat = radians(lat_b - lat_a)
    delta_lon = radians(lon_b - lon_a)

    haversine = (
        sin(delta_lat / 2) ** 2
        + cos(lat_a_rad) * cos(lat_b_rad) * sin(delta_lon / 2) ** 2
    )
    central_angle = 2 * atan2(sqrt(haversine), sqrt(1 - haversine))
    return earth_radius_m * central_angle
