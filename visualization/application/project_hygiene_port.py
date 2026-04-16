from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProjectHygienePort(Protocol):
    """Application-facing boundary for qfit-owned project cleanup rules."""

    def remove_stale_qfit_layers(self) -> None: ...


__all__ = ["ProjectHygienePort"]
