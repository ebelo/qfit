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
from dataclasses import dataclass

from .cover_composer import AtlasCoverComposer

logger = logging.getLogger(__name__)

_DEFAULT_COVER_COMPOSER = AtlasCoverComposer()


def _format_unexpected_export_error(exc: Exception) -> str:
    detail = str(exc).strip()
    if detail:
        return f"Unexpected atlas export failure ({exc.__class__.__name__}): {detail}"
    return f"Unexpected atlas export failure ({exc.__class__.__name__})"

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemMap,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProfileRequest,
    QgsProject,
    QgsRectangle,
    QgsTask,
    QgsUnitTypes,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont

from ..activities.domain.activity_classification import ordered_canonical_activity_labels
from .layout_metrics import BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO
from .profile_item import (
    NativeProfileItemConfig,
    atlas_layer_supports_native_profile_atlas,
    build_native_profile_curve,
    build_native_profile_curve_from_feature,
    build_profile_item,
    configure_native_profile_plot_range,
)
from .cover_summary import build_cover_summary_from_rows

_COVER_SUMMARY_ROW_FIELDS = (
    "page_date",
    "activity_type",
    "sport_type",
    "distance_m",
    "moving_time_s",
    "total_elevation_gain_m",
    "center_x_3857",
    "center_y_3857",
    "extent_width_m",
    "extent_height_m",
    "source_activity_id",
)
from .export_coordinator import AtlasExportCoordinator
from .export_front_matter import export_cover_page, export_toc_page
from .export_page_runtime_builder import AtlasPageRuntimeBuilder
from .export_page_runner import AtlasPageExportRunner
from .infrastructure.pdf_assembly import AtlasPdfAssembler
from .profile_export_workflow import AtlasPageProfileWorkflow
from .profile_payload_resolver import (
    AtlasProfileSampleLookup,
    PageProfilePayloadResolver,
    feature_attribute,
    load_profile_points_from_feature as resolver_load_profile_points_from_feature,
)

try:  # pragma: no cover - availability depends on QGIS build
    from qgis.core import QgsProfilePlotRenderer
except ImportError:  # pragma: no cover - exercised in stubbed/unit-test mode
    QgsProfilePlotRenderer = None

_DEFAULT_PROFILE_CRS_AUTH_ID = "EPSG:3857"


