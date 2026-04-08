import os

DEFAULT_FREQUENT_STARTING_POINTS_LAYER_NAME = "qfit frequent starting points"


def _frequent_starting_points_layer_name() -> str:
    try:
        from ...analysis.infrastructure.frequent_start_points_layer import (
            FREQUENT_STARTING_POINTS_LAYER_NAME,
        )
    except Exception:
        return DEFAULT_FREQUENT_STARTING_POINTS_LAYER_NAME
    return FREQUENT_STARTING_POINTS_LAYER_NAME


def _default_project():
    from qgis.core import QgsProject

    return QgsProject.instance()


class ProjectHygieneService:
    """Apply small qfit-owned cleanup rules to the current QGIS project."""

    _QFIT_LAYER_NAMES = {
        "qfit activities",
        "qfit activity starts",
        "qfit activity points",
        "qfit atlas pages",
        _frequent_starting_points_layer_name(),
    }

    def __init__(self, *, project=None, path_exists=None):
        self._project = project or _default_project()
        self._path_exists = path_exists or os.path.exists

    def remove_stale_qfit_layers(self) -> None:
        """Remove qfit file-backed layers whose GeoPackage no longer exists."""
        to_remove = []
        for layer in self._project.mapLayers().values():
            if layer.name() not in self._QFIT_LAYER_NAMES:
                continue

            source = (layer.source() or "").strip()
            normalized_source = source.lower()
            is_file_backed_qfit_layer = (
                "|layername=" in normalized_source or normalized_source.endswith(".gpkg")
            )
            if not is_file_backed_qfit_layer:
                continue

            gpkg_path = source.split("|")[0].strip()
            if gpkg_path and not self._path_exists(gpkg_path):
                to_remove.append(layer.id())

        for layer_id in to_remove:
            self._project.removeMapLayer(layer_id)
