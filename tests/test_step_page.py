import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules


def _load_step_page_module():
    for name in (
        "qfit.ui.dockwidget.step_page",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.step_page")


class StepPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.step_page = _load_step_page_module()

    def test_builds_spec_step_chrome_with_header_content_and_nav(self):
        page = self.step_page.StepPage(
            2,
            5,
            "Synchronisation des activités",
            "Récupération depuis Strava vers un GeoPackage.",
        )

        self.assertEqual(page.objectName(), "qfitWizardStepPage")
        self.assertEqual(page.step_label.text(), "ÉTAPE 2/5")
        self.assertEqual(page.title_label.text(), "Synchronisation des activités")
        self.assertEqual(
            page.subtitle_label.text(),
            "Récupération depuis Strava vers un GeoPackage.",
        )
        self.assertEqual(page.content_container.objectName(), "qfitWizardStepContent")
        self.assertEqual(page.content_layout().contents_margins, (0, 0, 0, 0))
        self.assertEqual(page.back_button.text(), "Précédent")
        self.assertEqual(page.back_button.property("wizardActionRole"), "back")
        self.assertEqual(page.next_button.text(), "Suivant →")
        self.assertEqual(page.next_button.property("wizardActionRole"), "primary")
        self.assertFalse(page.status_pill.isVisible())

    def test_status_pill_can_be_shown_and_hidden_with_tone(self):
        page = self.step_page.StepPage(1, 5, "Connexion", "Configure qfit.")

        page.set_status("Connecté", tone="ok")

        self.assertTrue(page.status_pill.isVisible())
        self.assertEqual(page.status_pill.text(), "Connecté")
        self.assertEqual(page.status_pill.property("tone"), "ok")

        page.set_status("  ")

        self.assertFalse(page.status_pill.isVisible())
        self.assertEqual(page.status_pill.text(), "")
        self.assertEqual(page.status_pill.property("tone"), "muted")

    def test_navigation_buttons_emit_dedicated_step_signals(self):
        calls = []
        page = self.step_page.StepPage(3, 5, "Carte", "Charge les couches.")
        page.backRequested.connect(lambda: calls.append("back"))
        page.nextRequested.connect(lambda: calls.append("next"))

        page.back_button.clicked.emit()
        page.next_button.clicked.emit()

        self.assertEqual(calls, ["back", "next"])

    def test_next_and_back_configuration_updates_roles_and_availability(self):
        page = self.step_page.StepPage(4, 5, "Analyse", "Calcule les sorties.")

        page.set_next("Lancer l'analyse", icon="", primary=False, enabled=False)
        page.set_back("Retour", enabled=False)

        self.assertEqual(page.next_button.text(), "Lancer l'analyse")
        self.assertFalse(page.next_button.isEnabled())
        self.assertEqual(page.next_button.property("wizardActionRole"), "secondary")
        self.assertEqual(page.back_button.text(), "Retour")
        self.assertFalse(page.back_button.isEnabled())

    def test_content_and_extra_buttons_are_extensible_for_concrete_pages(self):
        page = self.step_page.StepPage(5, 5, "Atlas PDF", "Configure l'export.")
        extra_button = self.step_page.QToolButton(page)
        content_widget = self.step_page.QWidget(page)

        page.add_extra_button(extra_button)
        page.content_layout().addWidget(content_widget)

        self.assertEqual(extra_button.property("wizardActionRole"), "extra")
        self.assertIn(extra_button, page._extra_right_layout.widgets)
        self.assertIn(content_widget, page.content_layout().widgets)

    def test_extra_button_alignment_can_target_left_nav_cluster(self):
        page = self.step_page.StepPage(1, 5, "Connexion", "Configure qfit.")
        extra_button = self.step_page.QToolButton(page)

        page.add_extra_button(extra_button, align="left")

        self.assertIn(extra_button, page._extra_left_layout.widgets)
        self.assertNotIn(extra_button, page._extra_right_layout.widgets)

    def test_rejects_unknown_extra_button_alignment(self):
        page = self.step_page.StepPage(1, 5, "Connexion", "Configure qfit.")

        with self.assertRaisesRegex(ValueError, "align must be 'left' or 'right'"):
            page.add_extra_button(self.step_page.QToolButton(page), align="center")


if __name__ == "__main__":
    unittest.main()
