from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SettingsPort(Protocol):
    """Application-facing settings access port.

    qfit workflows and UI helpers should depend on this small contract rather
    than on QGIS-specific settings details directly.
    """

    def get(self, key: str, default: Any = None) -> Any:
        """Return the stored value for *key*, or *default* when unset."""

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Return the stored setting coerced to a boolean value."""

    def set(self, key: str, value: Any) -> None:
        """Persist *value* under *key*."""
