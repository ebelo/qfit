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
class SyncPageState:
    """Render facts for the #609 synchronization wizard page."""

    ready: bool = False
    status_text: str = "Activities not synced yet"
    detail_text: str = "Fetch Strava activities and store detailed routes in the GeoPackage."
    activity_summary_text: str = "No activities stored"
    primary_action_label: str = "Sync activities"


class SyncPageContent(QWidget):
    """Reusable second-page content for the wizard synchronization step."""

    syncRequested = pyqtSignal()

    def __init__(self, state: SyncPageState | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("qfitWizardSyncPageContent")
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("qfitWizardSyncStatus")
        self.detail_label = QLabel("", self)
        self.detail_label.setObjectName("qfitWizardSyncDetail")
        if hasattr(self.detail_label, "setWordWrap"):
            self.detail_label.setWordWrap(True)
        self.activity_summary_label = QLabel("", self)
        self.activity_summary_label.setObjectName("qfitWizardSyncActivitySummary")
        self.sync_button = QToolButton(self)
        self.sync_button.setObjectName("qfitWizardSyncButton")
        style_primary_action_button(
            self.sync_button,
            action_name="sync_activities",
        )
        self.sync_button.clicked.connect(self.syncRequested.emit)
        self.action_row = build_wizard_action_row(
            self.sync_button,
            parent=self,
            object_name="qfitWizardSyncActionRow",
        )
        self._layout = self._build_layout()
        self.set_state(state or SyncPageState())

    def set_state(self, state: SyncPageState) -> None:
        """Refresh copy and state properties without rebuilding the page."""

        sync_state = "ready" if state.ready else "not_synced"
        self.status_label.setText(state.status_text)
        self.status_label.setProperty("syncState", sync_state)
        self.status_label.setStyleSheet(_status_stylesheet(ready=state.ready))
        self.detail_label.setText(state.detail_text)
        self.detail_label.setStyleSheet(
            f"QLabel#qfitWizardSyncDetail {{ color: {COLOR_MUTED}; }}"
        )
        self.activity_summary_label.setText(state.activity_summary_text)
        self.activity_summary_label.setProperty("syncState", sync_state)
        self.sync_button.setText(state.primary_action_label)

    def outer_layout(self):
        """Expose the layout for adapter wiring and pure tests."""

        return self._layout

    def _build_layout(self):
        layout = QVBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardSyncPageContentLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.status_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.activity_summary_label)
        layout.addWidget(self.action_row)
        return layout


def build_sync_page_content(
    *,
    parent=None,
    state: SyncPageState | None = None,
) -> SyncPageContent:
    """Build the reusable synchronization-step content widget."""

    return SyncPageContent(state=state, parent=parent)


def install_sync_page_content(
    page,
    *,
    state: SyncPageState | None = None,
) -> SyncPageContent:
    """Append synchronization content to the matching wizard page body layout."""

    if page.spec.key != "sync":
        raise ValueError(
            "Sync page content can only be installed on the synchronization wizard page"
        )
    content = build_sync_page_content(parent=page, state=state)
    page.body_layout().addWidget(content)
    page.retire_primary_action_hint()
    return content


def _status_stylesheet(*, ready: bool) -> str:
    color = COLOR_ACCENT if ready else COLOR_WARN
    return (
        "QLabel#qfitWizardSyncStatus { "
        f"color: {color}; "
        "font-weight: 700; "
        "}"
    )


__all__ = [
    "SyncPageContent",
    "SyncPageState",
    "build_sync_page_content",
    "install_sync_page_content",
]
