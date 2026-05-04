import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests import _path  # noqa: F401
from qfit.activities.application.load_workflow import (
    ClearDatabaseRequest,
    ClearDatabaseResult,
    ClearDatabaseWorkflow,
    LoadDatabaseRequest,
    LoadDatasetResult,
    LoadDatasetWorkflow,
    LoadExistingRequest,
    LoadResult,
    LoadWorkflowError,
    LoadWorkflowService,
    StoreActivitiesResult,
    StoreActivitiesWorkflow,
)
from qfit.atlas.publish_atlas import (
    DEFAULT_ATLAS_MARGIN_PERCENT,
    DEFAULT_ATLAS_TARGET_ASPECT_RATIO,
    DEFAULT_MIN_EXTENT_DEGREES,
)
from qfit.sync_repository import SyncStats

# Ensure a stub ``qfit.activities.infrastructure.geopackage.gpkg_writer`` is
# present in ``sys.modules`` so the lazy import inside ``write_and_load`` does
# not trigger the real module (which requires full QGIS bindings that may be
# unavailable or mocked out by other test modules). Restore the original module
# afterwards so other tests do not inherit the stub via import-order leakage.
_GPKG_WRITER_MODULE = "qfit.activities.infrastructure.geopackage.gpkg_writer"
_original_gpkg_writer = sys.modules.get(_GPKG_WRITER_MODULE)
_gpkg_writer_stub = MagicMock()
sys.modules[_GPKG_WRITER_MODULE] = _gpkg_writer_stub


def tearDownModule():
    if _original_gpkg_writer is None:
        sys.modules.pop(_GPKG_WRITER_MODULE, None)
    else:
        sys.modules[_GPKG_WRITER_MODULE] = _original_gpkg_writer


class StoreActivitiesWorkflowTests(unittest.TestCase):
    def test_write_database_request_returns_focused_store_result(self):
        writer = MagicMock()
        writer.write_activities.return_value = {
            "path": "/tmp/out.gpkg",
            "fetched_count": 2,
            "track_count": 2,
            "start_count": 2,
            "point_count": 0,
            "atlas_count": 2,
            "sync": SyncStats(total_count=7, inserted=2, updated=1, unchanged=0),
        }
        workflow = StoreActivitiesWorkflow(writer_factory=lambda **_kwargs: writer)

        result = workflow.write_database_request(
            workflow.build_write_request(
                activities=["a", "b"],
                output_path="/tmp/out.gpkg",
            )
        )

        self.assertIsInstance(result, StoreActivitiesResult)
        self.assertEqual(result.output_path, "/tmp/out.gpkg")
        self.assertEqual(result.total_stored, 7)
        self.assertIn("Use Load stored map layers in Visualize", result.status)


