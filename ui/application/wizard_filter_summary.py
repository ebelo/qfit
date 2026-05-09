from __future__ import annotations

from typing import Any

from .local_first_filter_summary import build_local_first_filter_description


def build_wizard_filter_description(request: Any) -> str | None:
    """Compatibility wrapper for the local-first filter summary policy."""

    return build_local_first_filter_description(request)


__all__ = ["build_wizard_filter_description"]
