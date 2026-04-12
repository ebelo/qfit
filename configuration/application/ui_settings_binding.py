"""Explicit UI-field to settings-key binding for standardised settings persistence.

This module provides a lightweight mechanism to declare the mapping between
UI widget accessor pairs and settings keys in a single place, removing the
implicit coupling that arises when ``_load`` / ``_save`` methods each enumerate
widget → key pairs independently.

Usage example::

    from qfit.configuration.application.ui_settings_binding import UIFieldBinding, load_bindings, save_bindings

    bindings = [
        UIFieldBinding(
            key="client_id",
            default="",
            getter=lambda: widget.text().strip(),
            setter=widget.setText,
        ),
    ]

    load_bindings(bindings, settings_service)   # populate widgets from settings
    save_bindings(bindings, settings_service)   # persist widget values to settings
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .settings_port import SettingsPort


@dataclass
class UIFieldBinding:
    """Single-source mapping between a settings key and a UI widget.

    Attributes
    ----------
    key:
        The settings key (without prefix).
    default:
        Value returned when the key has no stored value.
    getter:
        Zero-argument callable that returns the widget's current value.
    setter:
        Single-argument callable that writes a value to the widget.
    """

    key: str
    default: Any
    getter: Callable[[], Any]
    setter: Callable[[Any], None]


def load_bindings(
    bindings: list[UIFieldBinding],
    settings: SettingsPort,
) -> None:
    """Populate each widget from *settings* using the explicit binding table."""
    for b in bindings:
        b.setter(settings.get(b.key, b.default))


def save_bindings(
    bindings: list[UIFieldBinding],
    settings: SettingsPort,
) -> None:
    """Persist each widget value to *settings* using the explicit binding table."""
    for b in bindings:
        settings.set(b.key, b.getter())
