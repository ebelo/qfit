"""Probe test: resolve class-scope and module-scope Qt enums against the real binding.

This test exists because qfit uses Qt enum members (``Qt.Horizontal``,
``QDockWidget.DockWidgetClosable``, etc.) at class-body and module scope.
In Qt 5 these are flat attributes; in Qt 6 they moved under nested enum
classes.  A broad ``try/except`` import guard in other test modules can
silently swallow the resulting ``AttributeError`` into a skip, hiding real
crashes from the test suite.

This probe runs unconditionally (no skip guard) so that import-surface
Qt enum failures are caught immediately on both Qt 5 and Qt 6.
"""

import unittest

from tests import _path  # noqa: F401


def _import_qt():
    """Import the Qt binding qfit actually uses, or skip if unavailable."""
    try:
        from qgis.PyQt.QtCore import Qt, QStandardPaths
        from qgis.PyQt.QtGui import QImage
        from qgis.PyQt.QtWidgets import (
            QDockWidget,
            QFormLayout,
            QFrame,
            QSizePolicy,
            QToolButton,
            QDialogButtonBox,
        )
    except Exception:
        try:
            from PyQt5.QtCore import Qt, QStandardPaths
            from PyQt5.QtGui import QImage
            from PyQt5.QtWidgets import (
                QDockWidget,
                QFormLayout,
                QFrame,
                QSizePolicy,
                QToolButton,
                QDialogButtonBox,
            )
        except Exception:
            try:
                from PyQt6.QtCore import Qt, QStandardPaths
                from PyQt6.QtGui import QImage
                from PyQt6.QtWidgets import (
                    QDockWidget,
                    QFormLayout,
                    QFrame,
                    QSizePolicy,
                    QToolButton,
                    QDialogButtonBox,
                )
            except Exception:
                raise unittest.SkipTest("No Qt binding available")
    return (
        Qt,
        QStandardPaths,
        QDockWidget,
        QFormLayout,
        QFrame,
        QImage,
        QSizePolicy,
        QToolButton,
        QDialogButtonBox,
    )


(
    Qt,
    QStandardPaths,
    QDockWidget,
    QFormLayout,
    QFrame,
    QImage,
    QSizePolicy,
    QToolButton,
    QDialogButtonBox,
) = _import_qt()

# Every class-scope Qt enum used at class-body or function-call level in qfit source.
# Each entry: (class, enum_name, member_name)
# Update this list when adding new class-scope Qt enum references.
CLASS_SCOPE_ENUMS = [
    (QDockWidget, "DockWidgetFeature", "DockWidgetClosable"),
    (QDockWidget, "DockWidgetFeature", "DockWidgetMovable"),
    (QDockWidget, "DockWidgetFeature", "DockWidgetFloatable"),
    (QStandardPaths, "StandardLocation", "AppDataLocation"),
    (QFormLayout, "RowWrapPolicy", "WrapLongRows"),
    (QFrame, "Shape", "HLine"),
    (QFrame, "Shape", "VLine"),
    (QFrame, "Shape", "NoFrame"),
    (QFrame, "Shadow", "Plain"),
    (QImage, "Format", "Format_ARGB32"),
    (QSizePolicy, "Policy", "Expanding"),
    (QSizePolicy, "Policy", "Fixed"),
    (QSizePolicy, "Policy", "Ignored"),
    (QSizePolicy, "Policy", "Preferred"),
    (QToolButton, "ToolButtonPopupMode", "InstantPopup"),
    (QDialogButtonBox, "StandardButton", "Save"),
    (QDialogButtonBox, "StandardButton", "Close"),
]

# Every module-scope Qt enum used at module/class-body level via qt_enum_value.
# Each entry: (qt_module, enum_name, member_name)
MODULE_SCOPE_ENUMS = [
    ("AlignmentFlag", "AlignLeft"),
    ("AlignmentFlag", "AlignRight"),
    ("AlignmentFlag", "AlignTop"),
    ("AlignmentFlag", "AlignVCenter"),
    ("AlignmentFlag", "AlignCenter"),
    ("CheckState", "Checked"),
    ("GlobalColor", "white"),
    ("CheckState", "Unchecked"),
    ("CursorShape", "ForbiddenCursor"),
    ("CursorShape", "PointingHandCursor"),
    ("CursorShape", "WhatsThisCursor"),
    ("DockWidgetArea", "LeftDockWidgetArea"),
    ("DockWidgetArea", "RightDockWidgetArea"),
    ("FocusPolicy", "StrongFocus"),
    ("FocusPolicy", "NoFocus"),
    ("ItemDataRole", "UserRole"),
    ("ItemFlag", "ItemIsUserCheckable"),
    ("Key", "Key_Enter"),
    ("Key", "Key_Return"),
    ("Key", "Key_Space"),
    ("MouseButton", "LeftButton"),
    ("Orientation", "Horizontal"),
    ("PenStyle", "DashLine"),
    ("PenCapStyle", "RoundCap"),
    ("PenJoinStyle", "RoundJoin"),
    ("TextInteractionFlag", "TextBrowserInteraction"),
    ("TextInteractionFlag", "TextSelectableByMouse"),
    ("ToolButtonStyle", "ToolButtonTextBesideIcon"),
]


class QtClassEnumProbeTest(unittest.TestCase):
    """Verify class-scope Qt enums resolve on the real binding."""

    def test_class_scope_enums_resolve(self):
        for cls, enum_name, member_name in CLASS_SCOPE_ENUMS:
            with self.subTest(cls=cls.__name__, member=member_name):
                # Try flat (Qt 5) then nested (Qt 6)
                direct = getattr(cls, member_name, None)
                if direct is not None:
                    continue
                enum_type = getattr(cls, enum_name, None)
                nested = getattr(enum_type, member_name, None) if enum_type else None
                self.assertIsNotNone(
                    nested,
                    f"{cls.__name__}.{member_name} not found as flat or "
                    f"{cls.__name__}.{enum_name}.{member_name}",
                )


class QtModuleEnumProbeTest(unittest.TestCase):
    """Verify module-scope Qt enums resolve on the real binding."""

    def test_module_scope_enums_resolve(self):
        for enum_name, member_name in MODULE_SCOPE_ENUMS:
            with self.subTest(enum=enum_name, member=member_name):
                # Try flat (Qt 5) then nested (Qt 6)
                direct = getattr(Qt, member_name, None)
                if direct is not None:
                    continue
                enum_type = getattr(Qt, enum_name, None)
                nested = getattr(enum_type, member_name, None) if enum_type else None
                self.assertIsNotNone(
                    nested,
                    f"Qt.{member_name} not found as flat or "
                    f"Qt.{enum_name}.{member_name}",
                )


if __name__ == "__main__":
    unittest.main()