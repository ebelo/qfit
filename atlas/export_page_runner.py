from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from qgis.core import QgsLayoutExporter, QgsRectangle

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AtlasPerPageFieldIndexes:
    """Resolved atlas-layer field indexes used during the export loop."""

    cx_idx: int
    cy_idx: int
    ew_idx: int
    eh_idx: int
    sid_atlas_idx: int
    profile_summary_idx: int
    detail_field_indices: list[tuple[int, str]]

    @property
    def has_stored_extents(self) -> bool:
        return all(index >= 0 for index in (self.cx_idx, self.cy_idx, self.ew_idx, self.eh_idx))


@dataclass(frozen=True)
class AtlasPerPageLayoutItems:
    """Layout items that receive per-page updates during export."""

    map_item: object | None = None
    profile_adapter: object | None = None
    profile_summary_label: object | None = None
    detail_block_label: object | None = None

    @property
    def manual_profile_updates_enabled(self) -> bool:
        return bool(
            self.profile_adapter is not None
            and getattr(self.profile_adapter, "requires_manual_page_updates", False)
        )


@dataclass(frozen=True)
class AtlasPageExportRuntime:
    """All dependencies required to export atlas pages one-by-one."""

    atlas: object
    exporter: object
    settings: object
    output_path: str
    field_indexes: AtlasPerPageFieldIndexes
    layout_items: AtlasPerPageLayoutItems
    filterable_layers: list[tuple]
    profile_sample_lookup: object | None
    build_page_profile_payload: object
    apply_page_profile_payload: object
    normalize_extent: object
    target_aspect_ratio: float
    is_canceled: object


class AtlasPageExportRunner:
    """Run the page-by-page atlas export loop.

    This keeps per-page filtering, profile binding, map extent updates, and
    single-page PDF emission outside :class:`AtlasExportTask` so those
    responsibilities can be tested in isolation from the task lifecycle.
    """

    def __init__(self, runtime: AtlasPageExportRuntime):
        self.runtime = runtime

    def export_pages(self) -> tuple[list[str], str | None]:
        atlas = self.runtime.atlas
        page_paths: list[str] = []
        profile_temp_files: list[str] = []

        atlas.beginRender()
        atlas.updateFeatures()
        ok = atlas.first()
        page_index = 0
        try:
            while ok:
                if self.runtime.is_canceled():
                    return page_paths, None

                feat = atlas.layout().reportContext().feature()
                self._apply_page_layer_filter(feat)
                self._apply_manual_profile_updates(feat, profile_temp_files)
                self._apply_page_text(feat)
                self._apply_map_extent(feat)

                page_path = f"{self.runtime.output_path}.page_{page_index}.pdf"
                page_result = self.runtime.exporter.exportToPdf(page_path, self.runtime.settings)
                if page_result != QgsLayoutExporter.Success:
                    return (
                        page_paths,
                        f"PDF export failed on page {page_index + 1} "
                        f"(QgsLayoutExporter error code {page_result}).",
                    )
                page_paths.append(page_path)
                page_index += 1
                ok = atlas.next()
        finally:
            self._restore_filterable_layers()
            self._cleanup_profile_temp_files(profile_temp_files)
            atlas.endRender()

        return page_paths, None

    def _apply_page_layer_filter(self, feat) -> None:
        field_indexes = self.runtime.field_indexes
        if not self.runtime.filterable_layers or field_indexes.sid_atlas_idx < 0:
            return

        sid_value = feat.attribute(field_indexes.sid_atlas_idx)
        if sid_value in (None, ""):
            return

        safe_sid = str(sid_value).replace("'", "''")
        page_filter = f'"source_activity_id" = \'{safe_sid}\''
        for layer, _original_subset in self.runtime.filterable_layers:
            try:
                layer.setSubsetString(page_filter)
            except RuntimeError:
                logger.debug("Failed to set page filter on layer", exc_info=True)

    def _apply_manual_profile_updates(self, feat, profile_temp_files: list[str]) -> None:
        layout_items = self.runtime.layout_items
        if not layout_items.manual_profile_updates_enabled or layout_items.profile_adapter is None:
            return

        profile_payload = self.runtime.build_page_profile_payload(
            feat,
            self.runtime.filterable_layers,
            profile_altitude_lookup=getattr(self.runtime.profile_sample_lookup, "lookup", None),
        )
        self.runtime.apply_page_profile_payload(
            layout_items.profile_adapter,
            profile_payload,
            output_path=self.runtime.output_path,
            profile_temp_files=profile_temp_files,
        )

    def _apply_page_text(self, feat) -> None:
        field_indexes = self.runtime.field_indexes
        layout_items = self.runtime.layout_items

        if layout_items.profile_summary_label is not None and field_indexes.profile_summary_idx >= 0:
            val = feat.attribute(field_indexes.profile_summary_idx)
            layout_items.profile_summary_label.setText(str(val) if val else "")

        if layout_items.detail_block_label is None or not field_indexes.detail_field_indices:
            return

        lines = []
        for idx, human_label in field_indexes.detail_field_indices:
            val = feat.attribute(idx)
            if val is not None and val != "":
                lines.append(f"{human_label}: {val}")
        layout_items.detail_block_label.setText("\n".join(lines))

    def _apply_map_extent(self, feat) -> None:
        layout_items = self.runtime.layout_items
        field_indexes = self.runtime.field_indexes
        if layout_items.map_item is None or not field_indexes.has_stored_extents:
            return

        cx = feat.attribute(field_indexes.cx_idx)
        cy = feat.attribute(field_indexes.cy_idx)
        ew = feat.attribute(field_indexes.ew_idx)
        eh = feat.attribute(field_indexes.eh_idx)
        if not all(value is not None and value != "" for value in (cx, cy, ew, eh)):
            return

        half_width = float(ew) / 2.0
        half_height = float(eh) / 2.0
        rect = QgsRectangle(
            float(cx) - half_width,
            float(cy) - half_height,
            float(cx) + half_width,
            float(cy) + half_height,
        )
        rect = self.runtime.normalize_extent(rect, self.runtime.target_aspect_ratio)
        layout_items.map_item.setExtent(rect)
        layout_items.map_item.refresh()

    def _restore_filterable_layers(self) -> None:
        for layer, original_subset in self.runtime.filterable_layers:
            try:
                layer.setSubsetString(original_subset)
            except RuntimeError:
                logger.debug("Failed to restore layer subset", exc_info=True)

    @staticmethod
    def _cleanup_profile_temp_files(profile_temp_files: list[str]) -> None:
        for temp_path in profile_temp_files:
            try:
                os.remove(temp_path)
            except OSError:
                pass
