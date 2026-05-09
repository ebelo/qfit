import unittest

from qfit.ui.application import DockWorkflowProgress as exported_progress
from qfit.ui.application import (
    build_progress_workflow_step_statuses as exported_status_builder,
)
from qfit.ui.application import build_workflow_progress_from_facts as exported_builder
from qfit.ui.application import (
    build_startup_workflow_progress_facts as exported_startup_facts_builder,
)
from qfit.ui.application import (
    build_workflow_progress_from_facts_and_settings as exported_settings_builder,
)
from qfit.ui.application.workflow_progress import (
    build_startup_workflow_progress_facts,
    build_workflow_progress_from_facts,
    build_workflow_progress_from_facts_and_settings,
)
from qfit.ui.application.dock_workflow_sections import (
    DockWorkflowProgress,
    build_progress_workflow_step_statuses,
)
from qfit.ui.application.workflow_progress_facts import WorkflowProgressFacts
from qfit.ui.application.workflow_settings import WorkflowSettingsSnapshot
from qfit.ui.application.wizard_progress import (
    build_startup_wizard_progress_facts,
    build_wizard_progress_from_facts,
    build_wizard_progress_from_facts_and_settings,
)


class WorkflowProgressTests(unittest.TestCase):
    def test_builder_prefix_gates_completed_workflow_steps(self):
        progress = build_workflow_progress_from_facts(
            WorkflowProgressFacts(
                connection_configured=True,
                activity_layers_loaded=True,
                analysis_generated=True,
                atlas_exported=True,
            )
        )

        self.assertEqual(progress.current_key, "sync")
        self.assertEqual(progress.completed_keys, frozenset({"connection"}))
        self.assertEqual(progress.visited_keys, frozenset({"sync"}))

    def test_builder_allows_reachable_preferred_current_key(self):
        progress = build_workflow_progress_from_facts(
            WorkflowProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
                preferred_current_key="atlas",
            )
        )

        self.assertEqual(progress.current_key, "atlas")
        self.assertEqual(
            progress.completed_keys,
            frozenset({"connection", "sync", "map"}),
        )

    def test_wizard_builder_delegates_to_neutral_workflow_builder(self):
        facts = WorkflowProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
            analysis_generated=True,
            preferred_current_key="atlas",
        )

        self.assertEqual(
            build_wizard_progress_from_facts(facts),
            build_workflow_progress_from_facts(facts),
        )

    def test_settings_builder_applies_reachable_persisted_step(self):
        progress = build_workflow_progress_from_facts_and_settings(
            WorkflowProgressFacts(
                connection_configured=True,
                activities_stored=True,
                activity_layers_loaded=True,
            ),
            WorkflowSettingsSnapshot(
                settings_version=1,
                last_step_index=2,
                first_launch=False,
            ),
        )

        self.assertEqual(progress.current_key, "map")
        self.assertEqual(
            progress.completed_keys,
            frozenset({"connection", "sync", "map"}),
        )

    def test_wizard_settings_builder_delegates_to_neutral_workflow_builder(self):
        facts = WorkflowProgressFacts(
            connection_configured=True,
            activities_stored=True,
            activity_layers_loaded=True,
        )
        settings = WorkflowSettingsSnapshot(
            settings_version=1,
            last_step_index=4,
            first_launch=False,
        )

        self.assertEqual(
            build_wizard_progress_from_facts_and_settings(facts, settings),
            build_workflow_progress_from_facts_and_settings(facts, settings),
        )

    def test_startup_facts_skip_configured_connection_restore_target(self):
        settings = WorkflowSettingsSnapshot(
            settings_version=1,
            last_step_index=0,
            first_launch=False,
        )
        startup_facts = build_startup_workflow_progress_facts(
            WorkflowProgressFacts(connection_configured=True),
            settings,
        )

        progress = build_workflow_progress_from_facts_and_settings(
            startup_facts,
            settings,
        )

        self.assertEqual(progress.current_key, "sync")
        self.assertEqual(progress.completed_keys, frozenset({"connection"}))

    def test_startup_facts_preserve_explicit_user_selected_connection_step(self):
        settings = WorkflowSettingsSnapshot(
            settings_version=1,
            last_step_index=0,
            last_step_index_user_selected=True,
            first_launch=False,
        )
        startup_facts = build_startup_workflow_progress_facts(
            WorkflowProgressFacts(connection_configured=True),
            settings,
        )

        progress = build_workflow_progress_from_facts_and_settings(
            startup_facts,
            settings,
        )

        self.assertEqual(progress.current_key, "connection")
        self.assertEqual(progress.completed_keys, frozenset({"connection"}))

    def test_wizard_startup_facts_builder_delegates_to_neutral_workflow_builder(self):
        facts = WorkflowProgressFacts(connection_configured=True)
        settings = WorkflowSettingsSnapshot(
            settings_version=1,
            last_step_index=0,
            first_launch=False,
        )

        self.assertEqual(
            build_startup_wizard_progress_facts(facts, settings),
            build_startup_workflow_progress_facts(facts, settings),
        )

    def test_application_package_exports_neutral_workflow_builder(self):
        self.assertIs(exported_progress, DockWorkflowProgress)
        self.assertIs(
            exported_status_builder,
            build_progress_workflow_step_statuses,
        )
        self.assertIs(exported_builder, build_workflow_progress_from_facts)
        self.assertIs(
            exported_settings_builder,
            build_workflow_progress_from_facts_and_settings,
        )
        self.assertIs(
            exported_startup_facts_builder,
            build_startup_workflow_progress_facts,
        )


if __name__ == "__main__":
    unittest.main()
