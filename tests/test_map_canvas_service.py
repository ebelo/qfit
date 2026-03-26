import importlib
import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    _REAL_QGIS_PRESENT = importlib.util.find_spec("qgis") is not None
except ValueError:
    _REAL_QGIS_PRESENT = any(
        os.path.isdir(os.path.join(p, "qgis")) for p in sys.path if p
    )

try:
    from qfit.map_canvas_service import MapCanvasService, WORKING_CRS

    QGIS_AVAILABLE = True
    QGIS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    MapCanvasService = None
    QGIS_AVAILABLE = False
    QGIS_IMPORT_ERROR = exc

SKIP_REAL = f"QGIS not available: {QGIS_IMPORT_ERROR}" if not QGIS_AVAILABLE else ""

_def_service_cls = None
_def_service_module = None


def _load_service_with_mock_qgis():
    qstub = MagicMock()
    qgis_modules = ["qgis", "qgis.core"]

    saved_qgis = {name: sys.modules.get(name) for name in qgis_modules}
    saved_module = sys.modules.get("qfit.map_canvas_service")

    for name in qgis_modules:
        sys.modules[name] = qstub

    sys.modules.pop("qfit.map_canvas_service", None)

    try:
        module = importlib.import_module("qfit.map_canvas_service")
        return module.MapCanvasService, module
    except Exception:  # pragma: no cover
        return None, None
    finally:
        for name, original in saved_qgis.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        if saved_module is None:
            sys.modules.pop("qfit.map_canvas_service", None)
        else:
            sys.modules["qfit.map_canvas_service"] = saved_module


if not QGIS_AVAILABLE:
    _def_service_cls, _def_service_module = _load_service_with_mock_qgis()

SKIP_MOCK = "QGIS is installed — real-QGIS suite provides coverage" if QGIS_AVAILABLE else ""
SKIP_MOCK_LOAD = (
    "Could not load MapCanvasService with mock QGIS"
    if (_def_service_cls is None and not _REAL_QGIS_PRESENT)
    else ""
)


def _make_iface(canvas=None):
    iface = MagicMock()
    if canvas is None:
        canvas = MagicMock()
    iface.mapCanvas.return_value = canvas
    return iface, canvas


def _make_layer(extent_vals=None, valid=True):
    """Create a mock layer with an optional extent rectangle.

    *extent_vals* should be ``(xmin, ymin, xmax, ymax)`` or ``None`` for an
    empty extent.
    """
    layer = MagicMock()
    layer.isValid.return_value = valid
    if QGIS_AVAILABLE and extent_vals is not None:
        from qgis.core import QgsRectangle

        extent = QgsRectangle(*extent_vals)
    elif QGIS_AVAILABLE:
        from qgis.core import QgsRectangle

        extent = QgsRectangle()
    else:
        extent = MagicMock()
        if extent_vals is None:
            extent.isEmpty.return_value = True
        else:
            extent.isEmpty.return_value = False
    layer.extent.return_value = extent
    return layer, extent


# ---------------------------------------------------------------------------
# Real-QGIS tests
# ---------------------------------------------------------------------------


