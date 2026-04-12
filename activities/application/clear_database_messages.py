from __future__ import annotations


def build_clear_database_confirmation_title() -> str:
    return "Clear database"


def build_clear_database_confirmation_body(output_path: str) -> str:
    return (
        "This will delete the GeoPackage file and remove all qfit layers from QGIS:\n\n"
        f"  {output_path}\n\n"
        "The file cannot be recovered. Continue?"
    )


def build_clear_database_delete_failure_error_title() -> str:
    return "Could not delete database"


def build_clear_database_delete_failure_status() -> str:
    return "Failed to delete the GeoPackage file"


def build_clear_database_load_workflow_error_title() -> str:
    return "No database path"


def build_missing_output_path_error() -> tuple[str, str]:
    return (
        "No database path",
        "Set a GeoPackage output path first.",
    )
