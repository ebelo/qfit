from __future__ import annotations

from .export_runtime import AtlasExportRuntime
from .infrastructure.pdf_assembly import load_pdf_writer


class QgisAtlasExportRuntime(AtlasExportRuntime):
    """QGIS-backed atlas export runtime adapter."""

    def check_pdf_export_prerequisites(self) -> str | None:
        try:
            load_pdf_writer()
        except ImportError:
            return (
                "Atlas PDF export requires the bundled 'pypdf' runtime for qfit's current PDF assembly pipeline. "
                "Install qfit with scripts/install_plugin.py --mode copy or use the packaged plugin zip so runtime dependencies are vendored."
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
