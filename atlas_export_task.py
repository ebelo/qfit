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
    │  [footer / profile area reserved]      │
    │  Page N / Total                        │
    └────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
import os

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

MAP_X = MARGIN_MM
MAP_Y = MARGIN_MM + HEADER_HEIGHT_MM + HEADER_GAP_MM
MAP_W = PAGE_WIDTH_MM - 2 * MARGIN_MM                   # 190 mm
MAP_H = MAP_W                                            # square
BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO = MAP_W / MAP_H   # 1.0

# Profile area: reserved below the map for route profile content
PROFILE_X = MARGIN_MM
PROFILE_Y = MAP_Y + MAP_H + PROFILE_GAP_MM
PROFILE_W = MAP_W
PROFILE_H = (PAGE_HEIGHT_MM - MARGIN_MM - FOOTER_HEIGHT_MM
             - FOOTER_GAP_MM - PROFILE_Y)

# Sub-layout within profile area: chart on top, summary text below
PROFILE_SUMMARY_H = 10.0   # height of the text summary label
PROFILE_SUMMARY_GAP = 2.0  # gap between chart and summary text
PROFILE_CHART_H = PROFILE_H - PROFILE_SUMMARY_H - PROFILE_SUMMARY_GAP
PROFILE_CHART_Y = PROFILE_Y
PROFILE_SUMMARY_Y = PROFILE_CHART_Y + PROFILE_CHART_H + PROFILE_SUMMARY_GAP

# Identifier for the profile picture item (used to find it during export)
_PROFILE_PICTURE_ID = "qfit_profile_chart"


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
    label.setVAlign(Qt.AlignVCenter)
    label.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    label.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(label)
    return label


