from __future__ import annotations

from typing import Iterable

_LINE_GEOMETRY_TYPE = 1
_LINE_WKB_TYPES = frozenset((2, 5))


def layer_features(layer):
    if layer is None:
        return ()
    features = getattr(layer, "getFeatures", None)
    if not callable(features):
        return ()
    return features()


def sample_group_key(sample, group_field_sets):
    for group_fields in group_field_sets:
        values = tuple(sample_value(sample, field_name) for field_name in group_fields)
        if any(value not in (None, "") for value in values):
            return values
    return (None,)


def sample_value(sample, field_name):
    if isinstance(sample, dict):
        return sample.get(field_name)
    try:
        return sample[field_name]
    except (KeyError, IndexError, TypeError, AttributeError):
        pass
    value = getattr(sample, field_name, None)
    if callable(value):
        return value()
    return value


def numeric_value(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sample_xy(sample):
    geometry = _sample_geometry(sample)
    if geometry is not None and not _is_empty_geometry(geometry):
        point = _geometry_point(geometry)
        xy = _point_xy(point)
        if xy is not None:
            return xy

    lon = numeric_value(sample_value(sample, "lon"))
    lat = numeric_value(sample_value(sample, "lat"))
    if lon is None or lat is None:
        return None
    return lon, lat


def is_line_layer(layer) -> bool:
    geometry_type = _call_if_present(layer, "geometryType")
    if _looks_like_line_geometry_type(geometry_type):
        return True
    wkb_type = _call_if_present(layer, "wkbType")
    return _looks_like_line_wkb_type(wkb_type)


def has_fields(layer, expected: Iterable[str]) -> bool:
    field_names = _field_names(layer)
    return all(field_name in field_names for field_name in expected)


def _sample_geometry(sample):
    geometry = getattr(sample, "geometry", None)
    if callable(geometry):
        return geometry()
    return geometry


def _is_empty_geometry(geometry) -> bool:
    is_empty = getattr(geometry, "isEmpty", None)
    return bool(is_empty()) if callable(is_empty) else False


def _geometry_point(geometry):
    as_point = getattr(geometry, "asPoint", None)
    if callable(as_point):
        return as_point()
    return geometry


def _point_xy(point):
    if point is None:
        return None
    x_value = _coordinate_value(point, "x")
    y_value = _coordinate_value(point, "y")
    if x_value is None or y_value is None:
        return None
    return x_value, y_value


def _coordinate_value(point, attr):
    value = getattr(point, attr, None)
    if callable(value):
        value = value()
    return numeric_value(value)


def _field_names(layer) -> frozenset[str]:
    if layer is None:
        return frozenset()
    fields = layer.fields() if callable(getattr(layer, "fields", None)) else ()
    names: list[str] = []
    for field in fields or ():
        name = field.name() if callable(getattr(field, "name", None)) else field
        if name:
            names.append(str(name))
    return frozenset(names)


def _call_if_present(obj, attr: str):
    method = getattr(obj, attr, None)
    if callable(method):
        return method()
    return None


def _looks_like_line_geometry_type(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        lowered = value.lower()
        return "line" in lowered and "polygon" not in lowered
    # QgsWkbTypes.LineGeometry is 1 in QGIS, but keep this module QGIS-free.
    return value == _LINE_GEOMETRY_TYPE


def _looks_like_line_wkb_type(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        lowered = value.lower()
        return "line" in lowered and "polygon" not in lowered
    # Common QgsWkbTypes values: LineString=2 and MultiLineString=5.
    return value in _LINE_WKB_TYPES


__all__ = [
    "has_fields",
    "is_line_layer",
    "layer_features",
    "numeric_value",
    "sample_group_key",
    "sample_value",
    "sample_xy",
]
