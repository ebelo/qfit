"""Source-backed Light strokes, independent of native converter versions."""

import math

from ...mapbox_config import _is_mapbox_light_style

_OWNERS = {"road-simple", "tunnel-simple", "bridge-simple", "bridge-case-simple"}
_ZOOM = "@vector_tile_zoom"


def _is_class_width_match(value):
    if not isinstance(value, list) or len(value) < 5 or len(value) % 2 != 1:
        return False
    if value[:2] != ["match", ["get", "class"]]:
        return False
    groups = value[2:-1:2]
    outputs = [*value[3:-1:2], value[-1]]
    return all(
        isinstance(group, list) and group
        and all(isinstance(name, str) for name in group)
        for group in groups
    ) and all(
        not isinstance(width, bool) and isinstance(width, (int, float))
        and math.isfinite(width) and 0 <= width <= 300
        for width in outputs
    )


def _source_widths(style):
    """Recognize only the four audited Light owners and numeric class/zoom shape."""
    if not _is_mapbox_light_style(style):
        return {}
    widths = {}
    for layer in style.get("layers", []):
        if (not isinstance(layer, dict) or layer.get("id") not in _OWNERS
                or layer.get("type") != "line" or layer.get("source-layer") != "road"):
            continue
        width = layer.get("paint", {}).get("line-width")
        stops = [5, 13, 18, 22] if layer["id"] == "road-simple" else [13, 18, 22]
        if (isinstance(width, list)
                and width[:3] == ["interpolate", ["exponential", 1.5], ["zoom"]]
                and len(width) == 3 + 2 * len(stops) and width[3::2] == stops
                and all(_is_class_width_match(output) for output in width[4::2])):
            widths[layer["id"]] = width
    return widths


def _class_width(match):
    from qgis.core import QgsExpression

    cases = []
    for group, value in zip(match[2:-1:2], match[3:-1:2]):
        names = ", ".join(QgsExpression.quotedValue(name) for name in group)
        cases.append(f'WHEN "class" IN ({names}) THEN {value!r}')
    return "(CASE " + " ".join(cases) + f" ELSE {match[-1]!r} END)"


def _width_expression(width):
    """Mapbox base-exponential interpolation with endpoint clamping, then px/mm.

    Older QGIS uses exponent rather than base interpolation, and 3.34 omits the
    unit multiplier for equal expression endpoints. Basic QGIS arithmetic avoids
    both converter dependencies; no artificial stops or version cutoff is needed.
    """
    stops = list(zip(width[3::2], map(_class_width, width[4::2])))
    clauses = [f"WHEN {_ZOOM} <= {stops[0][0]} THEN {stops[0][1]}"]
    for (low, start), (high, end) in zip(stops, stops[1:]):
        ratio = f"((1.5^({_ZOOM} - {low}) - 1) / (1.5^({high} - {low}) - 1))"
        clauses.append(f"WHEN {_ZOOM} <= {high} THEN ({start} + ({end} - {start}) * {ratio})")
    return "(CASE " + " ".join(clauses) + f" ELSE {stops[-1][1]} END) * 25.4 / 96"


def apply_light_road_widths(renderer, source_style: dict) -> int:
    """Restore source widths only on unsplit, fixed-width native road strokes.

    Preserve filters, ordering, other paint and any existing data-defined width.
    Native expression evaluation requests the class field from the VT decoder.
    """
    widths = _source_widths(source_style)
    if not widths:
        return 0
    from qgis.core import Qgis, QgsProperty, QgsSimpleLineSymbolLayer, QgsSymbolLayer

    styles = list(renderer.styles())
    changed = 0
    for rule in styles:
        width = widths.get(rule.styleName())
        symbol = rule.symbol()
        if width is None or rule.layerName() != "road" or symbol is None or symbol.symbolLayerCount() != 1:
            continue
        stroke = symbol.symbolLayer(0)
        if not isinstance(stroke, QgsSimpleLineSymbolLayer) or stroke.widthUnit() != Qgis.RenderUnit.Millimeters:
            continue
        if stroke.dataDefinedProperties().property(QgsSymbolLayer.PropertyStrokeWidth).isActive():
            continue
        stroke.setDataDefinedProperty(QgsSymbolLayer.PropertyStrokeWidth, QgsProperty.fromExpression(_width_expression(width)))
        changed += 1
    if changed:
        renderer.setStyles(styles)
    return changed


