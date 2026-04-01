"""Background task for generating an activity atlas PDF from the atlas_pages QGIS layer.

Uses :class:`qgis.core.QgsTask` so that export runs off the main thread,
keeping the QGIS UI responsive.  The layout is constructed programmatically
using :class:`qgis.core.QgsPrintLayout` with an atlas coverage from the
``activity_atlas_pages`` vector layer.

Page template (A4 portrait, 210 × 297 mm):

    ┌────────────────────────────────────────┐
    │  [Title]                       [Date]  │
    │  [Subtitle / stats]                    │
    │  ┌──────────────────────────────────┐  │
    │  │                                  │  │
    │  │         MAP FRAME (square)       │  │
    │  │    (atlas-controlled extent)     │  │
    │  │                                  │  │
    │  └──────────────────────────────────┘  │
    │  [elevation profile chart]              │
    │  [profile summary]                     │
    │  [detail block: per-page metric items] │
    │  Page N / Total                        │
    └────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemMap,
    QgsLayoutItemPicture,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsTask,
    QgsUnitTypes,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont

from ..activity_classification import ordered_canonical_activity_labels
from .profile_item import (
    NativeProfileItemConfig,
    atlas_layer_supports_native_profile_atlas,
    build_native_profile_inputs,
    build_profile_item,
    build_profile_item_adapter,
)

# ---------------------------------------------------------------------------
# Page geometry (mm, A4 portrait with square map)
# ---------------------------------------------------------------------------

PAGE_WIDTH_MM = 210.0
PAGE_HEIGHT_MM = 297.0
MARGIN_MM = 10.0
HEADER_HEIGHT_MM = 16.0
FOOTER_HEIGHT_MM = 8.0
HEADER_GAP_MM = 3.0    # gap between header and map
PROFILE_GAP_MM = 3.0   # gap between map and profile area
FOOTER_GAP_MM = 3.0    # gap between profile area and footer

MAP_Y = MARGIN_MM + HEADER_HEIGHT_MM + HEADER_GAP_MM
MAP_W = (PAGE_WIDTH_MM - 2 * MARGIN_MM) * 0.90          # 10% smaller than full usable width
MAP_H = MAP_W                                            # square
MAP_X = (PAGE_WIDTH_MM - MAP_W) / 2.0                    # centered horizontally
BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO = MAP_W / MAP_H   # 1.0

# Profile area: reserved below the map for route profile content
PROFILE_X = MAP_X
PROFILE_Y = MAP_Y + MAP_H + PROFILE_GAP_MM
PROFILE_W = MAP_W
PROFILE_H = (PAGE_HEIGHT_MM - MARGIN_MM - FOOTER_HEIGHT_MM
             - FOOTER_GAP_MM - PROFILE_Y)

# Sub-layout within profile area: chart on top, profile summary, detail block
PROFILE_SUMMARY_H = 5.0     # height of the profile summary label
DETAIL_BLOCK_H = 12.0       # height of the per-page detail item block
PROFILE_SUMMARY_GAP = 2.0   # gap between chart and profile summary line
DETAIL_BLOCK_GAP = 1.0      # gap between profile summary and detail block
PROFILE_CHART_H = (PROFILE_H - PROFILE_SUMMARY_H - DETAIL_BLOCK_H
                   - PROFILE_SUMMARY_GAP - DETAIL_BLOCK_GAP)
PROFILE_CHART_Y = PROFILE_Y
PROFILE_SUMMARY_Y = PROFILE_CHART_Y + PROFILE_CHART_H + PROFILE_SUMMARY_GAP
DETAIL_BLOCK_Y = PROFILE_SUMMARY_Y + PROFILE_SUMMARY_H + DETAIL_BLOCK_GAP

# Identifier for the profile picture item (used to find it during export)
_PROFILE_PICTURE_ID = "qfit_profile_chart"
_PROFILE_SUMMARY_ID = "qfit_profile_summary"
_DETAIL_BLOCK_ID = "qfit_detail_block"

# Per-page detail item fields: (field_name, human_label).  Shared between
# build_atlas_layout (to decide whether to create the label) and the export
# loop (to build the plain-text content per page).
_DETAIL_ITEM_FIELDS = [
    ("page_distance_label", "Distance"),
    ("page_duration_label", "Moving time"),
    ("page_average_speed_label", "Speed"),
    ("page_average_pace_label", "Pace"),
    ("page_elevation_gain_label", "Climbing"),
]


def _load_pdf_writer():
    """Return :class:`pypdf.PdfWriter`, preferring bundled plugin vendoring.

    Resolution order:

    1. top-level ``pypdf`` from the current Python environment
    2. vendored ``qfit/vendor/pypdf`` packaged inside the plugin zip
    3. legacy/manual ``qfit.pypdf`` fallback used during ad-hoc debugging
    """
    try:
        import pypdf as _pypdf_module  # noqa: PLC0415

        return _pypdf_module.PdfWriter
    except ImportError:
        pass

    plugin_root = os.path.dirname(os.path.dirname(__file__))
    vendor_dir = os.path.join(plugin_root, "vendor")
    if os.path.isdir(vendor_dir) and vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)

    try:
        import pypdf as _pypdf_module  # noqa: PLC0415

        return _pypdf_module.PdfWriter
    except ImportError:
        pass

    try:
        import qfit.pypdf as _vendored_pypdf_module  # noqa: PLC0415

        return _vendored_pypdf_module.PdfWriter
    except ImportError as exc:
        raise ImportError("pypdf is unavailable for atlas PDF merging") from exc


def _normalize_profile_sample_key(value) -> str | None:
    """Return a stable string key for atlas profile sample lookup."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass
class PageProfilePayload:
    """Per-page profile inputs for both legacy and future native rendering paths."""

    sample_key: str | None
    page_points: list
    feature_geometry: object | None

    def native_inputs(self):
        return build_native_profile_inputs(self.feature_geometry)


def _render_page_profile_svg(page_points, *, output_path: str) -> str | None:
    """Render the legacy sampled SVG profile for a single atlas page."""
    from .profile_renderer import render_profile_to_file  # noqa: PLC0415

    return render_profile_to_file(
        page_points,
        width_mm=PROFILE_W,
        height_mm=PROFILE_CHART_H,
        directory=os.path.dirname(output_path) or None,
    )


