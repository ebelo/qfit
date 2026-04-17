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


def _module_scope_condition_value(node: ast.AST) -> bool | None:
    """Return a statically-known boolean value for simple module-scope guards."""

    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
        return False
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        if node.value.id == "typing" and node.attr == "TYPE_CHECKING":
            return False
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        operand = _module_scope_condition_value(node.operand)
        return None if operand is None else not operand
    return None


def _collect_module_scope_import_targets(tree: ast.AST) -> set[str]:
    """Return imports executed at module import time.

    This intentionally ignores imports nested inside functions/methods, so the
    test can distinguish eager module-scope coupling from lazy runtime imports.
    """

    targets: set[str] = set()

    def visit_statements(statements):
        for statement in statements:
            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    targets.add(alias.name)
            elif isinstance(statement, ast.ImportFrom):
                base = ('.' * statement.level) + (statement.module or '')
                for alias in statement.names:
                    if alias.name == '*':
                        targets.add(base)
                    elif base:
                        targets.add(f"{base}.{alias.name}")
                    else:
                        targets.add(alias.name)
            elif isinstance(statement, ast.Try):
                visit_statements(statement.body)
                visit_statements(statement.handlers)
                visit_statements(statement.orelse)
                visit_statements(statement.finalbody)
            elif isinstance(statement, ast.ExceptHandler):
                visit_statements(statement.body)
            elif isinstance(statement, ast.If):
                condition_value = _module_scope_condition_value(statement.test)
                if condition_value is True:
                    visit_statements(statement.body)
                elif condition_value is False:
                    visit_statements(statement.orelse)
                else:
                    visit_statements(statement.body)
                    visit_statements(statement.orelse)
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                visit_statements(statement.body)
            elif isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
                visit_statements(statement.body)
                visit_statements(statement.orelse)
            elif isinstance(statement, ast.Match):
                for case in statement.cases:
                    visit_statements(case.body)

    visit_statements(tree.body)
    return targets


def _module_scope_import_targets(relative_path: str) -> set[str]:
    path = REPO_ROOT / relative_path
    tree = ast.parse(path.read_text(), filename=str(path))
    return _collect_module_scope_import_targets(tree)


