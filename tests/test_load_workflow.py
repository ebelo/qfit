import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401

try:
    from qgis.core import QgsApplication
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None

if QgsApplication is not None:
    from qfit.load_workflow import LoadResult, LoadWorkflowError, LoadWorkflowService
else:  # pragma: no cover
    LoadResult = None
    LoadWorkflowError = None
    LoadWorkflowService = None


@unittest.skipIf(LoadWorkflowService is None, "QGIS Python bindings are not available")
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


@unittest.skipIf(LoadWorkflowService is None, "QGIS Python bindings are not available")
class WriteAndLoadSuccessTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.service = LoadWorkflowService(self.layer_manager)

    @patch("qfit.load_workflow.GeoPackageWriter")
    def test_returns_load_result_with_layers(self, MockWriter):
        mock_writer_instance = MockWriter.return_value
        mock_writer_instance.write_activities.return_value = {
            "path": "/tmp/out.gpkg",
            "fetched_count": 3,
            "track_count": 3,
            "start_count": 3,
            "point_count": 0,
            "atlas_count": 3,
            "sync": {
                "total_count": 10,
                "inserted": 2,
                "updated": 1,
                "unchanged": 0,
            },
        }
        mock_layers = (
            MagicMock(name="activities"),
            MagicMock(name="starts"),
            MagicMock(name="points"),
            MagicMock(name="atlas"),
        )
        self.layer_manager.load_output_layers.return_value = mock_layers

        activities = [SimpleNamespace(name="a1"), SimpleNamespace(name="a2"), SimpleNamespace(name="a3")]
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

    @patch("qfit.load_workflow.GeoPackageWriter")
    def test_passes_sync_metadata_to_writer(self, MockWriter):
        mock_writer_instance = MockWriter.return_value
        mock_writer_instance.write_activities.return_value = {
            "path": "/tmp/out.gpkg",
            "fetched_count": 1,
            "track_count": 1,
            "start_count": 1,
            "point_count": 0,
            "atlas_count": 1,
            "sync": {"total_count": 1, "inserted": 1, "updated": 0, "unchanged": 0},
        }
        self.layer_manager.load_output_layers.return_value = (None, None, None, None)

        metadata = {"provider": "strava"}
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

        mock_writer_instance.write_activities.assert_called_once_with(
            ["a"], sync_metadata=metadata,
        )

    @patch("qfit.load_workflow.GeoPackageWriter")
    def test_constructs_writer_with_correct_params(self, MockWriter):
        mock_writer_instance = MockWriter.return_value
        mock_writer_instance.write_activities.return_value = {
            "path": "/tmp/out.gpkg",
            "fetched_count": 1,
            "track_count": 0,
            "start_count": 0,
            "point_count": 0,
            "atlas_count": 0,
            "sync": {"total_count": 1, "inserted": 1, "updated": 0, "unchanged": 0},
        }
        self.layer_manager.load_output_layers.return_value = (None, None, None, None)

        self.service.write_and_load(
            activities=["a"],
            output_path="/tmp/test.gpkg",
            write_activity_points=True,
            point_stride=10,
            atlas_margin_percent=5.0,
            atlas_min_extent_degrees=0.02,
            atlas_target_aspect_ratio=2.0,
        )

        MockWriter.assert_called_once_with(
            output_path="/tmp/test.gpkg",
            write_activity_points=True,
            point_stride=10,
            atlas_margin_percent=5.0,
            atlas_min_extent_degrees=0.02,
            atlas_target_aspect_ratio=2.0,
        )


@unittest.skipIf(LoadWorkflowService is None, "QGIS Python bindings are not available")
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


@unittest.skipIf(LoadWorkflowService is None, "QGIS Python bindings are not available")
class LoadExistingSuccessTests(unittest.TestCase):
    def setUp(self):
        self.layer_manager = MagicMock()
        self.service = LoadWorkflowService(self.layer_manager)

    @patch("qfit.load_workflow.os.path.exists", return_value=True)
    def test_returns_load_result(self, mock_exists):
        mock_activities_layer = MagicMock()
        mock_activities_layer.featureCount.return_value = 42
        mock_layers = (
            mock_activities_layer,
            MagicMock(name="starts"),
            MagicMock(name="points"),
            MagicMock(name="atlas"),
        )
        self.layer_manager.load_output_layers.return_value = mock_layers

        result = self.service.load_existing("/tmp/existing.gpkg")

        self.assertIsInstance(result, LoadResult)
        self.assertEqual(result.output_path, "/tmp/existing.gpkg")
        self.assertEqual(result.total_stored, 42)
        self.assertEqual(result.activities_layer, mock_activities_layer)
        self.assertIn("/tmp/existing.gpkg", result.status)
        self.layer_manager.load_output_layers.assert_called_once_with("/tmp/existing.gpkg")

    @patch("qfit.load_workflow.os.path.exists", return_value=True)
    def test_handles_none_activities_layer(self, mock_exists):
        self.layer_manager.load_output_layers.return_value = (None, None, None, None)

        result = self.service.load_existing("/tmp/empty.gpkg")

        self.assertEqual(result.total_stored, 0)


@unittest.skipIf(LoadResult is None, "QGIS Python bindings are not available")
class LoadResultTests(unittest.TestCase):
    def test_default_values(self):
        result = LoadResult()
        self.assertEqual(result.output_path, "")
        self.assertIsNone(result.activities_layer)
        self.assertEqual(result.total_stored, 0)
        self.assertEqual(result.status, "")
        self.assertEqual(result.sync, {})

    def test_custom_values(self):
        result = LoadResult(
            output_path="/tmp/test.gpkg",
            total_stored=5,
            status="ok",
        )
        self.assertEqual(result.output_path, "/tmp/test.gpkg")
        self.assertEqual(result.total_stored, 5)
        self.assertEqual(result.status, "ok")
