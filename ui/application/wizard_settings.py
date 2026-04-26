from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...configuration.application.settings_port import SettingsPort
from .dock_workflow_sections import WIZARD_WORKFLOW_STEPS

WIZARD_VERSION = 1
WIZARD_VERSION_KEY = "ui/wizard_version"
LAST_STEP_INDEX_KEY = "ui/last_step_index"
LAST_STEP_INDEX_USER_SELECTED_KEY = "ui/last_step_index_user_selected"
COLLAPSED_GROUPS_KEY = "ui/collapsed_groups"
WIZARD_STEP_COUNT = 5

DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES: tuple[str, ...] = (
    "advancedOptionsGroup",
    "layoutGroup",
    "temporalGroup",
)


@dataclass(frozen=True)
class WizardSettingsSnapshot:
    """UI-neutral persisted settings for the future wizard dock shell."""

    wizard_version: int | None
    last_step_index: int = 0
    last_step_index_user_selected: bool = False
    collapsed_groups: tuple[str, ...] = DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES
    first_launch: bool = True


def load_wizard_settings(settings: SettingsPort) -> WizardSettingsSnapshot:
    """Load persisted wizard settings without writing defaults."""

    raw_version = settings.get(WIZARD_VERSION_KEY)
    wizard_version = _coerce_int(raw_version)
    return WizardSettingsSnapshot(
        wizard_version=wizard_version,
        last_step_index=clamp_wizard_step_index(settings.get(LAST_STEP_INDEX_KEY, 0)),
        last_step_index_user_selected=_coerce_bool(
            settings.get(LAST_STEP_INDEX_USER_SELECTED_KEY, False)
        ),
        collapsed_groups=_normalise_collapsed_groups(
            settings.get(COLLAPSED_GROUPS_KEY, DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES)
        ),
        first_launch=wizard_version is None,
    )


def ensure_wizard_settings(settings: SettingsPort) -> WizardSettingsSnapshot:
    """Write first-launch defaults and return the populated wizard snapshot.

    On first launch, this persists ``qfit/ui/wizard_version`` and returns a
    snapshot with ``wizard_version`` populated while preserving
    ``first_launch=True`` so the wizard can still apply the spec's initial step
    state. Existing wizard settings are returned unchanged.
    """

    snapshot = load_wizard_settings(settings)
    if snapshot.first_launch:
        settings.set(WIZARD_VERSION_KEY, WIZARD_VERSION)
        settings.set(COLLAPSED_GROUPS_KEY, list(snapshot.collapsed_groups))
        return WizardSettingsSnapshot(
            wizard_version=WIZARD_VERSION,
            last_step_index=snapshot.last_step_index,
            last_step_index_user_selected=snapshot.last_step_index_user_selected,
            collapsed_groups=snapshot.collapsed_groups,
            first_launch=snapshot.first_launch,
        )
    return snapshot


def save_last_step_index(
    settings: SettingsPort,
    index: int,
    *,
    user_selected: bool = True,
) -> int:
    """Persist the wizard's last step index after clamping to the valid range."""

    clamped_index = clamp_wizard_step_index(index)
    settings.set(LAST_STEP_INDEX_KEY, clamped_index)
    settings.set(LAST_STEP_INDEX_USER_SELECTED_KEY, bool(user_selected))
    return clamped_index


def save_collapsed_groups(settings: SettingsPort, object_names: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Persist known collapsible group object names in stable spec order."""

    collapsed_groups = _normalise_collapsed_groups(object_names)
    settings.set(COLLAPSED_GROUPS_KEY, list(collapsed_groups))
    return collapsed_groups


def wizard_step_key_for_index(index: int) -> str:
    """Return the stable wizard step key for a persisted step index."""

    return WIZARD_WORKFLOW_STEPS[clamp_wizard_step_index(index)].key


def preferred_current_key_from_settings(
    snapshot: WizardSettingsSnapshot,
) -> str | None:
    """Return the restore target from persisted wizard settings.

    First launch intentionally has no restore target: the #609 spec requires the
    connection page to be current with all other steps locked. Once wizard
    settings already exist, the saved index becomes a preferred target that
    progress derivation can still gate behind incomplete prerequisites.
    """

    if snapshot.first_launch:
        return None
    return wizard_step_key_for_index(snapshot.last_step_index)


def clamp_wizard_step_index(value: Any) -> int:
    """Coerce a persisted step index into the wizard's 0-based page range."""

    step_index = _coerce_int(value)
    if step_index is None:
        step_index = 0
    return min(max(step_index, 0), WIZARD_STEP_COUNT - 1)


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
    requested = {name for name in raw_names if name in DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES}
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
    "WIZARD_STEP_COUNT",
    "WIZARD_VERSION",
    "WIZARD_VERSION_KEY",
    "WizardSettingsSnapshot",
    "clamp_wizard_step_index",
    "ensure_wizard_settings",
    "load_wizard_settings",
    "save_collapsed_groups",
    "save_last_step_index",
    "preferred_current_key_from_settings",
    "wizard_step_key_for_index",
]
