import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.wizard_page_specs import build_default_wizard_page_specs
from qfit.ui.tokens import COLOR_MUTED


def _load_atlas_modules():
    for name in (
        "qfit.ui.dockwidget.atlas_page",
        "qfit.ui.dockwidget.wizard_page",
        "qfit.ui.dockwidget.action_row",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return (
            importlib.import_module("qfit.ui.dockwidget.atlas_page"),
            importlib.import_module("qfit.ui.dockwidget.wizard_page"),
        )


class AtlasPageContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atlas_page, cls.wizard_page = _load_atlas_modules()

    def test_builds_default_fifth_page_content(self):
        content = self.atlas_page.AtlasPageContent()

        self.assertEqual(content.objectName(), "qfitWizardAtlasPageContent")
        self.assertEqual(content.status_label.objectName(), "qfitWizardAtlasStatus")
        self.assertEqual(content.status_label.text(), "Atlas PDF not exported yet")
        self.assertEqual(content.status_label.property("atlasState"), "not_ready")
        self.assertEqual(content.status_label.property("tone"), "warn")
        self.assertEqual(content.detail_label.objectName(), "qfitWizardAtlasDetail")
        self.assertIn("PDF title", content.detail_label.text())
        self.assertIn(COLOR_MUTED, content.detail_label.styleSheet())
        self.assertEqual(
            content.input_summary_label.objectName(),
            "qfitWizardAtlasInputSummary",
        )
        self.assertEqual(
            content.input_summary_label.text(),
            "No atlas layer selected for export",
        )
        self.assertIn(COLOR_MUTED, content.input_summary_label.styleSheet())
        self.assertEqual(
            content.output_summary_label.objectName(),
            "qfitWizardAtlasOutputSummary",
        )
        self.assertEqual(
            content.output_summary_label.text(),
            "PDF output path will be chosen before generation",
        )
        self.assertIn(COLOR_MUTED, content.output_summary_label.styleSheet())
        self.assertEqual(content.title_label.objectName(), "qfitWizardAtlasTitleLabel")
        self.assertEqual(content.title_label.text(), "Atlas title")
        self.assertEqual(
            content.title_line_edit.objectName(),
            "qfitWizardAtlasTitleLineEdit",
        )
        self.assertEqual(content.title_line_edit.text(), "qfit Activity Atlas")
        self.assertEqual(
            content.subtitle_label.objectName(),
            "qfitWizardAtlasSubtitleLabel",
        )
        self.assertEqual(content.subtitle_label.text(), "Atlas subtitle")
        self.assertEqual(
            content.subtitle_line_edit.objectName(),
            "qfitWizardAtlasSubtitleLineEdit",
        )
        self.assertEqual(content.subtitle_line_edit.placeholderText(), "Optional subtitle…")
        self.assertEqual(
            content.export_atlas_button.objectName(),
            "qfitWizardAtlasExportButton",
        )
        self.assertEqual(content.export_atlas_button.text(), "Export atlas PDF")
        self.assertEqual(
            content.export_atlas_button.property("primaryAction"),
            "export_atlas_pdf",
        )
        self.assertEqual(
            content.export_atlas_button.property("wizardActionRole"),
            "primary",
        )
        self.assertFalse(content.export_atlas_button.isEnabled())
        self.assertEqual(
            content.export_atlas_button.property("wizardActionAvailability"),
            "blocked",
        )
        self.assertIn("Load activity layers", content.export_atlas_button.toolTip())
        self.assertEqual(content.action_row.objectName(), "qfitWizardAtlasActionRow")
        self.assertEqual(
            content.action_row.outer_layout().widgets,
            [content.export_atlas_button],
        )
        self.assertEqual(
            content.outer_layout().widgets,
            [
                content.status_label,
                content.detail_label,
                content.title_label,
                content.title_line_edit,
                content.subtitle_label,
                content.subtitle_line_edit,
                content.input_summary_label,
                content.output_summary_label,
                content.action_row,
            ],
        )

    def test_can_seed_and_update_visible_document_settings(self):
        content = self.atlas_page.AtlasPageContent(
            atlas_title="Spring Atlas",
            atlas_subtitle="Road and trail",
        )

        self.assertEqual(content.title_line_edit.text(), "Spring Atlas")
        self.assertEqual(content.subtitle_line_edit.text(), "Road and trail")

        content.set_document_settings(
            atlas_title="Summer Atlas",
            atlas_subtitle="Gravel rides",
        )

        self.assertEqual(content.title_line_edit.text(), "Summer Atlas")
        self.assertEqual(content.subtitle_line_edit.text(), "Gravel rides")

    def test_document_settings_emit_when_user_edits_fields(self):
        content = self.atlas_page.AtlasPageContent()
        calls = []
        content.atlasDocumentSettingsChanged.connect(
            lambda title, subtitle: calls.append((title, subtitle))
        )

        content.title_line_edit.setText("Custom Atlas")
        content.subtitle_line_edit.setText("April 2026")

        self.assertEqual(
            calls,
            [
                ("Custom Atlas", ""),
                ("Custom Atlas", "April 2026"),
            ],
        )

    def test_programmatic_document_settings_update_does_not_emit_user_change(self):
        content = self.atlas_page.AtlasPageContent()
        calls = []
        content.atlasDocumentSettingsChanged.connect(
            lambda title, subtitle: calls.append((title, subtitle))
        )

        content.set_document_settings(
            atlas_title="Saved Atlas",
            atlas_subtitle="Saved subtitle",
        )

        self.assertEqual(calls, [])

    def test_refreshes_ready_state_without_rebuilding(self):
        content = self.atlas_page.AtlasPageContent()
        state = self.atlas_page.AtlasPageState(
            ready=True,
            status_text="Atlas ready",
            detail_text="Export the filtered activity atlas to the selected PDF path.",
            input_summary_text="42 activities selected for atlas export",
            output_summary_text="/tmp/qfit-atlas.pdf · A4 landscape",
            primary_action_label="Refresh atlas PDF",
        )

        content.set_state(state)

        self.assertEqual(content.status_label.text(), "Atlas ready")
        self.assertEqual(content.status_label.property("atlasState"), "ready")
        self.assertEqual(content.status_label.property("tone"), "ok")
        self.assertEqual(
            content.detail_label.text(),
            "Export the filtered activity atlas to the selected PDF path.",
        )
        self.assertEqual(
            content.input_summary_label.text(),
            "42 activities selected for atlas export",
        )
        self.assertEqual(content.input_summary_label.property("atlasState"), "ready")
        self.assertEqual(
            content.output_summary_label.text(),
            "/tmp/qfit-atlas.pdf · A4 landscape",
        )
        self.assertEqual(content.output_summary_label.property("atlasState"), "ready")
        self.assertEqual(content.export_atlas_button.text(), "Refresh atlas PDF")
        self.assertTrue(content.export_atlas_button.isEnabled())
        self.assertEqual(
            content.export_atlas_button.property("wizardActionAvailability"),
            "available",
        )
        self.assertEqual(content.export_atlas_button.toolTip(), "")

    def test_can_override_export_availability(self):
        content = self.atlas_page.AtlasPageContent(
            self.atlas_page.AtlasPageState(
                ready=True,
                primary_action_enabled=False,
                primary_action_blocked_tooltip="Choose a PDF output path.",
            )
        )

        self.assertFalse(content.export_atlas_button.isEnabled())
        self.assertEqual(
            content.export_atlas_button.toolTip(),
            "Choose a PDF output path.",
        )

    def test_button_emits_reusable_page_signal(self):
        content = self.atlas_page.AtlasPageContent()
        calls = []
        content.exportAtlasRequested.connect(lambda: calls.append("export"))

        content.export_atlas_button.clicked.emit()

        self.assertEqual(calls, ["export"])

    def test_installs_only_on_atlas_wizard_page_body(self):
        atlas_spec = next(
            spec for spec in build_default_wizard_page_specs() if spec.key == "atlas"
        )
        atlas_page = self.wizard_page.WizardPage(atlas_spec)

        content = self.atlas_page.install_atlas_page_content(atlas_page)

        self.assertIs(atlas_page.body_layout().widgets[-1], content)

    def test_rejects_installing_on_other_wizard_page(self):
        analysis_spec = next(
            spec for spec in build_default_wizard_page_specs() if spec.key == "analysis"
        )
        analysis_page = self.wizard_page.WizardPage(analysis_spec)

        with self.assertRaisesRegex(ValueError, "atlas wizard page"):
            self.atlas_page.install_atlas_page_content(analysis_page)


if __name__ == "__main__":
    unittest.main()