_NATIONAL_BOUNDARY_WIDTH = ["interpolate", ["linear"], ["zoom"], 3, 0.65, 12, 2.6]
_NATIONAL_BOUNDARY_EXPRESSION = (
    "(CASE WHEN @vector_tile_zoom <= 3 THEN 0.65 "
    "WHEN @vector_tile_zoom <= 12 THEN 0.65 + 1.95 * (@vector_tile_zoom - 3) / 9 "
    "ELSE 2.6 END) * 25.4 / 96"
)


def _has_solid_national_boundary(style):
    if not _is_mapbox_light_style(style):
        return False
    for layer in style.get("layers", []):
        if not isinstance(layer, dict):
            continue
        paint = layer.get("paint")
        if (layer.get("id") == "admin-0-boundary" and layer.get("type") == "line"
                and layer.get("source-layer") == "admin" and isinstance(paint, dict)
                and paint.get("line-width") == _NATIONAL_BOUNDARY_WIDTH
                and paint.get("line-dasharray") == [10, 0]):
            return True
    return False


def apply_light_national_boundary_stroke(renderer, source_style: dict) -> int:
    """Restore the ordinary national boundary's source width and zero-gap line.

    Native zero-gap custom dashes introduce visible gaps. Use a solid pen for
    this audited source contract; preserve every status/worldview filter and
    other owner, including disputed borders and administrative subdivisions.
    Existing native overrides and changed source contracts are not adapted.
    """
    if not _has_solid_national_boundary(source_style):
        return 0
    from qgis.core import Qgis, QgsProperty, QgsSimpleLineSymbolLayer, QgsSymbolLayer
    from qgis.PyQt.QtCore import Qt

    styles = list(renderer.styles())
    changed = 0
    for rule in styles:
        symbol = rule.symbol()
        if (rule.styleName() != "admin-0-boundary" or rule.layerName() != "admin"
                or symbol is None or symbol.symbolLayerCount() != 1):
            continue
        stroke = symbol.symbolLayer(0)
        if (not isinstance(stroke, QgsSimpleLineSymbolLayer)
                or stroke.widthUnit() != Qgis.RenderUnit.Millimeters
                or stroke.customDashPatternUnit() != Qgis.RenderUnit.Millimeters
                or not stroke.useCustomDashPattern() or stroke.penStyle() != Qt.PenStyle.SolidLine
                or stroke.dataDefinedProperties().hasActiveProperties()):
            continue
        dash = stroke.customDashVector()
        if len(dash) != 2 or dash[1] != 0 or not math.isclose(dash[0], stroke.width() * 10):
            continue
        stroke.setUseCustomDashPattern(False)
        stroke.setDataDefinedProperty(
            QgsSymbolLayer.PropertyStrokeWidth, QgsProperty.fromExpression(_NATIONAL_BOUNDARY_EXPRESSION)
        )
        changed += 1
    if changed:
        renderer.setStyles(styles)
    return changed


_NATIONAL_BACKGROUND_PAINT = {
    "line-width": ["interpolate", ["linear"], ["zoom"], 3, 5.2, 12, 10.4],
    "line-color": "hsl(220, 0%, 87%)",
    "line-opacity": ["interpolate", ["linear"], ["zoom"], 3, 0, 4, 0.5],
    "line-blur": ["interpolate", ["linear"], ["zoom"], 3, 0, 12, 2.6],
}
_NATIONAL_BACKGROUND_WIDTH = (
    "(CASE WHEN @vector_tile_zoom <= 3 THEN 5.2 "
    "WHEN @vector_tile_zoom <= 12 THEN 5.2 + 5.2 * (@vector_tile_zoom - 3) / 9 "
    "ELSE 10.4 END) * 25.4 / 96"
)
_NATIONAL_BACKGROUND_OPACITY = (
    "CASE WHEN @vector_tile_zoom <= 3 THEN 0 "
    "WHEN @vector_tile_zoom < 4 THEN 50 * (@vector_tile_zoom - 3) ELSE 50 END"
)


_NATIONAL_BACKGROUND_FILTER = [
    "all", ["==", ["get", "admin_level"], 0],
    ["==", ["get", "maritime"], "false"],
    ["match", ["get", "worldview"], ["all", "US"], True, False],
]
_ORDINARY_NATIONAL_FILTER = [
    "all", _NATIONAL_BACKGROUND_FILTER[1],
    ["==", ["get", "disputed"], "false"], *_NATIONAL_BACKGROUND_FILTER[2:],
]


