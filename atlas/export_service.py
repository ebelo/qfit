"""Service for orchestrating atlas PDF export task lifecycle.

Handles basemap tile-mode switching strategy, task construction, and result
message building — all independent of the UI layer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)

from ..mapbox_config import TILE_MODE_RASTER, TILE_MODE_VECTOR


@dataclass
class AtlasExportResult:
    """Structured outcome from a completed atlas PDF export."""

    output_path: str | None = None
    page_count: int = 0
    error: str | None = None
    cancelled: bool = False

    @property
    def pdf_status(self) -> str:
        """Short status string for the atlas PDF status label."""
        if self.cancelled:
            return "Atlas PDF export cancelled."
        if self.error is not None:
            return f"Export failed: {self.error}"
        return f"Atlas PDF exported: {self.page_count} page(s) → {self.output_path}"

    @property
    def main_status(self) -> str:
        """Status string for the main dock status bar."""
        if self.cancelled:
            return "Atlas PDF export cancelled."
        if self.error is not None:
            return "Atlas PDF export failed."
        return self.pdf_status


class AtlasExportService:
    """Orchestrates atlas PDF export: basemap preparation and task construction.

    Separates the tile-mode switching strategy and task wiring from the UI layer,
    making both independently testable.
    """

    def __init__(self, layer_manager) -> None:
        self.layer_manager = layer_manager

    def prepare_basemap_for_export(
        self,
        *,
        pre_export_tile_mode: str,
        background_enabled: bool,
        preset_name: str,
        access_token: str,
        style_owner: str,
        style_id: str,
    ) -> None:
        """Switch to vector tiles before export when currently using raster tiles.

        Vector tiles embed as true PDF vectors, dramatically reducing file size.
        Silently falls back to raster on error so the export can still proceed.
        """
        if pre_export_tile_mode != TILE_MODE_RASTER or not background_enabled:
            return
        try:
            self.layer_manager.ensure_background_layer(
                enabled=True,
                preset_name=preset_name,
                access_token=access_token,
                style_owner=style_owner,
                style_id=style_id,
                tile_mode=TILE_MODE_VECTOR,
            )
        except RuntimeError:
            logger.warning("Vector tile mode failed, falling back to raster", exc_info=True)

    def build_task(
        self,
        *,
        atlas_layer,
        output_path: str,
        on_finished: Callable,
        pre_export_tile_mode: str,
        preset_name: str,
        access_token: str,
        style_owner: str,
        style_id: str,
        background_enabled: bool,
    ):
        """Construct an :class:`AtlasExportTask` ready to submit to the QGIS task manager."""
        from .export_task import AtlasExportTask  # lazy import: QGIS runtime only
        return AtlasExportTask(
            atlas_layer=atlas_layer,
            output_path=output_path,
            on_finished=on_finished,
            restore_tile_mode=pre_export_tile_mode,
            layer_manager=self.layer_manager,
            preset_name=preset_name,
            access_token=access_token,
            style_owner=style_owner,
            style_id=style_id,
            background_enabled=background_enabled,
        )

    @staticmethod
    def build_result(
        output_path: str | None,
        error: str | None,
        cancelled: bool,
        page_count: int,
    ) -> AtlasExportResult:
        """Wrap raw task callback parameters into a structured :class:`AtlasExportResult`."""
        return AtlasExportResult(
            output_path=output_path,
            page_count=page_count,
            error=error,
            cancelled=cancelled,
        )
