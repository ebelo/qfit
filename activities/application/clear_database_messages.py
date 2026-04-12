from __future__ import annotations


def build_clear_database_delete_failure_status() -> str:
    return "Failed to delete the GeoPackage file"


def build_missing_output_path_error() -> tuple[str, str]:
    return (
        "No database path",
        "Set a GeoPackage output path first.",
    )
