import ast
import pathlib
import unittest

from tests import _path  # noqa: F401

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _import_targets(relative_path: str) -> set[str]:
    path = REPO_ROOT / relative_path
    tree = ast.parse(path.read_text(), filename=str(path))
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = ('.' * node.level) + (node.module or '')
            for alias in node.names:
                if alias.name == '*':
                    targets.add(base)
                elif base:
                    targets.add(f"{base}.{alias.name}")
                else:
                    targets.add(alias.name)
    return targets


class CoreModuleBoundaryTests(unittest.TestCase):
    CORE_MODULES = [
        "activities/domain/activity_classification.py",
        "activities/domain/activity_query.py",
        "activities/domain/models.py",
        "map_style.py",
        "polyline_utils.py",
        "providers/domain/provider.py",
        "qfit_cache.py",
        "temporal_config.py",
        "time_utils.py",
        "atlas/profile_renderer.py",
        "atlas/publish_atlas.py",
    ]

    FORBIDDEN_PREFIXES = (
        "qgis",
        ".qfit_dockwidget",
        ".qfit_plugin",
        ".qfit_config_dialog",
    )

    def test_provider_neutral_core_modules_do_not_import_qgis_or_ui_modules(self):
        offenders = {}
        for relative_path in self.CORE_MODULES:
            forbidden = sorted(
                target
                for target in _import_targets(relative_path)
                if target.startswith(self.FORBIDDEN_PREFIXES)
            )
            if forbidden:
                offenders[relative_path] = forbidden
        self.assertEqual(
            {},
            offenders,
            f"Provider-neutral core modules should stay free of QGIS/UI imports: {offenders}",
        )


class WorkflowBoundaryTests(unittest.TestCase):
    WORKFLOW_MODULES = [
        "activities/application/fetch_result_service.py",
        "activities/application/fetch_task.py",
        "activities/application/load_workflow.py",
        "activities/application/sync_controller.py",
        "atlas/export_controller.py",
        "background_map_controller.py",
        "visual_apply.py",
    ]

    FORBIDDEN_UI_IMPORTS = (
        ".qfit_dockwidget",
        ".qfit_plugin",
        ".qfit_config_dialog",
    )

    def test_workflow_modules_do_not_import_ui_modules(self):
        offenders = {}
        for relative_path in self.WORKFLOW_MODULES:
            forbidden = sorted(
                target
                for target in _import_targets(relative_path)
                if target.startswith(self.FORBIDDEN_UI_IMPORTS)
            )
            if forbidden:
                offenders[relative_path] = forbidden
        self.assertEqual(
            {},
            offenders,
            f"Workflow modules should not depend on UI modules directly: {offenders}",
        )

    def test_atlas_package_init_does_not_import_qgis_heavy_export_task(self):
        imports = _import_targets("atlas/__init__.py")
        self.assertNotIn(
            ".export_task",
            imports,
            "qfit.atlas package import should stay usable without pulling in QGIS-heavy export_task",
        )


if __name__ == "__main__":
    unittest.main()
