from __future__ import annotations

from importlib import import_module
from typing import Sequence


def import_qt_module(qgis_module: str, pyqt_module: str, required_attributes: Sequence[str]):
    """Import a QGIS PyQt module, falling back to PyQt5 for incomplete test stubs."""

    try:
        module = import_module(qgis_module)
    except ModuleNotFoundError as exc:
        if not str(exc).startswith("No module named 'qgis"):
            raise
        return import_module(pyqt_module)
    if all(hasattr(module, attribute) for attribute in required_attributes):
        return module
    # Some pure tests temporarily register tiny qgis.PyQt stubs. Fall back to
    # PyQt5 when those stubs do not provide every widget API needed here.
    return import_module(pyqt_module)


__all__ = ["import_qt_module"]
