import importlib
import sys
import unittest

from tests import _path  # noqa: F401


class ApplicationProgressExportTests(unittest.TestCase):
    def test_package_import_defers_wizard_progress_compatibility_exports(self):
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

            self.assertNotIn("qfit.ui.application.wizard_progress", sys.modules)

            from qfit.ui.application import (  # noqa: PLC0415
                WizardProgressFacts,
                build_startup_wizard_progress_facts,
                build_wizard_progress_facts_from_runtime_state,
                build_wizard_progress_from_facts,
                build_wizard_progress_from_facts_and_settings,
            )

            wizard_progress = importlib.import_module(
                "qfit.ui.application.wizard_progress"
            )
            compat_exports = {
                "WizardProgressFacts": WizardProgressFacts,
                "build_startup_wizard_progress_facts": (
                    build_startup_wizard_progress_facts
                ),
                "build_wizard_progress_facts_from_runtime_state": (
                    build_wizard_progress_facts_from_runtime_state
                ),
                "build_wizard_progress_from_facts": build_wizard_progress_from_facts,
                "build_wizard_progress_from_facts_and_settings": (
                    build_wizard_progress_from_facts_and_settings
                ),
            }
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


if __name__ == "__main__":
    unittest.main()
