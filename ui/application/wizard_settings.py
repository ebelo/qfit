from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...configuration.application.settings_port import SettingsPort

WIZARD_VERSION = 1
WIZARD_VERSION_KEY = "ui/wizard_version"
LAST_STEP_INDEX_KEY = "ui/last_step_index"
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
    collapsed_groups: tuple[str, ...] = DEFAULT_COLLAPSED_GROUP_OBJECT_NAMES
    first_launch: bool = True


def load_wizard_settings(settings: SettingsPort) -> WizardSettingsSnapshot:
    """Load persisted wizard settings without writing defaults."""

    raw_version = settings.get(WIZARD_VERSION_KEY)
    wizard_version = _coerce_int(raw_version)
    return WizardSettingsSnapshot(
        wizard_version=wizard_version,
        last_step_index=clamp_wizard_step_index(settings.get(LAST_STEP_INDEX_KEY, 0)),
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
            collapsed_groups=snapshot.collapsed_groups,
            first_launch=snapshot.first_launch,
        )
    return snapshot


def save_last_step_index(settings: SettingsPort, index: int) -> int:
    """Persist the wizard's last step index after clamping to the valid range."""

    clamped_index = clamp_wizard_step_index(index)
    settings.set(LAST_STEP_INDEX_KEY, clamped_index)
    return clamped_index


def save_collapsed_groups(settings: SettingsPort, object_names: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Persist known collapsible group object names in stable spec order."""

    collapsed_groups = _normalise_collapsed_groups(object_names)
    settings.set(COLLAPSED_GROUPS_KEY, list(collapsed_groups))
    return collapsed_groups


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
    "WIZARD_STEP_COUNT",
    "WIZARD_VERSION",
    "WIZARD_VERSION_KEY",
    "WizardSettingsSnapshot",
    "clamp_wizard_step_index",
    "ensure_wizard_settings",
    "load_wizard_settings",
    "save_collapsed_groups",
    "save_last_step_index",
]
