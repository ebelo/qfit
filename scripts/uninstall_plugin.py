#!/usr/bin/env python3
"""Backward-compatible helper to remove qfit from a local QGIS plugin profile."""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = ROOT / "scripts" / "install_plugin.py"


def main() -> int:
    command = [sys.executable, str(INSTALL_SCRIPT), "--remove", *sys.argv[1:]]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