def build_atlas_layout(
    atlas_layer,
    project: QgsProject | None = None,
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

    # -- Profile area: chart image + summary text below map ------------------
    # Picture item for the SVG elevation profile (source set per page during export)
    profile_pic = QgsLayoutItemPicture(layout)
    profile_pic.setId(_PROFILE_PICTURE_ID)
    profile_pic.attemptMove(
        QgsLayoutPoint(PROFILE_X, PROFILE_CHART_Y, QgsUnitTypes.LayoutMillimeters)
    )
    profile_pic.attemptResize(
        QgsLayoutSize(PROFILE_W, PROFILE_CHART_H, QgsUnitTypes.LayoutMillimeters)
    )
    profile_pic.setResizeMode(QgsLayoutItemPicture.Zoom)
    layout.addLayoutItem(profile_pic)

    # Text summary below the chart
    profile_field = "page_profile_summary" if fields.indexOf("page_profile_summary") >= 0 else ""
    if profile_field:
        _add_label(
            layout,
            f'[% coalesce("{profile_field}", \'\') %]',
            x=PROFILE_X,
            y=PROFILE_SUMMARY_Y,
            w=PROFILE_W,
            h=PROFILE_SUMMARY_H,
            font_size=8.0,
            color=QColor(80, 80, 80),
        )

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


def build_cover_layout(
    atlas_layer,
    project=None,
) -> QgsPrintLayout | None:
    """Build a single-page cover layout from document-level fields on *atlas_layer*.

    Returns ``None`` if the atlas layer has no features or the required
    document-level fields are absent (cover is simply skipped in that case).
    """
    if atlas_layer is None or atlas_layer.featureCount() == 0:
        return None

    # Read the first feature — all features carry identical document-level fields.
    feat = next(iter(atlas_layer.getFeatures()), None)
    if feat is None:
        return None

    fields = atlas_layer.fields()

    def _get(name: str, default: str = "") -> str:
        idx = fields.indexOf(name)
        if idx < 0:
            return default
        val = feat.attribute(idx)
        return str(val) if val is not None else default

    cover_summary = _get("document_cover_summary")
    activity_count = _get("document_activity_count")
    date_range_label = _get("document_date_range_label")
    total_distance_label = _get("document_total_distance_label")
    total_duration_label = _get("document_total_duration_label")
    total_elevation_gain_label = _get("document_total_elevation_gain_label")
    activity_types_label = _get("document_activity_types_label")

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
    title_y = PAGE_HEIGHT_MM * 0.30
    title_h = 18.0
    _add_label(
        layout,
        "qfit Activity Atlas",
        x=center_x,
        y=title_y,
        w=content_width,
        h=title_h,
        font_size=24.0,
        bold=True,
        align_right=False,
    )

    # Subtitle (cover summary) — just below title
    if cover_summary:
        _add_label(
            layout,
            cover_summary,
            x=center_x,
            y=title_y + title_h + 4.0,
            w=content_width,
            h=10.0,
            font_size=11.0,
            bold=False,
            color=QColor(60, 60, 60),
        )

    # Separator line (thin label with underline approximated via background color)
    sep_y = title_y + title_h + 18.0
    sep_label = QgsLayoutItemLabel(layout)
    sep_label.setText("")
    sep_label.attemptMove(QgsLayoutPoint(center_x, sep_y, QgsUnitTypes.LayoutMillimeters))
    sep_label.attemptResize(QgsLayoutSize(content_width, 0.3, QgsUnitTypes.LayoutMillimeters))
    sep_label.setBackgroundColor(QColor(180, 180, 180))
    sep_label.setBackgroundEnabled(True)
    layout.addLayoutItem(sep_label)

    # Stats block — label/value rows
    stats_y = sep_y + 6.0
    row_h = 8.0
    label_col_w = 60.0
    value_col_w = content_width - label_col_w
    label_color = QColor(100, 100, 100)
    value_color = QColor(20, 20, 20)

    stats_rows: list[tuple[str, str]] = []
    if activity_count and activity_count != "0":
        stats_rows.append(("Activities", activity_count))
    if date_range_label:
        stats_rows.append(("Date range", date_range_label))
    if total_distance_label:
        stats_rows.append(("Distance", total_distance_label))
    if total_duration_label:
        stats_rows.append(("Moving time", total_duration_label))
    if total_elevation_gain_label:
        stats_rows.append(("Climbing", total_elevation_gain_label))
    if activity_types_label:
        stats_rows.append(("Activity types", activity_types_label))

    for i, (row_label, row_value) in enumerate(stats_rows):
        row_y = stats_y + i * row_h
        _add_label(
            layout,
            f"{row_label}:",
            x=center_x,
            y=row_y,
            w=label_col_w,
            h=row_h,
            font_size=9.0,
            color=label_color,
        )
        _add_label(
            layout,
            row_value,
            x=center_x + label_col_w,
            y=row_y,
            w=value_col_w,
            h=row_h,
            font_size=9.0,
            color=value_color,
        )

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

            # Locate the profile picture item so we can set its source per page.
            profile_pic = None
            for item in layout.items():
                if getattr(item, "id", lambda: None)() == _PROFILE_PICTURE_ID:
                    profile_pic = item
                    break

            # Pre-load profile samples grouped by page_sort_key.
            profile_samples: dict[str, list[tuple[float, float]]] = {}
            sort_key_idx = fields.indexOf("page_sort_key")
            try:
                source = self._atlas_layer.source()
                gpkg_path = source.split("|")[0] if "|" in source else source
                if gpkg_path and os.path.isfile(gpkg_path):
                    from .atlas_profile_renderer import load_profile_samples_from_gpkg  # noqa: PLC0415
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
                    if profile_pic is not None and sort_key_idx >= 0:
                        page_sort_key = feat.attribute(sort_key_idx)
                        page_points = profile_samples.get(page_sort_key, []) if page_sort_key else []
                        if len(page_points) >= 2:
                            try:
                                from .atlas_profile_renderer import render_profile_to_file  # noqa: PLC0415
                                svg_path = render_profile_to_file(
                                    page_points,
                                    width_mm=PROFILE_W,
                                    height_mm=PROFILE_CHART_H,
                                    directory=os.path.dirname(self._output_path) or None,
                                )
                                if svg_path:
                                    profile_pic.setPicturePath(svg_path)
                                    profile_temp_files.append(svg_path)
                                else:
                                    profile_pic.setPicturePath("")
                            except Exception:  # noqa: BLE001
                                logger.debug("Profile chart render failed", exc_info=True)
                                profile_pic.setPicturePath("")
                        else:
                            profile_pic.setPicturePath("")

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
            all_paths = ([cover_path] if cover_path else []) + page_paths

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
        *atlas_layer*.  Failures are swallowed so they never abort the main export.
        """
        try:
            cover_layout = build_cover_layout(atlas_layer, project=project)
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

    @staticmethod
    def _merge_pdfs(page_paths: list[str], output_path: str) -> None:
        """Merge per-page PDF files into a single multi-page PDF."""
        try:
            from pypdf import PdfWriter  # noqa: PLC0415
            writer = PdfWriter()
            for path in page_paths:
                writer.append(path)
            with open(output_path, "wb") as fout:
                writer.write(fout)
            return
        except ImportError:
            pass
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
                from mapbox_config import TILE_MODE_RASTER  # noqa: PLC0415
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
