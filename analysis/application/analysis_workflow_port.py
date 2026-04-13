from __future__ import annotations

from typing import Protocol, runtime_checkable

from .analysis_models import RunAnalysisRequest, RunAnalysisResult


@runtime_checkable
class AnalysisWorkflowPort(Protocol):
    def build_request(
        self,
        analysis_mode: str,
        starts_layer: object,
        selection_state=None,
        activities_layer: object = None,
        points_layer: object = None,
    ) -> RunAnalysisRequest: ...

    def run_request(self, request: RunAnalysisRequest) -> RunAnalysisResult: ...
