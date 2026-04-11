#!/usr/bin/env python3
"""Install qfit into a local QGIS plugin profile for development/testing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from package_plugin import _vendor_runtime_dependencies

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN_NAME = "qfit"
EXCLUDED_DIRS = {".git", "dist", "__pycache__"}
EXCLUDED_FILES = {".gitignore"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
DEPLOYMENT_MANIFEST = ".qfit-deploy-manifest.json"


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


def _iter_source_files():
    for path in sorted(ROOT.rglob("*")):
        if should_copy(path):
            yield path


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_manifest() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): _sha256(path) for path in _iter_source_files()}


def _git_revision() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _write_deployment_manifest(destination: pathlib.Path, source_manifest: dict[str, str]) -> None:
    payload = {
        "plugin": PLUGIN_NAME,
        "source_root": str(ROOT),
        "git_revision": _git_revision(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "copied_files": len(source_manifest),
        "files": source_manifest,
    }
    (destination / DEPLOYMENT_MANIFEST).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_install_copy(destination: pathlib.Path, source_manifest: dict[str, str] | None = None) -> None:
    source_manifest = source_manifest or _source_manifest()
    mismatches: list[str] = []

    for relative, expected_hash in source_manifest.items():
        deployed_path = destination / relative
        if not deployed_path.exists():
            mismatches.append(f"missing:{relative}")
            continue
        if _sha256(deployed_path) != expected_hash:
            mismatches.append(f"different:{relative}")

    if not (destination / DEPLOYMENT_MANIFEST).exists():
        mismatches.append(f"missing:{DEPLOYMENT_MANIFEST}")

    if mismatches:
        preview = ", ".join(mismatches[:10])
        raise RuntimeError(f"deployment verification failed ({preview})")


def _staging_destination(destination: pathlib.Path) -> pathlib.Path:
    return destination.parent / f".{PLUGIN_NAME}.staging"


def install_copy(destination: pathlib.Path) -> None:
    source_manifest = _source_manifest()
    staging = _staging_destination(destination)
    if staging.exists() or staging.is_symlink():
        remove_destination(staging)
    staging.mkdir(parents=True, exist_ok=True)

    try:
        for path in _iter_source_files():
            relative = path.relative_to(ROOT)
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

        _vendor_runtime_dependencies(staging)
        _write_deployment_manifest(staging, source_manifest)
        verify_install_copy(staging, source_manifest)

        if destination.exists() or destination.is_symlink():
            remove_destination(destination)
        staging.rename(destination)
        verify_install_copy(destination, source_manifest)
    except Exception:
        if staging.exists() or staging.is_symlink():
            remove_destination(staging)
        raise


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