def _apply_page_profile_payload(
    profile_adapter,
    profile_payload: PageProfilePayload,
    *,
    output_path: str,
    profile_temp_files: list[str],
) -> None:
    """Apply per-page profile data to the active layout item backend."""
    if profile_adapter.supports_native_profile:
        if getattr(profile_adapter, "atlas_driven", False):
            return
        native_curve, _native_request = profile_payload.native_inputs()
        if native_curve is not None and profile_adapter.bind_native_profile(profile_curve=native_curve):
            return

    page_points = profile_payload.page_points
    if len(page_points) < 2:
        profile_adapter.clear_profile()
        return

    try:
        svg_path = _render_page_profile_svg(page_points, output_path=output_path)
        if svg_path:
            profile_adapter.set_svg_profile(svg_path)
            profile_temp_files.append(svg_path)
        else:
            profile_adapter.clear_profile()
    except Exception:  # noqa: BLE001
        logger.debug("Profile chart render failed", exc_info=True)
        profile_adapter.clear_profile()


def _build_page_profile_payload(feat, sort_key_idx, profile_samples) -> PageProfilePayload:
    sample_key = None
    if sort_key_idx >= 0:
        sample_key = _normalize_profile_sample_key(feat.attribute(sort_key_idx))

    page_points = profile_samples.get(sample_key, []) if sample_key else []

    geometry_getter = getattr(feat, "geometry", None)
    geometry = geometry_getter() if callable(geometry_getter) else None
    return PageProfilePayload(
        sample_key=sample_key,
        page_points=page_points,
        feature_geometry=geometry,
    )


def _mm(layout, value):
    """Return a :class:`QgsLayoutSize` / helper in millimetres."""
    return value  # used directly; callers build QgsLayoutSize themselves


def _add_label(
    layout,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    font_size: float = 9.0,
    bold: bool = False,
    align_right: bool = False,
    color: QColor | None = None,
    v_align_top: bool = False,
) -> QgsLayoutItemLabel:
    """Add a text label item to *layout* at mm coordinates."""
    label = QgsLayoutItemLabel(layout)
    label.setText(text)
    font = QFont()
    font.setPointSizeF(font_size)
    font.setBold(bold)
    label.setFont(font)
    if color is not None:
        label.setFontColor(color)
    h_align = Qt.AlignRight if align_right else Qt.AlignLeft
    label.setHAlign(h_align)
    label.setVAlign(Qt.AlignTop if v_align_top else Qt.AlignVCenter)
    label.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    label.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(label)
    return label


def _normalize_extent_to_aspect_ratio(rect: QgsRectangle, target_aspect_ratio: float) -> QgsRectangle:
    """Return a centered rectangle expanded to match *target_aspect_ratio*.

    The shorter dimension is expanded; the longer one is preserved.
    Returns the input rect unchanged if geometry values are unavailable/non-numeric
    (useful for headless tests with mocks).
    """
    try:
        width = float(rect.width())
        height = float(rect.height())
        center_x = (float(rect.xMinimum()) + float(rect.xMaximum())) / 2.0
        center_y = (float(rect.yMinimum()) + float(rect.yMaximum())) / 2.0
    except (TypeError, ValueError):
        return rect

    if width <= 0 or height <= 0 or target_aspect_ratio <= 0:
        return rect

    current_ratio = width / height

    if abs(current_ratio - target_aspect_ratio) < 1e-9:
        return rect

    if current_ratio < target_aspect_ratio:
        width = height * target_aspect_ratio
    else:
        height = width / target_aspect_ratio

    half_w = width / 2.0
    half_h = height / 2.0
    return QgsRectangle(center_x - half_w, center_y - half_h, center_x + half_w, center_y + half_h)


