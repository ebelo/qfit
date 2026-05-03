from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from .infrastructure.pdf_assembly import AtlasPdfAssemblyCancelled


@dataclass(frozen=True)
class AtlasExportExecutionResult:
    success: bool
    page_count: int = 0
    error: str | None = None


class AtlasExportCoordinator:
    """Coordinate the atlas export workflow independently from the QgsTask shell."""

    def __init__(
        self,
        *,
        atlas_layer,
        output_path: str,
        project,
        profile_plot_style,
        is_canceled: Callable[[], bool],
        build_layout: Callable[..., object],
        layout_exporter_cls,
        build_pdf_export_settings: Callable[[], object],
        ensure_output_directory: Callable[[], None],
        build_page_export_runner: Callable[..., object],
        export_cover_page: Callable[..., str | None],
        export_toc_page: Callable[..., str | None],
        assemble_output_pdf: Callable[..., None],
        logger,
    ):
        self.atlas_layer = atlas_layer
        self.output_path = output_path
        self.project = project
        self.profile_plot_style = profile_plot_style
        self.is_canceled = is_canceled
        self.build_layout = build_layout
        self.layout_exporter_cls = layout_exporter_cls
        self.build_pdf_export_settings = build_pdf_export_settings
        self.ensure_output_directory = ensure_output_directory
        self.build_page_export_runner = build_page_export_runner
        self.export_cover_page = export_cover_page
        self.export_toc_page = export_toc_page
        self.assemble_output_pdf = assemble_output_pdf
        self.logger = logger

    def _stage_failure(
        self,
        stage: str,
        exc: Exception,
        *,
        page_count: int = 0,
        user_label: str | None = None,
    ) -> AtlasExportExecutionResult:
        self.logger.exception(f"Atlas export {stage} failed")
        detail = str(exc).strip() or exc.__class__.__name__
        return AtlasExportExecutionResult(
            success=False,
            page_count=page_count,
            error=f"{user_label or stage.capitalize()} failed: {detail}",
        )

    @staticmethod
    def _discard_pdf_parts(page_paths: list[str], *front_paths: str | None) -> None:
        for path in [path for path in front_paths if path] + page_paths:
            try:
                os.remove(path)
            except OSError:
                pass

    def execute(self) -> AtlasExportExecutionResult:
        try:
            feature_count = self.atlas_layer.featureCount() if self.atlas_layer else 0
        except (RuntimeError, OSError) as exc:
            return self._stage_failure(
                "atlas layer inspection",
                exc,
                user_label="Atlas layer inspection",
            )

        if feature_count == 0:
            return AtlasExportExecutionResult(
                success=False,
                error="No atlas pages found. Store and load activity layers first.",
            )

        if self.is_canceled():
            return AtlasExportExecutionResult(success=False, page_count=feature_count)

        try:
            layout = self.build_layout(
                self.atlas_layer,
                project=self.project,
                profile_plot_style=self.profile_plot_style,
            )
        except (RuntimeError, OSError) as exc:
            return self._stage_failure("layout preparation", exc, user_label="Layout preparation")

        page_count = feature_count

        if self.is_canceled():
            return AtlasExportExecutionResult(success=False, page_count=page_count)

        try:
            exporter = self.layout_exporter_cls(layout)
            settings = self.build_pdf_export_settings()
            self.ensure_output_directory()

            page_runner = self.build_page_export_runner(
                layout=layout,
                exporter=exporter,
                settings=settings,
            )
        except (RuntimeError, OSError) as exc:
            return self._stage_failure("export setup", exc, page_count=page_count, user_label="Export setup")

        try:
            page_paths, page_error = page_runner.export_pages()
        except (RuntimeError, OSError) as exc:
            return self._stage_failure("page export", exc, page_count=page_count, user_label="Page export")

        if page_error is not None:
            return AtlasExportExecutionResult(success=False, page_count=page_count, error=page_error)
        if self.is_canceled():
            self._discard_pdf_parts(page_paths)
            return AtlasExportExecutionResult(success=False, page_count=page_count)
        if not page_paths:
            return AtlasExportExecutionResult(
                success=False,
                page_count=page_count,
                error="No pages were exported.",
            )

        try:
            cover_path = self.export_cover_page(
                self.atlas_layer,
                self.output_path,
                project=self.project,
            )
            if self.is_canceled():
                self._discard_pdf_parts(page_paths, cover_path)
                return AtlasExportExecutionResult(success=False, page_count=page_count)
            toc_path = self.export_toc_page(
                self.atlas_layer,
                self.output_path,
                project=self.project,
            )
            if self.is_canceled():
                self._discard_pdf_parts(page_paths, cover_path, toc_path)
                return AtlasExportExecutionResult(success=False, page_count=page_count)
            self.assemble_output_pdf(page_paths, cover_path=cover_path, toc_path=toc_path)
        except AtlasPdfAssemblyCancelled:
            self._discard_pdf_parts(page_paths, cover_path, toc_path)
            return AtlasExportExecutionResult(success=False, page_count=page_count)
        except (RuntimeError, OSError) as exc:
            return self._stage_failure(
                "final PDF assembly",
                exc,
                page_count=page_count,
                user_label="Final PDF assembly",
            )

        return AtlasExportExecutionResult(success=not self.is_canceled(), page_count=page_count)
