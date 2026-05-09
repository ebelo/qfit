from __future__ import annotations

from .dock_workflow_sections import DockWizardProgress
from .workflow_progress import (
    build_startup_workflow_progress_facts,
    build_workflow_progress_from_facts,
    build_workflow_progress_from_facts_and_settings,
)
from .workflow_progress_facts import (
    WorkflowProgressFacts,
    build_workflow_progress_facts_from_runtime_state,
)
from .wizard_settings import WizardSettingsSnapshot


WizardProgressFacts = WorkflowProgressFacts
"""Compatibility alias for wizard progress callers during the #805 migration."""


build_wizard_progress_facts_from_runtime_state = (
    build_workflow_progress_facts_from_runtime_state
)
"""Compatibility alias for wizard-named progress fact construction."""


def build_wizard_progress_from_facts(facts: WizardProgressFacts) -> DockWizardProgress:
    """Compatibility wrapper for neutral workflow progress construction."""

    return build_workflow_progress_from_facts(facts)


def build_wizard_progress_from_facts_and_settings(
    facts: WizardProgressFacts,
    settings: WizardSettingsSnapshot,
) -> DockWizardProgress:
    """Compatibility wrapper for settings-aware workflow progress."""

    return build_workflow_progress_from_facts_and_settings(facts, settings)


def build_startup_wizard_progress_facts(
    facts: WizardProgressFacts,
    settings: WizardSettingsSnapshot,
) -> WizardProgressFacts:
    """Return startup-only facts for the first visible wizard page.

    Persisted step settings still control normal refreshes. Startup is the one
    place where a saved default Connection target should not make configured
    users reconfirm an already-completed prerequisite before continuing.
    """

    return build_startup_workflow_progress_facts(facts, settings)


__all__ = [
    "WizardProgressFacts",
    "build_startup_wizard_progress_facts",
    "build_wizard_progress_facts_from_runtime_state",
    "build_wizard_progress_from_facts_and_settings",
    "build_wizard_progress_from_facts",
]
