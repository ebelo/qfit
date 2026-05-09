from __future__ import annotations

from typing import Any

from ...configuration.application.settings_port import SettingsPort
from .workflow_settings import (
    COLLAPSED_GROUPS_KEY,
    DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES,
    LAST_STEP_INDEX_KEY,
    LAST_STEP_INDEX_USER_SELECTED_KEY,
    WORKFLOW_SETTINGS_VERSION,
    WORKFLOW_SETTINGS_VERSION_KEY,
    WORKFLOW_STEP_COUNT,
    WorkflowSettingsSnapshot,
    clamp_workflow_step_index,
    ensure_workflow_settings,
    load_workflow_settings,
    preferred_current_key_from_workflow_settings,
    save_collapsed_groups,
    save_workflow_step_index,
    workflow_step_key_for_index,
)

WIZARD_VERSION = WORKFLOW_SETTINGS_VERSION
WIZARD_VERSION_KEY = WORKFLOW_SETTINGS_VERSION_KEY
WIZARD_STEP_COUNT = WORKFLOW_STEP_COUNT
WizardSettingsSnapshot = WorkflowSettingsSnapshot


def load_wizard_settings(settings: SettingsPort) -> WizardSettingsSnapshot:
    """Compatibility wrapper for loading local-first workflow settings."""

    return load_workflow_settings(settings)


def ensure_wizard_settings(settings: SettingsPort) -> WizardSettingsSnapshot:
    """Compatibility wrapper for ensuring local-first workflow settings."""

    return ensure_workflow_settings(settings)


def save_last_step_index(
    settings: SettingsPort,
    index: int,
    *,
    user_selected: bool = True,
) -> int:
    """Compatibility wrapper for persisting the selected workflow step."""

    return save_workflow_step_index(settings, index, user_selected=user_selected)


def wizard_step_key_for_index(index: int) -> str:
    """Compatibility wrapper for resolving workflow step keys by index."""

    return workflow_step_key_for_index(index)


def preferred_current_key_from_settings(
    snapshot: WizardSettingsSnapshot,
) -> str | None:
    """Compatibility wrapper for resolving the preferred workflow page."""

    return preferred_current_key_from_workflow_settings(snapshot)


def clamp_wizard_step_index(value: Any) -> int:
    """Compatibility wrapper for clamping workflow step indexes."""

    return clamp_workflow_step_index(value)


__all__ = [
    "COLLAPSED_GROUPS_KEY",
    "DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES",
    "LAST_STEP_INDEX_KEY",
    "LAST_STEP_INDEX_USER_SELECTED_KEY",
    "WIZARD_STEP_COUNT",
    "WIZARD_VERSION",
    "WIZARD_VERSION_KEY",
    "WizardSettingsSnapshot",
    "clamp_wizard_step_index",
    "ensure_wizard_settings",
    "load_wizard_settings",
    "preferred_current_key_from_settings",
    "save_collapsed_groups",
    "save_last_step_index",
    "wizard_step_key_for_index",
]
