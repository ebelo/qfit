import ast
from pathlib import Path
import unittest

from tests import _path  # noqa: F401

from qfit.ui.qt_enum_compat import (
    optional_qt_enum_value,
    qt_class_enum_value,
    qt_enum_value,
)


class _FlatQt:
    Horizontal = 1


class _NestedQt:
    class Orientation:
        Horizontal = 2


class QtEnumCompatTest(unittest.TestCase):
    def test_resolves_qt5_flat_enum_member(self):
        self.assertEqual(qt_enum_value(_FlatQt, "Orientation", "Horizontal"), 1)

    def test_resolves_qt6_nested_enum_member(self):
        self.assertEqual(qt_enum_value(_NestedQt, "Orientation", "Horizontal"), 2)

    def test_optional_resolver_returns_none_for_missing_member(self):
        self.assertIsNone(optional_qt_enum_value(_NestedQt, "FocusPolicy", "NoFocus"))


class _FlatDockWidget:
    DockWidgetClosable = 1
    DockWidgetMovable = 2
    DockWidgetFloatable = 4


class _NestedDockWidget:
    class DockWidgetFeature:
        DockWidgetClosable = 1
        DockWidgetMovable = 2
        DockWidgetFloatable = 4


class QtClassEnumCompatTest(unittest.TestCase):
    def test_resolves_qt5_flat_class_enum_member(self):
        self.assertEqual(
            qt_class_enum_value(_FlatDockWidget, "DockWidgetFeature", "DockWidgetClosable"),
            1,
        )

    def test_resolves_qt6_nested_class_enum_member(self):
        self.assertEqual(
            qt_class_enum_value(
                _NestedDockWidget, "DockWidgetFeature", "DockWidgetMovable"
            ),
            2,
        )

    def test_class_enum_raises_for_missing_member(self):
        with self.assertRaises(AttributeError):
            qt_class_enum_value(_NestedDockWidget, "DockWidgetFeature", "NoDock")


class QgisScopedEnumSourceTest(unittest.TestCase):
    def test_shipped_source_does_not_use_flagged_flat_qgis_enums(self):
        from qfit.scripts.package_plugin import should_include

        root = Path(__file__).resolve().parents[1]
        flagged = {
            "QgsTask": {"CanCancel"},
            "QgsSymbolLayer": {
                "PropertyName", "PropertySize", "PropertyStrokeWidth", "PropertyWidth",
            },
            "QgsWkbTypes": {"PointZ"},
            "QgsVectorFileWriter": {"NoError"},
            "QgsLayoutItemPicture": {"Zoom"},
            "QgsUnitTypes": {"LayoutMillimeters", "RenderMapUnits"},
            "QgsLayoutExporter": {"Success"},
            "QgsLayoutItemMap": {"Fixed"},
            "QgsTextBackgroundSettings": {"ShapeSVG", "SizeFixed"},
            "QgsSymbol": {"PropertyOpacity"},
            "QgsMapBoxGlStyleConverter": {"Success"},
        }
        violations = []
        for path in root.rglob("*.py"):
            if not should_include(path) or "vendor" in path.relative_to(root).parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.attr in flagged.get(node.value.id, ())
                ):
                    violations.append(f"{path.relative_to(root)}:{node.lineno}: {node.value.id}.{node.attr}")
        self.assertEqual(violations, [], "Use scoped PyQGIS enum members: " + ", ".join(violations))


if __name__ == "__main__":
    unittest.main()
