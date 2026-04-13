from __future__ import annotations

from dataclasses import dataclass, field

from ...activities.application.activity_selection_state import ActivitySelectionState


@dataclass(frozen=True)
class RunAnalysisRequest:
    analysis_mode: str = ""
    activities_layer: object = None
    starts_layer: object = None
    points_layer: object = None
    selection_state: ActivitySelectionState = field(default_factory=ActivitySelectionState)


@dataclass(frozen=True)
class RunAnalysisResult:
    status: str = ""
    layer: object = None
