"""Deprecated compatibility shim for the activity domain model.

The canonical activity model now lives in :mod:`qfit.activities.domain.models`.
Keep this module as a stable import surface while the package structure is
refactored incrementally. Do not add new in-repo imports here.
"""

from .activities.domain.models import Activity

__all__ = ["Activity"]
