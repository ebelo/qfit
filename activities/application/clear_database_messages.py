from __future__ import annotations


def build_missing_output_path_error() -> tuple[str, str]:
    return (
        "No database path",
        "Set a GeoPackage output path first.",
    )
