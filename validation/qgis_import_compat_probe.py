#!/usr/bin/env python3
"""Report eager qfit imports that would fail before runtime compatibility code runs."""

from __future__ import annotations

import argparse
import ast
import pathlib

from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    ".github",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "debug",
    "dist",
    "docs",
    "scripts",
    "tests",
    "validation",
    "validation_artifacts",
}
MATCH_NODE = getattr(ast, "Match", None)


@dataclass(frozen=True)
class ImportRef:
    relative_path: str
    line: int
    module: str
    names: tuple[str, ...]


def _should_scan(path: pathlib.Path, root: pathlib.Path) -> bool:
    if path.suffix != ".py":
        return False
    relative = path.relative_to(root)
    return not any(part in EXCLUDED_DIRS for part in relative.parts)


def _qgis_import_from_node(relative_path: str, node: ast.AST) -> ImportRef | None:
    if isinstance(node, ast.Import):
        names = tuple(alias.name for alias in node.names if alias.name == "qgis" or alias.name.startswith("qgis."))
        if names:
            return ImportRef(
                relative_path=relative_path,
                line=node.lineno,
                module="import",
                names=names,
            )
    if isinstance(node, ast.ImportFrom) and node.module and (
        node.module == "qgis" or node.module.startswith("qgis.")
    ):
        return ImportRef(
            relative_path=relative_path,
            line=node.lineno,
            module=node.module,
            names=tuple(alias.name for alias in node.names),
        )
    return None


def _nested_statement_blocks(statement: ast.stmt) -> list[list[ast.stmt]]:
    if isinstance(statement, ast.Try):
        return [
            statement.body,
            *(handler.body for handler in statement.handlers),
            statement.orelse,
            statement.finalbody,
        ]
    if isinstance(statement, ast.If):
        return [statement.body, statement.orelse]
    if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While)):
        return [statement.body, getattr(statement, "orelse", [])]
    if MATCH_NODE is not None and isinstance(statement, MATCH_NODE):
        return [case.body for case in statement.cases]
    if isinstance(statement, ast.ClassDef):
        return [statement.body]
    return []


def _module_scope_imports(tree: ast.Module, relative_path: str) -> list[ImportRef]:
    refs: list[ImportRef] = []
    pending_blocks = [tree.body]
    while pending_blocks:
        for statement in pending_blocks.pop():
            ref = _qgis_import_from_node(relative_path, statement)
            if ref is not None:
                refs.append(ref)
                continue
            pending_blocks.extend(_nested_statement_blocks(statement))
    return refs


def collect_eager_qgis_imports(root: pathlib.Path = ROOT) -> list[ImportRef]:
    refs: list[ImportRef] = []
    for path in sorted(root.rglob("*.py")):
        if not _should_scan(path, root):
            continue
        relative_path = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        refs.extend(_module_scope_imports(tree, relative_path))
    return refs


def render_report(refs: list[ImportRef]) -> str:
    grouped: dict[str, list[ImportRef]] = {}
    for ref in refs:
        grouped.setdefault(ref.relative_path, []).append(ref)

    lines = [
        "QGIS import compatibility probe",
        f"Packaged Python modules with eager qgis imports: {len(grouped)}",
        f"Total eager qgis import statements: {len(refs)}",
        "",
    ]
    for relative_path, file_refs in grouped.items():
        lines.append(relative_path)
        for ref in file_refs:
            names = ", ".join(ref.names)
            lines.append(f"  line {ref.line}: {ref.module} -> {names}")
    lines.extend(
        [
            "",
            "Assessment:",
            "- Runtime branching cannot protect module-scope imports if QGIS 4 removes the imported module or symbol.",
            "- Lazy imports or a QGIS-major-specific package can protect those paths before plugin load.",
            "- API behavior changes after import are adapter problems, not package-splitting problems.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=ROOT,
        help="Repository root to scan. Defaults to the qfit checkout.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    refs = collect_eager_qgis_imports(args.root)
    print(render_report(refs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
