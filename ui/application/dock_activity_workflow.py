from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ...activities.application import (
    ActivityPreviewRequest,
    ActivityPreviewResult,
    ActivityTypeOptionsResult,
    build_activity_type_options_from_activities,
)


_DEFAULT_PER_PAGE = 200
_DEFAULT_MAX_PAGES = 0
_DEFAULT_MAX_DETAILED_ACTIVITIES = 25


@dataclass(frozen=True)
class DockFetchRequest:
    client_id: str
    client_secret: str
    refresh_token: str
    cache: object
    detailed_route_strategy: str
    on_finished: object
    advanced_fetch_enabled: bool
    detailed_streams_checked: bool
    per_page_value: int
    max_pages_value: int
    max_detailed_activities_value: int
    use_detailed_streams_override: bool | None = None


@dataclass(frozen=True)
class DockFetchCompletionRequest:
    activities: list[object] = field(default_factory=list)
    error: str | None = None
    cancelled: bool = False
    provider: object = None
    current_activity_type: str = "All"
    preview_request: ActivityPreviewRequest | None = None


@dataclass(frozen=True)
class DockFetchCompletionResult:
    activities: list[object] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    today_str: str = ""
    count_label_text: str = ""
    status_text: str = ""
    cancelled: bool = False
    error_title: str | None = None
    error_message: str | None = None
    activity_type_options: ActivityTypeOptionsResult | None = None
    preview_result: ActivityPreviewResult | None = None


class DockActivityWorkflowCoordinator:
    """Coordinate the dock's fetch and preview workflow family.

    This keeps fetch-task request building, completion handling, and preview
    refresh orchestration out of ``QfitDockWidget`` so the widget can focus on
    rendering and signal wiring.
    """

    def __init__(
        self,
        *,
        sync_controller,
        fetch_result_service,
        activity_preview_service,
    ) -> None:
        self.sync_controller = sync_controller
        self.fetch_result_service = fetch_result_service
        self.activity_preview_service = activity_preview_service

    def build_fetch_task(self, request: DockFetchRequest):
        use_detailed_streams = self._resolve_use_detailed_streams(request)
        fetch_request = self.sync_controller.build_fetch_task_request(
            client_id=request.client_id,
            client_secret=request.client_secret,
            refresh_token=request.refresh_token,
            cache=request.cache,
            per_page=self._resolve_per_page(request),
            max_pages=self._resolve_max_pages(request),
            use_detailed_streams=use_detailed_streams,
            max_detailed_activities=self._resolve_max_detailed_activities(
                request,
                use_detailed_streams=use_detailed_streams,
            ),
            detailed_route_strategy=request.detailed_route_strategy,
            on_finished=request.on_finished,
        )
        return self.sync_controller.build_fetch_task(fetch_request)

    def build_fetch_completion_result(
        self,
        request: DockFetchCompletionRequest,
    ) -> DockFetchCompletionResult:
        fetch_request = self.fetch_result_service.build_request(
            activities=request.activities,
            error=request.error,
            cancelled=request.cancelled,
            provider=request.provider,
        )
        fetch_result = self.fetch_result_service.build_result_request(fetch_request)

        if fetch_result.cancelled:
            return DockFetchCompletionResult(
                cancelled=True,
                status_text=fetch_result.status_text,
            )

        if fetch_result.error is not None:
            return DockFetchCompletionResult(
                error_title="Strava import failed",
                error_message=fetch_result.error,
                status_text=fetch_result.status_text,
            )

        activity_type_options = build_activity_type_options_from_activities(
            fetch_result.activities,
            current_value=request.current_activity_type or "All",
        )
        preview_result = None
        if request.preview_request is not None:
            preview_request = replace(
                request.preview_request,
                activities=fetch_result.activities,
                activity_type=activity_type_options.selected_value,
            )
            preview_result = self.build_preview_result(preview_request)

        return DockFetchCompletionResult(
            activities=fetch_result.activities,
            metadata=fetch_result.metadata,
            today_str=fetch_result.today_str,
            count_label_text=fetch_result.count_label_text,
            status_text=fetch_result.status_text,
            activity_type_options=activity_type_options,
            preview_result=preview_result,
        )

    def build_preview_result(self, request: ActivityPreviewRequest) -> ActivityPreviewResult:
        return self.activity_preview_service.build_result_request(request)

    @staticmethod
    def _resolve_use_detailed_streams(request: DockFetchRequest) -> bool:
        if request.use_detailed_streams_override is not None:
            return request.use_detailed_streams_override
        if request.advanced_fetch_enabled:
            return request.detailed_streams_checked
        return False

    @staticmethod
    def _resolve_per_page(request: DockFetchRequest) -> int:
        if request.advanced_fetch_enabled:
            return request.per_page_value
        return _DEFAULT_PER_PAGE

    @staticmethod
    def _resolve_max_pages(request: DockFetchRequest) -> int:
        if request.advanced_fetch_enabled:
            return request.max_pages_value
        return _DEFAULT_MAX_PAGES

    @staticmethod
    def _resolve_max_detailed_activities(
        request: DockFetchRequest,
        *,
        use_detailed_streams: bool,
    ) -> int:
        if request.advanced_fetch_enabled or use_detailed_streams:
            return request.max_detailed_activities_value
        return _DEFAULT_MAX_DETAILED_ACTIVITIES


__all__ = [
    "DockActivityWorkflowCoordinator",
    "DockFetchCompletionRequest",
    "DockFetchCompletionResult",
    "DockFetchRequest",
]