def build_atlas_layout(
    atlas_layer,
    project: QgsProject | None = None,
    profile_plot_style=None,
) -> QgsPrintLayout:
    """Build a :class:`QgsPrintLayout` with per-activity atlas pages.

    Parameters
    ----------
    atlas_layer:
        The ``activity_atlas_pages`` :class:`QgsVectorLayer` used as the
        atlas coverage layer.
    project:
        The QGIS project to attach the layout to.  Defaults to
        ``QgsProject.instance()``.

    Returns
    -------
    QgsPrintLayout
        A fully configured layout ready for atlas export.
    """
    proj = project or QgsProject.instance()
    layout = QgsPrintLayout(proj)
    layout.initializeDefaults()
    layout.setName("qfit Activity Atlas")

    # -- Page size (A4 portrait) -------------------------------------------
    page_collection = layout.pageCollection()
    if page_collection.pageCount() > 0:
        page = page_collection.page(0)
        page.setPageSize(
            QgsLayoutSize(PAGE_WIDTH_MM, PAGE_HEIGHT_MM, QgsUnitTypes.LayoutMillimeters)
        )

    # -- Atlas setup -------------------------------------------------------
    atlas = layout.atlas()
    atlas.setCoverageLayer(atlas_layer)
    atlas.setEnabled(True)
    atlas.setSortFeatures(True)
    # Sort by page_sort_key if the field exists
    fields = atlas_layer.fields()
    sort_field = "page_sort_key" if fields.indexOf("page_sort_key") >= 0 else ""
    if sort_field:
        atlas.setSortExpression(f'"{sort_field}"')

    # -- Map frame (atlas-controlled extent) --------------------------------
    # Only include layers that are checked/visible in the layer tree —
    # hidden layers (including any with debug tile borders enabled) are excluded.
    root = proj.layerTreeRoot()
    visible_layers = [
        node.layer()
        for node in root.findLayers()
        if node.isVisible() and node.layer() is not None and node.layer() is not atlas_layer
    ]

    map_item = QgsLayoutItemMap(layout)
    map_item.setLayers(visible_layers)
    map_item.setKeepLayerSet(True)
    map_item.attemptMove(QgsLayoutPoint(MAP_X, MAP_Y, QgsUnitTypes.LayoutMillimeters))
    map_item.attemptResize(QgsLayoutSize(MAP_W, MAP_H, QgsUnitTypes.LayoutMillimeters))
    # Use Fixed mode: we set the map extent explicitly per page from the stored
    # center_x_3857/center_y_3857/extent_width_m/extent_height_m fields so that
    # QGIS atlas auto-fit cannot distort or shift the precomputed page extents.
    map_item.setAtlasDriven(True)
    map_item.setAtlasScalingMode(QgsLayoutItemMap.Fixed)
    map_item.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))

    # Disable tile border rendering on visible vector tile layers (debug overlay)
    try:
        from qgis.core import QgsVectorTileLayer  # noqa: PLC0415
        for layer in visible_layers:
            if isinstance(layer, QgsVectorTileLayer):
                layer.setTileBorderRenderingEnabled(False)
    except (RuntimeError, ImportError, AttributeError):
        logger.debug("Vector tile label priority adjustment skipped", exc_info=True)

    layout.addLayoutItem(map_item)

    # -- Title label (large, left-aligned, atlas expression) ----------------
    title_field = "page_title" if fields.indexOf("page_title") >= 0 else ""
    title_expr = f'[% "{title_field}" %]' if title_field else "Activity"
    _add_label(
        layout,
        title_expr,
        x=MARGIN_MM,
        y=MARGIN_MM,
        w=PAGE_WIDTH_MM - 2 * MARGIN_MM - 60.0,
        h=HEADER_HEIGHT_MM * 0.6,
        font_size=12.0,
        bold=True,
    )

    # -- Subtitle / stats label (smaller, below title) ----------------------
    stats_field = "page_stats_summary" if fields.indexOf("page_stats_summary") >= 0 else ""
    subtitle_field = "page_subtitle" if fields.indexOf("page_subtitle") >= 0 else ""
    if stats_field:
        stats_expr = f'[% coalesce("{stats_field}", "{subtitle_field}") %]'
    elif subtitle_field:
        stats_expr = f'[% "{subtitle_field}" %]'
    else:
        stats_expr = ""
    if stats_expr:
        _add_label(
            layout,
            stats_expr,
            x=MARGIN_MM,
            y=MARGIN_MM + HEADER_HEIGHT_MM * 0.6,
            w=PAGE_WIDTH_MM - 2 * MARGIN_MM - 60.0,
            h=HEADER_HEIGHT_MM * 0.4,
            font_size=8.0,
            color=QColor(80, 80, 80),
        )

    # -- Date label (right-aligned header) ----------------------------------
    date_field = "page_date" if fields.indexOf("page_date") >= 0 else ""
    if date_field:
        _add_label(
            layout,
            f'[% "{date_field}" %]',
            x=PAGE_WIDTH_MM - MARGIN_MM - 60.0,
            y=MARGIN_MM,
            w=60.0,
            h=HEADER_HEIGHT_MM * 0.6,
            font_size=9.0,
            align_right=True,
            color=QColor(60, 60, 60),
        )

    # -- Profile area: chart item + summary text below map -------------------
    # The profile item currently wraps the legacy SVG/picture implementation,
    # but is created through an adapter so the export loop can later swap in a
    # native QGIS elevation-profile item without another large rewrite.
    build_profile_item(
        layout,
        item_id=_PROFILE_PICTURE_ID,
        x=PROFILE_X,
        y=PROFILE_CHART_Y,
        w=PROFILE_W,
        h=PROFILE_CHART_H,
        native_config=NativeProfileItemConfig(
            atlas_driven=atlas_layer_supports_native_profile_atlas(atlas_layer),
            layers=visible_layers,
            plot_style=profile_plot_style,
        ),
    )

    # Text summaries below the chart — text is set per page during the export
    # loop so that no [% %] expressions remain in the layout.  This avoids raw
    # template syntax leaking into the final PDF when QGIS fails to evaluate
    # inline atlas expressions (see issue #108).
    if fields.indexOf("page_profile_summary") >= 0:
        lbl = _add_label(
            layout,
            "",
            x=PROFILE_X,
            y=PROFILE_SUMMARY_Y,
            w=PROFILE_W,
            h=PROFILE_SUMMARY_H,
            font_size=7.0,
            color=QColor(100, 100, 100),
        )
        lbl.setId(_PROFILE_SUMMARY_ID)

    # Detail block: per-page detail items (label: value lines) from individual
    # fields.  Like the profile summary the text is set per page during export.
    has_any_detail_field = any(
        fields.indexOf(fn) >= 0 for fn, _ in _DETAIL_ITEM_FIELDS
    )
    if has_any_detail_field:
        lbl = _add_label(
            layout,
            "",
            x=PROFILE_X,
            y=DETAIL_BLOCK_Y,
            w=PROFILE_W,
            h=DETAIL_BLOCK_H,
            font_size=7.0,
            color=QColor(100, 100, 100),
            v_align_top=True,
        )
        lbl.setId(_DETAIL_BLOCK_ID)

    # -- Footer: page number -----------------------------------------------
    footer_y = PROFILE_Y + PROFILE_H + FOOTER_GAP_MM
    _add_label(
        layout,
        "[% @atlas_featurenumber %] / [% @atlas_totalfeatures %]",
        x=MARGIN_MM,
        y=footer_y,
        w=60.0,
        h=FOOTER_HEIGHT_MM,
        font_size=7.0,
        color=QColor(120, 120, 120),
    )

    return layout


