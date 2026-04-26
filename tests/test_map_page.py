import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.wizard_page_specs import build_default_wizard_page_specs
from qfit.ui.tokens import COLOR_MUTED


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
        self.assertEqual(content.status_label.property("tone"), "warn")
        self.assertEqual(content.detail_label.objectName(), "qfitWizardMapDetail")
        self.assertIn("apply filters", content.detail_label.text())
        self.assertIn(COLOR_MUTED, content.detail_label.styleSheet())
        self.assertEqual(
            content.layer_summary_label.objectName(),
            "qfitWizardMapLayerSummary",
        )
        self.assertEqual(
            content.layer_summary_label.text(),
            "No activity layers on the map",
        )
        self.assertIn(COLOR_MUTED, content.layer_summary_label.styleSheet())
        self.assertEqual(
            content.background_summary_label.objectName(),
            "qfitWizardMapBackgroundSummary",
        )
        self.assertEqual(content.background_summary_label.text(), "Basemap disabled")
        self.assertIn(COLOR_MUTED, content.background_summary_label.styleSheet())
        self.assertEqual(
            content.style_summary_label.objectName(),
            "qfitWizardMapStyleSummary",
        )
        self.assertEqual(content.style_summary_label.text(), "Default activity styling")
        self.assertIn(COLOR_MUTED, content.style_summary_label.styleSheet())
        self.assertEqual(
            content.filter_summary_label.objectName(),
            "qfitWizardMapFilterSummary",
        )
        self.assertEqual(
            content.filter_summary_label.text(),
            "All stored activities visible once layers are loaded",
        )
        self.assertIn(COLOR_MUTED, content.filter_summary_label.styleSheet())
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
        self.assertTrue(content.load_layers_button.isEnabled())
        self.assertEqual(
            content.load_layers_button.property("wizardActionAvailability"),
            "available",
        )
        self.assertEqual(content.load_layers_button.toolTip(), "")
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
        self.assertFalse(content.apply_filters_button.isEnabled())
        self.assertEqual(
            content.apply_filters_button.property("wizardActionAvailability"),
            "blocked",
        )
        self.assertIn("Load activity layers", content.apply_filters_button.toolTip())
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
                content.background_summary_label,
                content.style_summary_label,
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
            background_summary_text="Basemap loaded: Outdoors",
            style_summary_text="Selected activity style: By activity type",
            filter_summary_text="42 activities · Ride and Run · 2026",
            load_action_label="Reload layers",
            primary_action_label="Apply saved filters",
        )

        content.set_state(state)

        self.assertEqual(content.status_label.text(), "Map ready")
        self.assertEqual(content.status_label.property("mapState"), "loaded")
        self.assertEqual(content.status_label.property("tone"), "ok")
        self.assertEqual(
            content.detail_label.text(),
            "Use saved filters for the loaded activity layers.",
        )
        self.assertEqual(
            content.layer_summary_label.text(),
            "4 layers loaded from qfit.gpkg",
        )
        self.assertEqual(content.layer_summary_label.property("mapState"), "loaded")
        self.assertEqual(content.background_summary_label.text(), "Basemap loaded: Outdoors")
        self.assertEqual(content.background_summary_label.property("mapState"), "loaded")
        self.assertEqual(
            content.style_summary_label.text(),
            "Selected activity style: By activity type",
        )
        self.assertEqual(content.style_summary_label.property("mapState"), "loaded")
        self.assertEqual(
            content.filter_summary_label.text(),
            "42 activities · Ride and Run · 2026",
        )
        self.assertEqual(content.filter_summary_label.property("mapState"), "loaded")
        self.assertEqual(content.load_layers_button.text(), "Reload layers")
        self.assertTrue(content.load_layers_button.isEnabled())
        self.assertEqual(
            content.load_layers_button.property("wizardActionAvailability"),
            "available",
        )
        self.assertEqual(content.load_layers_button.toolTip(), "")
        self.assertEqual(content.apply_filters_button.text(), "Apply saved filters")
        self.assertTrue(content.apply_filters_button.isEnabled())
        self.assertEqual(
            content.apply_filters_button.property("wizardActionAvailability"),
            "available",
        )
        self.assertEqual(content.apply_filters_button.toolTip(), "")

    def test_can_block_load_layers_until_sync_prerequisite_is_ready(self):
        content = self.map_page.MapPageContent(
            self.map_page.MapPageState(
                load_action_enabled=False,
                load_action_blocked_tooltip="Store activities before loading layers.",
            )
        )

        self.assertFalse(content.load_layers_button.isEnabled())
        self.assertEqual(
            content.load_layers_button.property("wizardActionAvailability"),
            "blocked",
        )
        self.assertEqual(
            content.load_layers_button.toolTip(),
            "Store activities before loading layers.",
        )

    def test_can_override_apply_filter_availability(self):
        content = self.map_page.MapPageContent(
            self.map_page.MapPageState(
                loaded=True,
                apply_action_enabled=False,
                apply_action_blocked_tooltip="Choose at least one activity layer.",
            )
        )

        self.assertFalse(content.apply_filters_button.isEnabled())
        self.assertEqual(
            content.apply_filters_button.toolTip(),
            "Choose at least one activity layer.",
        )

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
