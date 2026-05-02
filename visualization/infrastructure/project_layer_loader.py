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
    ROUTE_LAYERS = [
        ("route_tracks", "qfit saved routes"),
        ("route_points", "qfit route profile samples"),
    ]
    ROUTE_GROUP_NAME = "qfit routes"

    def load_output_layers(self, gpkg_path):
        activities_layer = self._load_first_available(gpkg_path, self.ACTIVITIES_CANDIDATES)
        optional_layers = [
            self._load_optional_layer(gpkg_path, layer_name, display_name)
            for layer_name, display_name in self.OPTIONAL_LAYERS
        ]
        return (activities_layer, *optional_layers)

    def load_route_layers(self, gpkg_path):
        """Load saved-route catalog layers into a dedicated project group."""
        return tuple(
            self._load_optional_layer(gpkg_path, layer_name, display_name, group_name=self.ROUTE_GROUP_NAME)
            for layer_name, display_name in self.ROUTE_LAYERS
        )

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

    def _load_optional_layer(self, gpkg_path, layer_name, display_name, group_name=None):
        try:
            return self._load_layer(gpkg_path, layer_name, display_name, group_name=group_name)
        except RuntimeError:
            return None

    def _load_layer(self, gpkg_path, layer_name, display_name, group_name=None):
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
        if group_name:
            project.addMapLayer(layer, False)
            self._add_layer_to_group(project, layer, group_name)
        else:
            project.addMapLayer(layer, layer_name not in self.HIDDEN_LAYER_NAMES)
        return layer

    def _add_layer_to_group(self, project, layer, group_name):
        root = project.layerTreeRoot()
        group = root.findGroup(group_name) if hasattr(root, "findGroup") else None
        if group is None:
            group = root.addGroup(group_name)
        group.addLayer(layer)
