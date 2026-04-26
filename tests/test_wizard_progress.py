import unittest

from qfit.ui.application.dock_runtime_state import (
    DockRuntimeLayers,
    DockRuntimeState,
    DockRuntimeTasks,
)
from qfit.ui.application.dock_workflow_sections import build_progress_wizard_step_statuses
from qfit.ui.application.wizard_progress import (
    WizardProgressFacts,
    build_wizard_progress_facts_from_runtime_state,
    build_wizard_progress_from_facts,
    build_wizard_progress_from_facts_and_settings,
)
from qfit.ui.application.wizard_settings import WizardSettingsSnapshot


class WizardProgressFactsTests(unittest.TestCase):
    def test_runtime_state_adapter_defaults_to_no_completed_workflow_facts(self):
        facts = build_wizard_progress_facts_from_runtime_state(DockRuntimeState())

        self.assertEqual(facts, WizardProgressFacts())

    def test_runtime_state_adapter_maps_persisted_and_loaded_workflow_facts(self):
        activities_layer = object()
        analysis_layer = object()
        state = DockRuntimeState(
            activities=(object(), object()),
            output_path="/tmp/qfit.gpkg",
            layers=DockRuntimeLayers(
                activities=activities_layer,
                analysis=analysis_layer,
            ),
        )

        facts = build_wizard_progress_facts_from_runtime_state(
            state,
            connection_configured=True,
            atlas_exported=True,
            preferred_current_key="atlas",
            atlas_output_path="/tmp/qfit-atlas.pdf",
        )

        self.assertEqual(
            facts,
            WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                analysis_generated=True,
                atlas_exported=True,
                preferred_current_key="atlas",
                output_name="qfit.gpkg",
                atlas_output_name="qfit-atlas.pdf",
            ),
        )

    def test_runtime_state_adapter_maps_running_workflow_tasks(self):
        cases = (
            DockRuntimeTasks(fetch="fetch"),
            DockRuntimeTasks(store="store"),
            DockRuntimeTasks(fetch="fetch", store="store", atlas_export="atlas"),
        )
        for tasks in cases:
            with self.subTest(tasks=tasks):
                state = DockRuntimeState(tasks=tasks)

                facts = build_wizard_progress_facts_from_runtime_state(state)

                self.assertTrue(facts.sync_in_progress)
                self.assertEqual(
                    facts.atlas_export_in_progress,
                    tasks.atlas_export is not None,
                )

    def test_runtime_state_adapter_treats_blank_output_path_as_not_stored(self):
        facts = build_wizard_progress_facts_from_runtime_state(
            DockRuntimeState(output_path="   ")
        )

        self.assertFalse(facts.activities_stored)

    def test_runtime_state_adapter_keeps_unknown_activity_count_for_loaded_file(self):
        facts = build_wizard_progress_facts_from_runtime_state(
            DockRuntimeState(output_path="/tmp/qfit.gpkg")
        )

        self.assertIsNone(facts.activity_count)
        self.assertEqual(facts.output_name, "qfit.gpkg")

    def test_runtime_state_adapter_does_not_treat_fetch_count_as_stored_count(self):
        facts = build_wizard_progress_facts_from_runtime_state(
            DockRuntimeState(
                activities=(object(), object(), object()),
                output_path="/tmp/qfit.gpkg",
            )
        )

        self.assertIsNone(facts.activity_count)
        self.assertEqual(facts.output_name, "qfit.gpkg")

    def test_runtime_state_adapter_normalises_windows_output_filename(self):
        facts = build_wizard_progress_facts_from_runtime_state(
            DockRuntimeState(output_path="C:\\Users\\Emman\\qfit.gpkg")
        )

        self.assertEqual(facts.output_name, "qfit.gpkg")

    def test_runtime_state_adapter_normalises_escaped_windows_output_filename(self):
        facts = build_wizard_progress_facts_from_runtime_state(
            DockRuntimeState(output_path=r"C:\\Users\\Emman\\qfit.gpkg")
        )

        self.assertEqual(facts.output_name, "qfit.gpkg")

    def test_runtime_state_adapter_normalises_atlas_output_filename(self):
        facts = build_wizard_progress_facts_from_runtime_state(
            DockRuntimeState(),
            atlas_output_path=r"C:\\Users\\Emman\\qfit-atlas.pdf",
        )

        self.assertEqual(facts.atlas_output_name, "qfit-atlas.pdf")

    def test_defaults_keep_connection_current_with_no_completed_steps(self):
        progress = build_wizard_progress_from_facts(WizardProgressFacts())

        self.assertEqual(progress.current_key, "connection")
        self.assertEqual(progress.completed_keys, frozenset())
        self.assertEqual(progress.visited_keys, frozenset({"connection"}))

    def test_selects_first_incomplete_step_from_completed_prefix(self):
        progress = build_wizard_progress_from_facts(
            WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
            )
        )

        self.assertEqual(progress.current_key, "analysis")
        self.assertEqual(
            progress.completed_keys,
            frozenset({"connection", "sync", "map"}),
        )
        statuses = build_progress_wizard_step_statuses(progress)
        self.assertEqual(
            [status.state.value for status in statuses],
            ["done", "done", "done", "current", "locked"],
        )

    def test_ignores_later_completed_facts_until_prerequisites_are_done(self):
        progress = build_wizard_progress_from_facts(
            WizardProgressFacts(
                connection_configured=True,
                activities_stored=False,
                activity_layers_loaded=True,
                analysis_generated=True,
                atlas_exported=True,
            )
        )

        self.assertEqual(progress.current_key, "sync")
        self.assertEqual(progress.completed_keys, frozenset({"connection"}))

    def test_accepts_preferred_current_key_only_when_reachable(self):
        progress = build_wizard_progress_from_facts(
            WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                preferred_current_key="connection",
            )
        )

        self.assertEqual(progress.current_key, "connection")
        self.assertEqual(progress.completed_keys, frozenset({"connection", "sync"}))

        clamped = build_wizard_progress_from_facts(
            WizardProgressFacts(
                connection_configured=True,
                preferred_current_key="analysis",
            )
        )

        self.assertEqual(clamped.current_key, "sync")
        self.assertEqual(clamped.completed_keys, frozenset({"connection"}))

    def test_fully_completed_progress_keeps_atlas_current(self):
        progress = build_wizard_progress_from_facts(
            WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                analysis_generated=True,
                atlas_exported=True,
            )
        )

        self.assertEqual(progress.current_key, "atlas")
        self.assertEqual(
            progress.completed_keys,
            frozenset({"connection", "sync", "map", "analysis", "atlas"}),
        )

    def test_rejects_unknown_preferred_current_key(self):
        with self.assertRaisesRegex(KeyError, "review"):
            build_wizard_progress_from_facts(
                WizardProgressFacts(preferred_current_key="review")
            )

    def test_existing_settings_restore_reachable_preferred_step(self):
        progress = build_wizard_progress_from_facts_and_settings(
            WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
            ),
            WizardSettingsSnapshot(wizard_version=1, last_step_index=2, first_launch=False),
        )

        self.assertEqual(progress.current_key, "map")
        self.assertEqual(
            progress.completed_keys,
            frozenset({"connection", "sync", "map"}),
        )

    def test_first_launch_settings_keep_default_connection_step(self):
        progress = build_wizard_progress_from_facts_and_settings(
            WizardProgressFacts(connection_configured=True),
            WizardSettingsSnapshot(wizard_version=1, last_step_index=4, first_launch=True),
        )

        self.assertEqual(progress.current_key, "sync")

    def test_explicit_preferred_key_wins_over_persisted_step(self):
        progress = build_wizard_progress_from_facts_and_settings(
            WizardProgressFacts(
                connection_configured=True,
                activities_stored=True,
                preferred_current_key="connection",
            ),
            WizardSettingsSnapshot(wizard_version=1, last_step_index=2, first_launch=False),
        )

        self.assertEqual(progress.current_key, "connection")


if __name__ == "__main__":
    unittest.main()
