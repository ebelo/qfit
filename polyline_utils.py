def decode_polyline(encoded: str | None) -> list[tuple[float, float]]:
    """Decode a Google encoded polyline into (lat, lon) tuples."""
    if not encoded:
        return []

    index = 0
    lat = 0
    lon = 0
    coordinates = []

    while index < len(encoded):
        shift = 0
        result = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lat = ~(result >> 1) if result & 1 else (result >> 1)
        lat += delta_lat

        shift = 0
        result = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lon = ~(result >> 1) if result & 1 else (result >> 1)
        lon += delta_lon

        coordinates.append((lat / 1e5, lon / 1e5))

    return coordinates
