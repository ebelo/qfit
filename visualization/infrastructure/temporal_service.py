from qgis.core import QgsVectorLayerTemporalProperties

from ..application.temporal_config import (
    build_temporal_plan,
    describe_temporal_configuration,
    is_temporal_mode_enabled,
)


class TemporalService:
    """Applies temporal configuration to qfit output layers.

    Reads temporal plans from :mod:`visualization.application.temporal_config`
    and wires them into the QGIS temporal-properties API on each layer.
    """

    LAYER_SPECS = [
        ("activities", "activity_tracks"),
        ("starts", "activity_starts"),
        ("points", "activity_points"),
        ("atlas", "activity_atlas_pages"),
    ]

    def apply_temporal_configuration(self, activities_layer, starts_layer, points_layer, atlas_layer, mode_label):
        layers_by_slot = {
            "activities": activities_layer,
            "starts": starts_layer,
            "points": points_layer,
            "atlas": atlas_layer,
        }
        plans = []
        for slot, layer_key in self.LAYER_SPECS:
            layer = layers_by_slot[slot]
            if layer is None:
                continue
            plan = self._apply_temporal_plan(layer, layer_key, mode_label)
            if plan is not None:
                plans.append(plan)
        return describe_temporal_configuration(plans, mode_label)

    @staticmethod
    def _apply_temporal_plan(layer, layer_key, mode_label):
        props = layer.temporalProperties()
        if props is None:
            return None
        if not is_temporal_mode_enabled(mode_label):
            props.setIsActive(False)
            layer.triggerRepaint()
            return None

        available_fields = [field.name() for field in layer.fields()]
        plan = build_temporal_plan(layer_key, available_fields, mode_label)
        if plan is None:
            props.setIsActive(False)
            layer.triggerRepaint()
            return None

        props.setIsActive(True)
        props.setMode(QgsVectorLayerTemporalProperties.ModeFeatureDateTimeStartAndEndFromExpressions)
        props.setStartExpression(plan.expression)
        props.setEndExpression(plan.expression)
        layer.triggerRepaint()
        return plan
