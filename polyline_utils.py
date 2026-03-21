from typing import List, Optional, Tuple


def _decode_value(encoded: str, index: int) -> Tuple[int, int]:
    shift = 0
    result = 0

    while True:
        if index >= len(encoded):
            raise ValueError("Truncated encoded polyline")

        byte = ord(encoded[index]) - 63
        index += 1
        result |= (byte & 0x1F) << shift
        shift += 5
        if byte < 0x20:
            break

    delta = ~(result >> 1) if result & 1 else (result >> 1)
    return delta, index


def decode_polyline(encoded: Optional[str]) -> List[Tuple[float, float]]:
    """Decode a Google encoded polyline into (lat, lon) tuples.

    Invalid or truncated input returns an empty list instead of raising, which
    keeps downstream QGIS import/render flows resilient to bad upstream data.
    """
    if not encoded:
        return []

    index = 0
    lat = 0
    lon = 0
    coordinates: List[Tuple[float, float]] = []

    try:
        while index < len(encoded):
            delta_lat, index = _decode_value(encoded, index)
            lat += delta_lat

            delta_lon, index = _decode_value(encoded, index)
            lon += delta_lon

            coordinates.append((lat / 1e5, lon / 1e5))
    except ValueError:
        return []

    return coordinates
