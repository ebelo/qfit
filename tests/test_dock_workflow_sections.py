import unittest

from tests import _path  # noqa: F401

from qfit.ui.application.dock_workflow_sections import (
    CURRENT_DOCK_SECTIONS,
    WIZARD_WORKFLOW_STEPS,
    build_current_dock_workflow_label,
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

    def test_get_workflow_section_rejects_unknown_keys(self):
        with self.assertRaises(KeyError):
            get_workflow_section("unknown")


if __name__ == "__main__":
    unittest.main()