def _build_cover_summary_from_current_atlas_features(atlas_layer) -> dict:
    """Compute cover-summary strings from the current atlas feature subset.

    This intentionally ignores stale per-row `document_*` fields and instead
    aggregates over the currently exported atlas-layer features, so cover stats
    reflect the actual PDF contents after filtering/subsetting.

    Also computes the combined EPSG:3857 bounding box and collects unique
    ``source_activity_id`` values for the cover heatmap overview map.
    """
    from .publish_atlas import (  # noqa: PLC0415
        build_date_range_label,
        format_distance_label,
        format_duration_label,
        format_elevation_label,
    )

    features = list(atlas_layer.getFeatures())
    if not features:
        return {}

    fields = atlas_layer.fields()

    def _idx(name: str) -> int:
        return fields.indexOf(name)

    def _safe_attr(feature, name: str):
        idx = _idx(name)
        if idx < 0:
            return None
        value = feature.attribute(idx)
        if value is None:
            return None
        is_null = getattr(value, "isNull", None)
        try:
            if callable(is_null) and is_null():
                return None
        except Exception:  # noqa: BLE001
            logger.debug("Failed to inspect QVariant null state", exc_info=True)
        if isinstance(value, str) and value.strip().upper() == "NULL":
            return None
        return value

    def _safe_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    activity_count = len(features)
    page_dates = [str(v) for v in (_safe_attr(f, "page_date") for f in features) if v]
    total_distance_m = sum(v for v in (_safe_float(_safe_attr(f, "distance_m")) for f in features) if v is not None)
    total_moving_time_s = sum(v for v in (_safe_int(_safe_attr(f, "moving_time_s")) for f in features) if v is not None)
    total_elevation_gain_m = sum(
        v for v in (_safe_float(_safe_attr(f, "total_elevation_gain_m")) for f in features) if v is not None
    )

    # Extent field indices for cover heatmap map
    cx_idx = _idx("center_x_3857")
    cy_idx = _idx("center_y_3857")
    ew_idx = _idx("extent_width_m")
    eh_idx = _idx("extent_height_m")
    has_extent_fields = all(i >= 0 for i in (cx_idx, cy_idx, ew_idx, eh_idx))
    sid_idx = _idx("source_activity_id")

    extent_xmin = float("inf")
    extent_ymin = float("inf")
    extent_xmax = float("-inf")
    extent_ymax = float("-inf")

    ordered_activity_types = ordered_canonical_activity_labels(
        (
            _safe_attr(feature, "activity_type"),
            _safe_attr(feature, "sport_type"),
        )
        for feature in features
    )
    atlas_activity_ids: list[str] = []

    for feature in features:
        # Accumulate combined extent from stored per-page bounds
        if has_extent_fields:
            cx = _safe_float(feature.attribute(cx_idx))
            cy = _safe_float(feature.attribute(cy_idx))
            ew = _safe_float(feature.attribute(ew_idx))
            eh = _safe_float(feature.attribute(eh_idx))
            if all(v is not None for v in (cx, cy, ew, eh)):
                hw, hh = ew / 2.0, eh / 2.0
                extent_xmin = min(extent_xmin, cx - hw)
                extent_ymin = min(extent_ymin, cy - hh)
                extent_xmax = max(extent_xmax, cx + hw)
                extent_ymax = max(extent_ymax, cy + hh)

        # Collect unique activity IDs for subset filtering
        if sid_idx >= 0:
            sid = feature.attribute(sid_idx)
            if sid is not None and sid != "":
                sid_str = str(sid)
                if sid_str not in atlas_activity_ids:
                    atlas_activity_ids.append(sid_str)

    valid_extent = extent_xmin < extent_xmax and extent_ymin < extent_ymax

    activity_label = "activity" if activity_count == 1 else "activities"
    date_range_label = build_date_range_label(min(page_dates), max(page_dates)) if page_dates else None
    total_distance_label = format_distance_label(total_distance_m) if total_distance_m > 0 else None
    total_duration_label = format_duration_label(total_moving_time_s) if total_moving_time_s > 0 else None
    total_elevation_gain_label = format_elevation_label(total_elevation_gain_m) if total_elevation_gain_m > 0 else None
    activity_types_label = ", ".join(ordered_activity_types) if ordered_activity_types else None

    cover_parts = [f"{activity_count} {activity_label}"]
    for part in [date_range_label, total_distance_label, total_duration_label, total_elevation_gain_label, activity_types_label]:
        if part:
            cover_parts.append(part)

    return {
        "document_cover_summary": " · ".join(cover_parts) if cover_parts else "",
        "document_activity_count": str(activity_count),
        "document_date_range_label": date_range_label or "",
        "document_total_distance_label": total_distance_label or "",
        "document_total_duration_label": total_duration_label or "",
        "document_total_elevation_gain_label": total_elevation_gain_label or "",
        "document_activity_types_label": activity_types_label or "",
        # Cover heatmap map data
        "_cover_extent_xmin": extent_xmin if valid_extent else None,
        "_cover_extent_ymin": extent_ymin if valid_extent else None,
        "_cover_extent_xmax": extent_xmax if valid_extent else None,
        "_cover_extent_ymax": extent_ymax if valid_extent else None,
        "_atlas_activity_ids": atlas_activity_ids,
    }


def _apply_cover_heatmap_renderer(layer) -> None:
    """Apply a heatmap renderer to *layer* for the cover overview map.

    Uses a slightly larger radius and lower quality than the interactive
    heatmap preset to suit the zoomed-out overview.  Imports are deferred
    so the module can load without a full QGIS runtime (e.g. in tests).
    """
    try:
        from qgis.core import (  # noqa: PLC0415
            QgsHeatmapRenderer,
            QgsStyle,
            QgsGradientColorRamp,
        )
    except ImportError:
        return
    renderer = QgsHeatmapRenderer()
    renderer.setRadius(8)
    renderer.setRadiusUnit(QgsUnitTypes.RenderMillimeters)
    renderer.setRenderQuality(1)
    color_ramp = QgsStyle.defaultStyle().colorRamp("Turbo")
    if color_ramp is None:
        color_ramp = QgsGradientColorRamp(QColor("#00000000"), QColor("#e74c3c"))
    renderer.setColorRamp(color_ramp)
    layer.setRenderer(renderer)
    layer.setOpacity(0.85)


