"""Runtime loading for the FIT decoder bundled with packaged qfit builds."""

from __future__ import annotations

import importlib
import os
import sys


def load_fitdecode():
    """Return the ``fitdecode`` module, preferring the active environment.

    Packaged plugin builds vendor the pure-Python dependency under ``vendor``.
    Source checkouts may instead install it into the current Python environment.
    """

    try:
        return importlib.import_module("fitdecode")
    except ImportError:
        vendor_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
        )
        if vendor_dir not in sys.path:
            sys.path.insert(0, vendor_dir)
        try:
            return importlib.import_module("fitdecode")
        except ImportError as exc:
            raise ImportError(
                "Strava bulk FIT import requires the bundled 'fitdecode' runtime. "
                "Install qfit from a packaged build or install fitdecode in the "
                "QGIS Python environment."
            ) from exc


__all__ = ["load_fitdecode"]
