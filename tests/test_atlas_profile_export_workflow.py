import unittest
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401


class _FakeQgsTask:
    CanCancel = 1

    def __init__(self, description="", flags=0):
        self._cancelled = False

    def isCanceled(self):
        return self._cancelled

    def setProgress(self, value):  # noqa: N802
        pass


def _install_qgis_stub():
    qgis_core = ModuleType("qgis.core")
    qgis_core.QgsTask = _FakeQgsTask
    qgis_core.QgsProject = MagicMock()
    layout_instance = MagicMock()
    layout_instance.pageCollection.return_value.pageCount.return_value = 1
    layout_instance.pageCollection.return_value.page.return_value = MagicMock()
    layout_cls = MagicMock(return_value=layout_instance)
    qgis_core.QgsPrintLayout = layout_cls
    qgis_core.QgsLayoutItemMap = MagicMock()
    qgis_core.QgsLayoutItemMap.Auto = 1
    qgis_core.QgsLayoutItemMap.Fixed = 0
    picture_cls = MagicMock()
    picture_cls.Zoom = 0
    qgis_core.QgsLayoutItemPicture = picture_cls
    qgis_core.QgsLayoutPoint = MagicMock()
    qgis_core.QgsLayoutSize = MagicMock()
    qgis_core.QgsLayoutItemLabel = MagicMock()
    qgis_core.QgsUnitTypes = MagicMock()
    qgis_core.QgsUnitTypes.LayoutMillimeters = 0
    qgis_core.QgsUnitTypes.RenderMillimeters = 1
    qgis_core.QgsGeometry = MagicMock()
    qgis_core.QgsRectangle = MagicMock(return_value=MagicMock())
    qgis_core.QgsCoordinateReferenceSystem = MagicMock(return_value=MagicMock())
    qgis_core.QgsLayoutItemElevationProfile = MagicMock()
    qgis_core.QgsProfileRequest = MagicMock()
    qgis_core.QgsProfilePlotRenderer = MagicMock()
    qgis_core.QgsLayoutExporter = MagicMock()
    qgis_core.QgsLayoutExporter.Success = 0
    qgis_core.QgsAtlasComposition = MagicMock()
    qgis_core.QgsHeatmapRenderer = MagicMock()
    qgis_core.QgsStyle = MagicMock()
    qgis_core.QgsGradientColorRamp = MagicMock()
    qgis_core.QgsWkbTypes = MagicMock()
    qgis_core.QgsFillSymbol = MagicMock()
    qgis_core.QgsLineSymbol = MagicMock()

    qgis_pyt = ModuleType("qgis.PyQt")
    qgis_pyt_core = ModuleType("qgis.PyQt.QtCore")
    qgis_pyt_core.Qt = MagicMock()
    qgis_pyt_core.Qt.AlignRight = 2
    qgis_pyt_core.Qt.AlignLeft = 1
    qgis_pyt_core.Qt.AlignVCenter = 32
    qgis_pyt_gui = ModuleType("qgis.PyQt.QtGui")
    qgis_pyt_gui.QColor = MagicMock(return_value=MagicMock())
    qgis_pyt_gui.QFont = MagicMock(return_value=MagicMock())

    qgis_mod = ModuleType("qgis")
    qgis_mod.core = qgis_core

    sys.modules.setdefault("qgis", qgis_mod)
    sys.modules["qgis.core"] = qgis_core
    sys.modules.setdefault("qgis.PyQt", qgis_pyt)
    sys.modules["qgis.PyQt.QtCore"] = qgis_pyt_core
    sys.modules["qgis.PyQt.QtGui"] = qgis_pyt_gui


_install_qgis_stub()

from qfit.atlas.profile_export_workflow import AtlasPageProfileWorkflow, PageProfilePayload


class AtlasPageProfileWorkflowTests(unittest.TestCase):
    def test_render_page_profile_svg_uses_configured_dimensions(self):
        workflow = AtlasPageProfileWorkflow(
            profile_chart_width_mm=123.0,
            profile_chart_height_mm=45.0,
        )

        with patch("qfit.atlas.profile_export_workflow._render_page_profile_svg", return_value="/tmp/profile.svg") as render_svg:
            result = workflow.render_page_profile_svg([(0.0, 10.0), (1.0, 20.0)], output_path="/tmp/out.pdf")

        self.assertEqual(result, "/tmp/profile.svg")
        render_svg.assert_called_once_with(
            [(0.0, 10.0), (1.0, 20.0)],
            output_path="/tmp/out.pdf",
            profile_chart_width_mm=123.0,
            profile_chart_height_mm=45.0,
        )

    def test_build_page_profile_payload_delegates_to_helper(self):
        workflow = AtlasPageProfileWorkflow(
            profile_chart_width_mm=123.0,
            profile_chart_height_mm=45.0,
        )
        expected = PageProfilePayload(feature_geometry="geom", feature="feat", crs_auth_id="EPSG:3857")

        with patch("qfit.atlas.profile_export_workflow._build_page_profile_payload", return_value=expected) as build_payload:
            result = workflow.build_page_profile_payload("feat", [("layer", "subset")], profile_altitude_lookup="lookup")

        self.assertIs(result, expected)
        build_payload.assert_called_once_with(
            "feat",
            [("layer", "subset")],
            profile_altitude_lookup="lookup",
        )

    def test_apply_page_profile_payload_delegates_to_helper_with_configured_render_fn(self):
        workflow = AtlasPageProfileWorkflow(
            profile_chart_width_mm=123.0,
            profile_chart_height_mm=45.0,
            default_profile_crs_auth_id="EPSG:2056",
        )
        adapter = MagicMock(name="adapter")
        payload = PageProfilePayload(feature_geometry=None)

        with patch("qfit.atlas.profile_export_workflow._apply_page_profile_payload") as apply_payload:
            workflow.apply_page_profile_payload(
                adapter,
                payload,
                output_path="/tmp/out.pdf",
                profile_temp_files=["/tmp/one.svg"],
            )

        self.assertEqual(apply_payload.call_count, 1)
        args, kwargs = apply_payload.call_args
        self.assertEqual(args, (adapter, payload))
        self.assertEqual(kwargs["output_path"], "/tmp/out.pdf")
        self.assertEqual(kwargs["profile_temp_files"], ["/tmp/one.svg"])
        self.assertEqual(kwargs["default_profile_crs_auth_id"], "EPSG:2056")
        self.assertEqual(kwargs["render_native_profile_image_fn"].__name__, "_render_native_profile_image")
        self.assertTrue(callable(kwargs["render_page_profile_svg_fn"]))


if __name__ == "__main__":
    unittest.main()
