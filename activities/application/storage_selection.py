from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import Callable


StorageIntent = str

STORAGE_INTENT_NEW = "new"
STORAGE_INTENT_EXISTING = "existing"
STORAGE_INTENT_INVALID = "invalid"

NEW_DATABASE_STATUS = "New database will be created"
EXISTING_QFIT_DATABASE_STATUS = "Existing qfit database selected"
NON_QFIT_GEOPACKAGE_STATUS = "Existing GeoPackage selected; qfit schema not found"
ROUTE_ONLY_QFIT_DATABASE_STATUS = (
    "Existing qfit database selected; store activities to add map layers"
)
PATH_CHANGED_STATUS = "Path changed; load stored layers to refresh the map"
INVALID_DATABASE_PATH_STATUS = "Invalid database path"

QFIT_ACTIVITY_SCHEMA_TABLE = "activity_registry"
QFIT_ROUTE_SCHEMA_TABLE = "route_registry"


@dataclass(frozen=True)
class StorageSelectionResult:
    """Validated GeoPackage storage selection rendered by the dock UI."""

    normalized_path: str
    intent: StorageIntent
    can_load: bool
    can_store: bool
    status_text: str
    validation_reason: str = ""

    @property
    def is_valid(self) -> bool:
        return self.intent != STORAGE_INTENT_INVALID


@dataclass(frozen=True)
class StoragePathProbe:
    """Filesystem and schema probes for storage-selection resolution."""

    path_exists: Callable[[str], bool] = os.path.exists
    is_file: Callable[[str], bool] = os.path.isfile
    is_dir: Callable[[str], bool] = os.path.isdir
    is_readable: Callable[[str], bool] = lambda path: os.access(path, os.R_OK)
    has_qfit_schema: Callable[[str], bool] | None = None
    has_qfit_store_schema: Callable[[str], bool] | None = None


def normalize_storage_path(raw_path: str) -> str:
    """Normalize committed storage text without mutating mid-edit input."""

    value = (raw_path or "").strip()
    if not value:
        return ""
    expanded = os.path.expanduser(value)
    _root, extension = os.path.splitext(expanded)
    if not extension:
        expanded = "{path}.gpkg".format(path=expanded)
    return os.path.normpath(expanded)


def default_has_qfit_schema(path: str) -> bool:
    """Return whether an existing GeoPackage has qfit's activity schema."""

    return _has_any_table(path, (QFIT_ACTIVITY_SCHEMA_TABLE,))


def default_has_qfit_store_schema(path: str) -> bool:
    """Return whether an existing GeoPackage can be updated by qfit."""

    return _has_any_table(
        path,
        (QFIT_ACTIVITY_SCHEMA_TABLE, QFIT_ROUTE_SCHEMA_TABLE),
    )


def _has_any_table(path: str, table_names: tuple[str, ...]) -> bool:
    placeholders = ", ".join("?" for _table_name in table_names)

    try:
        with sqlite3.connect(path) as connection:
            row = connection.execute(
                f"""
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name IN ({placeholders})
                LIMIT 1
                """,
                table_names,
            ).fetchone()
    except (OSError, sqlite3.DatabaseError):
        return False
    return row is not None


def resolve_storage_selection(
    raw_path: str,
    *,
    probe: StoragePathProbe | None = None,
    loaded_dataset_path: str | None = None,
) -> StorageSelectionResult:
    """Classify a committed GeoPackage path for create/load/switch workflows."""

    probe = probe or StoragePathProbe()
    normalized_path = normalize_storage_path(raw_path)

    initial_result = _resolve_initial_path_state(normalized_path, probe)
    if initial_result is not None:
        return initial_result

    existing_path_error = _existing_path_error(normalized_path, probe)
    if existing_path_error is not None:
        return existing_path_error

    return _resolve_existing_schema_state(
        normalized_path,
        probe,
        loaded_dataset_path=loaded_dataset_path,
    )


def _resolve_initial_path_state(
    normalized_path: str,
    probe: StoragePathProbe,
) -> StorageSelectionResult | None:
    if not normalized_path:
        return _invalid_result("", "Choose a GeoPackage path first.")

    if os.path.splitext(normalized_path)[1].lower() != ".gpkg":
        return _invalid_result(normalized_path, "Use a .gpkg GeoPackage file.")

    parent_directory = os.path.dirname(normalized_path) or "."
    if not probe.path_exists(parent_directory) or not probe.is_dir(parent_directory):
        return _invalid_result(
            normalized_path,
            "The parent directory does not exist: {path}".format(
                path=parent_directory,
            ),
        )

    if probe.path_exists(normalized_path):
        return None

    return StorageSelectionResult(
        normalized_path=normalized_path,
        intent=STORAGE_INTENT_NEW,
        can_load=False,
        can_store=True,
        status_text=NEW_DATABASE_STATUS,
    )


def _existing_path_error(
    normalized_path: str,
    probe: StoragePathProbe,
) -> StorageSelectionResult | None:
    if not probe.is_file(normalized_path):
        return _invalid_result(normalized_path, "The selected path is not a file.")

    if probe.is_readable(normalized_path):
        return None

    return _invalid_result(
        normalized_path,
        "The selected GeoPackage is not readable.",
    )


def _resolve_existing_schema_state(
    normalized_path: str,
    probe: StoragePathProbe,
    *,
    loaded_dataset_path: str | None,
) -> StorageSelectionResult:

    has_qfit_schema = probe.has_qfit_schema or default_has_qfit_schema
    has_qfit_store_schema = (
        probe.has_qfit_store_schema or default_has_qfit_store_schema
    )
    if not has_qfit_schema(normalized_path):
        if has_qfit_store_schema(normalized_path):
            return StorageSelectionResult(
                normalized_path=normalized_path,
                intent=STORAGE_INTENT_EXISTING,
                can_load=False,
                can_store=True,
                status_text=ROUTE_ONLY_QFIT_DATABASE_STATUS,
                validation_reason=(
                    "The selected qfit database does not contain stored "
                    "activity layers yet. Store activities first."
                ),
            )
        return StorageSelectionResult(
            normalized_path=normalized_path,
            intent=STORAGE_INTENT_EXISTING,
            can_load=False,
            can_store=False,
            status_text=NON_QFIT_GEOPACKAGE_STATUS,
            validation_reason=(
                "The selected GeoPackage does not contain qfit's activity "
                "schema. Choose a qfit database or a new file path."
            ),
        )

    loaded_dataset_path = normalize_storage_path(loaded_dataset_path or "")
    status = EXISTING_QFIT_DATABASE_STATUS
    if loaded_dataset_path and loaded_dataset_path != normalized_path:
        status = PATH_CHANGED_STATUS

    return StorageSelectionResult(
        normalized_path=normalized_path,
        intent=STORAGE_INTENT_EXISTING,
        can_load=True,
        can_store=True,
        status_text=status,
    )


def _invalid_result(path: str, reason: str) -> StorageSelectionResult:
    return StorageSelectionResult(
        normalized_path=path,
        intent=STORAGE_INTENT_INVALID,
        can_load=False,
        can_store=False,
        status_text=INVALID_DATABASE_PATH_STATUS,
        validation_reason=reason,
    )
