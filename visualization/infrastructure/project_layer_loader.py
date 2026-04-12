from qgis.core import QgsCoordinateReferenceSystem, QgsProject, QgsVectorLayer


class ProjectLayerLoader:
    """Loads and replaces qfit output layers in the current QGIS project."""

    DEFAULT_LAYER_CRS = "EPSG:4326"
    LAYER_FALLBACK_CRS = {
        "activity_atlas_pages": "EPSG:3857",
    }
    HIDDEN_LAYER_NAMES = {"activity_atlas_pages"}

    ACTIVITIES_CANDIDATES = [
        ("activity_tracks", "qfit activities"),
        ("activities", "qfit activities"),
    ]
    OPTIONAL_LAYERS = [
        ("activity_starts", "qfit activity starts"),
        ("activity_points", "qfit activity points"),
        ("activity_atlas_pages", "qfit atlas pages"),
    ]

    def load_output_layers(self, gpkg_path):
        activities_layer = self._load_first_available(gpkg_path, self.ACTIVITIES_CANDIDATES)
        optional_layers = [
            self._load_optional_layer(gpkg_path, layer_name, display_name)
            for layer_name, display_name in self.OPTIONAL_LAYERS
        ]
        return (activities_layer, *optional_layers)

    def _load_first_available(self, gpkg_path, candidates):
        last_error = None
        for layer_name, display_name in candidates:
            try:
                return self._load_layer(gpkg_path, layer_name, display_name)
            except RuntimeError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        return None

    def _load_optional_layer(self, gpkg_path, layer_name, display_name):
        try:
            return self._load_layer(gpkg_path, layer_name, display_name)
        except RuntimeError:
            return None

    def _load_layer(self, gpkg_path, layer_name, display_name):
        uri = f"{gpkg_path}|layername={layer_name}"
        layer = QgsVectorLayer(uri, display_name, "ogr")
        if not layer.isValid():
            raise RuntimeError(f"Could not load layer '{layer_name}' from {gpkg_path}")

        layer_crs = layer.crs()
        if layer_crs is None or not layer_crs.isValid():
            fallback_authid = self.LAYER_FALLBACK_CRS.get(layer_name, self.DEFAULT_LAYER_CRS)
            layer.setCrs(QgsCoordinateReferenceSystem(fallback_authid))

        project = QgsProject.instance()
        for old_layer in project.mapLayersByName(display_name):
            project.removeMapLayer(old_layer.id())
        project.addMapLayer(layer, layer_name not in self.HIDDEN_LAYER_NAMES)
        return layer
