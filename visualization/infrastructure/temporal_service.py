class TemporalService:
    """Keep qfit output layers out of QGIS temporal playback by default.

    Date/time filtering is owned by qfit's Map tab filters. Loaded layers should
    therefore not activate QGIS temporal properties and expose a second temporal
    control path through the QGIS temporal controller or layer tree.
    """

    LAYER_SLOTS = ("activities", "starts", "points", "atlas")

    def apply_temporal_configuration(self, activities_layer, starts_layer, points_layer, atlas_layer, mode_label):
        _ = mode_label
        layers_by_slot = {
            "activities": activities_layer,
            "starts": starts_layer,
            "points": points_layer,
            "atlas": atlas_layer,
        }
        for slot in self.LAYER_SLOTS:
            layer = layers_by_slot[slot]
            if layer is None:
                continue
            self._disable_temporal_properties(layer)
        return ""

    @staticmethod
    def _disable_temporal_properties(layer):
        props = layer.temporalProperties()
        if props is None:
            return
        props.setIsActive(False)
        layer.triggerRepaint()
