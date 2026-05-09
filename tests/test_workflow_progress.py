import unittest

from qfit.ui.application import build_workflow_progress_from_facts as exported_builder
from qfit.ui.application.workflow_progress import build_workflow_progress_from_facts
from qfit.ui.application.workflow_progress_facts import WorkflowProgressFacts
from qfit.ui.application.wizard_progress import build_wizard_progress_from_facts


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

    def test_application_package_exports_neutral_workflow_builder(self):
        self.assertIs(exported_builder, build_workflow_progress_from_facts)


if __name__ == "__main__":
    unittest.main()
