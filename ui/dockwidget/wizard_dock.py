from __future__ import annotations

from typing import Protocol

from ._qt_compat import import_qt_module

_qtcore = import_qt_module("qgis.PyQt.QtCore", "PyQt5.QtCore", ("Qt",))
_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    ("QDockWidget", "QWidget"),
)

Qt = _qtcore.Qt
QDockWidget = _qtwidgets.QDockWidget
QWidget = _qtwidgets.QWidget

WIZARD_DOCK_OBJECT_NAME = "qfitWizardDockWidget"
WIZARD_DOCK_TITLE = "qfit"
WIZARD_DOCK_ALLOWED_AREAS = Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
WIZARD_DOCK_FEATURES = (
    QDockWidget.DockWidgetClosable
    | QDockWidget.DockWidgetMovable
    | QDockWidget.DockWidgetFloatable
)


class WizardShellCompositionLike(Protocol):
    """Small structural protocol for dock-hostable wizard compositions."""

    shell: QWidget


class WizardDockWidget(QDockWidget):
    """QDockWidget host for the #609 wizard shell composition.

    The current production dock still uses the legacy ``.ui`` while the wizard
    migrates page-by-page. This adapter captures the final dock-level shape from
    the Option B spec now: a normal QGIS dock widget whose contents are the
    reusable ``WizardShell`` composition, without coupling the shell back to the
    long-scroll dock implementation.
    """

    def __init__(
        self,
        composition: WizardShellCompositionLike,
        *,
        parent=None,
        title: str = WIZARD_DOCK_TITLE,
    ) -> None:
        super().__init__(parent)
        self.composition: WizardShellCompositionLike | None = None
        self.setObjectName(WIZARD_DOCK_OBJECT_NAME)
        self.setWindowTitle(title)
        self.setFeatures(WIZARD_DOCK_FEATURES)
        self.setAllowedAreas(WIZARD_DOCK_ALLOWED_AREAS)
        self.set_composition(composition)

    def set_composition(self, composition: WizardShellCompositionLike) -> None:
        """Install or replace the hosted wizard composition shell."""

        shell = _composition_shell(composition)
        self.setWidget(shell)
        self.composition = composition


def build_wizard_dock_widget(
    composition: WizardShellCompositionLike,
    *,
    parent=None,
    title: str = WIZARD_DOCK_TITLE,
) -> WizardDockWidget:
    """Build the dock-level container for a reusable wizard composition."""

    return WizardDockWidget(composition, parent=parent, title=title)


def _composition_shell(composition: WizardShellCompositionLike):
    shell = getattr(composition, "shell", None)
    if shell is None:
        raise ValueError("Wizard dock compositions must expose a shell widget")
    return shell


__all__ = [
    "WIZARD_DOCK_ALLOWED_AREAS",
    "WIZARD_DOCK_FEATURES",
    "WIZARD_DOCK_OBJECT_NAME",
    "WIZARD_DOCK_TITLE",
    "WizardDockWidget",
    "build_wizard_dock_widget",
]