@dataclass
class PageProfilePayload:
    """Compatibility wrapper around the extracted profile payload value object."""

    feature_geometry: object | None = None
    feature: object | None = None
    crs_auth_id: str | None = None
    page_points: list[tuple[float, float]] | None = None

    def native_inputs(self):
        return (
            build_native_profile_curve_from_feature(
                self.feature_geometry,
                feature=self.feature,
                altitudes=[altitude for _distance, altitude in self.page_points or []],
            ),
            None,
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

def _render_page_profile_svg(page_points, *, output_path: str) -> str | None:
    return AtlasPageProfileWorkflow(
        profile_chart_width_mm=PROFILE_W,
        profile_chart_height_mm=PROFILE_CHART_H,
        default_profile_crs_auth_id=_DEFAULT_PROFILE_CRS_AUTH_ID,
    ).render_page_profile_svg(
        page_points,
        output_path=output_path,
    )


def _build_native_renderer_mem_layer(native_curve, crs_str: str):
    from . import profile_export_workflow

    return profile_export_workflow._build_native_renderer_mem_layer(native_curve, crs_str)


def _resolve_renderer_z_range(renderer, page_points):
    from . import profile_export_workflow

    return profile_export_workflow._resolve_renderer_z_range(renderer, page_points)


def _resolve_renderer_x_range(native_curve, page_points):
    from . import profile_export_workflow

    return profile_export_workflow._resolve_renderer_x_range(native_curve, page_points)


def _save_renderer_image(renderer, width_px, height_px, x_min, x_max, z_min, z_max, output_dir):
    from . import profile_export_workflow

    return profile_export_workflow._save_renderer_image(
        renderer,
        width_px,
        height_px,
        x_min,
        x_max,
        z_min,
        z_max,
        output_dir,
    )


def _render_native_profile_image(
    native_curve,
    layers: list,
    *,
    crs_auth_id: str | None = None,
    tolerance: float | None = None,
    width_px: int = 1000,
    height_px: int = 220,
    output_dir: str | None = None,
    page_points: list[tuple[float, float]] | None = None,
) -> str | None:
    from . import profile_export_workflow

    return profile_export_workflow._render_native_profile_image(
        native_curve,
        layers,
        crs_auth_id=crs_auth_id,
        tolerance=tolerance,
        width_px=width_px,
        height_px=height_px,
        output_dir=output_dir,
        page_points=page_points,
        profile_request_cls=QgsProfileRequest,
        qgs_crs_factory=QgsCoordinateReferenceSystem,
        profile_plot_renderer_cls=QgsProfilePlotRenderer,
        build_native_renderer_mem_layer_fn=_build_native_renderer_mem_layer,
        save_renderer_image_fn=_save_renderer_image,
    )


def _geometry_supports_native_profile(feature_geometry) -> bool:
    return build_native_profile_curve(feature_geometry) is not None


def _geometry_looks_line_like(feature_geometry) -> bool:
    if feature_geometry is None:
        return False

    if _geometry_supports_native_profile(feature_geometry):
        return True

    const_get = getattr(feature_geometry, "constGet", None)
    curve = const_get() if callable(const_get) else feature_geometry
    if curve is None:
        return False

    type_name = type(curve).__name__.lower()
    if "line" in type_name or "curve" in type_name:
        return True

    return any(callable(getattr(curve, name, None)) for name in ("curveToLine", "numPoints", "pointN"))


def _apply_picture_profile(
    profile_adapter,
    profile_payload: PageProfilePayload,
    output_path: str | None,
    profile_temp_files: list[str] | None,
    *,
    render_page_profile_svg_fn=_render_page_profile_svg,
    render_native_profile_image_fn=_render_native_profile_image,
    default_profile_crs_auth_id: str = _DEFAULT_PROFILE_CRS_AUTH_ID,
) -> None:
    from . import profile_export_workflow

    profile_export_workflow._apply_picture_profile(
        profile_adapter,
        profile_payload,
        output_path,
        profile_temp_files,
        render_page_profile_svg_fn=render_page_profile_svg_fn,
        render_native_profile_image_fn=render_native_profile_image_fn,
        default_profile_crs_auth_id=default_profile_crs_auth_id,
    )


def _apply_native_profile(profile_adapter, profile_payload: PageProfilePayload) -> None:
    from . import profile_export_workflow

    profile_export_workflow._apply_native_profile(
        profile_adapter,
        profile_payload,
        resolve_native_profile_plot_ranges_fn=_resolve_native_profile_plot_ranges,
        configure_native_profile_plot_range_fn=configure_native_profile_plot_range,
    )


def _apply_page_profile_payload(
    profile_adapter,
    profile_payload: PageProfilePayload,
    *,
    output_path: str | None = None,
    profile_temp_files: list[str] | None = None,
) -> None:
    from . import profile_export_workflow

    profile_export_workflow._apply_page_profile_payload(
        profile_adapter,
        profile_payload,
        output_path=output_path,
        profile_temp_files=profile_temp_files,
        render_page_profile_svg_fn=_render_page_profile_svg,
        render_native_profile_image_fn=_render_native_profile_image,
        default_profile_crs_auth_id=_DEFAULT_PROFILE_CRS_AUTH_ID,
        apply_picture_profile_fn=_apply_picture_profile,
        apply_native_profile_fn=_apply_native_profile,
    )


_feature_attribute = feature_attribute
_AtlasProfileSampleLookup = AtlasProfileSampleLookup


def _load_profile_points_from_feature(feature) -> list[tuple[float, float]] | None:
    return resolver_load_profile_points_from_feature(feature)


def _layer_crs_authid(layer) -> str | None:
    return PageProfilePayloadResolver._layer_crs_authid(layer)


def _scan_layer_for_profile_source(layer):
    return PageProfilePayloadResolver()._scan_layer_for_profile_source(layer)


def _resolve_page_profile_source(feat, filterable_layers) -> tuple[object | None, object | None, str | None]:
    return PageProfilePayloadResolver()._resolve_page_profile_source(feat, filterable_layers)


def _item_crs_authid(item) -> str | None:
    from . import profile_export_workflow

    return profile_export_workflow._item_crs_authid(item)


def _item_tolerance(item) -> float | None:
    from . import profile_export_workflow

    return profile_export_workflow._item_tolerance(item)


def _profile_elevation_range_from_renderer(profile_adapter, native_curve, *, crs_auth_id: str | None = None):
    from . import profile_export_workflow

    return profile_export_workflow._profile_elevation_range_from_renderer(
        profile_adapter,
        native_curve,
        crs_auth_id=crs_auth_id,
        profile_request_cls=QgsProfileRequest,
        qgs_crs_factory=QgsCoordinateReferenceSystem,
        profile_plot_renderer_cls=QgsProfilePlotRenderer,
        item_crs_authid_fn=_item_crs_authid,
        item_tolerance_fn=_item_tolerance,
    )


def _resolve_native_profile_plot_ranges(profile_adapter, profile_payload, native_curve):
    from . import profile_export_workflow

    return profile_export_workflow._resolve_native_profile_plot_ranges(
        profile_adapter,
        profile_payload,
        native_curve,
        profile_elevation_range_from_renderer_fn=_profile_elevation_range_from_renderer,
    )


def _build_page_profile_payload(
    feat,
    filterable_layers,
    profile_altitude_lookup=None,
) -> PageProfilePayload:
    payload = AtlasPageProfileWorkflow(
        profile_chart_width_mm=PROFILE_W,
        profile_chart_height_mm=PROFILE_CHART_H,
        default_profile_crs_auth_id=_DEFAULT_PROFILE_CRS_AUTH_ID,
    ).build_page_profile_payload(
        feat,
        filterable_layers,
        profile_altitude_lookup=profile_altitude_lookup,
    )
    return PageProfilePayload(
        feature_geometry=payload.feature_geometry,
        feature=payload.feature,
        crs_auth_id=payload.crs_auth_id,
        page_points=payload.page_points,
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
    map_item.setCrs(QgsCoordinateReferenceSystem(_DEFAULT_PROFILE_CRS_AUTH_ID))

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

    # -- Profile area: native chart item + summary text below map ------------
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
    features = list(atlas_layer.getFeatures())
    if not features:
        return {}

    fields = atlas_layer.fields()
    field_indexes = {
        field_name: fields.indexOf(field_name)
        for field_name in _COVER_SUMMARY_ROW_FIELDS
        if fields.indexOf(field_name) >= 0
    }

    def _normalize_value(value):
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

    rows = []
    for feature in features:
        row = {
            field_name: _normalize_value(feature.attribute(index))
            for field_name, index in field_indexes.items()
        }
        rows.append(row)

    return build_cover_summary_from_rows(rows)


def _build_cover_data_for_export(
    atlas_layer,
    *,
    atlas_title: str = "",
    atlas_subtitle: str = "",
) -> dict:
    cover_data = _build_cover_summary_from_current_atlas_features(atlas_layer)
    if not cover_data:
        return cover_data

    title = atlas_title.strip()
    subtitle = atlas_subtitle.strip()
    if title:
        cover_data["title"] = title
    if subtitle:
        cover_data["subtitle"] = subtitle
    return cover_data


def _apply_cover_heatmap_renderer(layer) -> None:
    """Apply a heatmap renderer to *layer* for the cover overview map.

    Uses a slightly larger radius and lower quality than the interactive
    heatmap preset to suit the zoomed-out overview.  Imports are deferred
    so the module can load without a full QGIS runtime (e.g. in tests).
    """
    try:
        from ..visualization.infrastructure.layer_style_service import (  # noqa: PLC0415
            build_qfit_heatmap_renderer,
        )
    except ImportError:
        return

    layer.setRenderer(build_qfit_heatmap_renderer())
    layer.setOpacity(0.55)


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

    cover_title = str(cover_data.get("title") or "qfit Activity Atlas").strip()
    cover_subtitle = str(cover_data.get("subtitle") or "").strip()
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

    def _join_cover_parts(parts: list[str]) -> str:
        return " · ".join(part for part in parts if part)

    def _points_to_mm(points: float) -> float:
        return points * 0.352778

    cover_left_margin_mm = 18.0
    cover_right_margin_mm = 18.0
    cover_top_margin_mm = 18.0
    cover_bottom_margin_mm = 16.0
    content_width = PAGE_WIDTH_MM - cover_left_margin_mm - cover_right_margin_mm
    printable_height = PAGE_HEIGHT_MM - cover_top_margin_mm - cover_bottom_margin_mm
    content_x = cover_left_margin_mm

    activity_count_label = ""
    if activity_count:
        activity_noun = "activity" if str(activity_count) == "1" else "activities"
        activity_count_label = f"{activity_count} {activity_noun}"

    subtitle_line = cover_subtitle or _join_cover_parts([
        activity_count_label,
        date_range_label,
        activity_types_label,
    ])
    summary_line = _join_cover_parts([
        total_distance_label,
        total_duration_label,
        total_elevation_gain_label,
    ])
    if not subtitle_line and cover_summary:
        subtitle_line = cover_summary

    title_h = _points_to_mm(26.0)
    detail_line_h = _points_to_mm(12.0)
    title_to_subtitle_gap = 4.0
    subtitle_to_summary_gap = 2.0
    header_to_map_gap = 8.0
    map_to_metrics_gap = 8.0

    title_y = cover_top_margin_mm
    _add_label(
        layout,
        cover_title,
        x=content_x,
        y=title_y,
        w=content_width,
        h=title_h,
        font_size=22.0,
        bold=True,
        align_right=False,
        v_align_top=True,
    )

    current_y = title_y + title_h
    if subtitle_line:
        subtitle_y = current_y + title_to_subtitle_gap
        _add_label(
            layout,
            subtitle_line,
            x=content_x,
            y=subtitle_y,
            w=content_width,
            h=detail_line_h,
            font_size=9.5,
            bold=False,
            color=QColor(60, 60, 60),
            v_align_top=True,
        )
        current_y = subtitle_y + detail_line_h

    if summary_line:
        summary_y = current_y + (subtitle_to_summary_gap if subtitle_line else title_to_subtitle_gap)
        _add_label(
            layout,
            summary_line,
            x=content_x,
            y=summary_y,
            w=content_width,
            h=detail_line_h,
            font_size=9.5,
            bold=False,
            color=QColor(60, 60, 60),
            v_align_top=True,
        )
        current_y = summary_y + detail_line_h

    hero_map_top = current_y + header_to_map_gap
    extent_bounds = (
        cover_data.get("_cover_extent_xmin"),
        cover_data.get("_cover_extent_ymin"),
        cover_data.get("_cover_extent_xmax"),
        cover_data.get("_cover_extent_ymax"),
    )
    cover_map_bottom = hero_map_top
    if map_layers and all(v is not None for v in extent_bounds):
        xmin, ymin, xmax, ymax = (float(v) for v in extent_bounds)
        span = max(xmax - xmin, ymax - ymin)
        margin_m = span * 0.10
        map_extent = QgsRectangle(
            xmin - margin_m, ymin - margin_m,
            xmax + margin_m, ymax + margin_m,
        )
        map_extent = _normalize_extent_to_aspect_ratio(map_extent, 1.0)

        cover_map_size = min(content_width * 0.72, printable_height * 0.46)
        available_h = PAGE_HEIGHT_MM - cover_bottom_margin_mm - hero_map_top
        cover_map_size = min(cover_map_size, available_h)

        if cover_map_size >= 40.0:
            cover_map_x = content_x + (content_width - cover_map_size) / 2.0
            cover_map = QgsLayoutItemMap(layout)
            cover_map.setLayers(map_layers)
            cover_map.setKeepLayerSet(True)
            try:
                cover_map.setFrameEnabled(False)
            except AttributeError:
                logger.debug("Cover map frame disabling unavailable", exc_info=True)
            cover_map.attemptMove(
                QgsLayoutPoint(cover_map_x, hero_map_top, QgsUnitTypes.LayoutMillimeters)
            )
            cover_map.attemptResize(
                QgsLayoutSize(cover_map_size, cover_map_size, QgsUnitTypes.LayoutMillimeters)
            )
            cover_map.setCrs(QgsCoordinateReferenceSystem(_DEFAULT_PROFILE_CRS_AUTH_ID))
            cover_map.setExtent(map_extent)
            layout.addLayoutItem(cover_map)
            cover_map_bottom = hero_map_top + cover_map_size

    metrics_top = cover_map_bottom + (map_to_metrics_gap if cover_map_bottom > hero_map_top else 0.0)
    metrics_cols = 3
    metrics_col_gap = 8.0
    metrics_row_gap = 4.0
    metric_w = (content_width - metrics_col_gap * (metrics_cols - 1)) / metrics_cols
    metric_label_h = _points_to_mm(7.0) + 0.6
    metric_label_to_value_gap = 1.5
    metric_value_h = _points_to_mm(11.0) + 0.8
    metric_row_h = metric_label_h + metric_label_to_value_gap + metric_value_h
    label_color = QColor(120, 120, 120)
    value_color = QColor(20, 20, 20)

    highlight_cards = [
        ("Activities", activity_count),
        ("Distance", total_distance_label),
        ("Moving time", total_duration_label),
        ("Climbing", total_elevation_gain_label),
        ("Date range", date_range_label),
        ("Activity types", activity_types_label),
    ]
    highlight_cards = [
        (card_label, card_value)
        for card_label, card_value in highlight_cards
        if card_value and not (card_label == "Activities" and card_value == "0")
    ]

    for i, (card_label, card_value) in enumerate(highlight_cards):
        row = i // metrics_cols
        col = i % metrics_cols
        card_x = content_x + col * (metric_w + metrics_col_gap)
        card_y = metrics_top + row * (metric_row_h + metrics_row_gap)
        _add_label(
            layout,
            card_label.upper(),
            x=card_x,
            y=card_y,
            w=metric_w,
            h=metric_label_h,
            font_size=7.0,
            color=label_color,
            v_align_top=True,
        )
        _add_label(
            layout,
            card_value,
            x=card_x,
            y=card_y + metric_label_h + metric_label_to_value_gap,
            w=metric_w,
            h=metric_value_h,
            font_size=11.0,
            bold=True,
            color=value_color,
            v_align_top=True,
        )

    footer_h = _points_to_mm(9.0)
    footer_y = PAGE_HEIGHT_MM - cover_bottom_margin_mm - footer_h
    _add_label(
        layout,
        "Generated with qfit",
        x=content_x,
        y=footer_y,
        w=content_width,
        h=footer_h,
        font_size=7.0,
        color=QColor(130, 130, 130),
        v_align_top=True,
    )

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
        on_finished=None,
        atlas_title: str = "",
        atlas_subtitle: str = "",
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
        self._atlas_title = atlas_title
        self._atlas_subtitle = atlas_subtitle
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
            self._error = _format_unexpected_export_error(exc)
            return False

    def _run_export(self) -> bool:
        """Internal export logic (called from run())."""
        result = AtlasExportCoordinator(
            atlas_layer=self._atlas_layer,
            output_path=self._output_path,
            project=self._project,
            profile_plot_style=self._profile_plot_style,
            is_canceled=self.isCanceled,
            build_layout=build_atlas_layout,
            layout_exporter_cls=QgsLayoutExporter,
            build_pdf_export_settings=self._build_pdf_export_settings,
            ensure_output_directory=self._ensure_output_directory,
            build_page_export_runner=self._build_page_export_runner,
            export_cover_page=lambda atlas_layer, output_path, project=None: self._export_cover_page(
                atlas_layer,
                output_path,
                atlas_title=self._atlas_title,
                atlas_subtitle=self._atlas_subtitle,
                project=project,
            ),
            export_toc_page=self._export_toc_page,
            assemble_output_pdf=self._assemble_output_pdf,
            logger=logger,
        ).execute()
        self._page_count = result.page_count
        self._error = result.error
        return result.success

    @staticmethod
    def _build_pdf_export_settings():
        settings = QgsLayoutExporter.PdfExportSettings()
        settings.dpi = 150
        settings.rasterizeWholeImage = False
        settings.forceVectorOutput = True
        return settings

    def _ensure_output_directory(self) -> None:
        output_dir = os.path.dirname(self._output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

    def _build_page_export_runner(self, *, layout, exporter, settings) -> AtlasPageExportRunner:
        return AtlasPageRuntimeBuilder(
            atlas_layer=self._atlas_layer,
            output_path=self._output_path,
            detail_item_fields=_DETAIL_ITEM_FIELDS,
            profile_picture_id=_PROFILE_PICTURE_ID,
            profile_summary_id=_PROFILE_SUMMARY_ID,
            detail_block_id=_DETAIL_BLOCK_ID,
            profile_sample_lookup=_AtlasProfileSampleLookup(self._atlas_layer),
            build_page_profile_payload=_build_page_profile_payload,
            apply_page_profile_payload=_apply_page_profile_payload,
            normalize_extent=_normalize_extent_to_aspect_ratio,
            target_aspect_ratio=BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO,
            is_canceled=self.isCanceled,
        ).build_runner(layout=layout, exporter=exporter, settings=settings)

    def _build_pdf_assembler(self) -> AtlasPdfAssembler:
        return AtlasPdfAssembler(
            is_canceled=self.isCanceled,
            warn=logger.warning,
        )

    def _assemble_output_pdf(
        self,
        page_paths: list[str],
        *,
        cover_path: str | None = None,
        toc_path: str | None = None,
    ) -> None:
        self._build_pdf_assembler().assemble(
            page_paths,
            self._output_path,
            cover_path=cover_path,
            toc_path=toc_path,
        )

    @staticmethod
    def _export_cover_page(
        atlas_layer,
        output_path: str,
        atlas_title: str = "",
        atlas_subtitle: str = "",
        project=None,
        cover_composer=_DEFAULT_COVER_COMPOSER,
    ) -> str | None:
        """Export a single cover-page PDF and return its path, or None on failure."""
        return export_cover_page(
            atlas_layer,
            output_path,
            project=project,
            get_project_instance=QgsProject.instance,
            build_cover_data=lambda layer: _build_cover_data_for_export(
                layer,
                atlas_title=atlas_title,
                atlas_subtitle=atlas_subtitle,
            ),
            apply_cover_heatmap_renderer=_apply_cover_heatmap_renderer,
            build_cover_layout_fn=cover_composer.build_layout,
            layout_exporter_cls=QgsLayoutExporter,
            logger=logger,
        )

    @staticmethod
    def _export_toc_page(
        atlas_layer,
        output_path: str,
        project=None,
    ) -> str | None:
        """Export a single table-of-contents PDF and return its path, or None on failure."""
        return export_toc_page(
            atlas_layer,
            output_path,
            project=project,
            build_toc_layout_fn=build_toc_layout,
            layout_exporter_cls=QgsLayoutExporter,
            logger=logger,
        )

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
