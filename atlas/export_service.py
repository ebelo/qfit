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
from ..visualization.application.layer_gateway import LayerGateway
from .qgis_export_runtime import QgisAtlasExportRuntime


@dataclass
class GenerateAtlasPdfRequest:
    """Structured input for the atlas PDF generation workflow."""

    atlas_layer: object = None
    output_path: str = ""
    on_finished: Callable | None = None
    pre_export_tile_mode: str = ""
    preset_name: str = ""
    access_token: str = ""
    style_owner: str = ""
    style_id: str = ""
    background_enabled: bool = False
    profile_plot_style: object | None = None


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

    def __init__(self, layer_gateway: LayerGateway, runtime=None) -> None:
        self.layer_gateway = layer_gateway
        self.runtime = runtime or QgisAtlasExportRuntime()

    @staticmethod
    def build_request(
        atlas_layer,
        output_path: str,
        on_finished: Callable | None,
        pre_export_tile_mode: str,
        preset_name: str,
        access_token: str,
        style_owner: str,
        style_id: str,
        background_enabled: bool,
        profile_plot_style: object | None = None,
    ) -> GenerateAtlasPdfRequest:
        return GenerateAtlasPdfRequest(
            atlas_layer=atlas_layer,
            output_path=output_path,
            on_finished=on_finished,
            pre_export_tile_mode=pre_export_tile_mode,
            preset_name=preset_name,
            access_token=access_token,
            style_owner=style_owner,
            style_id=style_id,
            background_enabled=background_enabled,
            profile_plot_style=profile_plot_style,
        )

    def prepare_basemap_for_export(
        self,
        request: GenerateAtlasPdfRequest | None = None,
        **legacy_kwargs,
    ) -> None:
        """Switch to vector tiles before export when currently using raster tiles.

        Vector tiles embed as true PDF vectors, dramatically reducing file size.
        Silently falls back to raster on error so the export can still proceed.
        """
        if request is None:
            request = self.build_request(atlas_layer=None, output_path="", on_finished=None, **legacy_kwargs)
        if request.pre_export_tile_mode != TILE_MODE_RASTER or not request.background_enabled:
            return
        try:
            self.layer_gateway.ensure_background_layer(
                enabled=True,
                preset_name=request.preset_name,
                access_token=request.access_token,
                style_owner=request.style_owner,
                style_id=request.style_id,
                tile_mode=TILE_MODE_VECTOR,
            )
        except RuntimeError:
            logger.warning("Vector tile mode failed, falling back to raster", exc_info=True)

    def check_pdf_export_prerequisites(self) -> str | None:
        """Return a user-facing error when atlas PDF export prerequisites are missing."""
        return self.runtime.check_pdf_export_prerequisites()

    def build_task(self, request: GenerateAtlasPdfRequest | None = None, **legacy_kwargs):
        """Construct an :class:`AtlasExportTask` ready to submit to the QGIS task manager."""
        if request is None:
            request = self.build_request(**legacy_kwargs)
        return self.runtime.build_task(request, layer_gateway=self.layer_gateway)

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
