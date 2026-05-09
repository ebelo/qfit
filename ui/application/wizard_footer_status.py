from __future__ import annotations

from qfit.ui.application.workflow_footer_status import (
    WorkflowFooterFacts,
    build_workflow_footer_facts_from_progress_facts,
    build_workflow_footer_status,
)
from qfit.ui.application.workflow_progress_facts import WorkflowProgressFacts

WizardFooterFacts = WorkflowFooterFacts
"""Compatibility alias for wizard footer callers during #805."""


def build_wizard_footer_status(
    *,
    connection_status: str | None,
    activity_summary: str | None,
    map_summary: str | None,
    analysis_status: str | None,
    atlas_status: str | None,
) -> str:
    """Compatibility wrapper for :func:`build_workflow_footer_status`."""

    return build_workflow_footer_status(
        connection_status=connection_status,
        activity_summary=activity_summary,
        map_summary=map_summary,
        analysis_status=analysis_status,
        atlas_status=atlas_status,
    )


def build_wizard_footer_facts_from_progress_facts(
    facts: WorkflowProgressFacts,
) -> WizardFooterFacts:
    """Compatibility wrapper for workflow footer fact construction."""

    return build_workflow_footer_facts_from_progress_facts(facts)


__all__ = [
    "WizardFooterFacts",
    "build_wizard_footer_facts_from_progress_facts",
    "build_wizard_footer_status",
]
