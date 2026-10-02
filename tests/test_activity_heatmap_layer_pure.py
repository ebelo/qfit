import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from tests import _path  # noqa: F401
from qfit.analysis.infrastructure.activity_heatmap_layer import build_activity_heatmap_layer


class HeatmapCompatibilityTests(unittest.TestCase):
    def test_requires_stored_line_tracks_and_ignores_sample_points(self):
        self.assertEqual(build_activity_heatmap_layer(None, object()), (None, 0))
        invalid = SimpleNamespace(isValid=lambda: False)
        self.assertEqual(build_activity_heatmap_layer(invalid), (None, 0))
        memory = SimpleNamespace(isValid=lambda: True, source=lambda: "memory:tracks")
        self.assertEqual(build_activity_heatmap_layer(memory), (None, 0))

    def test_synchronous_entry_uses_same_cached_raster_and_provider_subset(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "routes.gpkg"
            source.touch()
            layer = SimpleNamespace(isValid=lambda: True, source=lambda: str(source) + "|layername=activity_tracks",
                                    subsetString=lambda: "source_activity_id = '42'")
            qtcore = ModuleType("qgis.PyQt.QtCore")
            qtcore.QStandardPaths = SimpleNamespace(AppDataLocation=1, writableLocation=lambda _: root)
            artifact = SimpleNamespace(activity_count=3)
            with patch.dict("sys.modules", {"qgis.PyQt.QtCore": qtcore}), patch(
                "qfit.analysis.infrastructure.route_heatmap_raster.build_route_heatmap", return_value=artifact,
            ) as build, patch("qfit.analysis.infrastructure.route_heatmap_layer.create_route_heatmap_layer", return_value="raster"):
                self.assertEqual(build_activity_heatmap_layer(layer, object()), ("raster", 3))
                request = build.call_args.args[0]
                self.assertEqual(request.source_path, str(source))
                self.assertEqual(request.subset, "source_activity_id = '42'")
                build.return_value = None
                self.assertEqual(build_activity_heatmap_layer(layer), (None, 0))
