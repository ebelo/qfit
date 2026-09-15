"""Preserve source-specific Light label content and cross-feature spacing."""

import math

from ...mapbox_config import (
    _is_mapbox_light_style, _waterway_label_symbol_spacing_layer_variants,
)

_ROAD_LABEL_ID = "road-label-simple"
_ROAD_LABEL_RULES = {_ROAD_LABEL_ID, _ROAD_LABEL_ID + "-z12-to-z15"}
_DEFAULT_SYMBOL_SPACING_PX = 250.0
_PIXEL_TO_MM = 25.4 / 96.0
_PLACE_NAME_OWNERS = {"country-label", "settlement-major-label"}
_NAME_EN_FALLBACK = ["coalesce", ["get", "name_en"], ["get", "name"]]


def _road_symbol_spacing(source_style):
    if not _is_mapbox_light_style(source_style):
        return None
    for layer in source_style.get("layers", []):
        if not isinstance(layer, dict) or layer.get("id") != _ROAD_LABEL_ID:
            continue
        layout = layer.get("layout", {})
        if layer.get("source-layer") != "road" or layout.get("symbol-placement") != "line":
            return None
        spacing = layout.get("symbol-spacing", _DEFAULT_SYMBOL_SPACING_PX)
        # Expression-based spacing needs its own zoom-aware implementation.
        if isinstance(spacing, bool) or not isinstance(spacing, (int, float)):
            return None
        return spacing if math.isfinite(spacing) and spacing > 0 else None
    return None


def apply_light_road_duplicate_spacing(labeling, source_style: dict) -> int:
    """Apply source spacing between duplicate road names, not along each part.

    QGIS 3.44 introduced cross-feature duplicate removal. Older supported QGIS
    versions retain their existing labels. Run before font-band splitting so
    both the original and derived rules inherit the same placement settings.
    """
    spacing = _road_symbol_spacing(source_style)
    if spacing is None:
        return 0
    try:
        from qgis.core import Qgis, QgsLabelThinningSettings
    except ImportError:
        # Some supported versions predate the thinning settings class itself.
        return 0

    if not hasattr(QgsLabelThinningSettings, "setAllowDuplicateRemoval"):
        return 0
    styles = list(labeling.styles())
    changed = 0
    for label in styles:
        if label.styleName() not in _ROAD_LABEL_RULES:
            continue
        settings = label.labelSettings()
        thinning = settings.thinningSettings()
        # Retain explicit converter/user duplicate-removal settings.
        if thinning.allowDuplicateRemoval():
            continue
        thinning.setAllowDuplicateRemoval(True)
        thinning.setMinimumDistanceToDuplicate(spacing * _PIXEL_TO_MM)
        thinning.setMinimumDistanceToDuplicateUnit(Qgis.RenderUnit.Millimeters)
        settings.setThinningSettings(thinning)
        label.setLabelSettings(settings)
        changed += 1
    if changed:
        labeling.setStyles(styles)
    return changed


def _light_name_fallback_owners(source_style):
    if not _is_mapbox_light_style(source_style):
        return set()
    return {
        layer["id"] for layer in source_style.get("layers", [])
        if isinstance(layer, dict)
        and layer.get("id") in _PLACE_NAME_OWNERS
        and layer.get("type") == "symbol"
        and layer.get("source-layer") == "place_label"
        and layer.get("layout", {}).get("text-field") == _NAME_EN_FALLBACK
    }


def _light_road_name_fallback_rules(source_style):
    if not _is_mapbox_light_style(source_style):
        return set()
    layers = source_style.get("layers", [])
    # A source-owned layer must never be mistaken for our generated size band.
    derived_ids = _ROAD_LABEL_RULES - {_ROAD_LABEL_ID}
    if any(isinstance(layer, dict) and layer.get("id") in derived_ids for layer in layers):
        return set()
    owners = [layer for layer in layers
              if isinstance(layer, dict) and layer.get("id") == _ROAD_LABEL_ID]
    if len(owners) != 1:
        return set()
    owner = owners[0]
    layout = owner.get("layout", {})
    if (owner.get("type") != "symbol" or owner.get("source-layer") != "road"
            or layout.get("symbol-placement") != "line"
            or layout.get("text-field") != _NAME_EN_FALLBACK
            or layout.get("text-transform", "none") != "none"):
        return set()
    return _ROAD_LABEL_RULES


