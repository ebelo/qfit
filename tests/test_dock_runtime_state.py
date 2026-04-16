import unittest

from tests import _path  # noqa: F401

from qfit.ui.application.dock_runtime_state import DockRuntimeStore


class TestDockRuntimeStore(unittest.TestCase):
    def test_fetch_lifecycle_tracks_task_activities_and_metadata(self):
        store = DockRuntimeStore()
        task = object()

        store.begin_fetch(task)
        self.assertIs(store.state.fetch_task, task)

        activities = ["run", "ride"]
        metadata = {"provider": "strava"}
        store.finish_fetch(activities=activities, metadata=metadata)

        self.assertIsNone(store.state.fetch_task)
        self.assertEqual(store.state.activities, tuple(activities))
        self.assertEqual(store.state.last_fetch_context, metadata)

    def test_store_and_load_lifecycle_updates_output_and_layers(self):
        store = DockRuntimeStore()
        task = object()
        activities_layer = object()
        starts_layer = object()
        points_layer = object()
        atlas_layer = object()

        store.begin_store(task)
        self.assertIs(store.state.store_task, task)

        store.finish_store(output_path="/tmp/qfit.gpkg")
        self.assertIsNone(store.state.store_task)
        self.assertEqual(store.state.output_path, "/tmp/qfit.gpkg")

        store.load_dataset(
            output_path="/tmp/qfit.gpkg",
            activities_layer=activities_layer,
            starts_layer=starts_layer,
            points_layer=points_layer,
            atlas_layer=atlas_layer,
        )
        self.assertIs(store.state.activities_layer, activities_layer)
        self.assertIs(store.state.starts_layer, starts_layer)
        self.assertIs(store.state.points_layer, points_layer)
        self.assertIs(store.state.atlas_layer, atlas_layer)

    def test_reset_loaded_dataset_clears_loaded_runtime_fields(self):
        store = DockRuntimeStore()
        background_layer = object()
        analysis_layer = object()

        store.finish_fetch(activities=["run"], metadata={"provider": "strava"})
        store.finish_store(output_path="/tmp/qfit.gpkg")
        store.load_dataset(
            output_path="/tmp/qfit.gpkg",
            activities_layer=object(),
            starts_layer=object(),
            points_layer=object(),
            atlas_layer=object(),
        )
        store.set_background_layer(background_layer)
        store.set_analysis_layer(analysis_layer)

        store.reset_loaded_dataset()

        self.assertEqual(store.state.activities, ())
        self.assertIsNone(store.state.output_path)
        self.assertIsNone(store.state.activities_layer)
        self.assertIsNone(store.state.starts_layer)
        self.assertIsNone(store.state.points_layer)
        self.assertIsNone(store.state.atlas_layer)
        self.assertEqual(store.state.last_fetch_context, {})
        self.assertIs(store.state.background_layer, background_layer)
        self.assertIs(store.state.analysis_layer, analysis_layer)

    def test_analysis_background_and_export_helpers_update_runtime(self):
        store = DockRuntimeStore()
        background_layer = object()
        analysis_layer = object()
        export_task = object()

        store.set_background_layer(background_layer)
        store.set_analysis_layer(analysis_layer)
        store.begin_atlas_export(export_task)

        self.assertIs(store.state.background_layer, background_layer)
        self.assertIs(store.state.analysis_layer, analysis_layer)
        self.assertIs(store.state.atlas_export_task, export_task)

        store.clear_analysis_layer()
        store.clear_atlas_export()

        self.assertIsNone(store.state.analysis_layer)
        self.assertIsNone(store.state.atlas_export_task)


if __name__ == "__main__":
    unittest.main()