def build_cover_layout(
    atlas_layer,
    project=None,
    map_layers=None,
    cover_data=None,
) -> QgsPrintLayout | None:
    """Build a single-page cover layout from the current atlas-layer subset.

    Parameters
    ----------
    map_layers:
        Optional list of QGIS map layers to include in the cover heatmap
        overview map.  When provided together with extent data in
        *cover_data*, a square map is placed below the statistics block.
    cover_data:
        Pre-computed cover summary dict (from
        :func:`_build_cover_summary_from_current_atlas_features`).  If
        ``None`` it will be computed from *atlas_layer*.

    Returns ``None`` if the atlas layer has no features.
    """
    if atlas_layer is None or atlas_layer.featureCount() == 0:
        return None

    # Build cover stats from the currently exported atlas features so the cover
    # reflects the actual PDF subset, not stale precomputed document_* values.
    if cover_data is None:
        cover_data = _build_cover_summary_from_current_atlas_features(atlas_layer)
    if not cover_data:
        return None

    cover_summary = cover_data.get("document_cover_summary", "")
    activity_count = cover_data.get("document_activity_count", "")
    date_range_label = cover_data.get("document_date_range_label", "")
    total_distance_label = cover_data.get("document_total_distance_label", "")
    total_duration_label = cover_data.get("document_total_duration_label", "")
    total_elevation_gain_label = cover_data.get("document_total_elevation_gain_label", "")
    activity_types_label = cover_data.get("document_activity_types_label", "")
    proj = project or QgsProject.instance()
    layout = QgsPrintLayout(proj)
    layout.initializeDefaults()
    layout.setName("qfit Atlas Cover")

    page_collection = layout.pageCollection()
    if page_collection.pageCount() > 0:
        page = page_collection.page(0)
        page.setPageSize(
            QgsLayoutSize(PAGE_WIDTH_MM, PAGE_HEIGHT_MM, QgsUnitTypes.LayoutMillimeters)
        )

    # Vertical positioning helpers
    content_width = PAGE_WIDTH_MM - 2 * MARGIN_MM
    center_x = MARGIN_MM

    # Title — centred vertically at ~35% of page height
    title_y = PAGE_HEIGHT_MM * 0.28
    title_h = 14.0
    _add_label(
        layout,
        "qfit Activity Atlas",
        x=center_x,
        y=title_y,
        w=content_width,
        h=title_h,
        font_size=18.0,
        bold=True,
        align_right=False,
    )

    # Subtitle (cover summary) — just below title
    if cover_summary:
        _add_label(
            layout,
            cover_summary,
            x=center_x,
            y=title_y + title_h + 3.0,
            w=content_width,
            h=8.0,
            font_size=8.5,
            bold=False,
            color=QColor(60, 60, 60),
        )

    # Separator line (thin label with underline approximated via background color)
    sep_y = title_y + title_h + 13.0
    sep_label = QgsLayoutItemLabel(layout)
    sep_label.setText("")
    sep_label.attemptMove(QgsLayoutPoint(center_x, sep_y, QgsUnitTypes.LayoutMillimeters))
    sep_label.attemptResize(QgsLayoutSize(content_width, 0.3, QgsUnitTypes.LayoutMillimeters))
    sep_label.setBackgroundColor(QColor(180, 180, 180))
    sep_label.setBackgroundEnabled(True)
    layout.addLayoutItem(sep_label)

    # Highlight-card grid — 2-column layout for cover stats
    grid_y = sep_y + 7.0
    grid_cols = 2
    grid_gap_x = 6.0   # horizontal gap between columns
    card_w = (content_width - grid_gap_x) / grid_cols
    card_label_h = 4.0   # height for the label row
    card_value_h = 6.0   # height for the default value row
    card_value_h_long = 10.0  # extra room for long text values like activity types
    card_h = card_label_h + card_value_h
    card_h_long = card_label_h + card_value_h_long
    card_gap_y = 3.0     # vertical gap between card rows
    label_color = QColor(120, 120, 120)
    value_color = QColor(20, 20, 20)

    highlight_cards: list[tuple[str, str]] = []
    if activity_count and activity_count != "0":
        highlight_cards.append(("Activities", activity_count))
    if date_range_label:
        highlight_cards.append(("Date range", date_range_label))
    if total_distance_label:
        highlight_cards.append(("Distance", total_distance_label))
    if total_duration_label:
        highlight_cards.append(("Moving time", total_duration_label))
    if total_elevation_gain_label:
        highlight_cards.append(("Climbing", total_elevation_gain_label))
    if activity_types_label:
        highlight_cards.append(("Activity types", activity_types_label))

    row_y = grid_y
    row_max_h = 0.0
    for i, (card_label, card_value) in enumerate(highlight_cards):
        col = i % grid_cols
        if col == 0 and i > 0:
            row_y += row_max_h + card_gap_y
            row_max_h = 0.0

        is_long_text = card_label == "Activity types" or len(card_value) > 24
        value_h = card_value_h_long if is_long_text else card_value_h
        value_font = 8.5 if is_long_text else 10.0
        value_bold = not is_long_text
        card_total_h = card_label_h + value_h
        row_max_h = max(row_max_h, card_total_h)

        card_x = center_x + col * (card_w + grid_gap_x)
        card_y = row_y
        _add_label(
            layout,
            card_label.upper(),
            x=card_x,
            y=card_y,
            w=card_w,
            h=card_label_h,
            font_size=6.5,
            color=label_color,
            v_align_top=True,
        )
        _add_label(
            layout,
            card_value,
            x=card_x,
            y=card_y + card_label_h,
            w=card_w,
            h=value_h,
            font_size=value_font,
            bold=value_bold,
            color=value_color,
            v_align_top=is_long_text,
        )

    # -- Cover heatmap overview map (square, centered below stats) ----------
    grid_bottom_y = (row_y + row_max_h) if highlight_cards else sep_y + 2.0
    extent_bounds = (
        cover_data.get("_cover_extent_xmin"),
        cover_data.get("_cover_extent_ymin"),
        cover_data.get("_cover_extent_xmax"),
        cover_data.get("_cover_extent_ymax"),
    )
    if map_layers and all(v is not None for v in extent_bounds):
        xmin, ymin, xmax, ymax = (float(v) for v in extent_bounds)
        # Add 10% margin around the combined extent
        span = max(xmax - xmin, ymax - ymin)
        margin_m = span * 0.10
        map_extent = QgsRectangle(
            xmin - margin_m, ymin - margin_m,
            xmax + margin_m, ymax + margin_m,
        )
        map_extent = _normalize_extent_to_aspect_ratio(map_extent, 1.0)

        cover_map_gap = 8.0
        cover_map_top = grid_bottom_y + cover_map_gap
        available_h = PAGE_HEIGHT_MM - MARGIN_MM - cover_map_top - 4.0
        cover_map_size = min(available_h, content_width * 0.60)

        if cover_map_size >= 40.0:
            cover_map_x = (PAGE_WIDTH_MM - cover_map_size) / 2.0
            cover_map = QgsLayoutItemMap(layout)
            cover_map.setLayers(map_layers)
            cover_map.setKeepLayerSet(True)
            cover_map.attemptMove(
                QgsLayoutPoint(cover_map_x, cover_map_top, QgsUnitTypes.LayoutMillimeters)
            )
            cover_map.attemptResize(
                QgsLayoutSize(cover_map_size, cover_map_size, QgsUnitTypes.LayoutMillimeters)
            )
            cover_map.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
            cover_map.setExtent(map_extent)
            layout.addLayoutItem(cover_map)

    return layout


