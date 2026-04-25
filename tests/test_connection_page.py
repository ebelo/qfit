import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.wizard_page_specs import build_default_wizard_page_specs


def _load_connection_modules():
    for name in (
        "qfit.ui.dockwidget.connection_page",
        "qfit.ui.dockwidget.wizard_page",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return (
            importlib.import_module("qfit.ui.dockwidget.connection_page"),
            importlib.import_module("qfit.ui.dockwidget.wizard_page"),
        )


class ConnectionPageContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.connection_page, cls.wizard_page = _load_connection_modules()

    def test_builds_default_first_page_content(self):
        content = self.connection_page.ConnectionPageContent()

        self.assertEqual(content.objectName(), "qfitWizardConnectionPageContent")
        self.assertEqual(content.status_label.objectName(), "qfitWizardConnectionStatus")
        self.assertEqual(content.status_label.text(), "Strava not connected")
        self.assertEqual(
            content.status_label.property("connectionState"),
            "not_connected",
        )
        self.assertEqual(content.detail_label.objectName(), "qfitWizardConnectionDetail")
        self.assertIn("continue to synchronization", content.detail_label.text())
        self.assertEqual(
            content.configure_button.objectName(),
            "qfitWizardConnectionConfigureButton",
        )
        self.assertEqual(content.configure_button.text(), "Configure connection")
        self.assertEqual(
            content.configure_button.property("primaryAction"),
            "configure_connection",
        )
        self.assertEqual(
            content.outer_layout().widgets,
            [content.status_label, content.detail_label, content.configure_button],
        )

    def test_refreshes_connected_state_without_rebuilding(self):
        content = self.connection_page.ConnectionPageContent()
        state = self.connection_page.ConnectionPageState(
            connected=True,
            status_text="Connected to Strava",
            detail_text="Credentials are ready.",
            primary_action_label="Review connection",
        )

        content.set_state(state)

        self.assertEqual(content.status_label.text(), "Connected to Strava")
        self.assertEqual(content.status_label.property("connectionState"), "connected")
        self.assertEqual(content.detail_label.text(), "Credentials are ready.")
        self.assertEqual(content.configure_button.text(), "Review connection")

    def test_configure_button_emits_reusable_page_signal(self):
        content = self.connection_page.ConnectionPageContent()
        calls = []
        content.configureRequested.connect(lambda: calls.append("configure"))

        content.configure_button.clicked.emit()

        self.assertEqual(calls, ["configure"])

    def test_installs_only_on_connection_wizard_page_body(self):
        connection_spec = build_default_wizard_page_specs()[0]
        connection_page = self.wizard_page.WizardPage(connection_spec)

        content = self.connection_page.install_connection_page_content(connection_page)

        self.assertIs(connection_page.body_layout().widgets[-1], content)

    def test_rejects_installing_on_other_wizard_page(self):
        map_spec = build_default_wizard_page_specs()[2]
        map_page = self.wizard_page.WizardPage(map_spec)

        with self.assertRaisesRegex(ValueError, "connection wizard page"):
            self.connection_page.install_connection_page_content(map_page)


if __name__ == "__main__":
    unittest.main()
