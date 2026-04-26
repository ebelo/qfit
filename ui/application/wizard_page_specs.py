from __future__ import annotations

from dataclasses import dataclass

from .dock_workflow_sections import WIZARD_WORKFLOW_STEPS


@dataclass(frozen=True)
class DockWizardPageSpec:
    """Render-neutral metadata for one wizard page placeholder.

    The page spec is intentionally small: it gives the wizard shell stable page
    keys, object names, and visible copy without deciding the final controls for
    each page. That lets the dock migrate page-by-page toward #609 without
    entrenching the current long-scroll UI.
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
        "Load activity layers, choose a background map, and refine filters.",
        "Primary action: apply map filters",
    ),
    "analysis": (
        "Run heatmap, corridor, and start-point analysis from loaded data.",
        "Primary action: run analysis",
    ),
    "atlas": (
        "Configure and export multi-activity PDF atlases.",
        "Primary action: export atlas PDF",
    ),
}


def build_default_wizard_page_specs() -> tuple[DockWizardPageSpec, ...]:
    """Return the first page placeholders in stable #609 wizard order."""

    specs = []
    for step in WIZARD_WORKFLOW_STEPS:
        if step.key not in _PAGE_COPY_BY_KEY:
            raise KeyError(
                f"No page copy found for wizard step {step.key!r}. "
                "Add an entry to _PAGE_COPY_BY_KEY."
            )
        summary, primary_action_hint = _PAGE_COPY_BY_KEY[step.key]
        specs.append(
            DockWizardPageSpec(
                key=step.key,
                title=step.title,
                summary=summary,
                primary_action_hint=primary_action_hint,
            )
        )
    return tuple(specs)


def _camel_case_key(key: str) -> str:
    return "".join(part.capitalize() for part in key.split("_"))


__all__ = ["DockWizardPageSpec", "build_default_wizard_page_specs"]
