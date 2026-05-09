import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.workflow_page_specs import build_default_workflow_page_specs
from qfit.ui.tokens import COLOR_MUTED


def _load_analysis_modules():
    for name in (
        "qfit.ui.dockwidget.analysis_page",
        "qfit.ui.dockwidget.wizard_page",
        "qfit.ui.dockwidget.action_row",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return (
            importlib.import_module("qfit.ui.dockwidget.analysis_page"),
            importlib.import_module("qfit.ui.dockwidget.wizard_page"),
        )


class AnalysisPageContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis_page, cls.wizard_page = _load_analysis_modules()

    def test_builds_default_fourth_page_content(self):
        content = self.analysis_page.AnalysisPageContent()

        self.assertEqual(content.objectName(), "qfitWizardAnalysisPageContent")
        self.assertEqual(content.status_label.objectName(), "qfitWizardAnalysisStatus")
        self.assertEqual(content.status_label.text(), "Analysis not run yet")
        self.assertEqual(content.status_label.property("analysisState"), "not_ready")
        self.assertEqual(content.status_label.property("tone"), "warn")
        self.assertEqual(content.detail_label.objectName(), "qfitWizardAnalysisDetail")
        self.assertIn("heatmaps", content.detail_label.text())
        self.assertIn(COLOR_MUTED, content.detail_label.styleSheet())
        self.assertEqual(
            content.input_summary_label.objectName(),
            "qfitWizardAnalysisInputSummary",
        )
        self.assertEqual(
            content.input_summary_label.text(),
            "No loaded activity layers available for analysis",
        )
        self.assertIn(COLOR_MUTED, content.input_summary_label.styleSheet())
        self.assertEqual(
            content.result_summary_label.objectName(),
            "qfitWizardAnalysisResultSummary",
        )
        self.assertEqual(
            content.result_summary_label.text(),
            "No analysis displayed",
        )
        self.assertIn(COLOR_MUTED, content.result_summary_label.styleSheet())
        self.assertEqual(
            content.analysis_mode_label.objectName(),
            "qfitWizardAnalysisModeLabel",
        )
        self.assertEqual(content.analysis_mode_label.text(), "Analysis mode")
        self.assertEqual(
            content.analysis_mode_combo.objectName(),
            "qfitWizardAnalysisModeComboBox",
        )
        self.assertEqual(
            content.analysis_mode_combo.items,
            ["Heatmap", "Most frequent starting points"],
        )
        self.assertEqual(content.current_analysis_mode(), "Heatmap")
        self.assertEqual(
            content.temporal_controls_panel.objectName(),
            "qfitWizardAnalysisTemporalControlsPanel",
        )
        self.assertTrue(content.temporal_controls_panel.isVisible())
        self.assertEqual(
            content.temporal_controls_panel.property("temporalControlsState"),
            "expanded",
        )
        self.assertEqual(
            content.temporal_controls_layout().object_name,
            "qfitWizardAnalysisTemporalControlsLayout",
        )
        self.assertEqual(
            content.run_analysis_button.objectName(),
            "qfitWizardAnalysisRunButton",
        )
        self.assertEqual(content.run_analysis_button.text(), "Run analysis")
        self.assertEqual(
            content.run_analysis_button.property("primaryAction"),
            "run_analysis",
        )
        self.assertEqual(
            content.run_analysis_button.property("wizardActionRole"),
            "primary",
        )
        self.assertFalse(content.run_analysis_button.isEnabled())
        self.assertEqual(
            content.run_analysis_button.property("wizardActionAvailability"),
            "blocked",
        )
        self.assertIn("Load activity layers", content.run_analysis_button.toolTip())
        self.assertEqual(
            content.clear_analysis_button.objectName(),
            "qfitWizardAnalysisClearButton",
        )
        self.assertEqual(content.clear_analysis_button.text(), "Clear analysis")
        self.assertEqual(
            content.clear_analysis_button.property("secondaryAction"),
            "clear_analysis",
        )
        self.assertEqual(
            content.clear_analysis_button.property("wizardActionRole"),
            "secondary",
        )
        self.assertTrue(content.clear_analysis_button.isEnabled())
        self.assertEqual(content.action_row.objectName(), "qfitWizardAnalysisActionRow")
        self.assertEqual(
            content.action_row.outer_layout().widgets,
            [content.run_analysis_button, content.clear_analysis_button],
        )
        self.assertEqual(
            content.outer_layout().widgets,
            [
                content.status_label,
                content.detail_label,
                content.input_summary_label,
                content.analysis_mode_label,
                content.analysis_mode_combo,
                content.temporal_controls_panel,
                content.action_row,
                content.result_summary_label,
            ],
        )

    def test_refreshes_ready_state_without_rebuilding(self):
        content = self.analysis_page.AnalysisPageContent()
        state = self.analysis_page.AnalysisPageState(
            ready=True,
            status_text="Analysis ready",
            detail_text="Run analysis using the loaded filtered activity layers.",
            input_summary_text="4 layers loaded · 42 selected activities",
            result_summary_text="Heatmap and start-point layers can be refreshed",
            primary_action_label="Refresh analysis",
        )

        content.set_state(state)

        self.assertEqual(content.status_label.text(), "Analysis ready")
        self.assertEqual(content.status_label.property("analysisState"), "ready")
        self.assertEqual(content.status_label.property("tone"), "ok")
        self.assertEqual(
            content.detail_label.text(),
            "Run analysis using the loaded filtered activity layers.",
        )
        self.assertEqual(
            content.input_summary_label.text(),
            "4 layers loaded · 42 selected activities",
        )
        self.assertEqual(content.input_summary_label.property("analysisState"), "ready")
        self.assertEqual(
            content.result_summary_label.text(),
            "Heatmap and start-point layers can be refreshed",
        )
        self.assertEqual(content.result_summary_label.property("analysisState"), "ready")
        self.assertEqual(content.run_analysis_button.text(), "Refresh analysis")
        self.assertTrue(content.run_analysis_button.isEnabled())
        self.assertEqual(
            content.run_analysis_button.property("wizardActionAvailability"),
            "available",
        )
        self.assertEqual(content.run_analysis_button.toolTip(), "")

    def test_presentation_copy_wraps_without_forcing_panel_width(self):
        content = self.analysis_page.AnalysisPageContent()

        for label in (
            content.detail_label,
            content.input_summary_label,
            content.result_summary_label,
        ):
            self.assertTrue(label.word_wrap)
            self.assertEqual(label.minimumWidth(), 0)
            self.assertEqual(label.size_policy, (3, 4))

    def test_can_refresh_selectable_analysis_modes(self):
        content = self.analysis_page.AnalysisPageContent()
        calls = []
        content.analysisModeChanged.connect(calls.append)

        content.set_analysis_mode_options(
            ("Most frequent starting points", "Heatmap"),
            selected="Most frequent starting points",
        )

        self.assertEqual(
            content.analysis_mode_combo.items,
            ["Most frequent starting points", "Heatmap"],
        )
        self.assertEqual(
            content.current_analysis_mode(),
            "Most frequent starting points",
        )
        self.assertEqual(calls, ["Most frequent starting points"])

    def test_can_override_run_analysis_availability(self):
        content = self.analysis_page.AnalysisPageContent(
            self.analysis_page.AnalysisPageState(
                ready=True,
                primary_action_enabled=False,
                primary_action_blocked_tooltip="Choose an analysis input layer.",
            )
        )

        self.assertFalse(content.run_analysis_button.isEnabled())
        self.assertEqual(
            content.run_analysis_button.toolTip(),
            "Choose an analysis input layer.",
        )

    def test_buttons_emit_reusable_page_signals(self):
        content = self.analysis_page.AnalysisPageContent()
        calls = []
        content.runAnalysisRequested.connect(lambda: calls.append("run"))
        content.clearAnalysisRequested.connect(lambda: calls.append("clear"))

        content.run_analysis_button.clicked.emit()
        content.clear_analysis_button.clicked.emit()

        self.assertEqual(calls, ["run", "clear"])

    def test_installs_only_on_analysis_wizard_page_body(self):
        analysis_spec = next(
            spec for spec in build_default_workflow_page_specs() if spec.key == "analysis"
        )
        analysis_page = self.wizard_page.WizardPage(analysis_spec)

        content = self.analysis_page.install_analysis_page_content(analysis_page)

        self.assertIs(analysis_page.body_layout().widgets[-1], content)

    def test_rejects_installing_on_other_wizard_page(self):
        map_spec = next(
            spec for spec in build_default_workflow_page_specs() if spec.key == "map"
        )
        map_page = self.wizard_page.WizardPage(map_spec)

        with self.assertRaisesRegex(ValueError, "analysis wizard page"):
            self.analysis_page.install_analysis_page_content(map_page)


if __name__ == "__main__":
    unittest.main()
