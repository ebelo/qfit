import unittest

from tests import _path  # noqa: F401

from qfit.ui.application.dock_workflow_sections import (
    CURRENT_DOCK_SECTIONS,
    WIZARD_WORKFLOW_STEPS,
    DockWorkflowStepState,
    build_current_dock_workflow_label,
    build_initial_wizard_step_statuses,
    build_wizard_step_statuses,
    get_workflow_section,
)


class DockWorkflowSectionsTests(unittest.TestCase):
    def test_wizard_steps_keep_stable_order_and_labels(self):
        self.assertEqual(
            [section.key for section in WIZARD_WORKFLOW_STEPS],
            ["connection", "sync", "map", "analysis", "atlas"],
        )
        self.assertEqual(
            [section.title for section in WIZARD_WORKFLOW_STEPS],
            ["Connection", "Synchronization", "Map & filters", "Spatial analysis", "Atlas PDF"],
        )

    def test_current_dock_sections_reuse_wizard_steps_without_connection_page(self):
        self.assertEqual(
            [section.key for section in CURRENT_DOCK_SECTIONS],
            ["sync", "map", "analysis", "atlas"],
        )
        self.assertEqual(
            build_current_dock_workflow_label(),
            "Sections: Fetch & store · Visualize · Analyze · Publish",
        )
        self.assertEqual(get_workflow_section("sync").current_dock_title, "Fetch and store")

    def test_initial_wizard_step_statuses_match_first_launch_spec(self):
        statuses = build_initial_wizard_step_statuses()

        self.assertEqual(
            [status.key for status in statuses],
            ["connection", "sync", "map", "analysis", "atlas"],
        )
        self.assertEqual(statuses[0].state, DockWorkflowStepState.CURRENT)
        self.assertEqual(
            [status.state for status in statuses[1:]],
            [DockWorkflowStepState.LOCKED] * 4,
        )

    def test_wizard_step_statuses_distinguish_unlocked_from_done(self):
        statuses = build_wizard_step_statuses(
            current_key="map",
            completed_keys={"connection", "sync"},
            unlocked_keys={"analysis"},
        )

        self.assertEqual(
            [
                (status.key, status.index, status.title, status.state)
                for status in statuses
            ],
            [
                ("connection", 0, "Connection", DockWorkflowStepState.DONE),
                ("sync", 1, "Synchronization", DockWorkflowStepState.DONE),
                ("map", 2, "Map & filters", DockWorkflowStepState.CURRENT),
                ("analysis", 3, "Spatial analysis", DockWorkflowStepState.UNLOCKED),
                ("atlas", 4, "Atlas PDF", DockWorkflowStepState.LOCKED),
            ],
        )

    def test_get_workflow_section_rejects_unknown_keys(self):
        with self.assertRaises(KeyError):
            get_workflow_section("unknown")

    def test_wizard_step_statuses_reject_unknown_keys(self):
        with self.assertRaises(KeyError):
            build_wizard_step_statuses(current_key="connection", unlocked_keys={"unknown"})


if __name__ == "__main__":
    unittest.main()
