from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_VALIDATION_ARTIFACTS_DIRNAME = "validation_artifacts"


def resolve_repo_root() -> Path:
    env_value = os.environ.get("QFIT_VALIDATION_REPO_ROOT")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def ensure_repo_import_path() -> Path:
    repo_root = resolve_repo_root()
    repo_parent = repo_root.parent
    repo_parent_str = str(repo_parent)
    if repo_parent_str not in sys.path:
        sys.path.insert(0, repo_parent_str)
    return repo_root


def resolve_artifacts_dir() -> Path:
    repo_root = resolve_repo_root()
    output_dir = os.environ.get("QFIT_VALIDATION_OUTPUT_DIR")
    if output_dir:
        path = Path(output_dir).expanduser().resolve()
    else:
        path = repo_root / DEFAULT_VALIDATION_ARTIFACTS_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_source_gpkg() -> Path:
    raw_value = os.environ.get("QFIT_VALIDATION_SOURCE_GPKG")
    if not raw_value:
        raise RuntimeError(
            "QFIT_VALIDATION_SOURCE_GPKG is required for this validation scenario."
        )
    path = Path(raw_value).expanduser().resolve()
    if not path.exists():
        raise RuntimeError(f"Validation source GeoPackage not found: {path}")
    return path


def resolve_reference_artifacts_dir() -> Path:
    raw_value = os.environ.get("QFIT_VALIDATION_REFERENCE_ARTIFACTS_DIR")
    if raw_value:
        path = Path(raw_value).expanduser().resolve()
    else:
        path = resolve_repo_root() / DEFAULT_VALIDATION_ARTIFACTS_DIRNAME
    if not path.exists():
        raise RuntimeError(f"Validation reference artifacts directory not found: {path}")
    return path


def resolve_reference_artifact(filename: str) -> Path:
    path = resolve_reference_artifacts_dir() / filename
    if not path.exists():
        raise RuntimeError(f"Validation reference artifact not found: {path}")
    return path
