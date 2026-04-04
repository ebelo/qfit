import importlib
import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    _REAL_QGIS_PRESENT = importlib.util.find_spec("qgis") is not None
except ValueError:
    _REAL_QGIS_PRESENT = any(
        os.path.isdir(os.path.join(p, "qgis")) for p in sys.path if p
    )

try:
    from qfit.visualization.infrastructure.temporal_service import TemporalService

    QGIS_AVAILABLE = True
    QGIS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    TemporalService = None
    QGIS_AVAILABLE = False
    QGIS_IMPORT_ERROR = exc

SKIP_REAL = f"QGIS not available: {QGIS_IMPORT_ERROR}" if not QGIS_AVAILABLE else ""

_def_service_cls = None


def _load_service_with_mock_qgis():
    qstub = MagicMock()
    qgis_modules = ["qgis", "qgis.core"]

    saved_qgis = {name: sys.modules.get(name) for name in qgis_modules}
    saved_module = sys.modules.get("qfit.visualization.infrastructure.temporal_service")

    for name in qgis_modules:
        sys.modules[name] = qstub
    sys.modules.pop("qfit.visualization.infrastructure.temporal_service", None)

    try:
        module = importlib.import_module("qfit.visualization.infrastructure.temporal_service")
        return module.TemporalService, module
    except Exception:  # pragma: no cover
        return None, None
    finally:
        for name, original in saved_qgis.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        if saved_module is None:
            sys.modules.pop("qfit.visualization.infrastructure.temporal_service", None)
        else:
            sys.modules["qfit.visualization.infrastructure.temporal_service"] = saved_module


if not QGIS_AVAILABLE:
    _def_service_cls, _ = _load_service_with_mock_qgis()

SKIP_MOCK = "QGIS is installed — real-QGIS suite provides coverage" if QGIS_AVAILABLE else ""
SKIP_MOCK_LOAD = (
    "Could not load TemporalService with mock QGIS"
    if (_def_service_cls is None and not _REAL_QGIS_PRESENT)
    else ""
)


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


@unittest.skipUnless(QGIS_AVAILABLE, SKIP_REAL)
class TemporalServiceRealTests(unittest.TestCase):
    """Tests that run when real QGIS bindings are available."""

    def setUp(self):
        self.service = TemporalService()

    def test_applies_local_time_to_tracks_and_points(self):
        tracks, tracks_props = _make_layer(["start_date_local", "start_date"])
        starts, starts_props = _make_layer(["start_date_local", "start_date"])
        points, points_props = _make_layer(["point_timestamp_local", "point_timestamp_utc"])
        atlas, atlas_props = _make_layer(["some_field"])

        result = self.service.apply_temporal_configuration(
            tracks, starts, points, atlas, "Local activity time"
        )

        tracks_props.setIsActive.assert_called_with(True)
        tracks_props.setStartExpression.assert_called_with('to_datetime("start_date_local")')
        starts_props.setIsActive.assert_called_with(True)
        points_props.setIsActive.assert_called_with(True)
        points_props.setStartExpression.assert_called_with('to_datetime("point_timestamp_local")')
        # atlas has no temporal candidates, should be deactivated
        atlas_props.setIsActive.assert_called_with(False)
        self.assertIn("Temporal playback wired", result)

    def test_disabled_mode_deactivates_all_layers(self):
        tracks, tracks_props = _make_layer(["start_date_local"])
        points, points_props = _make_layer(["point_timestamp_local"])

        result = self.service.apply_temporal_configuration(
            tracks, None, points, None, "Disabled"
        )

        tracks_props.setIsActive.assert_called_with(False)
        points_props.setIsActive.assert_called_with(False)
        self.assertIn("disabled", result.lower())

    def test_skips_none_layers(self):
        tracks, tracks_props = _make_layer(["start_date_local"])

        result = self.service.apply_temporal_configuration(
            tracks, None, None, None, "Local activity time"
        )

        tracks_props.setIsActive.assert_called_with(True)
        self.assertIn("Temporal playback wired", result)

    def test_utc_mode_prefers_utc_fields(self):
        tracks, tracks_props = _make_layer(["start_date_local", "start_date"])

        self.service.apply_temporal_configuration(
            tracks, None, None, None, "UTC time"
        )

        tracks_props.setStartExpression.assert_called_with('to_datetime("start_date")')

    def test_no_temporal_properties_returns_gracefully(self):
        layer = MagicMock()
        layer.temporalProperties.return_value = None

        result = self.service.apply_temporal_configuration(
            layer, None, None, None, "Local activity time"
        )

        self.assertIn("no timestamp fields", result.lower())

    def test_triggers_repaint_on_each_configured_layer(self):
        tracks, _ = _make_layer(["start_date_local"])
        points, _ = _make_layer(["point_timestamp_local"])

        self.service.apply_temporal_configuration(tracks, None, points, None, "Local activity time")

        tracks.triggerRepaint.assert_called()
        points.triggerRepaint.assert_called()


@unittest.skipIf(QGIS_AVAILABLE, SKIP_MOCK)
@unittest.skipIf(_def_service_cls is None, SKIP_MOCK_LOAD)
class TemporalServiceMockTests(unittest.TestCase):
    """Tests that run with mock QGIS when real bindings are not available."""

    def setUp(self):
        self.service = _def_service_cls()

    def test_applies_temporal_plan_to_available_layers(self):
        tracks, tracks_props = _make_layer(["start_date_local", "start_date"])
        points, points_props = _make_layer(["point_timestamp_utc"])

        result = self.service.apply_temporal_configuration(
            tracks, None, points, None, "UTC time"
        )

        tracks_props.setIsActive.assert_called_with(True)
        points_props.setIsActive.assert_called_with(True)
        self.assertIn("Temporal playback wired", result)

    def test_disabled_mode_deactivates_layers(self):
        tracks, tracks_props = _make_layer(["start_date_local"])

        result = self.service.apply_temporal_configuration(
            tracks, None, None, None, "Disabled"
        )

        tracks_props.setIsActive.assert_called_with(False)
        self.assertIn("disabled", result.lower())

    def test_skips_none_layers_and_handles_no_candidates(self):
        atlas, atlas_props = _make_layer(["unrelated_field"])

        result = self.service.apply_temporal_configuration(
            None, None, None, atlas, "Local activity time"
        )

        atlas_props.setIsActive.assert_called_with(False)
        self.assertIn("no timestamp fields", result.lower())


if __name__ == "__main__":
    unittest.main()
