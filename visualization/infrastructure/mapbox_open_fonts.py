"""Resolve available open alternatives for the audited built-in DIN font stacks."""

from ...mapbox_config import _is_mapbox_light_style, _is_mapbox_outdoors_style

OPEN_FONT_FAMILY = "Barlow"
DIN_STYLES = {
    "DIN Pro Regular": "Regular",
    "DIN Pro Medium": "Medium",
    "DIN Pro Italic": "Italic",
    "DIN Pro Bold": "Bold",
}


# Existing Light camera/conversion bands bound the validated typography changes.
# Low-zoom country/state labels and mid-zoom roads retain their previous fonts.
LIGHT_FONT_MIN_ZOOMS = {
    "road-label-simple": 15,
    "waterway-label": 0,
    "water-line-label": 0,
    "water-point-label": 0,
    "natural-line-label": 8,
    "natural-point-label": 8,
    "airport-label": 8,
    "settlement-subdivision-label": 8,
    "settlement-minor-label": 8,
    "settlement-major-label": 8,
    "poi-label": 16,
}


def _source_layers(source_style):
    return [layer for layer in source_style.get("layers", []) if isinstance(layer, dict)]


def source_font_styles(source_style: dict) -> dict[str, str]:
    """Preserve source style distinctions before QGIS-safe simplification."""
    if not (_is_mapbox_outdoors_style(source_style) or _is_mapbox_light_style(source_style)):
        return {}
    result = {}
    for layer in _source_layers(source_style):
        stack = layer.get("layout", {}).get("text-font")
        if not isinstance(stack, list) or not stack or not isinstance(stack[0], str):
            continue
        style = DIN_STYLES.get(stack[0])
        name = layer.get("id")
        if style is not None and isinstance(name, str) and name:
            result[name] = style
    return result


def _available_styles(styles):
    from qgis.PyQt.QtGui import QFont, QFontInfo

    available = set()
    for style in set(styles):
        candidate = QFont(OPEN_FONT_FAMILY)
        candidate.setStyleName(style)
        resolved = QFontInfo(candidate)
        if resolved.family() == OPEN_FONT_FAMILY and resolved.styleName() == style:
            available.add(style)
    return available


def _set_open_font(label, face):
    settings = label.labelSettings()
    text_format = settings.format()
    font = text_format.font()
    # Qt 5 retains the converter's family list unless both are replaced.
    font.setFamily(OPEN_FONT_FAMILY)
    font.setFamilies([OPEN_FONT_FAMILY, "Noto Sans"])
    font.setStyleName(face)
    text_format.setFont(font)
    settings.setFormat(text_format)
    label.setLabelSettings(settings)


def _font_zoom_variants(label, minimum):
    """Preserve inclusive QGIS zoom bounds and leave lower bands untouched."""
    if minimum == 0:
        return [label], label
    maximum = label.maxZoomLevel()
    if maximum >= 0 and maximum < minimum:
        return [label], None
    if label.minZoomLevel() >= minimum:
        return [label], label
    from qgis.core import QgsVectorTileBasicLabelingStyle

    after = QgsVectorTileBasicLabelingStyle(label)
    after.setMinZoomLevel(minimum)
    after.setStyleName(f"{label.styleName()}-qfit-open-fonts-z{minimum}-plus")
    label.setMaxZoomLevel(minimum - 1)
    return [label, after], after


def apply_available_mapbox_fonts(labeling, source_style: dict) -> int:
    """Apply verified faces only in the preset/role/zoom ranges proven useful.

    Missing faces and custom styles retain the previous conversion. Light keeps
    low-zoom administrative names and mid-zoom road/POI placement unchanged.
    """
    mapping = source_font_styles(source_style)
    if not mapping:
        return 0
    available = _available_styles(mapping.values())
    owners = sorted(
        (layer["id"] for layer in _source_layers(source_style) if isinstance(layer.get("id"), str)),
        key=len, reverse=True,
    )
    light = _is_mapbox_light_style(source_style)
    result = []
    changed = 0
    for label in labeling.styles():
        name = label.styleName()
        owner = next((key for key in owners if name == key or name.startswith(key + "-")), None)
        minimum = LIGHT_FONT_MIN_ZOOMS.get(owner) if light else 0
        if mapping.get(owner) not in available or minimum is None:
            result.append(label)
            continue
        variants, target = _font_zoom_variants(label, minimum)
        result.extend(variants)
        if target is not None:
            _set_open_font(target, mapping[owner])
            changed += 1
    if changed:
        labeling.setStyles(result)
    return changed


def apply_available_outdoors_fonts(labeling, source_style: dict) -> int:
    """Compatibility entry point, retaining its Outdoors-only behavior."""
    if not _is_mapbox_outdoors_style(source_style):
        return 0
    return apply_available_mapbox_fonts(labeling, source_style)