def build_toc_layout(
    atlas_layer,
    project=None,
) -> QgsPrintLayout | None:
    """Build a single-page table-of-contents layout from *atlas_layer* features.

    Returns ``None`` if the atlas layer has no features or the required
    fields are absent (the TOC page is simply skipped in that case).
    """
    if atlas_layer is None or atlas_layer.featureCount() == 0:
        return None

    fields = atlas_layer.fields()
    pn_idx = fields.indexOf("page_number")
    toc_idx = fields.indexOf("page_toc_label")
    name_idx = fields.indexOf("page_name")
    sort_idx = fields.indexOf("page_sort_key")

    # We need at least page_number and one of toc_label/name to build entries.
    if pn_idx < 0 or (toc_idx < 0 and name_idx < 0):
        return None

    # Collect TOC entries from all features, sorted by page_sort_key or page_number.
    entries: list[tuple[str, str]] = []  # (sort_key, display_label)
    for feat in atlas_layer.getFeatures():
        page_num = feat.attribute(pn_idx)
        toc_label = feat.attribute(toc_idx) if toc_idx >= 0 else None
        page_name = feat.attribute(name_idx) if name_idx >= 0 else None
        sort_key = feat.attribute(sort_idx) if sort_idx >= 0 else ""

        label_text = toc_label or page_name or ""
        if not label_text and page_num is None:
            continue

        display = f"{page_num}.\u2002{label_text}" if label_text else str(page_num)
        entries.append((str(sort_key or ""), display))

    if not entries:
        return None

    # Sort by the sort key to match atlas page order.
    entries.sort(key=lambda e: e[0])

    proj = project or QgsProject.instance()
    layout = QgsPrintLayout(proj)
    layout.initializeDefaults()
    layout.setName("qfit Atlas Contents")

    page_collection = layout.pageCollection()
    if page_collection.pageCount() > 0:
        page = page_collection.page(0)
        page.setPageSize(
            QgsLayoutSize(PAGE_WIDTH_MM, PAGE_HEIGHT_MM, QgsUnitTypes.LayoutMillimeters)
        )

    content_width = PAGE_WIDTH_MM - 2 * MARGIN_MM

    # Title
    title_y = MARGIN_MM
    title_h = 14.0
    _add_label(
        layout,
        "Contents",
        x=MARGIN_MM,
        y=title_y,
        w=content_width,
        h=title_h,
        font_size=16.0,
        bold=True,
    )

    # Separator line below title
    sep_y = title_y + title_h + 2.0
    sep_label = QgsLayoutItemLabel(layout)
    sep_label.setText("")
    sep_label.attemptMove(QgsLayoutPoint(MARGIN_MM, sep_y, QgsUnitTypes.LayoutMillimeters))
    sep_label.attemptResize(QgsLayoutSize(content_width, 0.3, QgsUnitTypes.LayoutMillimeters))
    sep_label.setBackgroundColor(QColor(180, 180, 180))
    sep_label.setBackgroundEnabled(True)
    layout.addLayoutItem(sep_label)

    # TOC entries
    entry_y = sep_y + 4.0
    row_h = 7.0
    entry_color = QColor(30, 30, 30)

    for _sort_key, display in entries:
        _add_label(
            layout,
            display,
            x=MARGIN_MM,
            y=entry_y,
            w=content_width,
            h=row_h,
            font_size=9.0,
            color=entry_color,
        )
        entry_y += row_h

    return layout


