from __future__ import annotations

from dataclasses import dataclass

from qfit.ui.application.workflow_progress_facts import WorkflowProgressFacts


@dataclass(frozen=True)
class WorkflowFooterFacts:
    """Render-neutral facts for the dock workflow footer controls."""

    strava_connected: bool = False
    activity_count: int | None = None
    layer_count: int = 0
    gpkg_path: str | None = None
    last_sync_date: str | None = None


def build_workflow_footer_status(
    *,
    connection_status: str | None,
    activity_summary: str | None,
    map_summary: str | None,
    analysis_status: str | None,
    atlas_status: str | None,
) -> str:
    """Build the compact persistent footer text for the dock workflow.

    The footer summarizes page-level render facts instead of reading current dock
    widgets. That keeps the local-first replacement path free to migrate one
    page at a time while still giving users a one-glance workflow status.
    """

    return _join_unique_status_parts(
        connection_status,
        activity_summary,
        map_summary,
        analysis_status,
        atlas_status,
    )


def build_workflow_footer_facts_from_progress_facts(
    facts: WorkflowProgressFacts,
) -> WorkflowFooterFacts:
    """Build footer pill/path facts from shared workflow progress facts.

    The compact text summary remains available separately for placeholder shells.
    This adapter drives the footer's explicit Strava/activity/layer/path controls
    from the same render-neutral state used by workflow pages, avoiding any
    dependency on current long-scroll dock widgets.
    """

    return WorkflowFooterFacts(
        strava_connected=facts.connection_configured,
        activity_count=_stored_activity_count(facts),
        layer_count=_loaded_layer_count(facts),
        gpkg_path=facts.output_name,
        last_sync_date=_optional_text(facts.last_sync_date),
    )


def _join_unique_status_parts(*values: str | None) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        part = (value or "").strip()
        if not part or part in seen:
            continue
        parts.append(part)
        seen.add(part)

    if not parts:
        return "Ready"
    return " · ".join(parts)


def _optional_text(value: str | None) -> str | None:
    stripped = (value or "").strip()
    return stripped or None


def _stored_activity_count(facts: WorkflowProgressFacts) -> int | None:
    if not facts.activities_stored or facts.activity_count is None:
        return None
    return max(int(facts.activity_count), 0)


def _loaded_layer_count(facts: WorkflowProgressFacts) -> int:
    if not facts.activity_layers_loaded:
        return 0
    if facts.loaded_layer_count is None:
        return 1
    return max(int(facts.loaded_layer_count), 0)


__all__ = [
    "WorkflowFooterFacts",
    "build_workflow_footer_facts_from_progress_facts",
    "build_workflow_footer_status",
]
