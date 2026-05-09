from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .dock_workflow_sections import DockWorkflowSection, WIZARD_WORKFLOW_STEPS


@dataclass(frozen=True)
class DockWorkflowPageSpec:
    """Render-neutral metadata for one dock workflow page.

    The page spec is intentionally small: it gives the local-first dock shell
    stable page keys, object names, and visible copy without deciding the final
    controls for each page. That lets the dock migrate page-by-page toward the
    #805 local-first workflow without entrenching the legacy long-scroll UI.
    """

    key: str
    title: str
    summary: str
    primary_action_hint: str

    @property
    def page_object_name(self) -> str:
        return f"qfitWizard{_camel_case_key(self.key)}Page"

    @property
    def title_object_name(self) -> str:
        return f"{self.page_object_name}Title"

    @property
    def summary_object_name(self) -> str:
        return f"{self.page_object_name}Summary"

    @property
    def body_object_name(self) -> str:
        return f"{self.page_object_name}Body"

    @property
    def primary_hint_object_name(self) -> str:
        return f"{self.page_object_name}PrimaryHint"


_PAGE_COPY_BY_KEY = {
    "connection": (
        "Connect qfit to Strava before syncing activities.",
        "Primary action: configure connection",
    ),
    "sync": (
        "Sync Strava activities or load an existing GeoPackage.",
        "Primary action: sync activities; secondary action: load activities",
    ),
    "map": (
        "Load stored map layers, choose a background map, and refine filters.",
        "Primary action: apply map filters",
    ),
    "analysis": (
        "Optionally run heatmap, corridor, and start-point analysis from loaded data.",
        "Optional action: run spatial analysis",
    ),
    "atlas": (
        "Configure and export multi-activity PDF atlases.",
        "Primary action: export atlas PDF",
    ),
}


def build_default_workflow_page_specs(
    *,
    workflow_steps: Sequence[DockWorkflowSection] | None = None,
) -> tuple[DockWorkflowPageSpec, ...]:
    """Return local-first dock page specs in stable workflow order."""

    steps = WIZARD_WORKFLOW_STEPS if workflow_steps is None else tuple(workflow_steps)
    specs = []
    for step in steps:
        if step.key not in _PAGE_COPY_BY_KEY:
            raise KeyError(
                f"No page copy found for workflow step {step.key!r}. "
                "Add an entry to _PAGE_COPY_BY_KEY."
            )
        summary, primary_action_hint = _PAGE_COPY_BY_KEY[step.key]
        specs.append(
            DockWorkflowPageSpec(
                key=step.key,
                title=step.title,
                summary=summary,
                primary_action_hint=primary_action_hint,
            )
        )
    return tuple(specs)


def _camel_case_key(key: str) -> str:
    return "".join(part.capitalize() for part in key.split("_"))


__all__ = ["DockWorkflowPageSpec", "build_default_workflow_page_specs"]