class AtlasExportTask(QgsTask):
    """Export the qfit atlas as a multi-page PDF via QGIS print layout.

    Parameters
    ----------
    atlas_layer:
        The loaded ``activity_atlas_pages`` :class:`QgsVectorLayer`.
    output_path:
        Destination ``.pdf`` file path.
    on_finished:
        Callable invoked **on the main thread** when the task completes.
        Receives keyword arguments:
        ``output_path`` (str | None), ``error`` (str | None),
        ``cancelled`` (bool), ``page_count`` (int).
    project:
        Optional :class:`QgsProject`; defaults to ``QgsProject.instance()``.
    """

    def __init__(
        self,
        atlas_layer,
        output_path: str,
        on_finished,
        project=None,
        restore_tile_mode: str | None = None,
        layer_manager=None,
        preset_name: str | None = None,
        access_token: str = "",
        style_owner: str = "",
        style_id: str = "",
        background_enabled: bool = False,
        profile_plot_style=None,
    ):
        super().__init__("Export qfit atlas PDF", QgsTask.CanCancel)
        self._atlas_layer = atlas_layer
        self._output_path = output_path
        self._on_finished = on_finished
        self._project = project
        self._restore_tile_mode = restore_tile_mode
        self._layer_manager = layer_manager
        self._preset_name = preset_name
        self._access_token = access_token
        self._style_owner = style_owner
        self._style_id = style_id
        self._background_enabled = background_enabled
        self._profile_plot_style = profile_plot_style
        self._error: str | None = None
        self._page_count: int = 0

    # ------------------------------------------------------------------
    # QgsTask interface
    # ------------------------------------------------------------------

    def run(self) -> bool:
        """Build layout and export in the worker thread."""
        try:
            return self._run_export()
        except Exception as exc:  # noqa: BLE001 – QgsTask worker thread safety net
            logger.exception("Atlas export task failed")
            self._error = str(exc)
            return False

    def _run_export(self) -> bool:
        """Internal export logic (called from run())."""
        try:
            feature_count = self._atlas_layer.featureCount() if self._atlas_layer else 0
            if feature_count == 0:
                self._error = "No atlas pages found. Store and load activity layers first."
                return False

            layout = build_atlas_layout(
                self._atlas_layer,
                project=self._project,
                profile_plot_style=self._profile_plot_style,
            )

            atlas = layout.atlas()
            self._page_count = feature_count

            if self.isCanceled():
                return False

            # Locate the map item so we can set its extent per page.
            # Use duck-typing (setExtent + layers) so tests can mock without
            # needing a real QgsLayoutItemMap subclass.
            map_item = None
            for item in layout.items():
                if callable(getattr(item, "setExtent", None)) and callable(getattr(item, "layers", None)):
                    map_item = item
                    break

            # Identify stored extent field indices once.
            fields = self._atlas_layer.fields()
            cx_idx = fields.indexOf("center_x_3857")
            cy_idx = fields.indexOf("center_y_3857")
            ew_idx = fields.indexOf("extent_width_m")
            eh_idx = fields.indexOf("extent_height_m")
            has_stored_extents = all(i >= 0 for i in (cx_idx, cy_idx, ew_idx, eh_idx))

            exporter = QgsLayoutExporter(layout)
            settings = QgsLayoutExporter.PdfExportSettings()
            settings.dpi = 150
            settings.rasterizeWholeImage = False
            settings.forceVectorOutput = True

            # Ensure output directory exists
            output_dir = os.path.dirname(self._output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            # Locate per-page layout items so we can update them each iteration.
            profile_pic = None
            profile_summary_label = None
            detail_block_label = None
            for item in layout.items():
                item_id = getattr(item, "id", lambda: None)()
                if item_id == _PROFILE_PICTURE_ID:
                    profile_pic = item
                elif item_id == _PROFILE_SUMMARY_ID:
                    profile_summary_label = item
                elif item_id == _DETAIL_BLOCK_ID:
                    detail_block_label = item

            profile_adapter = build_profile_item_adapter(profile_pic) if profile_pic is not None else None
            manual_profile_updates_enabled = bool(
                profile_adapter is not None and profile_adapter.requires_manual_page_updates
            )

            # Pre-load profile samples grouped by page_sort_key.
            profile_samples: dict[str, list[tuple[float, float]]] = {}
            sort_key_idx = fields.indexOf("page_sort_key") if manual_profile_updates_enabled else -1
            if manual_profile_updates_enabled:
                try:
                    source = self._atlas_layer.source()
                    gpkg_path = source.split("|")[0] if "|" in source else source
                    if gpkg_path and os.path.isfile(gpkg_path):
                        from .profile_renderer import load_profile_samples_from_gpkg  # noqa: PLC0415
                        profile_samples = load_profile_samples_from_gpkg(gpkg_path)
                except Exception:  # noqa: BLE001
                    logger.debug("Could not load profile samples", exc_info=True)

            profile_temp_files: list[str] = []

            # Collect layers with source_activity_id field for per-page filtering.
            # These are the track/start/point layers that should show only the
            # current page's activity, not the full unfiltered dataset.
            filterable_layers: list[tuple] = []
            if map_item is not None:
                for layer in map_item.layers():
                    try:
                        layer_fields = layer.fields()
                        sid_idx = layer_fields.indexOf("source_activity_id")
                        if sid_idx >= 0:
                            filterable_layers.append((layer, layer.subsetString()))
                    except (RuntimeError, AttributeError):
                        logger.debug("Skipping non-filterable layer", exc_info=True)

            # Field index for source_activity_id in the atlas layer.
            sid_atlas_idx = fields.indexOf("source_activity_id")

            # Field indices for per-page text labels (profile summary + detail).
            profile_summary_idx = fields.indexOf("page_profile_summary")
            detail_field_indices = [
                (fields.indexOf(fn), human_label)
                for fn, human_label in _DETAIL_ITEM_FIELDS
                if fields.indexOf(fn) >= 0
            ]

            # Walk the atlas features in order, setting the map extent explicitly
            # from the stored center/size fields so QGIS atlas auto-fit cannot
            # distort or shift the precomputed page extents.
            atlas.beginRender()
            atlas.updateFeatures()
            ok = atlas.first()
            page_paths: list[str] = []
            page_index = 0
            try:
                while ok:
                    if self.isCanceled():
                        return False

                    feat = atlas.layout().reportContext().feature()

                    # Filter each data layer to show only this page's activity.
                    if filterable_layers and sid_atlas_idx >= 0:
                        sid_value = feat.attribute(sid_atlas_idx)
                        if sid_value is not None and sid_value != "":
                            safe_sid = str(sid_value).replace("'", "''")
                            page_filter = f"\"source_activity_id\" = '{safe_sid}'"
                            for layer, _original_subset in filterable_layers:
                                try:
                                    layer.setSubsetString(page_filter)
                                except RuntimeError:
                                    logger.debug("Failed to set page filter on layer", exc_info=True)

                    # Render profile chart SVG for this page.
                    if manual_profile_updates_enabled and profile_adapter is not None and sort_key_idx >= 0:
                        profile_payload = _build_page_profile_payload(
                            feat,
                            sort_key_idx,
                            profile_samples,
                        )
                        _apply_page_profile_payload(
                            profile_adapter,
                            profile_payload,
                            output_path=self._output_path,
                            profile_temp_files=profile_temp_files,
                        )

                    # Set profile summary text directly from the feature so that
                    # no raw [% %] template syntax can leak (issue #108).
                    if profile_summary_label is not None and profile_summary_idx >= 0:
                        val = feat.attribute(profile_summary_idx)
                        profile_summary_label.setText(str(val) if val else "")

                    if detail_block_label is not None and detail_field_indices:
                        lines = []
                        for idx, human_label in detail_field_indices:
                            val = feat.attribute(idx)
                            if val is not None and val != "":
                                lines.append(f"{human_label}: {val}")
                        detail_block_label.setText("\n".join(lines))

                    # Apply the stored precomputed extent to the map item.
                    if map_item is not None and has_stored_extents:
                        cx = feat.attribute(cx_idx)
                        cy = feat.attribute(cy_idx)
                        ew = feat.attribute(ew_idx)
                        eh = feat.attribute(eh_idx)
                        if all(v is not None and v != "" for v in (cx, cy, ew, eh)):
                            hw = float(ew) / 2.0
                            hh = float(eh) / 2.0
                            rect = QgsRectangle(
                                float(cx) - hw,
                                float(cy) - hh,
                                float(cx) + hw,
                                float(cy) + hh,
                            )
                            rect = _normalize_extent_to_aspect_ratio(
                                rect,
                                BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO,
                            )
                            map_item.setExtent(rect)
                            map_item.refresh()

                    # Export this single page as its own PDF then merge.
                    page_path = f"{self._output_path}.page_{page_index}.pdf"
                    page_result = exporter.exportToPdf(page_path, settings)
                    if page_result != QgsLayoutExporter.Success:
                        self._error = (
                            f"PDF export failed on page {page_index + 1} "
                            f"(QgsLayoutExporter error code {page_result})."
                        )
                        return False
                    page_paths.append(page_path)
                    page_index += 1
                    ok = atlas.next()
            finally:
                # Restore original subset strings on all filtered layers.
                for layer, original_subset in filterable_layers:
                    try:
                        layer.setSubsetString(original_subset)
                    except RuntimeError:
                        logger.debug("Failed to restore layer subset", exc_info=True)
                atlas.endRender()

            if not page_paths:
                self._error = "No pages were exported."
                return False

            # Prepend a cover page (silently skipped if generation fails).
            cover_path = self._export_cover_page(
                self._atlas_layer,
                self._output_path,
                project=self._project,
            )
            # Insert a table-of-contents page (silently skipped if generation fails).
            toc_path = self._export_toc_page(
                self._atlas_layer,
                self._output_path,
                project=self._project,
            )
            front_pages = [p for p in (cover_path, toc_path) if p]
            all_paths = front_pages + page_paths

            # Merge all per-page PDFs into a single output PDF.
            if len(all_paths) == 1:
                os.replace(all_paths[0], self._output_path)
            else:
                self._merge_pdfs(all_paths, self._output_path)
                for p in all_paths:
                    try:
                        os.remove(p)
                    except OSError:
                        pass

            # Clean up temporary profile SVG files.
            for svg_path in profile_temp_files:
                try:
                    os.remove(svg_path)
                except OSError:
                    pass

        except (RuntimeError, OSError) as exc:
            logger.exception("Atlas export failed")
            self._error = str(exc)
            return False

        return not self.isCanceled()

    @staticmethod
    def _export_cover_page(
        atlas_layer,
        output_path: str,
        project=None,
    ) -> str | None:
        """Export a single cover-page PDF and return its path, or None on failure.

        The cover is built from document-level fields stored on every feature of
        *atlas_layer*.  When the project contains visible point/start layers a
        square heatmap overview map is rendered below the statistics block.

        Failures are swallowed so they never abort the main export.
        """
        saved_state: list[dict] = []
        try:
            proj = project or QgsProject.instance()

            # Pre-compute cover data (summary + extent + activity IDs) once.
            cover_data = _build_cover_summary_from_current_atlas_features(atlas_layer)
            if not cover_data:
                return None

            # Determine if we can add a cover heatmap overview map.
            cover_map_layers = None
            extent_bounds = (
                cover_data.get("_cover_extent_xmin"),
                cover_data.get("_cover_extent_ymin"),
                cover_data.get("_cover_extent_xmax"),
                cover_data.get("_cover_extent_ymax"),
            )
            has_extent = all(v is not None for v in extent_bounds)

            if has_extent:
                try:
                    root = proj.layerTreeRoot()
                    visible_layers = [
                        node.layer()
                        for node in root.findLayers()
                        if node.isVisible()
                        and node.layer() is not None
                        and node.layer() is not atlas_layer
                    ]
                except (RuntimeError, AttributeError, TypeError):
                    visible_layers = []

                if visible_layers:
                    points_layer = None
                    starts_layer = None
                    background_layers: list = []

                    for layer in visible_layers:
                        try:
                            name = layer.name()
                        except (RuntimeError, AttributeError):
                            continue
                        if name == "qfit activity points":
                            points_layer = layer
                        elif name == "qfit activity starts":
                            starts_layer = layer
                        elif name == "qfit activities":
                            pass  # exclude track lines from cover heatmap
                        else:
                            background_layers.append(layer)

                    heatmap_target = points_layer or starts_layer

                    if heatmap_target is not None:
                        # Save current renderer, opacity and subset for restoration.
                        try:
                            old_renderer = heatmap_target.renderer().clone()
                        except (RuntimeError, AttributeError):
                            old_renderer = None
                        saved_state.append({
                            "layer": heatmap_target,
                            "renderer": old_renderer,
                            "opacity": heatmap_target.opacity(),
                            "subset": heatmap_target.subsetString(),
                        })

                        _apply_cover_heatmap_renderer(heatmap_target)

                        # Filter to the activities present in the atlas subset.
                        activity_ids = cover_data.get("_atlas_activity_ids", [])
                        if activity_ids:
                            safe_ids = ", ".join(
                                "'" + str(sid).replace("'", "''") + "'"
                                for sid in activity_ids
                            )
                            heatmap_target.setSubsetString(
                                f'"source_activity_id" IN ({safe_ids})'
                            )

                        # Hide start markers when detail points drive the heatmap.
                        if heatmap_target is points_layer and starts_layer is not None:
                            saved_state.append({
                                "layer": starts_layer,
                                "renderer": None,
                                "opacity": starts_layer.opacity(),
                                "subset": starts_layer.subsetString(),
                            })
                            starts_layer.setOpacity(0.0)

                        cover_map_layers = [heatmap_target] + background_layers

            cover_layout = build_cover_layout(
                atlas_layer,
                project=project,
                map_layers=cover_map_layers,
                cover_data=cover_data,
            )
            if cover_layout is None:
                return None

            cover_path = f"{output_path}.cover.pdf"
            exporter = QgsLayoutExporter(cover_layout)
            settings = QgsLayoutExporter.PdfExportSettings()
            settings.dpi = 150
            settings.rasterizeWholeImage = False
            settings.forceVectorOutput = True

            result = exporter.exportToPdf(cover_path, settings)
            if result != QgsLayoutExporter.Success:
                return None
            return cover_path
        except (RuntimeError, OSError):
            logger.exception("Cover page export failed")
            return None
        finally:
            # Restore original renderer, opacity and subset on modified layers.
            for state in saved_state:
                try:
                    layer = state["layer"]
                    if state.get("renderer") is not None:
                        layer.setRenderer(state["renderer"])
                    layer.setOpacity(state["opacity"])
                    layer.setSubsetString(state["subset"])
                except (RuntimeError, AttributeError):
                    pass

    @staticmethod
    def _export_toc_page(
        atlas_layer,
        output_path: str,
        project=None,
    ) -> str | None:
        """Export a single table-of-contents PDF and return its path, or None on failure.

        Failures are swallowed so they never abort the main export.
        """
        try:
            toc_layout = build_toc_layout(atlas_layer, project=project)
            if toc_layout is None:
                return None

            toc_path = f"{output_path}.toc.pdf"
            exporter = QgsLayoutExporter(toc_layout)
            settings = QgsLayoutExporter.PdfExportSettings()
            settings.dpi = 150
            settings.rasterizeWholeImage = False
            settings.forceVectorOutput = True

            result = exporter.exportToPdf(toc_path, settings)
            if result != QgsLayoutExporter.Success:
                return None
            return toc_path
        except (RuntimeError, OSError):
            logger.exception("TOC page export failed")
            return None

    @staticmethod
    def _merge_pdfs(page_paths: list[str], output_path: str) -> None:
        """Merge per-page PDF files into a single multi-page PDF."""
        try:
            pdf_writer_cls = _load_pdf_writer()
        except ImportError:
            pdf_writer_cls = None
            logger.warning("pypdf unavailable during atlas export; falling back to first-page-only PDF")

        if pdf_writer_cls is not None:
            writer = pdf_writer_cls()
            for path in page_paths:
                writer.append(path)
            with open(output_path, "wb") as fout:
                writer.write(fout)
            return

        # Fallback: if pypdf is unavailable, rename first page (single-page fallback)
        if page_paths:
            os.replace(page_paths[0], output_path)

    def finished(self, result: bool) -> None:
        """Called on the main thread after run() returns."""
        # Restore the original tile mode (raster) on the main thread after export
        if (
            self._restore_tile_mode is not None
            and self._layer_manager is not None
            and self._background_enabled
        ):
            try:
                from ..mapbox_config import TILE_MODE_RASTER  # noqa: PLC0415
                if self._restore_tile_mode == TILE_MODE_RASTER:
                    self._layer_manager.ensure_background_layer(
                        enabled=True,
                        preset_name=self._preset_name,
                        access_token=self._access_token,
                        style_owner=self._style_owner,
                        style_id=self._style_id,
                        tile_mode=self._restore_tile_mode,
                    )
            except (RuntimeError, ImportError):
                logger.warning("Failed to restore tile mode after export", exc_info=True)

        if self._on_finished is not None:
            self._on_finished(
                output_path=self._output_path if result else None,
                error=self._error,
                cancelled=self.isCanceled(),
                page_count=self._page_count,
            )
