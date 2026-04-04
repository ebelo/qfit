import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.atlas.export_coordinator import AtlasExportCoordinator, AtlasExportExecutionResult


class AtlasExportCoordinatorTests(unittest.TestCase):
    def _make_coordinator(self, *, feature_count=2, canceled=False):
        atlas_layer = MagicMock(name="atlas_layer")
        atlas_layer.featureCount.return_value = feature_count

        layout = object()
        exporter_instance = object()
        page_runner = MagicMock(name="page_runner")
        page_runner.export_pages.return_value = (["/tmp/page-0.pdf"], None)

        build_layout = MagicMock(return_value=layout)
        layout_exporter_cls = MagicMock(return_value=exporter_instance)
        build_pdf_export_settings = MagicMock(return_value=object())
        ensure_output_directory = MagicMock()
        build_page_export_runner = MagicMock(return_value=page_runner)
        export_cover_page = MagicMock(return_value="/tmp/cover.pdf")
        export_toc_page = MagicMock(return_value="/tmp/toc.pdf")
        assemble_output_pdf = MagicMock()
        logger = MagicMock()

        coordinator = AtlasExportCoordinator(
            atlas_layer=atlas_layer,
            output_path="/tmp/out.pdf",
            project=object(),
            profile_plot_style="style",
            is_canceled=MagicMock(return_value=canceled),
            build_layout=build_layout,
            layout_exporter_cls=layout_exporter_cls,
            build_pdf_export_settings=build_pdf_export_settings,
            ensure_output_directory=ensure_output_directory,
            build_page_export_runner=build_page_export_runner,
            export_cover_page=export_cover_page,
            export_toc_page=export_toc_page,
            assemble_output_pdf=assemble_output_pdf,
            logger=logger,
        )
        return {
            "coordinator": coordinator,
            "atlas_layer": atlas_layer,
            "build_layout": build_layout,
            "layout_exporter_cls": layout_exporter_cls,
            "build_pdf_export_settings": build_pdf_export_settings,
            "ensure_output_directory": ensure_output_directory,
            "build_page_export_runner": build_page_export_runner,
            "page_runner": page_runner,
            "export_cover_page": export_cover_page,
            "export_toc_page": export_toc_page,
            "assemble_output_pdf": assemble_output_pdf,
            "logger": logger,
        }

    def test_execute_returns_empty_layer_error(self):
        parts = self._make_coordinator(feature_count=0)

        result = parts["coordinator"].execute()

        self.assertEqual(
            result,
            AtlasExportExecutionResult(
                success=False,
                page_count=0,
                error="No atlas pages found. Store and load activity layers first.",
            ),
        )
        parts["build_layout"].assert_not_called()

    def test_execute_reports_atlas_layer_inspection_failure(self):
        parts = self._make_coordinator()
        parts["atlas_layer"].featureCount.side_effect = RuntimeError("wrapped layer deleted")

        result = parts["coordinator"].execute()

        self.assertEqual(
            result,
            AtlasExportExecutionResult(
                success=False,
                page_count=0,
                error="Atlas layer inspection failed: wrapped layer deleted",
            ),
        )
        parts["logger"].exception.assert_called_once_with("Atlas export atlas layer inspection failed")
        parts["build_layout"].assert_not_called()

    def test_execute_runs_full_export_flow(self):
        parts = self._make_coordinator()

        result = parts["coordinator"].execute()

        self.assertEqual(result, AtlasExportExecutionResult(success=True, page_count=2, error=None))
        parts["build_layout"].assert_called_once()
        parts["layout_exporter_cls"].assert_called_once()
        parts["build_pdf_export_settings"].assert_called_once_with()
        parts["ensure_output_directory"].assert_called_once_with()
        parts["build_page_export_runner"].assert_called_once()
        parts["export_cover_page"].assert_called_once()
        parts["export_toc_page"].assert_called_once()
        parts["assemble_output_pdf"].assert_called_once_with(
            ["/tmp/page-0.pdf"],
            cover_path="/tmp/cover.pdf",
            toc_path="/tmp/toc.pdf",
        )

    def test_execute_returns_page_runner_error(self):
        parts = self._make_coordinator()
        parts["page_runner"].export_pages.return_value = ([], "boom")

        result = parts["coordinator"].execute()

        self.assertEqual(result, AtlasExportExecutionResult(success=False, page_count=2, error="boom"))
        parts["assemble_output_pdf"].assert_not_called()

    def test_execute_returns_error_when_no_pages_exported(self):
        parts = self._make_coordinator()
        parts["page_runner"].export_pages.return_value = ([], None)

        result = parts["coordinator"].execute()

        self.assertEqual(
            result,
            AtlasExportExecutionResult(success=False, page_count=2, error="No pages were exported."),
        )
        parts["assemble_output_pdf"].assert_not_called()

    def test_execute_catches_runtime_error(self):
        parts = self._make_coordinator()
        parts["build_layout"].side_effect = RuntimeError("layout failed")

        result = parts["coordinator"].execute()

        self.assertEqual(
            result,
            AtlasExportExecutionResult(
                success=False,
                page_count=0,
                error="Layout preparation failed: layout failed",
            ),
        )
        parts["logger"].exception.assert_called_once_with("Atlas export layout preparation failed")

    def test_execute_reports_export_setup_stage(self):
        parts = self._make_coordinator()
        parts["ensure_output_directory"].side_effect = OSError("disk full")

        result = parts["coordinator"].execute()

        self.assertEqual(
            result,
            AtlasExportExecutionResult(
                success=False,
                page_count=2,
                error="Export setup failed: disk full",
            ),
        )
        parts["logger"].exception.assert_called_once_with("Atlas export export setup failed")

    def test_execute_reports_page_export_stage(self):
        parts = self._make_coordinator()
        parts["page_runner"].export_pages.side_effect = RuntimeError("renderer exploded")

        result = parts["coordinator"].execute()

        self.assertEqual(
            result,
            AtlasExportExecutionResult(
                success=False,
                page_count=2,
                error="Page export failed: renderer exploded",
            ),
        )
        parts["logger"].exception.assert_called_once_with("Atlas export page export failed")

    def test_execute_reports_final_pdf_assembly_stage(self):
        parts = self._make_coordinator()
        parts["assemble_output_pdf"].side_effect = OSError("permission denied")

        result = parts["coordinator"].execute()

        self.assertEqual(
            result,
            AtlasExportExecutionResult(
                success=False,
                page_count=2,
                error="Final PDF assembly failed: permission denied",
            ),
        )
        parts["logger"].exception.assert_called_once_with("Atlas export final PDF assembly failed")


if __name__ == "__main__":
    unittest.main()
