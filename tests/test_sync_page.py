import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.wizard_page_specs import build_default_wizard_page_specs


def _load_sync_modules():
    for name in (
        "qfit.ui.dockwidget.sync_page",
        "qfit.ui.dockwidget.wizard_page",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return (
            importlib.import_module("qfit.ui.dockwidget.sync_page"),
            importlib.import_module("qfit.ui.dockwidget.wizard_page"),
        )


class SyncPageContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sync_page, cls.wizard_page = _load_sync_modules()

    def test_builds_default_second_page_content(self):
        content = self.sync_page.SyncPageContent()

        self.assertEqual(content.objectName(), "qfitWizardSyncPageContent")
        self.assertEqual(content.status_label.objectName(), "qfitWizardSyncStatus")
        self.assertEqual(content.status_label.text(), "Activities not synced yet")
        self.assertEqual(content.status_label.property("syncState"), "not_synced")
        self.assertEqual(content.detail_label.objectName(), "qfitWizardSyncDetail")
        self.assertIn("GeoPackage", content.detail_label.text())
        self.assertEqual(
            content.activity_summary_label.objectName(),
            "qfitWizardSyncActivitySummary",
        )
        self.assertEqual(content.activity_summary_label.text(), "No activities stored")
        self.assertEqual(content.sync_button.objectName(), "qfitWizardSyncButton")
        self.assertEqual(content.sync_button.text(), "Sync activities")
        self.assertEqual(
            content.sync_button.property("primaryAction"),
            "sync_activities",
        )
        self.assertEqual(
            content.outer_layout().widgets,
            [
                content.status_label,
                content.detail_label,
                content.activity_summary_label,
                content.sync_button,
            ],
        )

    def test_refreshes_ready_state_without_rebuilding(self):
        content = self.sync_page.SyncPageContent()
        state = self.sync_page.SyncPageState(
            ready=True,
            status_text="Ready to sync new activities",
            detail_text="Use the latest saved Strava credentials.",
            activity_summary_text="42 activities stored · 40 detailed routes",
            primary_action_label="Fetch latest activities",
        )

        content.set_state(state)

        self.assertEqual(content.status_label.text(), "Ready to sync new activities")
        self.assertEqual(content.status_label.property("syncState"), "ready")
        self.assertEqual(
            content.detail_label.text(),
            "Use the latest saved Strava credentials.",
        )
        self.assertEqual(
            content.activity_summary_label.text(),
            "42 activities stored · 40 detailed routes",
        )
        self.assertEqual(content.activity_summary_label.property("syncState"), "ready")
        self.assertEqual(content.sync_button.text(), "Fetch latest activities")

    def test_sync_button_emits_reusable_page_signal(self):
        content = self.sync_page.SyncPageContent()
        calls = []
        content.syncRequested.connect(lambda: calls.append("sync"))

        content.sync_button.clicked.emit()

        self.assertEqual(calls, ["sync"])

    def test_installs_only_on_sync_wizard_page_body(self):
        sync_spec = build_default_wizard_page_specs()[1]
        sync_page = self.wizard_page.WizardPage(sync_spec)

        content = self.sync_page.install_sync_page_content(sync_page)

        self.assertIs(sync_page.body_layout().widgets[-1], content)

    def test_rejects_installing_on_other_wizard_page(self):
        connection_spec = build_default_wizard_page_specs()[0]
        connection_page = self.wizard_page.WizardPage(connection_spec)

        with self.assertRaisesRegex(ValueError, "synchronization wizard page"):
            self.sync_page.install_sync_page_content(connection_page)


if __name__ == "__main__":
    unittest.main()