@unittest.skipUnless(QGIS_AVAILABLE, SKIP_REAL)
class MapCanvasServiceRealTests(unittest.TestCase):
    """Tests that run when real QGIS bindings are available."""

    def setUp(self):
        self._bg = MagicMock()
        self.service = MapCanvasService(self._bg)

    # -- ensure_working_crs -------------------------------------------------

    @patch("qfit.map_canvas_service.QgsProject")
    def test_ensure_working_crs_sets_project_and_canvas_crs(self, mock_project_cls):
        project = MagicMock()
        project.crs.return_value = MagicMock(isValid=MagicMock(return_value=False))
        mock_project_cls.instance.return_value = project

        iface, canvas = _make_iface()
        canvas.extent.return_value = MagicMock(isEmpty=MagicMock(return_value=True))

        self.service.ensure_working_crs(iface)

        project.setCrs.assert_called_once()
        canvas.setDestinationCrs.assert_called_once()

    @patch("qfit.map_canvas_service.QgsCoordinateTransform")
    @patch("qfit.map_canvas_service.QgsProject")
    def test_ensure_working_crs_preserves_extent_on_crs_change(
        self, mock_project_cls, mock_transform_cls
    ):
        from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle

        project = MagicMock()
        old_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        project.crs.return_value = old_crs
        mock_project_cls.instance.return_value = project

        transformed_extent = QgsRectangle(0, 0, 1, 1)
        transform = MagicMock()
        transform.transformBoundingBox.return_value = transformed_extent
        mock_transform_cls.return_value = transform

        iface, canvas = _make_iface()
        canvas.extent.return_value = QgsRectangle(6, 46, 7, 47)

        self.service.ensure_working_crs(iface)

        project.setCrs.assert_called_once()
        canvas.setDestinationCrs.assert_called_once()
        canvas.setExtent.assert_called_once_with(transformed_extent)

    @patch("qfit.map_canvas_service.QgsProject")
    def test_ensure_working_crs_noop_when_iface_is_none(self, mock_project_cls):
        project = MagicMock()
        mock_project_cls.instance.return_value = project

        self.service.ensure_working_crs(None)

        project.setCrs.assert_called_once()

    # -- zoom_to_layers -----------------------------------------------------

    def test_zoom_to_layers_sets_canvas_extent(self):
        iface, canvas = _make_iface()
        layer, extent = _make_layer((0, 0, 1, 1))
        self._bg.snap_extent_to_background_tile_zoom.side_effect = lambda e, c: e

        self.service.zoom_to_layers(iface, [layer])

        canvas.setExtent.assert_called_once()
        canvas.refresh.assert_called_once()

    def test_zoom_to_layers_skips_none_and_invalid_layers(self):
        iface, canvas = _make_iface()
        invalid_layer, _ = _make_layer(valid=False)
        valid_layer, _ = _make_layer((0, 0, 1, 1))
        self._bg.snap_extent_to_background_tile_zoom.side_effect = lambda e, c: e

        self.service.zoom_to_layers(iface, [None, invalid_layer, valid_layer])

        canvas.setExtent.assert_called_once()

    def test_zoom_to_layers_noop_when_all_extents_empty(self):
        iface, canvas = _make_iface()
        layer, _ = _make_layer()  # empty extent

        self.service.zoom_to_layers(iface, [layer])

        canvas.setExtent.assert_not_called()

    def test_zoom_to_layers_noop_when_no_canvas(self):
        iface = MagicMock()
        iface.mapCanvas.return_value = None
        layer, _ = _make_layer((0, 0, 1, 1))

        self.service.zoom_to_layers(iface, [layer])

    def test_zoom_to_layers_delegates_snap_to_background_service(self):
        iface, canvas = _make_iface()
        layer, _ = _make_layer((0, 0, 1, 1))
        snapped = MagicMock()
        self._bg.snap_extent_to_background_tile_zoom.return_value = snapped

        self.service.zoom_to_layers(iface, [layer])

        self._bg.snap_extent_to_background_tile_zoom.assert_called_once()
        canvas.setExtent.assert_called_once_with(snapped)


# ---------------------------------------------------------------------------
# Mock-QGIS tests (for CI without real QGIS)
# ---------------------------------------------------------------------------


@unittest.skipIf(QGIS_AVAILABLE, SKIP_MOCK)
@unittest.skipIf(_def_service_cls is None, SKIP_MOCK_LOAD)
class MapCanvasServiceMockTests(unittest.TestCase):
    """Tests that run with mock QGIS when real bindings are not available."""

    def setUp(self):
        self._bg = MagicMock()
        if _def_service_module is not None:
            _def_service_module.QgsRectangle.side_effect = lambda rect=None: rect
        self.service = _def_service_cls(self._bg)

    def test_zoom_to_layers_sets_canvas_extent(self):
        iface, canvas = _make_iface()
        layer, _ = _make_layer((0, 0, 1, 1))
        self._bg.snap_extent_to_background_tile_zoom.side_effect = lambda e, c: e

        self.service.zoom_to_layers(iface, [layer])

        canvas.setExtent.assert_called_once()
        canvas.refresh.assert_called_once()

    def test_zoom_to_layers_noop_when_all_extents_empty(self):
        iface, canvas = _make_iface()
        layer, _ = _make_layer()

        self.service.zoom_to_layers(iface, [layer])

        canvas.setExtent.assert_not_called()

    def test_zoom_skips_none_layers(self):
        iface, canvas = _make_iface()
        valid_layer, _ = _make_layer((0, 0, 1, 1))
        self._bg.snap_extent_to_background_tile_zoom.side_effect = lambda e, c: e

        self.service.zoom_to_layers(iface, [None, valid_layer])

        canvas.setExtent.assert_called_once()


if __name__ == "__main__":
    unittest.main()
