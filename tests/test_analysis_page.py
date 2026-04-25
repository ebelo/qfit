import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.wizard_page_specs import build_default_wizard_page_specs


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
        self.assertEqual(content.detail_label.objectName(), "qfitWizardAnalysisDetail")
        self.assertIn("heatmaps", content.detail_label.text())
        self.assertEqual(
            content.input_summary_label.objectName(),
            "qfitWizardAnalysisInputSummary",
        )
        self.assertEqual(
            content.input_summary_label.text(),
            "No loaded activity layers available for analysis",
        )
        self.assertEqual(
            content.result_summary_label.objectName(),
            "qfitWizardAnalysisResultSummary",
        )
        self.assertEqual(
            content.result_summary_label.text(),
            "Analysis outputs will appear in the project once generated",
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
        self.assertEqual(content.action_row.objectName(), "qfitWizardAnalysisActionRow")
        self.assertEqual(
            content.action_row.outer_layout().widgets,
            [content.run_analysis_button],
        )
        self.assertEqual(
            content.outer_layout().widgets,
            [
                content.status_label,
                content.detail_label,
                content.input_summary_label,
                content.result_summary_label,
                content.action_row,
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

    def test_button_emits_reusable_page_signal(self):
        content = self.analysis_page.AnalysisPageContent()
        calls = []
        content.runAnalysisRequested.connect(lambda: calls.append("run"))

        content.run_analysis_button.clicked.emit()

        self.assertEqual(calls, ["run"])

    def test_installs_only_on_analysis_wizard_page_body(self):
        analysis_spec = next(
            spec for spec in build_default_wizard_page_specs() if spec.key == "analysis"
        )
        analysis_page = self.wizard_page.WizardPage(analysis_spec)

        content = self.analysis_page.install_analysis_page_content(analysis_page)

        self.assertIs(analysis_page.body_layout().widgets[-1], content)

    def test_rejects_installing_on_other_wizard_page(self):
        map_spec = next(
            spec for spec in build_default_wizard_page_specs() if spec.key == "map"
        )
        map_page = self.wizard_page.WizardPage(map_spec)

        with self.assertRaisesRegex(ValueError, "analysis wizard page"):
            self.analysis_page.install_analysis_page_content(map_page)


if __name__ == "__main__":
    unittest.main()
