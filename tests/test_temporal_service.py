import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.visualization.infrastructure.temporal_service import TemporalService


def _make_field(name):
    field = MagicMock()
    field.name.return_value = name
    return field


def _make_layer(field_names):
    layer = MagicMock()
    layer.fields.return_value = [_make_field(n) for n in field_names]
    props = MagicMock()
    layer.temporalProperties.return_value = props
    return layer, props


class TemporalServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = TemporalService()

    def test_disables_temporal_properties_on_loaded_layers(self):
        tracks, tracks_props = _make_layer(["start_date_local", "start_date"])
        starts, starts_props = _make_layer(["start_date_local", "start_date"])
        points, points_props = _make_layer(["point_timestamp_local", "point_timestamp_utc"])
        atlas, atlas_props = _make_layer(["some_field"])

        result = self.service.apply_temporal_configuration(
            tracks, starts, points, atlas, "Local activity time"
        )

        self.assertEqual(result, "")
        for layer, props in (
            (tracks, tracks_props),
            (starts, starts_props),
            (points, points_props),
            (atlas, atlas_props),
        ):
            props.setIsActive.assert_called_once_with(False)
            props.setMode.assert_not_called()
            props.setStartExpression.assert_not_called()
            props.setEndExpression.assert_not_called()
            layer.triggerRepaint.assert_called_once_with()

    def test_legacy_modes_still_leave_temporal_properties_inactive(self):
        tracks, tracks_props = _make_layer(["start_date_local"])
        points, points_props = _make_layer(["point_timestamp_local"])

        result = self.service.apply_temporal_configuration(
            tracks, None, points, None, "UTC time"
        )

        self.assertEqual(result, "")
        tracks_props.setIsActive.assert_called_once_with(False)
        points_props.setIsActive.assert_called_once_with(False)

    def test_skips_none_layers(self):
        tracks, tracks_props = _make_layer(["start_date_local"])

        result = self.service.apply_temporal_configuration(
            tracks, None, None, None, "Disabled"
        )

        self.assertEqual(result, "")
        tracks_props.setIsActive.assert_called_once_with(False)

    def test_no_temporal_properties_returns_gracefully(self):
        layer = MagicMock()
        layer.temporalProperties.return_value = None

        result = self.service.apply_temporal_configuration(
            layer, None, None, None, "Local activity time"
        )

        self.assertEqual(result, "")
        layer.triggerRepaint.assert_not_called()


if __name__ == "__main__":
    unittest.main()
