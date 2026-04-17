from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ...activities.application.activity_selection_state import ActivitySelectionState
from ...atlas.export_use_case import AtlasExportUseCase, GenerateAtlasPdfCommand


@dataclass(frozen=True)
class DockAtlasExportRequest:
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


class DockAtlasWorkflowCoordinator:
    """Build dock atlas export commands from a dock-edge request snapshot."""

    def __init__(self, *, atlas_export_use_case: AtlasExportUseCase) -> None:
        self.atlas_export_use_case = atlas_export_use_case

    def build_export_command(self, request: DockAtlasExportRequest) -> GenerateAtlasPdfCommand:
        return self.atlas_export_use_case.build_command(
            atlas_layer=request.atlas_layer,
            selection_state=request.selection_state,
            output_path=request.output_path,
            atlas_title=request.atlas_title,
            atlas_subtitle=request.atlas_subtitle,
            on_finished=request.on_finished,
            pre_export_tile_mode=request.pre_export_tile_mode,
            preset_name=request.preset_name,
            access_token=request.access_token,
            style_owner=request.style_owner,
            style_id=request.style_id,
            background_enabled=request.background_enabled,
            profile_plot_style=request.profile_plot_style,
        )


__all__ = [
    "DockAtlasExportRequest",
    "DockAtlasWorkflowCoordinator",
]
