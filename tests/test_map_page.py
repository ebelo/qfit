import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.wizard_page_specs import build_default_wizard_page_specs


def _load_map_modules():
    for name in (
        "qfit.ui.dockwidget.map_page",
        "qfit.ui.dockwidget.wizard_page",
        "qfit.ui.dockwidget.action_row",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return (
            importlib.import_module("qfit.ui.dockwidget.map_page"),
            importlib.import_module("qfit.ui.dockwidget.wizard_page"),
        )


class MapPageContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.map_page, cls.wizard_page = _load_map_modules()

    def test_builds_default_third_page_content(self):
        content = self.map_page.MapPageContent()

        self.assertEqual(content.objectName(), "qfitWizardMapPageContent")
        self.assertEqual(content.status_label.objectName(), "qfitWizardMapStatus")
        self.assertEqual(content.status_label.text(), "Activity layers not loaded")
        self.assertEqual(content.status_label.property("mapState"), "not_loaded")
        self.assertEqual(content.detail_label.objectName(), "qfitWizardMapDetail")
        self.assertIn("apply filters", content.detail_label.text())
        self.assertEqual(
            content.layer_summary_label.objectName(),
            "qfitWizardMapLayerSummary",
        )
        self.assertEqual(
            content.layer_summary_label.text(),
            "No activity layers on the map",
        )
        self.assertEqual(
            content.filter_summary_label.objectName(),
            "qfitWizardMapFilterSummary",
        )
        self.assertEqual(
            content.filter_summary_label.text(),
            "All stored activities visible once layers are loaded",
        )
        self.assertEqual(
            content.load_layers_button.objectName(),
            "qfitWizardMapLoadLayersButton",
        )
        self.assertEqual(content.load_layers_button.text(), "Load activity layers")
        self.assertEqual(
            content.load_layers_button.property("secondaryAction"),
            "load_activity_layers",
        )
        self.assertEqual(content.load_layers_button.property("wizardActionRole"), "secondary")
        self.assertEqual(
            content.apply_filters_button.objectName(),
            "qfitWizardMapApplyFiltersButton",
        )
        self.assertEqual(content.apply_filters_button.text(), "Apply filters")
        self.assertEqual(
            content.apply_filters_button.property("primaryAction"),
            "apply_map_filters",
        )
        self.assertEqual(content.apply_filters_button.property("wizardActionRole"), "primary")
        self.assertEqual(content.action_row.objectName(), "qfitWizardMapActionRow")
        self.assertEqual(
            content.action_row.outer_layout().widgets,
            [content.load_layers_button, content.apply_filters_button],
        )
        self.assertEqual(
            content.outer_layout().widgets,
            [
                content.status_label,
                content.detail_label,
                content.layer_summary_label,
                content.filter_summary_label,
                content.action_row,
            ],
        )

    def test_refreshes_loaded_state_without_rebuilding(self):
        content = self.map_page.MapPageContent()
        state = self.map_page.MapPageState(
            loaded=True,
            status_text="Map ready",
            detail_text="Use saved filters for the loaded activity layers.",
            layer_summary_text="4 layers loaded from qfit.gpkg",
            filter_summary_text="42 activities · Ride and Run · 2026",
            load_action_label="Reload layers",
            primary_action_label="Apply saved filters",
        )

        content.set_state(state)

        self.assertEqual(content.status_label.text(), "Map ready")
        self.assertEqual(content.status_label.property("mapState"), "loaded")
        self.assertEqual(
            content.detail_label.text(),
            "Use saved filters for the loaded activity layers.",
        )
        self.assertEqual(
            content.layer_summary_label.text(),
            "4 layers loaded from qfit.gpkg",
        )
        self.assertEqual(content.layer_summary_label.property("mapState"), "loaded")
        self.assertEqual(
            content.filter_summary_label.text(),
            "42 activities · Ride and Run · 2026",
        )
        self.assertEqual(content.filter_summary_label.property("mapState"), "loaded")
        self.assertEqual(content.load_layers_button.text(), "Reload layers")
        self.assertEqual(content.apply_filters_button.text(), "Apply saved filters")

    def test_buttons_emit_reusable_page_signals(self):
        content = self.map_page.MapPageContent()
        calls = []
        content.loadLayersRequested.connect(lambda: calls.append("load"))
        content.applyFiltersRequested.connect(lambda: calls.append("filter"))

        content.load_layers_button.clicked.emit()
        content.apply_filters_button.clicked.emit()

        self.assertEqual(calls, ["load", "filter"])

    def test_installs_only_on_map_wizard_page_body(self):
        map_spec = next(spec for spec in build_default_wizard_page_specs() if spec.key == "map")
        map_page = self.wizard_page.WizardPage(map_spec)

        content = self.map_page.install_map_page_content(map_page)

        self.assertIs(map_page.body_layout().widgets[-1], content)

    def test_rejects_installing_on_other_wizard_page(self):
        sync_spec = next(spec for spec in build_default_wizard_page_specs() if spec.key == "sync")
        sync_page = self.wizard_page.WizardPage(sync_spec)

        with self.assertRaisesRegex(ValueError, "map wizard page"):
            self.map_page.install_map_page_content(sync_page)


if __name__ == "__main__":
    unittest.main()