def _module_name_parts(relative_path: str) -> list[str]:
    parts = list(pathlib.Path(relative_path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ["qfit", *parts]


def _resolved_import_targets(relative_path: str) -> set[str]:
    resolved: set[str] = set()
    module_parts = _module_name_parts(relative_path)
    package_parts = module_parts
    if pathlib.Path(relative_path).stem != "__init__":
        package_parts = module_parts[:-1]

    for target in _import_targets(relative_path):
        level = len(target) - len(target.lstrip("."))
        if level == 0:
            resolved.add(target)
            continue

        remainder = target[level:]
        base_parts = package_parts[: len(package_parts) - (level - 1)]
        pieces = list(base_parts)
        if remainder:
            pieces.extend(remainder.split("."))
        resolved.add(".".join(pieces))
    return resolved


class CoreModuleBoundaryTests(unittest.TestCase):
    CORE_MODULES = [
        "activities/domain/activity_classification.py",
        "activities/domain/activity_query.py",
        "activities/domain/models.py",
        "visualization/map_style.py",
        "polyline_utils.py",
        "providers/domain/provider.py",
        "qfit_cache.py",
        "visualization/application/temporal_config.py",
        "time_utils.py",
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
        "atlas/export_service.py",
        "atlas/export_use_case.py",
        "visualization/application/background_map_controller.py",
        "visualization/application/visual_apply.py",
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


class PortBoundaryTests(unittest.TestCase):
    PORT_MODULES = [
        "atlas/export_runtime.py",
        "configuration/application/settings_port.py",
        "visualization/application/layer_gateway.py",
    ]

    FORBIDDEN_PREFIXES = (
        "qgis",
        ".qfit_dockwidget",
        ".qfit_plugin",
        ".qfit_config_dialog",
    )

    def test_port_modules_stay_free_of_qgis_and_ui_imports(self):
        offenders = {}
        for relative_path in self.PORT_MODULES:
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
            f"Port modules should stay QGIS/UI-free: {offenders}",
        )


class ModuleScopeImportBoundaryTests(unittest.TestCase):
    def test_atlas_export_service_does_not_eagerly_import_qgis_runtime_adapter(self):
        imports = _module_scope_import_targets("atlas/export_service.py")
        self.assertNotIn(
            ".qgis_export_runtime.QgisAtlasExportRuntime",
            imports,
            "AtlasExportService should obtain the QGIS runtime adapter lazily, not via module-scope imports.",
        )

    def test_atlas_cover_composer_keeps_export_task_import_lazy(self):
        imports = _module_scope_import_targets("atlas/cover_composer.py")
        self.assertFalse(
            any(target.startswith(".export_task") for target in imports),
            "AtlasCoverComposer should keep the heavy export_task dependency lazy at module scope.",
        )

    def test_dock_widget_does_not_import_qgis_export_runtime_directly(self):
        imports = _module_scope_import_targets("qfit_dockwidget.py")
        self.assertNotIn(
            ".atlas.qgis_export_runtime.QgisAtlasExportRuntime",
            imports,
            "QfitDockWidget should stay on the atlas use-case boundary instead of importing the QGIS export runtime directly.",
        )
        self.assertFalse(
            any(target.startswith(".atlas.export_task") for target in imports),
            "QfitDockWidget should not import from the QGIS-heavy atlas export task module at import time.",
        )

    def test_ui_dependency_builder_keeps_qgis_layer_gateway_import_lazy(self):
        imports = _module_scope_import_targets("ui/dockwidget_dependencies.py")
        self.assertNotIn(
            "..visualization.infrastructure.qgis_layer_gateway.QgisLayerGateway",
            imports,
            "Dock-widget dependency assembly should keep the QGIS layer gateway behind a lazy import seam.",
        )


class ModuleScopeImportScannerTests(unittest.TestCase):
    def _imports_from_source(self, source: str) -> set[str]:
        return _collect_module_scope_import_targets(ast.parse(source))

    def test_skips_imports_behind_type_checking_guard(self):
        imports = self._imports_from_source(
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    import qgis\n"
            "else:\n"
            "    import pathlib\n"
        )
        self.assertIn("pathlib", imports)
        self.assertNotIn("qgis", imports)

    def test_tracks_imports_in_other_module_scope_blocks(self):
        imports = self._imports_from_source(
            "with context():\n"
            "    import alpha\n"
            "for _item in items:\n"
            "    import beta\n"
            "while ready:\n"
            "    import gamma\n"
            "match state:\n"
            "    case 'x':\n"
            "        import delta\n"
        )
        self.assertEqual({"alpha", "beta", "gamma", "delta"}, imports)


class DeprecatedCompatibilityShimTests(unittest.TestCase):
    DEPRECATED_ROOT_SHIMS = {
        "activity_classification.py": "qfit.activities.domain.activity_classification",
        "activity_query.py": "qfit.activities.domain.activity_query",
        "models.py": "qfit.activities.domain.models",
    }

    FEATURE_ROOTS = (
        "activities",
        "analysis",
        "atlas",
        "configuration",
        "providers",
        "ui",
        "validation",
        "visualization",
    )

    def test_deprecated_root_shims_are_explicitly_marked(self):
        for relative_path, canonical_module in self.DEPRECATED_ROOT_SHIMS.items():
            source = (REPO_ROOT / relative_path).read_text()
            self.assertIn(
                "Deprecated compatibility shim",
                source,
                f"{relative_path} should clearly advertise its deprecated compatibility-shim status.",
            )
            self.assertIn(
                canonical_module,
                source,
                f"{relative_path} should point contributors at its canonical module.",
            )

    def test_feature_owned_modules_do_not_import_deprecated_root_shims(self):
        shim_prefixes = tuple(
            f"qfit.{pathlib.Path(relative_path).stem}"
            for relative_path in self.DEPRECATED_ROOT_SHIMS
        )
        offenders = {}

        for feature_root in self.FEATURE_ROOTS:
            for path in sorted((REPO_ROOT / feature_root).rglob("*.py")):
                relative_path = path.relative_to(REPO_ROOT).as_posix()
                forbidden = sorted(
                    target
                    for target in _resolved_import_targets(relative_path)
                    if target.startswith(shim_prefixes)
                )
                if forbidden:
                    offenders[relative_path] = forbidden

        self.assertEqual(
            {},
            offenders,
            "Feature-owned packages should import canonical package modules rather than deprecated root shims: "
            f"{offenders}",
        )


class PackageOwnershipBoundaryTests(unittest.TestCase):
    """Guardrails for where new code may live.

    The root-level Python module layer is transitional. New feature-owned code
    should land in packages such as ``activities/``, ``atlas/``, ``providers/``,
    ``visualization/``, ``ui/``, or ``validation/`` rather than adding more
    generic top-level modules.
    """

    ALLOWED_TOP_LEVEL_PYTHON_MODULES = {
        "__init__.py",
        "activity_classification.py",
        "activity_query.py",
        "detailed_route_strategy.py",
        "mapbox_config.py",
        "models.py",
        "polyline_utils.py",
        "qfit_cache.py",
        "qfit_config_dialog.py",
        "qfit_dockwidget.py",
        "qfit_plugin.py",
        "sync_repository.py",
        "time_utils.py",
    }

    def test_new_root_level_python_modules_require_explicit_ownership_review(self):
        root_modules = {path.name for path in REPO_ROOT.glob("*.py")}
        unexpected = sorted(root_modules - self.ALLOWED_TOP_LEVEL_PYTHON_MODULES)
        self.assertEqual(
            [],
            unexpected,
            "New root-level Python modules should not be added without explicit architecture review. "
            "Prefer feature-owned packages and update this allowlist only for justified exceptions: "
            f"{unexpected}",
        )


if __name__ == "__main__":
    unittest.main()
