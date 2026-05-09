from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...configuration.application.settings_port import SettingsPort
from .dock_workflow_sections import WIZARD_WORKFLOW_STEPS

WORKFLOW_SETTINGS_VERSION = 1
WORKFLOW_SETTINGS_VERSION_KEY = "ui/wizard_version"
LAST_STEP_INDEX_KEY = "ui/last_step_index"
LAST_STEP_INDEX_USER_SELECTED_KEY = "ui/last_step_index_user_selected"
COLLAPSED_GROUPS_KEY = "ui/collapsed_groups"
WORKFLOW_STEP_COUNT = 5

DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES: tuple[str, ...] = (
    "advancedOptionsGroup",
    "layoutGroup",
    "temporalGroup",
)


@dataclass(frozen=True, init=False)
class WorkflowSettingsSnapshot:
    """UI-neutral persisted settings for the local-first workflow shell."""

    settings_version: int | None
    last_step_index: int = 0
    last_step_index_user_selected: bool = False
    collapsed_groups: tuple[str, ...] = DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES
    first_launch: bool = True

    def __init__(
        self,
        settings_version: int | None = None,
        last_step_index: int = 0,
        last_step_index_user_selected: bool = False,
        collapsed_groups: tuple[str, ...] = DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES,
        first_launch: bool = True,
        *,
        wizard_version: int | None = None,
    ) -> None:
        """Create a workflow settings snapshot.

        ``wizard_version`` remains accepted as a keyword-only compatibility seam
        for callers that still construct the previous wizard-named snapshot.
        """

        if settings_version is not None and wizard_version is not None:
            if settings_version != wizard_version:
                raise ValueError("settings_version and wizard_version must match")
        resolved_version = (
            settings_version if settings_version is not None else wizard_version
        )
        object.__setattr__(self, "settings_version", resolved_version)
        object.__setattr__(self, "last_step_index", last_step_index)
        object.__setattr__(
            self,
            "last_step_index_user_selected",
            last_step_index_user_selected,
        )
        object.__setattr__(self, "collapsed_groups", collapsed_groups)
        object.__setattr__(self, "first_launch", first_launch)

    @property
    def wizard_version(self) -> int | None:
        """Compatibility alias for the persisted workflow settings version."""

        return self.settings_version


def load_workflow_settings(settings: SettingsPort) -> WorkflowSettingsSnapshot:
    """Load persisted workflow settings without writing defaults."""

    raw_version = settings.get(WORKFLOW_SETTINGS_VERSION_KEY)
    settings_version = _coerce_int(raw_version)
    return WorkflowSettingsSnapshot(
        settings_version=settings_version,
        last_step_index=clamp_workflow_step_index(settings.get(LAST_STEP_INDEX_KEY, 0)),
        last_step_index_user_selected=_coerce_bool(
            settings.get(LAST_STEP_INDEX_USER_SELECTED_KEY, False)
        ),
        collapsed_groups=_normalise_collapsed_groups(
            settings.get(COLLAPSED_GROUPS_KEY, DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES)
        ),
        first_launch=settings_version is None,
    )


def ensure_workflow_settings(settings: SettingsPort) -> WorkflowSettingsSnapshot:
    """Write first-launch defaults and return the populated workflow snapshot.

    The stored keys intentionally keep their legacy values so existing user
    preferences migrate into the local-first workflow shell without data loss.
    """

    snapshot = load_workflow_settings(settings)
    if snapshot.first_launch:
        settings.set(WORKFLOW_SETTINGS_VERSION_KEY, WORKFLOW_SETTINGS_VERSION)
        settings.set(COLLAPSED_GROUPS_KEY, list(snapshot.collapsed_groups))
        return WorkflowSettingsSnapshot(
            settings_version=WORKFLOW_SETTINGS_VERSION,
            last_step_index=snapshot.last_step_index,
            last_step_index_user_selected=snapshot.last_step_index_user_selected,
            collapsed_groups=snapshot.collapsed_groups,
            first_launch=snapshot.first_launch,
        )
    return snapshot


def save_workflow_step_index(
    settings: SettingsPort,
    index: int,
    *,
    user_selected: bool = True,
) -> int:
    """Persist the workflow's last step index after clamping to the valid range."""

    clamped_index = clamp_workflow_step_index(index)
    settings.set(LAST_STEP_INDEX_KEY, clamped_index)
    settings.set(LAST_STEP_INDEX_USER_SELECTED_KEY, bool(user_selected))
    return clamped_index


def save_collapsed_groups(
    settings: SettingsPort,
    object_names: list[str] | tuple[str, ...],
) -> tuple[str, ...]:
    """Persist known collapsible group object names in stable spec order."""

    collapsed_groups = _normalise_collapsed_groups(object_names)
    settings.set(COLLAPSED_GROUPS_KEY, list(collapsed_groups))
    return collapsed_groups


def workflow_step_key_for_index(index: int) -> str:
    """Return the stable workflow step key for a persisted step index."""

    return WIZARD_WORKFLOW_STEPS[clamp_workflow_step_index(index)].key


def preferred_current_key_from_workflow_settings(
    snapshot: WorkflowSettingsSnapshot,
) -> str | None:
    """Return the restore target from persisted workflow settings.

    First launch intentionally has no restore target: the local-first workflow
    should start from the initial connection page state. Once settings already
    exist, the saved index becomes a preferred target that progress derivation
    can still gate behind incomplete prerequisites.
    """

    if snapshot.first_launch:
        return None
    return workflow_step_key_for_index(snapshot.last_step_index)


def clamp_workflow_step_index(value: Any) -> int:
    """Coerce a persisted step index into the workflow's 0-based page range."""

    step_index = _coerce_int(value)
    if step_index is None:
        step_index = 0
    return min(max(step_index, 0), WORKFLOW_STEP_COUNT - 1)


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _normalise_collapsed_groups(value: Any) -> tuple[str, ...]:
    raw_names = _as_string_sequence(value)
    requested = {
        name for name in raw_names if name in DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES
    }
    return tuple(name for name in DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES if name in requested)


def _as_string_sequence(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES
    if isinstance(value, str):
        if "," in value:
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return (value,)
    try:
        return tuple(str(item) for item in value)
    except TypeError:
        return DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES


__all__ = [
    "COLLAPSED_GROUPS_KEY",
    "DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES",
    "LAST_STEP_INDEX_KEY",
    "LAST_STEP_INDEX_USER_SELECTED_KEY",
    "WORKFLOW_SETTINGS_VERSION",
    "WORKFLOW_SETTINGS_VERSION_KEY",
    "WORKFLOW_STEP_COUNT",
    "WorkflowSettingsSnapshot",
    "clamp_workflow_step_index",
    "ensure_workflow_settings",
    "load_workflow_settings",
    "preferred_current_key_from_workflow_settings",
    "save_collapsed_groups",
    "save_workflow_step_index",
    "workflow_step_key_for_index",
]