class LoadDatasetWorkflowTests(unittest.TestCase):
    def test_load_existing_request_returns_focused_load_result(self):
        layer_gateway = MagicMock()
        activities_layer = MagicMock()
        activities_layer.featureCount.return_value = 42
        route_layers = (
            MagicMock(name="route_tracks"),
            MagicMock(name="route_points"),
            MagicMock(name="route_profile_samples"),
        )
        route_layers[0].featureCount.return_value = 3
        route_layers[1].featureCount.return_value = 24
        route_layers[2].featureCount.return_value = 16
        layer_gateway.load_output_layers.return_value = (
            activities_layer,
            MagicMock(name="starts"),
            MagicMock(name="points"),
            MagicMock(name="atlas"),
        )
        layer_gateway.load_route_layers.return_value = route_layers
        workflow = LoadDatasetWorkflow(layer_gateway, path_exists=lambda _path: True)

        result = workflow.load_existing_request(
            workflow.build_load_existing_request("/tmp/existing.gpkg")
        )

        self.assertIsInstance(result, LoadDatasetResult)
        self.assertEqual(result.total_stored, 42)
        self.assertEqual(result.route_tracks_layer, route_layers[0])
        self.assertEqual(result.route_points_layer, route_layers[1])
        self.assertEqual(result.route_profile_samples_layer, route_layers[2])
        self.assertIn("/tmp/existing.gpkg", result.status)
        self.assertIn(
            "3 route tracks, 24 route points, and 16 profile samples",
            result.status,
        )

    def test_load_existing_status_explains_when_route_layers_are_missing(self):
        layer_gateway = MagicMock()
        activities_layer = MagicMock()
        activities_layer.featureCount.return_value = 42
        layer_gateway.load_output_layers.return_value = (
            activities_layer,
            MagicMock(name="starts"),
            MagicMock(name="points"),
            MagicMock(name="atlas"),
        )
        layer_gateway.load_route_layers.return_value = (None, None, None)
        workflow = LoadDatasetWorkflow(layer_gateway, path_exists=lambda _path: True)

        result = workflow.load_existing_request(
            workflow.build_load_existing_request("/tmp/existing.gpkg")
        )

        self.assertIn("No saved route layers found", result.status)
        self.assertIn("Sync saved routes", result.status)

    def test_load_existing_route_status_tolerates_uncountable_route_layers(self):
        class BrokenFeatureCountLayer:
            def featureCount(self):  # noqa: N802
                raise RuntimeError("provider unavailable")

        layer_gateway = MagicMock()
        activities_layer = MagicMock()
        activities_layer.featureCount.return_value = 42
        layer_gateway.load_output_layers.return_value = (
            activities_layer,
            MagicMock(name="starts"),
            MagicMock(name="points"),
            MagicMock(name="atlas"),
        )
        layer_gateway.load_route_layers.return_value = (
            object(),
            BrokenFeatureCountLayer(),
            None,
        )
        workflow = LoadDatasetWorkflow(layer_gateway, path_exists=lambda _path: True)

        result = workflow.load_existing_request(
            workflow.build_load_existing_request("/tmp/existing.gpkg")
        )

        self.assertIn("Loaded saved route layers: 0 route tracks", result.status)
        self.assertIn("0 route points", result.status)


class ClearDatabaseWorkflowTests(unittest.TestCase):
    def test_clear_database_request_deletes_existing_file(self):
        layer_gateway = MagicMock()
        remove_file = MagicMock()
        workflow = ClearDatabaseWorkflow(
            layer_gateway,
            path_exists=lambda _path: True,
            remove_file=remove_file,
        )

        result = workflow.clear_database_request(
            workflow.build_clear_database_request(
                "/tmp/out.gpkg",
                layers=["activities", "atlas"],
            )
        )

        self.assertIsInstance(result, ClearDatabaseResult)
        self.assertTrue(result.deleted)
        layer_gateway.remove_layers.assert_called_once_with(["activities", "atlas"])
        remove_file.assert_called_once_with("/tmp/out.gpkg")


class WriteAndLoadValidationTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.service = LoadWorkflowService(self.layer_manager)

    def test_raises_when_no_activities(self):
        with self.assertRaises(LoadWorkflowError) as ctx:
            self.service.write_and_load(
                activities=[],
                output_path="/tmp/test.gpkg",
                write_activity_points=False,
                point_stride=5,
                atlas_margin_percent=8.0,
                atlas_min_extent_degrees=0.01,
                atlas_target_aspect_ratio=1.5,
            )
        self.assertIn("Fetch activities", str(ctx.exception))

    def test_raises_when_no_output_path(self):
        with self.assertRaises(LoadWorkflowError) as ctx:
            self.service.write_and_load(
                activities=["activity"],
                output_path="",
                write_activity_points=False,
                point_stride=5,
                atlas_margin_percent=8.0,
                atlas_min_extent_degrees=0.01,
                atlas_target_aspect_ratio=1.5,
            )
        self.assertIn("output path", str(ctx.exception))

    def test_build_write_request_returns_structured_request(self):
        request = self.service.build_write_request(
            activities=["activity"],
            output_path="/tmp/test.gpkg",
            write_activity_points=True,
            point_stride=5,
            atlas_margin_percent=8.0,
            atlas_min_extent_degrees=0.01,
            atlas_target_aspect_ratio=1.5,
            sync_metadata={"provider": "strava"},
            last_sync_date="2026-01-01",
        )

        self.assertIsInstance(request, LoadDatabaseRequest)
        self.assertEqual(request.output_path, "/tmp/test.gpkg")
        self.assertTrue(request.write_activity_points)


class WriteAndLoadSuccessTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.service = LoadWorkflowService(self.layer_manager)

    def _make_writer_mock(self, write_result):
        mock_module = MagicMock()
        mock_writer_instance = mock_module.GeoPackageWriter.return_value
        mock_writer_instance.write_activities.return_value = write_result
        return mock_module

    def test_returns_load_result_with_layers(self):
        write_result = {
            "path": "/tmp/out.gpkg",
            "fetched_count": 3,
            "track_count": 3,
            "start_count": 3,
            "point_count": 0,
            "atlas_count": 3,
            "sync": SyncStats(total_count=10, inserted=2, updated=1, unchanged=0),
        }
        mock_gpkg = self._make_writer_mock(write_result)
        mock_layers = (
            MagicMock(name="activities"),
            MagicMock(name="starts"),
            MagicMock(name="points"),
            MagicMock(name="atlas"),
        )
        self.layer_manager.load_output_layers.return_value = mock_layers

        activities = [SimpleNamespace(name="a1"), SimpleNamespace(name="a2"), SimpleNamespace(name="a3")]
        with patch(f"{_GPKG_WRITER_MODULE}.GeoPackageWriter", mock_gpkg.GeoPackageWriter):
            result = self.service.write_and_load(
                activities=activities,
                output_path="/tmp/out.gpkg",
                write_activity_points=False,
                point_stride=5,
                atlas_margin_percent=8.0,
                atlas_min_extent_degrees=0.01,
                atlas_target_aspect_ratio=1.5,
                last_sync_date="2026-01-01",
            )

        self.assertIsInstance(result, LoadResult)
        self.assertEqual(result.output_path, "/tmp/out.gpkg")
        self.assertEqual(result.total_stored, 10)
        self.assertEqual(result.fetched_count, 3)
        self.assertEqual(result.track_count, 3)
        self.assertEqual(result.activities_layer, mock_layers[0])
        self.assertEqual(result.starts_layer, mock_layers[1])
        self.assertEqual(result.points_layer, mock_layers[2])
        self.assertEqual(result.atlas_layer, mock_layers[3])
        self.assertIn("inserted 2", result.status)
        self.assertIn("updated 1", result.status)

    def test_passes_sync_metadata_to_writer(self):
        write_result = {
            "path": "/tmp/out.gpkg",
            "fetched_count": 1,
            "track_count": 1,
            "start_count": 1,
            "point_count": 0,
            "atlas_count": 1,
            "sync": SyncStats(total_count=1, inserted=1, updated=0, unchanged=0),
        }
        mock_gpkg = self._make_writer_mock(write_result)
        self.layer_manager.load_output_layers.return_value = (None, None, None, None)

        metadata = {"provider": "strava"}
        with patch(f"{_GPKG_WRITER_MODULE}.GeoPackageWriter", mock_gpkg.GeoPackageWriter):
            self.service.write_and_load(
                activities=["a"],
                output_path="/tmp/out.gpkg",
                write_activity_points=True,
                point_stride=10,
                atlas_margin_percent=5.0,
                atlas_min_extent_degrees=0.02,
                atlas_target_aspect_ratio=1.0,
                sync_metadata=metadata,
            )

        mock_gpkg.GeoPackageWriter.return_value.write_activities.assert_called_once_with(
            ["a"], sync_metadata=metadata,
        )

    def test_constructs_writer_with_correct_params(self):
        write_result = {
            "path": "/tmp/out.gpkg",
            "fetched_count": 1,
            "track_count": 0,
            "start_count": 0,
            "point_count": 0,
            "atlas_count": 0,
            "sync": SyncStats(total_count=1, inserted=1, updated=0, unchanged=0),
        }
        mock_gpkg = self._make_writer_mock(write_result)
        self.layer_manager.load_output_layers.return_value = (None, None, None, None)

        with patch(f"{_GPKG_WRITER_MODULE}.GeoPackageWriter", mock_gpkg.GeoPackageWriter):
            self.service.write_and_load(
                activities=["a"],
                output_path="/tmp/test.gpkg",
                write_activity_points=True,
                point_stride=10,
                atlas_margin_percent=5.0,
                atlas_min_extent_degrees=0.02,
                atlas_target_aspect_ratio=2.0,
            )

        mock_gpkg.GeoPackageWriter.assert_called_once_with(
            output_path="/tmp/test.gpkg",
            write_activity_points=True,
            point_stride=10,
            atlas_margin_percent=5.0,
            atlas_min_extent_degrees=0.02,
            atlas_target_aspect_ratio=2.0,
        )

    def test_write_and_load_ignores_legacy_request_to_disable_activity_points(self):
        write_result = {
            "path": "/tmp/out.gpkg",
            "fetched_count": 1,
            "track_count": 0,
            "start_count": 0,
            "point_count": 0,
            "atlas_count": 0,
            "sync": SyncStats(total_count=1, inserted=1, updated=0, unchanged=0),
        }
        mock_gpkg = self._make_writer_mock(write_result)
        self.layer_manager.load_output_layers.return_value = (None, None, None, None)

        with patch(f"{_GPKG_WRITER_MODULE}.GeoPackageWriter", mock_gpkg.GeoPackageWriter):
            self.service.write_and_load(
                activities=["a"],
                output_path="/tmp/test.gpkg",
                write_activity_points=False,
                point_stride=10,
                atlas_margin_percent=5.0,
                atlas_min_extent_degrees=0.02,
                atlas_target_aspect_ratio=2.0,
            )

        mock_gpkg.GeoPackageWriter.assert_called_once_with(
            output_path="/tmp/test.gpkg",
            write_activity_points=True,
            point_stride=10,
            atlas_margin_percent=5.0,
            atlas_min_extent_degrees=0.02,
            atlas_target_aspect_ratio=2.0,
        )


class WriteDatabaseSuccessTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.service = LoadWorkflowService(self.layer_manager)

    def _make_writer_mock(self, write_result):
        mock_module = MagicMock()
        mock_writer_instance = mock_module.GeoPackageWriter.return_value
        mock_writer_instance.write_activities.return_value = write_result
        return mock_module

    def test_write_database_does_not_load_layers(self):
        write_result = {
            "path": "/tmp/out.gpkg",
            "fetched_count": 2,
            "track_count": 2,
            "start_count": 2,
            "point_count": 0,
            "atlas_count": 2,
            "sync": SyncStats(total_count=8, inserted=2, updated=0, unchanged=0),
        }
        mock_gpkg = self._make_writer_mock(write_result)

        with patch(f"{_GPKG_WRITER_MODULE}.GeoPackageWriter", mock_gpkg.GeoPackageWriter):
            result = self.service.write_database(
                activities=["a", "b"],
                output_path="/tmp/out.gpkg",
                write_activity_points=False,
                point_stride=5,
                atlas_margin_percent=8.0,
                atlas_min_extent_degrees=0.01,
                atlas_target_aspect_ratio=1.5,
                last_sync_date="2026-01-01",
            )

        self.layer_manager.load_output_layers.assert_not_called()
        self.assertEqual(result.output_path, "/tmp/out.gpkg")
        self.assertEqual(result.total_stored, 8)
        self.assertIsNone(result.activities_layer)
        self.assertIn("Use Load stored map layers in Visualize", result.status)


class LoadExistingValidationTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.service = LoadWorkflowService(self.layer_manager)

    def test_raises_when_no_output_path(self):
        with self.assertRaises(LoadWorkflowError) as ctx:
            self.service.load_existing("")
        self.assertIn("output path", str(ctx.exception))

    def test_raises_when_file_not_found(self):
        with self.assertRaises(LoadWorkflowError) as ctx:
            self.service.load_existing("/nonexistent/path.gpkg")
        self.assertIn("No database found", str(ctx.exception))
        self.assertIn("Store activities first", str(ctx.exception))

    def test_build_load_existing_request_returns_structured_request(self):
        request = self.service.build_load_existing_request("/tmp/existing.gpkg")

        self.assertIsInstance(request, LoadExistingRequest)
        self.assertEqual(request.output_path, "/tmp/existing.gpkg")


class LoadExistingSuccessTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.service = LoadWorkflowService(self.layer_manager)

    @patch("qfit.activities.application.load_workflow.os.path.exists", return_value=True)
    def test_returns_load_result(self, mock_exists):
        mock_activities_layer = MagicMock()
        mock_activities_layer.featureCount.return_value = 42
        mock_layers = (
            mock_activities_layer,
            MagicMock(name="starts"),
            MagicMock(name="points"),
            MagicMock(name="atlas"),
        )
        route_layers = (
            MagicMock(name="route_tracks"),
            MagicMock(name="route_points"),
            MagicMock(name="route_profile_samples"),
        )
        self.layer_manager.load_output_layers.return_value = mock_layers
        self.layer_manager.load_route_layers.return_value = route_layers

        result = self.service.load_existing("/tmp/existing.gpkg")

        self.assertIsInstance(result, LoadResult)
        self.assertEqual(result.output_path, "/tmp/existing.gpkg")
        self.assertEqual(result.total_stored, 42)
        self.assertEqual(result.activities_layer, mock_activities_layer)
        self.assertEqual(result.route_tracks_layer, route_layers[0])
        self.assertIn("/tmp/existing.gpkg", result.status)
        self.layer_manager.load_output_layers.assert_called_once_with("/tmp/existing.gpkg")
        self.layer_manager.load_route_layers.assert_called_once_with("/tmp/existing.gpkg")

    @patch("qfit.activities.application.load_workflow.os.path.exists", return_value=True)
    def test_handles_none_activities_layer(self, mock_exists):
        self.layer_manager.load_output_layers.return_value = (None, None, None, None)
        self.layer_manager.load_route_layers.return_value = (None, None, None)

        result = self.service.load_existing("/tmp/empty.gpkg")

        self.assertEqual(result.total_stored, 0)


class ClearDatabaseValidationTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.service = LoadWorkflowService(self.layer_manager)

    def test_raises_when_no_output_path(self):
        with self.assertRaises(LoadWorkflowError) as ctx:
            self.service.clear_database(output_path="", layers=[])

        self.assertIn("output path", str(ctx.exception))

    def test_build_clear_database_request_returns_dataclass(self):
        request = self.service.build_clear_database_request(
            "/tmp/test.gpkg",
            layers=["activities", "atlas"],
        )

        self.assertIsInstance(request, ClearDatabaseRequest)
        self.assertEqual(request.output_path, "/tmp/test.gpkg")
        self.assertEqual(request.layers, ["activities", "atlas"])


class ClearDatabaseSuccessTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.service = LoadWorkflowService(self.layer_manager)

    @patch("qfit.activities.application.load_workflow.os.path.exists", return_value=True)
    @patch("qfit.activities.application.load_workflow.os.remove")
    def test_removes_layers_and_deletes_file_when_present(self, mock_remove, _mock_exists):
        result = self.service.clear_database(
            output_path="/tmp/test.gpkg",
            layers=["activities", None, "atlas"],
        )

        self.assertIsInstance(result, ClearDatabaseResult)
        self.assertTrue(result.deleted)
        self.assertIn("/tmp/test.gpkg deleted", result.status)
        self.layer_manager.remove_layers.assert_called_once_with(["activities", None, "atlas"])
        mock_remove.assert_called_once_with("/tmp/test.gpkg")

    @patch("qfit.activities.application.load_workflow.os.path.exists", return_value=False)
    @patch("qfit.activities.application.load_workflow.os.remove")
    def test_clears_layers_without_delete_when_file_missing(self, mock_remove, _mock_exists):
        result = self.service.clear_database(
            output_path="/tmp/missing.gpkg",
            layers=["activities"],
        )

        self.assertFalse(result.deleted)
        self.assertEqual(result.status, "Layers cleared. No file to delete at the specified path.")
        self.layer_manager.remove_layers.assert_called_once_with(["activities"])
        mock_remove.assert_not_called()