def _light_waterway_name_fallback_rules(source_style):
    """Resolve only generated spacing bands belonging to the unique source owner."""
    if not _is_mapbox_light_style(source_style):
        return set()
    layers = source_style.get("layers", [])
    owners = [layer for layer in layers
              if isinstance(layer, dict) and layer.get("id") == "waterway-label"]
    if len(owners) != 1:
        return set()
    owner = owners[0]
    layout = owner.get("layout", {})
    if (owner.get("type") != "symbol" or owner.get("source-layer") != "natural_label"
            or layout.get("symbol-placement") != "line"
            or layout.get("text-field") != _NAME_EN_FALLBACK
            or layout.get("text-transform", "none") != "none"):
        return set()
    # Share the actual preprocessing generator, including its spacing contract
    # and clipped zoom bands. Unknown layouts keep their existing conversion.
    variants = _waterway_label_symbol_spacing_layer_variants(owner)
    rules = {variant["id"] for variant in variants or []}
    if any(isinstance(layer, dict) and layer.get("id") in rules for layer in layers):
        return set()
    return rules


def apply_light_name_fallback(labeling, source_style: dict) -> int:
    """Restore audited Light place/road/waterway content before font-band splitting.

    These source layouts miss the preprocessing helper's layout guards.
    Road rules include only the original and the known derived size band;
    source feature eligibility (including has(name)) stays unchanged.
    A native expression retains NULL/missing fallback and an intentional empty
    English name without adding companion rules or changing feature filters.
    Explicit column references are necessary: vector-tile decoding builds its
    requested field schema from them and leaves missing MVT values NULL.
    """
    owners = dict.fromkeys(_light_name_fallback_owners(source_style), "place_label")
    owners.update(dict.fromkeys(_light_road_name_fallback_rules(source_style), "road"))
    owners.update(dict.fromkeys(_light_waterway_name_fallback_rules(source_style), "natural_label"))
    if not owners:
        return 0
    styles = list(labeling.styles())
    changed = 0
    for label in styles:
        if label.styleName() not in owners or label.layerName() != owners[label.styleName()]:
            continue
        settings = label.labelSettings()
        # Do not overwrite a native converter fix or an explicit text override.
        if settings.fieldName != '"name"' or not settings.isExpression:
            continue
        settings.fieldName = 'coalesce("name_en", "name")'
        label.setLabelSettings(settings)
        changed += 1
    if changed:
        labeling.setStyles(styles)
    return changed


_AIRPORT_LABEL_ID = "airport-label"
_AIRPORT_TEXT_FIELD = [
    "step", ["get", "sizerank"],
    ["case", ["has", "ref"],
     ["concat", ["get", "ref"], " -\n", _NAME_EN_FALLBACK], _NAME_EN_FALLBACK],
    15, ["get", "ref"],
]
_AIRPORT_NATIVE_TEXT = (
    'CASE WHEN "sizerank" IS NULL THEN NULL '
    'WHEN "sizerank" >= 15 THEN "ref" '
    'WHEN "ref" IS NOT NULL THEN concat("ref", \' -\\n\', coalesce("name_en", "name")) '
    'ELSE coalesce("name_en", "name") END'
)


def _light_airport_content_owner(source_style):
    if not _is_mapbox_light_style(source_style):
        return False
    owners = [layer for layer in source_style.get("layers", [])
              if isinstance(layer, dict) and layer.get("id") == _AIRPORT_LABEL_ID]
    if len(owners) != 1:
        return False
    owner = owners[0]
    layout = owner.get("layout", {})
    return (owner.get("type") == "symbol"
            and owner.get("source-layer") == "airport_label"
            and layout.get("symbol-placement", "point") == "point"
            and layout.get("text-transform", "none") == "none"
            and layout.get("text-field") == _AIRPORT_TEXT_FIELD)


def apply_light_airport_content(labeling, source_style: dict) -> int:
    """Restore the source's rank-dependent airport code/name on native MVT labels.

    MVT has no explicit NULL property value: absent ref decodes to native NULL,
    while an empty ref still exists and retains the source's separator. Request
    all four text columns explicitly. Run before font splitting, retaining all
    native feature/zoom eligibility and non-content settings.
    """
    if not _light_airport_content_owner(source_style):
        return 0
    styles = list(labeling.styles())
    changed = 0
    for label in styles:
        if label.styleName() != _AIRPORT_LABEL_ID or label.layerName() != "airport_label":
            continue
        settings = label.labelSettings()
        if settings.fieldName != '"name"' or not settings.isExpression:
            continue
        settings.fieldName = _AIRPORT_NATIVE_TEXT
        label.setLabelSettings(settings)
        changed += 1
    if changed:
        labeling.setStyles(styles)
    return changed
