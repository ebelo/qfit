import os
import unittest
from unittest.mock import patch, sentinel

from tests import _path  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qfit.ui.dockwidget_dependencies import build_dockwidget_dependencies, _build_cache


class _FakeIface:
    def mapCanvas(self):
        return None

    def mainWindow(self):
        return None


class DockWidgetDependenciesTests(unittest.TestCase):
    def test_build_dockwidget_dependencies_wires_shared_gateway_and_sync_controller(self):
        iface = _FakeIface()

        with (
            patch("qfit.ui.dockwidget_dependencies.SettingsService", return_value=sentinel.settings),
            patch("qfit.ui.dockwidget_dependencies.SyncController", return_value=sentinel.sync_controller),
            patch(
                "qfit.ui.dockwidget_dependencies.AtlasExportController",
                return_value=sentinel.atlas_export_controller,
            ),
            patch(
                "qfit.ui.dockwidget_dependencies._build_layer_gateway",
                return_value=sentinel.layer_gateway,
            ),
            patch(
                "qfit.ui.dockwidget_dependencies.BackgroundMapController",
                return_value=sentinel.background_controller,
            ) as background_controller,
            patch(
                "qfit.ui.dockwidget_dependencies.LoadWorkflowService",
                return_value=sentinel.load_workflow,
            ) as load_workflow,
            patch(
                "qfit.ui.dockwidget_dependencies.VisualApplyService",
                return_value=sentinel.visual_apply,
            ) as visual_apply,
            patch(
                "qfit.ui.dockwidget_dependencies.AtlasExportService",
                return_value=sentinel.atlas_export_service,
            ) as atlas_export_service,
            patch(
                "qfit.ui.dockwidget_dependencies.FetchResultService",
                return_value=sentinel.fetch_result_service,
            ) as fetch_result_service,
            patch("qfit.ui.dockwidget_dependencies._build_cache", return_value=sentinel.cache),
        ):
            dependencies = build_dockwidget_dependencies(iface)

        self.assertIs(dependencies.settings, sentinel.settings)
        self.assertIs(dependencies.sync_controller, sentinel.sync_controller)
        self.assertIs(dependencies.atlas_export_controller, sentinel.atlas_export_controller)
        self.assertIs(dependencies.layer_gateway, sentinel.layer_gateway)
        self.assertIs(dependencies.background_controller, sentinel.background_controller)
        self.assertIs(dependencies.load_workflow, sentinel.load_workflow)
        self.assertIs(dependencies.visual_apply, sentinel.visual_apply)
        self.assertIs(dependencies.atlas_export_service, sentinel.atlas_export_service)
        self.assertIs(dependencies.fetch_result_service, sentinel.fetch_result_service)
        self.assertIs(dependencies.cache, sentinel.cache)

        background_controller.assert_called_once_with(sentinel.layer_gateway)
        load_workflow.assert_called_once_with(sentinel.layer_gateway)
        visual_apply.assert_called_once_with(sentinel.layer_gateway)
        atlas_export_service.assert_called_once_with(sentinel.layer_gateway)
        fetch_result_service.assert_called_once_with(sentinel.sync_controller)

    def test_build_cache_prefers_legacy_cache_path_when_current_path_is_missing(self):
        with (
            patch(
                "qfit.ui.dockwidget_dependencies._writable_app_data_location",
                return_value="/tmp/appdata",
            ),
            patch(
                "qfit.ui.dockwidget_dependencies.os.path.exists",
                side_effect=lambda path: path == "/tmp/appdata/QFIT/cache",
            ),
            patch("qfit.ui.dockwidget_dependencies.QfitCache", return_value=sentinel.cache) as cache_class,
        ):
            cache = _build_cache()

        self.assertIs(cache, sentinel.cache)
        cache_class.assert_called_once_with("/tmp/appdata/QFIT/cache")

    def test_build_cache_falls_back_to_home_dot_qfit_when_appdata_is_blank(self):
        with (
            patch("qfit.ui.dockwidget_dependencies._writable_app_data_location", return_value=""),
            patch("qfit.ui.dockwidget_dependencies.os.path.expanduser", return_value="/home/tester"),
            patch("qfit.ui.dockwidget_dependencies.os.path.exists", return_value=False),
            patch("qfit.ui.dockwidget_dependencies.QfitCache", return_value=sentinel.cache) as cache_class,
        ):
            cache = _build_cache()

        self.assertIs(cache, sentinel.cache)
        cache_class.assert_called_once_with("/home/tester/.qfit/qfit/cache")


if __name__ == "__main__":
    unittest.main()
