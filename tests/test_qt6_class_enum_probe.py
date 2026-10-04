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

import os
import unittest

from tests import _path  # noqa: F401


def _import_qt():
    """Import the Qt binding qfit actually uses, or skip if unavailable."""
    try:
        from qgis.PyQt.QtCore import Qt, QStandardPaths
        from qgis.PyQt.QtGui import QImage
        from qgis.PyQt.QtWidgets import (
            QBoxLayout,
            QDockWidget,
            QFormLayout,
            QFrame,
            QSizePolicy,
            QToolButton,
            QDialogButtonBox,
            QMessageBox,
        )
    except Exception:
        try:
            from PyQt5.QtCore import Qt, QStandardPaths
            from PyQt5.QtGui import QImage
            from PyQt5.QtWidgets import (
                QBoxLayout,
                QDockWidget,
                QFormLayout,
                QFrame,
                QSizePolicy,
                QToolButton,
                QDialogButtonBox,
                QMessageBox,
            )
        except Exception:
            try:
                from PyQt6.QtCore import Qt, QStandardPaths
                from PyQt6.QtGui import QImage
                from PyQt6.QtWidgets import (
                    QBoxLayout,
                    QDockWidget,
                    QFormLayout,
                    QFrame,
                    QSizePolicy,
                    QToolButton,
                    QDialogButtonBox,
                    QMessageBox,
                )
            except Exception:
                raise unittest.SkipTest("No Qt binding available")
    return (
        Qt,
        QStandardPaths,
        QBoxLayout,
        QDockWidget,
        QFormLayout,
        QFrame,
        QImage,
        QSizePolicy,
        QToolButton,
        QDialogButtonBox,
        QMessageBox,
    )


(
    Qt,
    QStandardPaths,
    QBoxLayout,
    QDockWidget,
    QFormLayout,
    QFrame,
    QImage,
    QSizePolicy,
    QToolButton,
    QDialogButtonBox,
    QMessageBox,
) = _import_qt()

# Every class-scope Qt enum used at class-body or function-call level in qfit source.
# Each entry: (class, enum_name, member_name)
# Update this list when adding new class-scope Qt enum references.
CLASS_SCOPE_ENUMS = [
    (QMessageBox, "StandardButton", "Yes"),
    (QMessageBox, "StandardButton", "No"),
    (QMessageBox, "StandardButton", "Ok"),
    (QBoxLayout, "Direction", "LeftToRight"),
    (QBoxLayout, "Direction", "TopToBottom"),
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
    ("PenStyle", "SolidLine"),
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


@unittest.skipUnless(os.environ.get("QFIT_REQUIRE_QGIS") == "1", "Native PyQGIS enum probe")
class QgisScopedEnumProbeTest(unittest.TestCase):
    def test_scoped_enums_preserve_values_on_real_binding(self):
        # Imports are mandatory in the native lanes: never hide binding failures.
        from qgis import core

        enums = (
            ("QgsTask", "Flag", "CanCancel"),
            ("QgsSymbolLayer", "Property", "PropertySize"),
            ("QgsWkbTypes", "Type", "PointZ"),
            ("QgsVectorFileWriter", "WriterError", "NoError"),
            ("QgsLayoutItemPicture", "ResizeMode", "Zoom"),
            ("QgsUnitTypes", "LayoutUnit", "LayoutMillimeters"),
            ("QgsLayoutExporter", "ExportResult", "Success"),
            ("QgsLayoutItemMap", "AtlasScalingMode", "Fixed"),
            ("QgsSymbolLayer", "Property", "PropertyName"),
            ("QgsTextBackgroundSettings", "ShapeType", "ShapeSVG"),
            ("QgsTextBackgroundSettings", "SizeType", "SizeFixed"),
            ("QgsSymbolLayer", "Property", "PropertyWidth"),
            ("QgsSymbolLayer", "Property", "PropertyStrokeWidth"),
            ("QgsSymbol", "Property", "PropertyOpacity"),
            ("QgsUnitTypes", "RenderUnit", "RenderMapUnits"),
            ("QgsMapBoxGlStyleConverter", "Result", "Success"),
        )
        for class_name, enum_name, member_name in enums:
            with self.subTest(cls=class_name, enum=enum_name, member=member_name):
                cls = getattr(core, class_name)
                scoped = getattr(getattr(cls, enum_name), member_name)
                # SIP still exposes legacy aliases in both tested bindings.
                self.assertEqual(scoped, getattr(cls, member_name))

    def test_all_affected_tasks_remain_cancellable(self):
        from qgis.core import QgsApplication, QgsTask
        from tests.qgis_app import get_shared_qgis_app
        from qfit.activities.application.fetch_task import FetchTask
        from qfit.activities.application.route_sync_task import RouteSyncTask
        from qfit.activities.application.store_task import StoreActivitiesTask
        from qfit.activities.application.activity_name_refresh_task import ActivityNameRefreshTask
        from qfit.activities.application.strava_bulk_import_task import (
            StravaBulkPreflightTask, StravaBulkImportTask,
        )
        from qfit.analysis.infrastructure.route_heatmap_task import RouteHeatmapTask
        from qfit.atlas.export_task import AtlasExportTask

        get_shared_qgis_app(QgsApplication)
        # Construct only: no tasks are submitted, no network/database work runs.
        tasks = (
            FetchTask(None, 200, 0, None, None, True, 0),
            RouteSyncTask(provider=None, output_path="unused.gpkg"),
            StoreActivitiesTask(None, None),
            ActivityNameRefreshTask(None, "unused.gpkg"),
            StravaBulkPreflightTask(None, "unused.zip"),
            StravaBulkImportTask(None, None),
            RouteHeatmapTask(None, None),
            AtlasExportTask(None, "unused.pdf"),
        )
        for task in tasks:
            with self.subTest(task=type(task).__name__):
                self.assertTrue(task.flags() & QgsTask.Flag.CanCancel)
                self.assertFalse(task.isCanceled())
                task.cancel()
                self.assertTrue(task.isCanceled())


if __name__ == "__main__":
    unittest.main()
