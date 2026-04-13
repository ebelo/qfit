from __future__ import annotations

from .activity_preview import ActivityPreviewRequest, ActivityPreviewResult, build_activity_preview


class ActivityPreviewService:
    """Structured seam for building dock activity-preview results.

    Keeps the preview-refresh workflow behind a feature-owned application service,
    matching the request/result service pattern already used by other dock-facing
    workflows.
    """

    @staticmethod
    def build_result(
        request: ActivityPreviewRequest | None = None,
        **legacy_kwargs,
    ) -> ActivityPreviewResult:
        if request is None:
            request = ActivityPreviewRequest(**legacy_kwargs)
        return build_activity_preview(request)

    def build_result_request(self, request: ActivityPreviewRequest) -> ActivityPreviewResult:
        return self.build_result(request=request)