class LoadResultTests(unittest.TestCase):
    def test_default_values(self):
        result = LoadResult()
        self.assertEqual(result.output_path, "")
        self.assertIsNone(result.activities_layer)
        self.assertEqual(result.total_stored, 0)
        self.assertEqual(result.status, "")
        self.assertIsNone(result.sync)

    def test_custom_values(self):
        result = LoadResult(
            output_path="/tmp/test.gpkg",
            total_stored=5,
            status="ok",
        )
        self.assertEqual(result.output_path, "/tmp/test.gpkg")
        self.assertEqual(result.total_stored, 5)
        self.assertEqual(result.status, "ok")


class LoadRequestContractTests(unittest.TestCase):
    def test_store_activities_request_defaults_keep_points_enabled(self):
        request = LoadDatabaseRequest()

        self.assertTrue(request.write_activity_points)
        self.assertEqual(request.point_stride, 5)

    def test_build_write_request_returns_dataclass(self):
        request = LoadWorkflowService.build_write_request(
            activities=["a"],
            output_path="/tmp/test.gpkg",
            write_activity_points=True,
            point_stride=10,
            atlas_margin_percent=5.0,
            atlas_min_extent_degrees=0.02,
            atlas_target_aspect_ratio=1.5,
            sync_metadata={"provider": "strava"},
            last_sync_date="2026-03-31",
        )

        self.assertIsInstance(request, LoadDatabaseRequest)
        self.assertEqual(request.output_path, "/tmp/test.gpkg")
        self.assertTrue(request.write_activity_points)
        self.assertEqual(request.sync_metadata["provider"], "strava")

    def test_build_write_request_defaults_to_activity_points(self):
        request = LoadWorkflowService.build_write_request(
            activities=["a"],
            output_path="/tmp/test.gpkg",
        )

        self.assertTrue(request.write_activity_points)
        self.assertEqual(request.point_stride, 5)

    def test_build_write_request_uses_internal_atlas_defaults_when_ui_omits_fields(self):
        request = LoadWorkflowService.build_write_request(
            activities=["a"],
            output_path="/tmp/test.gpkg",
        )

        self.assertEqual(request.atlas_margin_percent, DEFAULT_ATLAS_MARGIN_PERCENT)
        self.assertEqual(request.atlas_min_extent_degrees, DEFAULT_MIN_EXTENT_DEGREES)
        self.assertEqual(request.atlas_target_aspect_ratio, DEFAULT_ATLAS_TARGET_ASPECT_RATIO)

    def test_build_load_existing_request_returns_dataclass(self):
        request = LoadWorkflowService.build_load_existing_request("/tmp/existing.gpkg")
        self.assertEqual(request, LoadExistingRequest(output_path="/tmp/existing.gpkg"))

    @patch("qfit.activities.application.load_workflow.os.path.exists", return_value=True)
    def test_load_existing_request_matches_legacy_wrapper(self, _mock_exists):
        layer_manager = MagicMock()
        layer_manager.load_output_layers.return_value = (None, None, None, None)
        layer_manager.load_route_layers.return_value = (None, None, None)
        service = LoadWorkflowService(layer_manager)

        request = service.build_load_existing_request("/tmp/existing.gpkg")
        via_request = service.load_existing_request(request)
        via_wrapper = service.load_existing("/tmp/existing.gpkg")

        self.assertEqual(via_request.output_path, via_wrapper.output_path)
        self.assertEqual(via_request.total_stored, via_wrapper.total_stored)
