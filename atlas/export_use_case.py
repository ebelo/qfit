from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..activities.application.activity_selection_state import ActivitySelectionState
from .export_controller import AtlasExportValidationError
from .export_service import (
    AtlasExportPlan,
    AtlasExportResult,
    AtlasExportService,
    GenerateAtlasPdfRequest,
)


@dataclass(frozen=True)
class GenerateAtlasPdfCommand:
    """Application-layer command for starting atlas PDF export."""

    atlas_layer: object = None
    selection_state: ActivitySelectionState = field(default_factory=ActivitySelectionState)
    output_path: str = ""
    atlas_title: str = ""
    atlas_subtitle: str = ""
    on_finished: Callable | None = None
    pre_export_tile_mode: str = ""
    preset_name: str = ""
    access_token: str = ""
    style_owner: str = ""
    style_id: str = ""
    background_enabled: bool = False
    profile_plot_style: object | None = None


@dataclass(frozen=True)
class PrepareAtlasPdfExportResult:
    """Structured outcome of validating and preparing atlas export startup."""

    plan: AtlasExportPlan | None = None
    output_path: str = ""
    path_changed: bool = False
    error_title: str | None = None
    error_message: str | None = None
    pdf_status: str | None = None
    main_status: str | None = None

    @property
    def is_ready(self) -> bool:
        return self.plan is not None and self.error_message is None


class AtlasExportUseCase:
    """Application-layer boundary for atlas PDF export.

    Coordinates request validation, prerequisite checks, basemap preparation,
    task construction, and completion result handling so the UI can interact
    with atlas export through a single use-case object.
    """

    def __init__(self, controller, service: AtlasExportService) -> None:
        self.controller = controller
        self.service = service

    @staticmethod
    def build_command(**kwargs) -> GenerateAtlasPdfCommand:
        return GenerateAtlasPdfCommand(**kwargs)

    def prepare_export(self, command: GenerateAtlasPdfCommand) -> PrepareAtlasPdfExportResult:
        try:
            self.controller.validate_atlas_layer(command.atlas_layer)
        except AtlasExportValidationError as exc:
            return PrepareAtlasPdfExportResult(
                error_title="Atlas export error",
                error_message=str(exc),
            )

        try:
            output_path, changed = self.controller.normalize_pdf_path(command.output_path)
        except AtlasExportValidationError as exc:
            return PrepareAtlasPdfExportResult(
                error_title="Missing output path",
                error_message=str(exc),
            )

        prereq_error = self.service.check_pdf_export_prerequisites()
        if prereq_error is not None:
            return PrepareAtlasPdfExportResult(
                output_path=output_path,
                path_changed=changed,
                error_title="Atlas PDF export unavailable",
                error_message=prereq_error,
                pdf_status="Atlas PDF export unavailable.",
                main_status="Atlas PDF export unavailable.",
            )

        plan = self.service.build_plan(
            output_path=output_path,
            atlas_title=command.atlas_title,
            atlas_subtitle=command.atlas_subtitle,
            pre_export_tile_mode=command.pre_export_tile_mode,
            preset_name=command.preset_name,
            access_token=command.access_token,
            style_owner=command.style_owner,
            style_id=command.style_id,
            background_enabled=command.background_enabled,
            profile_plot_style=command.profile_plot_style,
        )
        return PrepareAtlasPdfExportResult(
            plan=plan,
            output_path=output_path,
            path_changed=changed,
        )

    def start_export(self, prepared: PrepareAtlasPdfExportResult, command: GenerateAtlasPdfCommand):
        if not prepared.is_ready or prepared.plan is None:
            raise ValueError("prepare_export() must succeed before start_export().")

        request = self.service.build_request_from_plan(
            plan=prepared.plan,
            atlas_layer=command.atlas_layer,
            on_finished=command.on_finished,
        )
        self.service.prepare_basemap_for_export(request)
        return self.service.build_task(request)

    def finish_export(
        self,
        output_path: str | None,
        error: str | None,
        cancelled: bool,
        page_count: int,
    ) -> AtlasExportResult:
        return self.service.build_result(output_path, error, cancelled, page_count)
