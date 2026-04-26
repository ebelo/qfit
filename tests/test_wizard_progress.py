import unittest

from qfit.ui.application.dock_workflow_sections import build_progress_wizard_step_statuses
from qfit.ui.application.wizard_progress import (
    WizardProgressFacts,
    build_wizard_progress_from_facts,
)


class WizardProgressFactsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
