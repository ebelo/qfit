import sys
import unittest
from types import ModuleType
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401


class _FakeRect:
    def __init__(self, xmin, ymin, xmax, ymax):
        self._xmin = xmin
        self._ymin = ymin
        self._xmax = xmax
        self._ymax = ymax

    def width(self):
        return self._xmax - self._xmin

    def height(self):
        return self._ymax - self._ymin

    def xMinimum(self):
        return self._xmin

    def yMinimum(self):
        return self._ymin

    def xMaximum(self):
        return self._xmax

    def yMaximum(self):
        return self._ymax


class _FakeLayoutExporter:
    Success = 0


def _install_qgis_stub():
    qgis_core = ModuleType("qgis.core")
    qgis_core.QgsLayoutExporter = _FakeLayoutExporter
    qgis_core.QgsRectangle = _FakeRect

    qgis_mod = ModuleType("qgis")
    qgis_mod.core = qgis_core
    sys.modules.setdefault("qgis", qgis_mod)
    sys.modules["qgis.core"] = qgis_core


_install_qgis_stub()

from qfit.atlas.export_page_runner import (  # noqa: E402
    AtlasPageExportRuntime,
    AtlasPageExportRunner,
    AtlasPerPageFieldIndexes,
    AtlasPerPageLayoutItems,
)


class AtlasPageExportRunnerTests(unittest.TestCase):
    def _make_runtime(self, *, page_result=0, canceled=False):
        feature = MagicMock(name="feature")
        values = {
            0: 1000.0,
            1: 2000.0,
            2: 300.0,
            3: 100.0,
            4: "activity-1",
            5: "5.2 km · 120–450 m",
            6: "5.2 km",
        }
        feature.attribute.side_effect = lambda idx: values.get(idx)

        atlas = MagicMock(name="atlas")
        atlas.layout.return_value.reportContext.return_value.feature.return_value = feature
        atlas.first.return_value = True
        atlas.next.return_value = False

        exporter = MagicMock(name="exporter")
        exporter.exportToPdf.return_value = page_result

        map_item = MagicMock(name="map_item")
        profile_adapter = MagicMock(name="profile_adapter")
        profile_adapter.requires_manual_page_updates = False
        profile_summary_label = MagicMock(name="profile_summary_label")
        detail_block_label = MagicMock(name="detail_block_label")

        filterable_layer = MagicMock(name="filterable_layer")
        runtime = AtlasPageExportRuntime(
            atlas=atlas,
            exporter=exporter,
            settings=object(),
            output_path="/tmp/atlas.pdf",
            field_indexes=AtlasPerPageFieldIndexes(
                cx_idx=0,
                cy_idx=1,
                ew_idx=2,
                eh_idx=3,
                sid_atlas_idx=4,
                profile_summary_idx=5,
                detail_field_indices=[(6, "Distance")],
            ),
            layout_items=AtlasPerPageLayoutItems(
                map_item=map_item,
                profile_adapter=profile_adapter,
                profile_summary_label=profile_summary_label,
                detail_block_label=detail_block_label,
            ),
            filterable_layers=[(filterable_layer, "")],
            profile_sample_lookup=MagicMock(name="profile_sample_lookup"),
            build_page_profile_payload=MagicMock(name="build_page_profile_payload"),
            apply_page_profile_payload=MagicMock(name="apply_page_profile_payload"),
            normalize_extent=MagicMock(side_effect=lambda rect, _aspect: rect),
            target_aspect_ratio=1.0,
            is_canceled=MagicMock(return_value=canceled),
        )
        return runtime, feature, filterable_layer

    def test_export_pages_updates_filters_labels_and_map_extent(self):
        runtime, feature, filterable_layer = self._make_runtime()

        page_paths, error = AtlasPageExportRunner(runtime).export_pages()

        self.assertIsNone(error)
        self.assertEqual(page_paths, ["/tmp/atlas.pdf.page_0.pdf"])
        filterable_layer.setSubsetString.assert_any_call('"source_activity_id" = \'activity-1\'')
        filterable_layer.setSubsetString.assert_called_with("")
        runtime.layout_items.profile_summary_label.setText.assert_called_once_with("5.2 km · 120–450 m")
        runtime.layout_items.detail_block_label.setText.assert_called_once_with("Distance: 5.2 km")
        runtime.normalize_extent.assert_called_once()
        runtime.layout_items.map_item.setExtent.assert_called_once()
        runtime.layout_items.map_item.refresh.assert_called_once()
        runtime.exporter.exportToPdf.assert_called_once_with(
            "/tmp/atlas.pdf.page_0.pdf",
            runtime.settings,
        )
        runtime.atlas.beginRender.assert_called_once_with()
        runtime.atlas.endRender.assert_called_once_with()

    def test_export_pages_runs_manual_profile_updates_and_cleans_temp_files(self):
        runtime, feature, filterable_layer = self._make_runtime()
        runtime.layout_items.profile_adapter.requires_manual_page_updates = True
        payload = MagicMock(name="payload")
        runtime.build_page_profile_payload.return_value = payload

        def _apply_profile(_adapter, _payload, **kwargs):
            kwargs["profile_temp_files"].append("/tmp/profile.svg")

        runtime.apply_page_profile_payload.side_effect = _apply_profile

        with patch("qfit.atlas.export_page_runner.os.remove") as remove_mock:
            page_paths, error = AtlasPageExportRunner(runtime).export_pages()

        self.assertIsNone(error)
        self.assertEqual(page_paths, ["/tmp/atlas.pdf.page_0.pdf"])
        runtime.build_page_profile_payload.assert_called_once_with(
            feature,
            runtime.filterable_layers,
            profile_altitude_lookup=runtime.profile_sample_lookup.lookup,
        )
        runtime.apply_page_profile_payload.assert_called_once()
        remove_mock.assert_called_once_with("/tmp/profile.svg")
        filterable_layer.setSubsetString.assert_called_with("")

    def test_export_pages_returns_error_when_exporter_fails(self):
        runtime, _feature, filterable_layer = self._make_runtime(page_result=7)

        page_paths, error = AtlasPageExportRunner(runtime).export_pages()

        self.assertEqual(page_paths, [])
        self.assertIn("page 1", error)
        filterable_layer.setSubsetString.assert_called_with("")
        runtime.atlas.endRender.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
