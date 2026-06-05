"""Floating About dock for qfit project information and support links."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QLabel, QDockWidget, QVBoxLayout, QWidget

from .about_info import AboutInfo, build_about_html, read_about_info


class QfitAboutDock(QDockWidget):
    """Small floating dock showing qfit version, project, and contact links."""

    DEFAULT_DOCK_FEATURES = (
        QDockWidget.DockWidgetClosable
        | QDockWidget.DockWidgetMovable
        | QDockWidget.DockWidgetFloatable
    )

    def __init__(self, info: AboutInfo | None = None, parent: QWidget | None = None):
        super().__init__("About", parent)
        self.setObjectName("qfitAboutDock")
        self.setWindowTitle("qfit — About")
        self.setFeatures(self.DEFAULT_DOCK_FEATURES)
        self.setMinimumWidth(420)
        self._info = info or read_about_info()
        self._build_ui()

    def _build_ui(self) -> None:
        container = QWidget(self)
        layout = QVBoxLayout(container)

        self._content_label = QLabel(build_about_html(self._info), container)
        self._content_label.setObjectName("qfitAboutContentLabel")
        self._content_label.setWordWrap(True)
        self._content_label.setOpenExternalLinks(True)
        self._content_label.setTextInteractionFlags(
            Qt.TextBrowserInteraction | Qt.TextSelectableByMouse
        )
        layout.addWidget(self._content_label)
        layout.addStretch(1)

        self.setWidget(container)
