"""Background task for generating an activity atlas PDF from the atlas_pages QGIS layer.

Uses :class:`qgis.core.QgsTask` so that export runs off the main thread,
keeping the QGIS UI responsive.  The layout is constructed programmatically
using :class:`qgis.core.QgsPrintLayout` with an atlas coverage from the
``activity_atlas_pages`` vector layer.

Page template (A4 landscape, 297 × 210 mm):

    ┌──────────────────────────────────────────────────────────────────┐
    │  [Title]                                      [Date]             │
    │  [Subtitle / stats]                                              │
    │  ┌────────────────────────────────────────────────────────────┐  │
    │  │                                                            │  │
    │  │                       MAP FRAME                            │  │
    │  │                  (atlas-controlled extent)                  │  │
    │  │                                                            │  │
    │  └────────────────────────────────────────────────────────────┘  │
    │  Page [% @atlas_featurenumber %] of [% @atlas_totalfeatures %]  │
    └──────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import os

from qgis.core import (
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemMap,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsTask,
    QgsUnitTypes,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont

# ---------------------------------------------------------------------------
# Page geometry (mm, A4 landscape)
# ---------------------------------------------------------------------------

PAGE_WIDTH_MM = 297.0
PAGE_HEIGHT_MM = 210.0
MARGIN_MM = 10.0
HEADER_HEIGHT_MM = 16.0
FOOTER_HEIGHT_MM = 8.0
HEADER_GAP_MM = 3.0   # gap between header and map
FOOTER_GAP_MM = 3.0   # gap between map and footer

MAP_X = MARGIN_MM
MAP_Y = MARGIN_MM + HEADER_HEIGHT_MM + HEADER_GAP_MM
MAP_W = PAGE_WIDTH_MM - 2 * MARGIN_MM
MAP_H = (PAGE_HEIGHT_MM - MARGIN_MM - HEADER_HEIGHT_MM - HEADER_GAP_MM
         - FOOTER_GAP_MM - FOOTER_HEIGHT_MM - MARGIN_MM)


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

    # -- Page size (A4 landscape) ------------------------------------------
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
    map_item = QgsLayoutItemMap(layout)
    map_item.setLayers(proj.mapLayers().values())
    map_item.attemptMove(QgsLayoutPoint(MAP_X, MAP_Y, QgsUnitTypes.LayoutMillimeters))
    map_item.attemptResize(QgsLayoutSize(MAP_W, MAP_H, QgsUnitTypes.LayoutMillimeters))
    map_item.setAtlasDriven(True)
    map_item.setAtlasScalingMode(QgsLayoutItemMap.Auto)
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

    # -- Footer: page number -----------------------------------------------
    footer_y = PAGE_HEIGHT_MM - MARGIN_MM - FOOTER_HEIGHT_MM - FOOTER_GAP_MM
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

    # -- Footer: activity type / profile summary ---------------------------
    profile_field = "page_profile_summary" if fields.indexOf("page_profile_summary") >= 0 else ""
    if profile_field:
        _add_label(
            layout,
            f'[% coalesce("{profile_field}", \'\') %]',
            x=MARGIN_MM + 60.0,
            y=footer_y,
            w=PAGE_WIDTH_MM - 2 * MARGIN_MM - 60.0,
            h=FOOTER_HEIGHT_MM,
            font_size=7.0,
            color=QColor(120, 120, 120),
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
    subset_string:
        Optional QGIS subset string (SQL WHERE clause) to apply to the atlas
        layer before export.  When provided, only activities that match the
        current visualization filter are included in the PDF.  If ``None``,
        the layer's existing subset string (if any) is preserved.
    """

    def __init__(
        self,
        atlas_layer,
        output_path: str,
        on_finished,
        project=None,
        subset_string: str | None = None,
    ):
        super().__init__("Export qfit atlas PDF", QgsTask.CanCancel)
        self._atlas_layer = atlas_layer
        self._output_path = output_path
        self._on_finished = on_finished
        self._project = project
        self._subset_string = subset_string
        self._error: str | None = None
        self._page_count: int = 0

    # ------------------------------------------------------------------
    # QgsTask interface
    # ------------------------------------------------------------------

    def run(self) -> bool:
        """Build layout and export in the worker thread."""
        try:
            # Apply visualization subset filter if provided (non-destructive:
            # we restore the original subset string after export)
            original_subset: str | None = None
            if self._subset_string is not None and self._atlas_layer is not None:
                original_subset = self._atlas_layer.subsetString()
                self._atlas_layer.setSubsetString(self._subset_string)

            try:
                return self._run_export()
            finally:
                # Restore the original subset string regardless of outcome
                if original_subset is not None and self._atlas_layer is not None:
                    self._atlas_layer.setSubsetString(original_subset)

        except Exception as exc:  # noqa: BLE001
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

            exporter = QgsLayoutExporter(layout)
            settings = QgsLayoutExporter.PdfExportSettings()
            settings.dpi = 150
            settings.rasterizeWholeImage = False
            settings.forceVectorOutput = True

            # Ensure output directory exists
            output_dir = os.path.dirname(self._output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            # The atlas export overload returns (ExportResult, error_string)
            export_result, export_error = exporter.exportToPdf(
                atlas,
                self._output_path,
                settings,
            )

            if export_result != QgsLayoutExporter.Success:
                self._error = (
                    f"PDF export failed (QgsLayoutExporter error code {export_result}"
                    + (f": {export_error}" if export_error else "")
                    + "). Check that the atlas layer has features and the output path is writable."
                )
                return False

        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return False

        return not self.isCanceled()

    def finished(self, result: bool) -> None:
        """Called on the main thread after run() returns."""
        if self._on_finished is not None:
            self._on_finished(
                output_path=self._output_path if result else None,
                error=self._error,
                cancelled=self.isCanceled(),
                page_count=self._page_count,
            )
