#!/usr/bin/env python3
"""Install qfit into a local QGIS plugin profile for development/testing."""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import sys

from package_plugin import _vendor_runtime_dependencies

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN_NAME = "qfit"
EXCLUDED_DIRS = {".git", "dist", "__pycache__"}
EXCLUDED_FILES = {".gitignore"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def default_plugins_dir(profile: str) -> pathlib.Path:
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        base = pathlib.Path(xdg_data_home)
    else:
        base = pathlib.Path.home() / ".local" / "share"
    return base / "QGIS" / "QGIS3" / "profiles" / profile / "python" / "plugins"


def should_copy(path: pathlib.Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.name in EXCLUDED_FILES:
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def install_copy(destination: pathlib.Path) -> None:
    if destination.exists() or destination.is_symlink():
        remove_destination(destination)
    destination.mkdir(parents=True, exist_ok=True)

    for path in sorted(ROOT.rglob("*")):
        if not should_copy(path):
            continue
        relative = path.relative_to(ROOT)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    _vendor_runtime_dependencies(destination)


def install_symlink(destination: pathlib.Path) -> None:
    if destination.exists() or destination.is_symlink():
        remove_destination(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(ROOT, target_is_directory=True)


def remove_destination(destination: pathlib.Path) -> None:
    if destination.is_symlink() or destination.is_file():
        destination.unlink()
    elif destination.is_dir():
        shutil.rmtree(destination)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="default", help="QGIS profile name (default: default)")
    parser.add_argument(
        "--plugins-dir",
        type=pathlib.Path,
        default=None,
        help="Override the QGIS plugins directory",
    )
    parser.add_argument(
        "--mode",
        choices=("symlink", "copy"),
        default="copy",
        help="Install mode (default: copy)",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove the installed plugin instead of installing it",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plugins_dir = args.plugins_dir or default_plugins_dir(args.profile)
    destination = plugins_dir / PLUGIN_NAME

    if args.remove:
        if destination.exists() or destination.is_symlink():
            remove_destination(destination)
            print(f"Removed {destination}")
        else:
            print(f"Nothing to remove at {destination}")
        return 0

    installed_mode = args.mode
    if args.mode == "copy":
        try:
            install_copy(destination)
        except RuntimeError as exc:
            install_symlink(destination)
            installed_mode = "symlink"
            print(
                "Warning: copy mode could not vendor runtime-only Python dependencies "
                f"({exc}). Falling back to symlink mode."
            )
    else:
        install_symlink(destination)

    print(f"Installed {PLUGIN_NAME} to {destination} using mode={installed_mode}")
    if installed_mode == "symlink":
        print(
            "Warning: symlink mode does not vendor runtime-only Python dependencies like pypdf. "
            "Use --mode copy or the packaged plugin zip when you need atlas PDF export."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
