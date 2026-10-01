import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests import _path  # noqa: F401
from qfit.analysis.application.route_heatmap import RouteHeatmapArtifact
from qfit.analysis.infrastructure.route_heatmap_layer import create_route_heatmap_layer


class RouteHeatmapLayerTests(unittest.TestCase):
    def test_fixed_global_red_ramp_and_invalid_raster(self):
        layer, shader_function, shader, renderer = Mock(), Mock(), Mock(), Mock()
        ramp_class = Mock(return_value=shader_function)
        ramp_class.ColorRampItem = lambda value, color, label: (value, color, label)
        core = SimpleNamespace(QgsRasterLayer=Mock(return_value=layer), QgsColorRampShader=ramp_class,
                               QgsRasterShader=Mock(return_value=shader), QgsBilinearRasterResampler=Mock(),
                               QgsSingleBandPseudoColorRenderer=Mock(return_value=renderer))
        artifact = RouteHeatmapArtifact('cache/heatmap.vrt', 'key', 7, 'EPSG:32632', 12)
        with patch.dict('sys.modules', {'qgis.core': core, 'qgis.PyQt.QtGui': SimpleNamespace(QColor=lambda *rgba: rgba)}), patch(
            'qfit.ui.qt_enum_compat.qt_class_enum_value', return_value='interpolated',
        ):
            self.assertIs(create_route_heatmap_layer(artifact), layer)
            core.QgsRasterLayer.assert_called_once_with(artifact.path, 'qfit activity heatmap', 'gdal')
            items = shader_function.setColorRampItemList.call_args.args[0]
            self.assertAlmostEqual(items[-1][0], 12)
            self.assertEqual(items[0][1][-1], 0)
            self.assertTrue(all(rgba[0] >= max(rgba[1:3]) for _, rgba, _ in items))
            renderer.setClassificationMin.assert_called_once_with(0)
            renderer.setClassificationMax.assert_called_once_with(12)
            layer.setCustomProperty.assert_any_call('qfit/heatmap/activity_count', 7)
            layer.isValid.return_value = False
            with self.assertRaises(ValueError):
                create_route_heatmap_layer(artifact)
