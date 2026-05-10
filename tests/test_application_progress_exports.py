import importlib
import sys
import unittest

from tests import _path  # noqa: F401


class ApplicationProgressExportTests(unittest.TestCase):
    def test_package_import_routes_wizard_aliases_through_workflow_exports(self):
        saved_modules = {
            name: module
            for name, module in sys.modules.items()
            if name == "qfit.ui.application"
            or name.startswith("qfit.ui.application.")
        }
        ui_package = importlib.import_module("qfit.ui")
        missing = object()
        saved_application = getattr(ui_package, "application", missing)
        for name in saved_modules:
            sys.modules.pop(name, None)
        if hasattr(ui_package, "application"):
            delattr(ui_package, "application")

        try:
            app = importlib.import_module("qfit.ui.application")

            for module_name in (
                "qfit.ui.application.wizard_filter_summary",
                "qfit.ui.application.wizard_footer_status",
                "qfit.ui.application.wizard_page_specs",
                "qfit.ui.application.wizard_progress",
                "qfit.ui.application.wizard_settings",
            ):
                with self.subTest(module_name=module_name):
                    self.assertNotIn(module_name, sys.modules)

            local_first_filter = importlib.import_module(
                "qfit.ui.application.local_first_filter_summary"
            )
            workflow_footer = importlib.import_module(
                "qfit.ui.application.workflow_footer_status"
            )
            workflow_pages = importlib.import_module(
                "qfit.ui.application.workflow_page_specs"
            )
            workflow_settings = importlib.import_module(
                "qfit.ui.application.workflow_settings"
            )

            eager_alias_names = (
                "DockWizardPageSpec",
                "DockWizardProgress",
                "WIZARD_STEP_COUNT",
                "WIZARD_VERSION",
                "WIZARD_VERSION_KEY",
                "WIZARD_WORKFLOW_STEPS",
                "WizardFooterFacts",
                "WizardSettingsSnapshot",
                "build_default_wizard_page_specs",
                "build_initial_wizard_step_statuses",
                "build_progress_wizard_step_statuses",
                "build_wizard_filter_description",
                "build_wizard_footer_facts_from_progress_facts",
                "build_wizard_footer_status",
                "build_wizard_step_statuses",
                "clamp_wizard_step_index",
                "ensure_wizard_settings",
                "load_wizard_settings",
                "preferred_current_key_from_settings",
                "save_last_step_index",
                "wizard_step_key_for_index",
            )
            for name in eager_alias_names:
                with self.subTest(eager_alias=name):
                    self.assertNotIn(name, app.__dict__)

            self.assertIs(
                app.DockWizardPageSpec,
                workflow_pages.DockWorkflowPageSpec,
            )
            self.assertIs(
                app.WizardFooterFacts,
                workflow_footer.WorkflowFooterFacts,
            )
            self.assertIs(
                app.WizardSettingsSnapshot,
                workflow_settings.WorkflowSettingsSnapshot,
            )
            self.assertIs(
                app.build_default_wizard_page_specs,
                workflow_pages.build_default_workflow_page_specs,
            )
            self.assertIs(
                app.build_wizard_filter_description,
                local_first_filter.build_local_first_filter_description,
            )
            self.assertIs(
                app.build_wizard_footer_facts_from_progress_facts,
                workflow_footer.build_workflow_footer_facts_from_progress_facts,
            )
            self.assertIs(
                app.build_wizard_footer_status,
                workflow_footer.build_workflow_footer_status,
            )

            for module_name in (
                "qfit.ui.application.wizard_filter_summary",
                "qfit.ui.application.wizard_footer_status",
                "qfit.ui.application.wizard_page_specs",
                "qfit.ui.application.wizard_progress",
                "qfit.ui.application.wizard_settings",
            ):
                with self.subTest(module_name=module_name):
                    self.assertNotIn(module_name, sys.modules)

            progress_export_names = (
                "WizardProgressFacts",
                "build_startup_wizard_progress_facts",
                "build_wizard_progress_facts_from_runtime_state",
                "build_wizard_progress_from_facts",
                "build_wizard_progress_from_facts_and_settings",
            )
            wizard_compat_export_names = (
                "DockWizardPageSpec",
                "DockWizardProgress",
                "WIZARD_STEP_COUNT",
                "WIZARD_VERSION",
                "WIZARD_VERSION_KEY",
                "WIZARD_WORKFLOW_STEPS",
                "WizardFooterFacts",
                "WizardSettingsSnapshot",
                "build_default_wizard_page_specs",
                "build_initial_wizard_step_statuses",
                "build_progress_wizard_step_statuses",
                "build_wizard_filter_description",
                "build_wizard_footer_facts_from_progress_facts",
                "build_wizard_footer_status",
                "build_wizard_step_statuses",
                "clamp_wizard_step_index",
                "ensure_wizard_settings",
                "load_wizard_settings",
                "preferred_current_key_from_settings",
                "save_last_step_index",
                "wizard_step_key_for_index",
                *progress_export_names,
            )
            for name in wizard_compat_export_names:
                with self.subTest(name=name):
                    self.assertNotIn(name, app.__all__)

            compat_exports = {
                name: getattr(app, name) for name in progress_export_names
            }
            wizard_progress = importlib.import_module(
                "qfit.ui.application.wizard_progress"
            )
            for name, value in compat_exports.items():
                with self.subTest(name=name):
                    self.assertIs(value, getattr(wizard_progress, name))
                    self.assertIs(getattr(app, name), value)
        finally:
            for name in list(sys.modules):
                if name == "qfit.ui.application" or name.startswith(
                    "qfit.ui.application."
                ):
                    sys.modules.pop(name, None)
            sys.modules.update(saved_modules)
            if saved_application is missing:
                if hasattr(ui_package, "application"):
                    delattr(ui_package, "application")
            else:
                setattr(ui_package, "application", saved_application)


    def test_lazy_wizard_alias_reports_missing_canonical_target_as_attribute_error(self):
        app = importlib.import_module("qfit.ui.application")
        app._WIZARD_COMPAT_ALIAS_TARGETS["BrokenWizardAlias"] = (
            "MissingWorkflowAlias"
        )
        try:
            self.assertFalse(hasattr(app, "BrokenWizardAlias"))
            with self.assertRaisesRegex(
                AttributeError,
                "BrokenWizardAlias.*MissingWorkflowAlias",
            ):
                app.__getattr__("BrokenWizardAlias")
        finally:
            app._WIZARD_COMPAT_ALIAS_TARGETS.pop("BrokenWizardAlias", None)
            app.__dict__.pop("BrokenWizardAlias", None)


if __name__ == "__main__":
    unittest.main()