def _unique_source_owner(style, owner):
    matches = [layer for layer in style.get("layers", [])
               if isinstance(layer, dict) and layer.get("id") == owner]
    return matches[0] if len(matches) == 1 else {}


def _has_national_background(style):
    if not _has_solid_national_boundary(style):
        return False
    background = _unique_source_owner(style, "admin-0-boundary-bg")
    core = _unique_source_owner(style, "admin-0-boundary")
    return (background.get("type") == "line" and background.get("source-layer") == "admin"
            and background.get("paint") == _NATIONAL_BACKGROUND_PAINT
            and background.get("filter") == _NATIONAL_BACKGROUND_FILTER
            and core.get("filter") == _ORDINARY_NATIONAL_FILTER)


def _has_repaired_ordinary_core(styles):
    from qgis.core import Qgis, QgsSimpleLineSymbolLayer, QgsSymbolLayer
    from qgis.PyQt.QtCore import Qt

    cores = [rule for rule in styles if rule.styleName() == "admin-0-boundary"]
    if len(cores) != 1 or cores[0].layerName() != "admin":
        return False
    symbol = cores[0].symbol()
    if symbol is None or symbol.symbolLayerCount() != 1:
        return False
    stroke = symbol.symbolLayer(0)
    if (not isinstance(stroke, QgsSimpleLineSymbolLayer)
            or stroke.widthUnit() != Qgis.RenderUnit.Millimeters
            or stroke.useCustomDashPattern() or stroke.penStyle() != Qt.PenStyle.SolidLine):
        return False
    width = stroke.dataDefinedProperties().property(QgsSymbolLayer.PropertyStrokeWidth)
    return width.isActive() and width.asExpression() == _NATIONAL_BOUNDARY_EXPRESSION


def _ordinary_background_expression(expression, fallback):
    # The shared owner includes disputes, whose thin native core is not repaired.
    # Match the ordinary core's status predicate; absent/other statuses keep the
    # converted background so a widened continuous halo cannot mask their texture.
    return f"CASE WHEN \"disputed\" IS 'false' THEN ({expression}) ELSE {fallback!r} END"


def apply_light_national_background(renderer, source_style: dict) -> int:
    """Restore the background only for the already-repaired ordinary core.

    Require the matching source predicates and already-repaired ordinary core.
    Keep native blur behavior, color, owner order and eligibility unchanged.
    Active native properties or custom symbols retain their existing path.
    QGIS symbol opacity is a percentage; source opacity is a zero-to-one value.
    """
    if not _has_national_background(source_style):
        return 0
    from qgis.core import Qgis, QgsProperty, QgsSimpleLineSymbolLayer, QgsSymbol, QgsSymbolLayer
    from qgis.PyQt.QtCore import Qt

    styles = list(renderer.styles())
    if not _has_repaired_ordinary_core(styles):
        return 0
    changed = 0
    for rule in styles:
        symbol = rule.symbol()
        if (rule.styleName() != "admin-0-boundary-bg" or rule.layerName() != "admin"
                or symbol is None or symbol.symbolLayerCount() != 1
                or symbol.dataDefinedProperties().hasActiveProperties()):
            continue
        stroke = symbol.symbolLayer(0)
        if (not isinstance(stroke, QgsSimpleLineSymbolLayer)
                or stroke.widthUnit() != Qgis.RenderUnit.Millimeters
                or stroke.useCustomDashPattern() or stroke.penStyle() != Qt.PenStyle.SolidLine
                or stroke.dataDefinedProperties().hasActiveProperties()):
            continue
        stroke.setDataDefinedProperty(
            QgsSymbolLayer.PropertyStrokeWidth, QgsProperty.fromExpression(
                _ordinary_background_expression(_NATIONAL_BACKGROUND_WIDTH, stroke.width())
            )
        )
        symbol.setDataDefinedProperty(
            QgsSymbol.PropertyOpacity, QgsProperty.fromExpression(
                _ordinary_background_expression(_NATIONAL_BACKGROUND_OPACITY, symbol.opacity() * 100)
            )
        )
        changed += 1
    if changed:
        renderer.setStyles(styles)
    return changed
