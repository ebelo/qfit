import sys
import types
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit.analysis.application.activity_heatmap_analysis import (
    _build_activity_heatmap_layer,
    run_activity_heatmap_analysis,
)


class TestActivityHeatmapAnalysis(unittest.TestCase):
    def test_run_activity_heatmap_analysis_returns_empty_result_without_layers(self):
        with patch(
            "qfit.analysis.application.activity_heatmap_analysis.build_empty_analysis_result",
            return_value="result",
        ) as build_empty:
            result = run_activity_heatmap_analysis()

        self.assertEqual(result, "result")
        build_empty.assert_called_once_with()

    def test_run_activity_heatmap_analysis_builds_result_from_layer_output(self):
        with patch(
            "qfit.analysis.application.activity_heatmap_analysis._build_activity_heatmap_layer",
            return_value=("layer", 42),
        ) as build_layer, patch(
            "qfit.analysis.application.activity_heatmap_analysis.build_activity_heatmap_result",
            return_value="result",
        ) as build_result:
            result = run_activity_heatmap_analysis(
                activities_layer="activities-layer",
                points_layer="points-layer",
            )

        self.assertEqual(result, "result")
        build_layer.assert_called_once_with(
            activities_layer="activities-layer",
            points_layer="points-layer",
        )
        build_result.assert_called_once_with("layer", 42)

    def test_build_activity_heatmap_layer_delegates_to_infrastructure_builder(self):
        fake_module = types.ModuleType("qfit.analysis.infrastructure.activity_heatmap_layer")
        fake_module.build_activity_heatmap_layer = lambda activities_layer=None, points_layer=None: (
            "built-layer",
            7,
        )

        with patch.dict(sys.modules, {fake_module.__name__: fake_module}):
            layer, sample_count = _build_activity_heatmap_layer(
                activities_layer="activities-layer",
                points_layer="points-layer",
            )

        self.assertEqual(layer, "built-layer")
        self.assertEqual(sample_count, 7)


if __name__ == "__main__":
    unittest.main()
