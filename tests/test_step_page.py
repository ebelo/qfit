import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.application.dock_workflow_sections import build_wizard_step_statuses
from qfit.ui.application.workflow_page_specs import build_default_workflow_page_specs


_STEP_PAGE_MODULES = (
    "qfit.ui.dockwidget.action_row",
    "qfit.ui.dockwidget.wizard_step_page",
    "qfit.ui.dockwidget.step_page",
    "qfit.ui.dockwidget.wizard_shell",
    "qfit.ui.dockwidget.stepper_bar",
    "qfit.ui.dockwidget",
)


def _clear_step_page_modules():
    for name in _STEP_PAGE_MODULES:
        sys.modules.pop(name, None)


def _load_only_step_page_module():
    _clear_step_page_modules()
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.step_page")


def _load_step_page_module():
    _clear_step_page_modules()
    with patch.dict(sys.modules, _fake_qt_modules()):
        step_page = importlib.import_module("qfit.ui.dockwidget.step_page")
        wizard_step_page = importlib.import_module("qfit.ui.dockwidget.wizard_step_page")
        wizard_shell = importlib.import_module("qfit.ui.dockwidget.wizard_shell")
        return step_page, wizard_step_page, wizard_shell


class _FakeSize:
    def __init__(self, width):
        self._width = width

    def width(self):
        return self._width


class _FakeResizeEvent:
    def __init__(self, width):
        self._size = _FakeSize(width)

    def size(self):
        return self._size


class StepPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.step_page, cls.wizard_step_page, cls.wizard_shell = _load_step_page_module()

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
        self.assertEqual(page.back_button.property("workflowActionRole"), "back")
        self.assertEqual(page.back_button.property("wizardActionRole"), "back")
        self.assertEqual(
            page.back_button.cursor().shape(),
            self.step_page.Qt.PointingHandCursor,
        )
        self.assertEqual(page.next_button.text(), "Suivant →")
        self.assertEqual(page.next_button.property("workflowActionRole"), "primary")
        self.assertEqual(page.next_button.property("wizardActionRole"), "primary")
        self.assertEqual(
            page.next_button.cursor().shape(),
            self.step_page.Qt.PointingHandCursor,
        )
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

        page.set_next(
            "Lancer l'analyse",
            primary=False,
            enabled=False,
            visible=False,
        )
        page.set_back("Retour", enabled=False)

        self.assertEqual(page.next_button.text(), "Lancer l'analyse")
        self.assertFalse(page.next_button.isEnabled())
        self.assertFalse(page.next_button.isVisible())
        self.assertEqual(page.next_button.property("workflowActionRole"), "secondary")
        self.assertEqual(page.next_button.property("wizardActionRole"), "secondary")
        self.assertEqual(page.back_button.text(), "Retour")
        self.assertFalse(page.back_button.isEnabled())
        self.assertEqual(page.back_button.property("workflowActionRole"), "back")

    def test_content_and_extra_buttons_are_extensible_for_concrete_pages(self):
        page = self.step_page.StepPage(5, 5, "Atlas PDF", "Configure l'export.")
        extra_button = self.step_page.QToolButton(page)
        content_widget = self.step_page.QWidget(page)

        page.add_extra_button(extra_button)
        page.content_layout().addWidget(content_widget)

        self.assertEqual(extra_button.property("workflowActionRole"), "extra")
        self.assertEqual(extra_button.property("wizardActionRole"), "extra")
        self.assertEqual(extra_button.minimumWidth(), 0)
        self.assertIn(extra_button, page._extra_right_layout.widgets)
        self.assertIn(content_widget, page.content_layout().widgets)

    def test_compacts_navigation_and_wraps_copy_for_narrow_docks(self):
        page = self.step_page.StepPage(
            4,
            5,
            "Spatial analysis with a long translated title",
            "Long helper copy should wrap instead of widening the dock.",
        )
        page.set_next("Lancer l'analyse spatiale détaillée", icon="")

        page.set_responsive_width(320)

        self.assertEqual(page.property("responsiveMode"), "narrow")
        self.assertEqual(page._nav_layout.direction, self.step_page.QBoxLayout.TopToBottom)
        self.assertEqual(page.outer_layout().contents_margins, (8, 10, 8, 10))
        self.assertTrue(page.title_label.word_wrap)
        self.assertTrue(page.subtitle_label.word_wrap)
        self.assertEqual(page.back_button.text(), "←")
        self.assertEqual(page.back_button.toolTip(), "Précédent")
        self.assertEqual(page.next_button.text(), "Lancer l'anal…")
        self.assertEqual(page.next_button.toolTip(), "Lancer l'analyse spatiale détaillée")
        self.assertEqual(page.next_button.minimumWidth(), 0)

        page.set_responsive_width(600)

        self.assertEqual(page.property("responsiveMode"), "wide")
        self.assertEqual(page._nav_layout.direction, self.step_page.QBoxLayout.LeftToRight)
        self.assertFalse(page.title_label.word_wrap)
        self.assertEqual(page.back_button.text(), "Précédent")
        self.assertEqual(page.back_button.toolTip(), "")
        self.assertEqual(page.next_button.text(), "Lancer l'analyse spatiale détaillée")
        self.assertEqual(page.next_button.toolTip(), "")

    def test_resize_event_drives_narrow_step_page_mode(self):
        page = self.step_page.StepPage(4, 5, "Analyse", "Calcule les sorties.")

        page.resizeEvent(_FakeResizeEvent(320))

        self.assertEqual(page.property("responsiveMode"), "narrow")
        self.assertEqual(page._nav_layout.direction, self.step_page.QBoxLayout.TopToBottom)

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

    def test_wizard_step_page_adapts_canonical_spec_to_step_chrome(self):
        spec = build_default_workflow_page_specs()[2]

        page = self.step_page.WizardStepPage(spec, step_num=3, step_total=5)

        self.assertIs(page.spec, spec)
        self.assertEqual(page.objectName(), "qfitWizardMapPage")
        self.assertEqual(page.step_label.text(), "ÉTAPE 3/5")
        self.assertEqual(page.title_label.objectName(), "qfitWizardMapPageTitle")
        self.assertIn("QLabel#qfitWizardMapPageTitle", page.title_label.styleSheet())
        self.assertEqual(page.summary_label.objectName(), "qfitWizardMapPageSummary")
        self.assertEqual(page.summary_label.text(), spec.summary)
        self.assertIn(
            "QLabel#qfitWizardMapPageSummary",
            page.summary_label.styleSheet(),
        )
        self.assertIs(page.body_container, page.content_container)
        self.assertEqual(page.body_container.objectName(), "qfitWizardMapPageBody")
        self.assertIs(page.body_layout(), page.content_layout())
        self.assertEqual(
            page.primary_hint_label.objectName(),
            "qfitWizardMapPagePrimaryHint",
        )
        self.assertEqual(
            page.primary_hint_label.property("workflowPlaceholderHint"),
            "retired",
        )
        self.assertEqual(
            page.primary_hint_label.property("wizardPlaceholderHint"),
            "retired",
        )
        self.assertFalse(page.primary_hint_label.isVisible())

    def test_wizard_step_page_retire_primary_hint_is_installer_compatible(self):
        spec = build_default_workflow_page_specs()[0]
        page = self.step_page.WizardStepPage(spec, step_num=1, step_total=5)

        page.primary_hint_label.setVisible(True)
        page.retire_primary_action_hint()

        self.assertEqual(page.primary_hint_label.text(), "")
        self.assertEqual(
            page.primary_hint_label.property("workflowPlaceholderHint"),
            "retired",
        )
        self.assertEqual(
            page.primary_hint_label.property("wizardPlaceholderHint"),
            "retired",
        )
        self.assertFalse(page.primary_hint_label.isVisible())

    def test_workflow_step_page_star_exports_only_canonical_workflow_names(self):
        spec = build_default_workflow_page_specs()[2]

        page = self.step_page.WorkflowStepPage(spec, step_num=3, step_total=5)

        self.assertEqual(page.objectName(), "qfitWizardMapPage")
        self.assertIn("WorkflowStepPage", self.step_page.__all__)
        self.assertIn("build_workflow_step_pages", self.step_page.__all__)
        self.assertIn("install_workflow_step_pages", self.step_page.__all__)
        self.assertIn("apply_workflow_step_page_statuses", self.step_page.__all__)
        for name in (
            "DockWizardPageSpec",
            "WizardStepPage",
            "build_default_wizard_page_specs",
            "build_wizard_step_pages",
            "install_wizard_step_pages",
            "apply_wizard_step_page_statuses",
        ):
            self.assertNotIn(name, self.step_page.__all__)

    def test_step_page_keeps_direct_wizard_named_compatibility_aliases(self):
        self.assertIs(self.step_page.WizardStepPage, self.step_page.WorkflowStepPage)
        self.assertIs(
            self.step_page.build_wizard_step_pages,
            self.step_page.build_workflow_step_pages,
        )
        self.assertIs(
            self.step_page.install_wizard_step_pages,
            self.step_page.install_workflow_step_pages,
        )
        self.assertIs(
            self.step_page.apply_wizard_step_page_statuses,
            self.step_page.apply_workflow_step_page_statuses,
        )

    def test_step_page_resolves_wizard_aliases_lazily(self):
        module = _load_only_step_page_module()
        alias_targets = module._WIZARD_COMPAT_ALIAS_TARGETS

        for name in alias_targets:
            with self.subTest(name=name):
                self.assertNotIn(name, module.__dict__)
                self.assertIs(getattr(module, name), getattr(module, alias_targets[name]))

    def test_lazy_wizard_alias_reports_missing_canonical_target_as_attribute_error(self):
        module = _load_only_step_page_module()
        module._WIZARD_COMPAT_ALIAS_TARGETS["BrokenWizardAlias"] = (
            "MissingWorkflowAlias"
        )
        try:
            self.assertFalse(hasattr(module, "BrokenWizardAlias"))
            with self.assertRaisesRegex(
                AttributeError,
                "BrokenWizardAlias.*MissingWorkflowAlias",
            ):
                module.__getattr__("BrokenWizardAlias")
        finally:
            module._WIZARD_COMPAT_ALIAS_TARGETS.pop("BrokenWizardAlias", None)

    def test_wizard_step_page_module_exports_compatibility_aliases(self):
        self.assertIs(
            self.wizard_step_page.WizardStepPage,
            self.step_page.WorkflowStepPage,
        )
        self.assertIs(
            self.wizard_step_page.build_wizard_step_pages,
            self.step_page.build_workflow_step_pages,
        )
        self.assertIs(
            self.wizard_step_page.install_wizard_step_pages,
            self.step_page.install_workflow_step_pages,
        )
        self.assertIs(
            self.wizard_step_page.apply_wizard_step_page_statuses,
            self.step_page.apply_workflow_step_page_statuses,
        )
        self.assertIn("WizardStepPage", self.wizard_step_page.__all__)
        self.assertIn("build_wizard_step_pages", self.wizard_step_page.__all__)
        self.assertIn("install_wizard_step_pages", self.wizard_step_page.__all__)
        self.assertIn("apply_wizard_step_page_statuses", self.wizard_step_page.__all__)
        for name in (
            "DockWorkflowPageSpec",
            "StepPage",
            "WorkflowStepPage",
            "apply_workflow_step_page_statuses",
            "build_default_workflow_page_specs",
            "build_workflow_step_pages",
            "install_workflow_step_pages",
        ):
            self.assertNotIn(name, self.wizard_step_page.__all__)

    def test_builds_wizard_step_pages_from_default_specs(self):
        pages = self.step_page.build_workflow_step_pages()

        self.assertEqual(
            [page.spec.key for page in pages],
            ["connection", "sync", "map", "analysis", "atlas"],
        )
        self.assertEqual(
            [page.step_label.text() for page in pages],
            ["ÉTAPE 1/5", "ÉTAPE 2/5", "ÉTAPE 3/5", "ÉTAPE 4/5", "ÉTAPE 5/5"],
        )

    def test_build_wizard_step_pages_preserves_explicit_empty_specs(self):
        pages = self.step_page.build_workflow_step_pages(specs=())

        self.assertEqual(pages, ())

    def test_applies_progress_status_pills_to_step_pages(self):
        pages = self.step_page.build_workflow_step_pages()
        statuses = build_wizard_step_statuses(
            current_key="map",
            completed_keys={"connection", "sync"},
            unlocked_keys={"analysis"},
        )

        self.step_page.apply_workflow_step_page_statuses(pages, statuses)

        self.assertEqual(
            [page.status_pill.text() for page in pages],
            ["Done", "Done", "", "Available", "Locked"],
        )
        self.assertEqual(
            [page.status_pill.property("tone") for page in pages],
            ["ok", "ok", "muted", "neutral", "muted"],
        )
        self.assertFalse(pages[2].status_pill.isVisible())
        self.assertTrue(
            all(page.status_pill.isVisible() for index, page in enumerate(pages) if index != 2)
        )

    def test_installs_wizard_step_pages_into_shell(self):
        shell = self.wizard_shell.WizardShell()

        pages = self.step_page.install_workflow_step_pages(shell)

        self.assertEqual(shell.page_count(), 5)
        self.assertEqual(shell.pages_stack.widgets, list(pages))

        shell.set_current_step(4)

        self.assertEqual(shell.pages_stack.currentIndex(), 4)


if __name__ == "__main__":
    unittest.main()
