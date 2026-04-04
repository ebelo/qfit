from __future__ import annotations

from .export_runtime import AtlasExportRuntime


class QgisAtlasExportRuntime(AtlasExportRuntime):
    """QGIS-backed atlas export runtime adapter."""

    def check_pdf_export_prerequisites(self) -> str | None:
        from .export_task import _load_pdf_writer  # lazy import: QGIS runtime only

        try:
            _load_pdf_writer()
        except ImportError:
            return (
                "Atlas PDF export requires the 'pypdf' runtime, but it is not available in this qfit install. "
                "Reinstall/update the plugin so bundled dependencies are included, then try again."
            )
        return None

    def build_task(self, request, *, layer_gateway):
        from .export_task import AtlasExportTask  # lazy import: QGIS runtime only

        return AtlasExportTask(
            atlas_layer=request.atlas_layer,
            output_path=request.output_path,
            on_finished=request.on_finished,
            restore_tile_mode=request.pre_export_tile_mode,
            layer_manager=layer_gateway,
            preset_name=request.preset_name,
            access_token=request.access_token,
            style_owner=request.style_owner,
            style_id=request.style_id,
            background_enabled=request.background_enabled,
            profile_plot_style=request.profile_plot_style,
        )
