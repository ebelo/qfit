"""Preserve source-specific Light label content and cross-feature spacing."""

import math

from ...mapbox_config import _is_mapbox_light_style

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


def apply_light_name_fallback(labeling, source_style: dict) -> int:
    """Restore the audited Light place-name coalesce before font-band splitting.

    These unsplit source layouts miss the preprocessing helper's layout guards.
    A native expression retains NULL/missing fallback and an intentional empty
    English name without adding companion rules or changing feature filters.
    Explicit column references are necessary: vector-tile decoding builds its
    requested field schema from them and leaves missing MVT values NULL.
    """
    owners = _light_name_fallback_owners(source_style)
    if not owners:
        return 0
    styles = list(labeling.styles())
    changed = 0
    for label in styles:
        if label.styleName() not in owners or label.layerName() != "place_label":
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
