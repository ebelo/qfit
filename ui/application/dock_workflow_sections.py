from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DockWorkflowSection:
    """UI-neutral workflow section metadata shared by dock layouts."""

    key: str
    title: str
    current_dock_title: str
    current_dock_overview_title: str | None = None

    @property
    def overview_title(self) -> str:
        return self.current_dock_overview_title or self.current_dock_title


WIZARD_WORKFLOW_STEPS: tuple[DockWorkflowSection, ...] = (
    DockWorkflowSection(
        key="connection",
        title="Connection",
        current_dock_title="Strava connection",
    ),
    DockWorkflowSection(
        key="sync",
        title="Synchronization",
        current_dock_title="Fetch and store",
        current_dock_overview_title="Fetch & store",
    ),
    DockWorkflowSection(
        key="map",
        title="Map & filters",
        current_dock_title="Visualize",
    ),
    DockWorkflowSection(
        key="analysis",
        title="Spatial analysis",
        current_dock_title="Analyze",
    ),
    DockWorkflowSection(
        key="atlas",
        title="Atlas PDF",
        current_dock_title="Publish / atlas",
        current_dock_overview_title="Publish",
    ),
)

CURRENT_DOCK_SECTION_KEYS: frozenset[str] = frozenset({"sync", "map", "analysis", "atlas"})
CURRENT_DOCK_SECTIONS: tuple[DockWorkflowSection, ...] = tuple(
    section for section in WIZARD_WORKFLOW_STEPS if section.key in CURRENT_DOCK_SECTION_KEYS
)


def build_current_dock_workflow_label() -> str:
    """Return the compact workflow overview label for the current dock shell."""

    titles = " · ".join(section.overview_title for section in CURRENT_DOCK_SECTIONS)
    return f"Sections: {titles}"


def get_workflow_section(key: str) -> DockWorkflowSection:
    """Return a workflow section by stable key."""

    for section in WIZARD_WORKFLOW_STEPS:
        if section.key == key:
            return section
    raise KeyError(key)
