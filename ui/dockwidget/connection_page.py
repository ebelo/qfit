from __future__ import annotations

from dataclasses import dataclass

from qfit.ui.tokens import COLOR_ACCENT, COLOR_MUTED, COLOR_WARN

from ._qt_compat import import_qt_module
from .action_row import build_wizard_action_row, style_primary_action_button

_qtcore = import_qt_module("qgis.PyQt.QtCore", "PyQt5.QtCore", ("pyqtSignal",))
_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    (
        "QLabel",
        "QToolButton",
        "QVBoxLayout",
        "QWidget",
    ),
)

pyqtSignal = _qtcore.pyqtSignal
QLabel = _qtwidgets.QLabel
QToolButton = _qtwidgets.QToolButton
QVBoxLayout = _qtwidgets.QVBoxLayout
QWidget = _qtwidgets.QWidget


@dataclass(frozen=True)
class ConnectionPageState:
    """Render facts for the first #609 wizard page.

    The state is intentionally UI-facing and small. It lets the future dock
    adapter update the connection page without binding the page to the current
    long-scroll dock implementation.
    """

    connected: bool = False
    status_text: str = "Strava not connected"
    detail_text: str = "Configure qfit once, then continue to synchronization."
    primary_action_label: str = "Configure connection"


class ConnectionPageContent(QWidget):
    """Reusable first-page content for the wizard connection step."""

    configureRequested = pyqtSignal()

    def __init__(self, state: ConnectionPageState | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("qfitWizardConnectionPageContent")
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("qfitWizardConnectionStatus")
        self.detail_label = QLabel("", self)
        self.detail_label.setObjectName("qfitWizardConnectionDetail")
        if hasattr(self.detail_label, "setWordWrap"):
            self.detail_label.setWordWrap(True)
        self.configure_button = QToolButton(self)
        self.configure_button.setObjectName("qfitWizardConnectionConfigureButton")
        style_primary_action_button(
            self.configure_button,
            action_name="configure_connection",
        )
        self.configure_button.clicked.connect(self.configureRequested.emit)
        self.action_row = build_wizard_action_row(
            self.configure_button,
            parent=self,
            object_name="qfitWizardConnectionActionRow",
        )
        self._layout = self._build_layout()
        self.set_state(state or ConnectionPageState())

    def set_state(self, state: ConnectionPageState) -> None:
        """Refresh copy and state properties without rebuilding the page."""

        self.status_label.setText(state.status_text)
        self.status_label.setProperty(
            "connectionState",
            "connected" if state.connected else "not_connected",
        )
        self.status_label.setStyleSheet(_status_stylesheet(connected=state.connected))
        self.detail_label.setText(state.detail_text)
        self.detail_label.setStyleSheet(
            f"QLabel#qfitWizardConnectionDetail {{ color: {COLOR_MUTED}; }}"
        )
        self.configure_button.setText(state.primary_action_label)

    def outer_layout(self):
        """Expose the layout for adapter wiring and pure tests."""

        return self._layout

    def _build_layout(self):
        layout = QVBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardConnectionPageContentLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.status_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.action_row)
        return layout


def build_connection_page_content(
    *,
    parent=None,
    state: ConnectionPageState | None = None,
) -> ConnectionPageContent:
    """Build the reusable connection-step content widget."""

    return ConnectionPageContent(state=state, parent=parent)


def install_connection_page_content(
    page,
    *,
    state: ConnectionPageState | None = None,
) -> ConnectionPageContent:
    """Append connection content to the matching wizard page body layout."""

    if page.spec.key != "connection":
        raise ValueError(
            "Connection page content can only be installed on the connection wizard page"
        )
    content = build_connection_page_content(parent=page, state=state)
    page.body_layout().addWidget(content)
    page.retire_primary_action_hint()
    return content


def _status_stylesheet(*, connected: bool) -> str:
    color = COLOR_ACCENT if connected else COLOR_WARN
    return (
        "QLabel#qfitWizardConnectionStatus { "
        f"color: {color}; "
        "font-weight: 700; "
        "}"
    )


__all__ = [
    "ConnectionPageContent",
    "ConnectionPageState",
    "build_connection_page_content",
    "install_connection_page_content",
]
