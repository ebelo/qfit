"""Dedicated configuration dialog for persistent qfit plugin settings.

This dialog is the first step toward separating setup concerns
(Strava/Mapbox connections, defaults) from the day-to-day activity
workflow in the main dock widget.
"""

import logging

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .config_status import mapbox_status_text, strava_status_text
from .settings_service import SettingsService

logger = logging.getLogger(__name__)


class QfitConfigDialog(QDialog):
    """Read-only configuration overview for qfit plugin settings.

    Displays the current connection status for Strava and Mapbox as
    persisted in QSettings.  Future increments will add editable
    controls and move setup responsibilities out of the main dock.
    """

    def __init__(self, settings_service: SettingsService | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = settings_service or SettingsService()
        self.setWindowTitle("qfit — Configuration")
        self.setMinimumWidth(420)
        self._build_ui()
        self._refresh()

    # -- UI construction -----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(self._build_strava_group())
        layout.addWidget(self._build_mapbox_group())
        layout.addStretch()

    def _build_strava_group(self) -> QGroupBox:
        group = QGroupBox("Strava connection")
        form = QFormLayout(group)
        self._strava_status_label = QLabel()
        self._strava_status_label.setObjectName("stravaStatusLabel")
        self._strava_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Status:", self._strava_status_label)
        return group

    def _build_mapbox_group(self) -> QGroupBox:
        group = QGroupBox("Mapbox connection")
        form = QFormLayout(group)
        self._mapbox_status_label = QLabel()
        self._mapbox_status_label.setObjectName("mapboxStatusLabel")
        self._mapbox_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Status:", self._mapbox_status_label)
        return group

    # -- Data refresh --------------------------------------------------------

    def _refresh(self) -> None:
        """Read current settings and update the status labels."""
        self._strava_status_label.setText(strava_status_text(self._settings))
        self._mapbox_status_label.setText(mapbox_status_text(self._settings))
