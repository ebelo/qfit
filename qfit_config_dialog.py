"""Dedicated configuration dialog for persistent qfit plugin settings.

This dialog is the second step toward separating setup concerns
(Strava/Mapbox connections, defaults) from the day-to-day activity
workflow in the main dock widget.  It now exposes editable fields
for Strava credentials and Mapbox connection settings.
"""

import logging

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from .config_status import mapbox_status_text, strava_status_text
from .mapbox_config import TILE_MODE_RASTER, TILE_MODES
from .settings_service import SettingsService
from .strava_client import StravaClient

logger = logging.getLogger(__name__)


class QfitConfigDialog(QDialog):
    """Editable configuration dialog for qfit plugin connection settings.

    Allows the user to view and edit Strava credentials and Mapbox
    connection parameters.  Changes are persisted to QSettings on save.
    """

    def __init__(self, settings_service: SettingsService | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = settings_service or SettingsService()
        self.setWindowTitle("qfit — Configuration")
        self.setMinimumWidth(420)
        self._build_ui()
        self._load()

    # -- UI construction -----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(self._build_strava_group())
        layout.addWidget(self._build_mapbox_group())
        layout.addStretch()

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Close,
        )
        self._button_box.button(QDialogButtonBox.Save).clicked.connect(self._save)
        self._button_box.rejected.connect(self.close)
        layout.addWidget(self._button_box)

    def _build_strava_group(self) -> QGroupBox:
        group = QGroupBox("Strava connection")
        form = QFormLayout(group)

        self._strava_status_label = QLabel()
        self._strava_status_label.setObjectName("stravaStatusLabel")
        self._strava_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Status:", self._strava_status_label)

        self._client_id_edit = QLineEdit()
        self._client_id_edit.setObjectName("cfgClientIdEdit")
        self._client_id_edit.setPlaceholderText("Strava application client ID")
        form.addRow("Client ID:", self._client_id_edit)

        self._client_secret_edit = QLineEdit()
        self._client_secret_edit.setObjectName("cfgClientSecretEdit")
        self._client_secret_edit.setEchoMode(QLineEdit.Password)
        self._client_secret_edit.setPlaceholderText("Strava application client secret")
        form.addRow("Client secret:", self._client_secret_edit)

        self._redirect_uri_edit = QLineEdit()
        self._redirect_uri_edit.setObjectName("cfgRedirectUriEdit")
        form.addRow("Redirect URI:", self._redirect_uri_edit)

        self._refresh_token_edit = QLineEdit()
        self._refresh_token_edit.setObjectName("cfgRefreshTokenEdit")
        self._refresh_token_edit.setEchoMode(QLineEdit.Password)
        self._refresh_token_edit.setPlaceholderText("Obtained via OAuth flow in Activities")
        form.addRow("Refresh token:", self._refresh_token_edit)

        return group

    def _build_mapbox_group(self) -> QGroupBox:
        group = QGroupBox("Mapbox connection")
        form = QFormLayout(group)

        self._mapbox_status_label = QLabel()
        self._mapbox_status_label.setObjectName("mapboxStatusLabel")
        self._mapbox_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Status:", self._mapbox_status_label)

        self._mapbox_token_edit = QLineEdit()
        self._mapbox_token_edit.setObjectName("cfgMapboxTokenEdit")
        self._mapbox_token_edit.setEchoMode(QLineEdit.Password)
        self._mapbox_token_edit.setPlaceholderText("pk.eyJ1Ijo...")
        form.addRow("Access token:", self._mapbox_token_edit)

        self._mapbox_style_owner_edit = QLineEdit()
        self._mapbox_style_owner_edit.setObjectName("cfgMapboxStyleOwnerEdit")
        self._mapbox_style_owner_edit.setPlaceholderText("mapbox")
        form.addRow("Style owner:", self._mapbox_style_owner_edit)

        self._mapbox_style_id_edit = QLineEdit()
        self._mapbox_style_id_edit.setObjectName("cfgMapboxStyleIdEdit")
        self._mapbox_style_id_edit.setPlaceholderText("outdoors-v12")
        form.addRow("Style ID:", self._mapbox_style_id_edit)

        self._tile_mode_combo = QComboBox()
        self._tile_mode_combo.setObjectName("cfgTileModeCombo")
        for mode in TILE_MODES:
            self._tile_mode_combo.addItem(mode)
        form.addRow("Tile mode:", self._tile_mode_combo)

        return group

    # -- Data load / save ----------------------------------------------------

    def _load(self) -> None:
        """Read current settings and populate all fields."""
        s = self._settings

        # Strava
        self._client_id_edit.setText(s.get("client_id", ""))
        self._client_secret_edit.setText(s.get("client_secret", ""))
        self._redirect_uri_edit.setText(
            s.get("redirect_uri", StravaClient.DEFAULT_REDIRECT_URI),
        )
        self._refresh_token_edit.setText(s.get("refresh_token", ""))

        # Mapbox
        self._mapbox_token_edit.setText(s.get("mapbox_access_token", ""))
        self._mapbox_style_owner_edit.setText(s.get("mapbox_style_owner", "mapbox"))
        self._mapbox_style_id_edit.setText(s.get("mapbox_style_id", ""))
        tile_mode = s.get("tile_mode", TILE_MODE_RASTER)
        idx = self._tile_mode_combo.findText(tile_mode)
        self._tile_mode_combo.setCurrentIndex(max(idx, 0))

        # Status labels
        self._strava_status_label.setText(strava_status_text(s))
        self._mapbox_status_label.setText(mapbox_status_text(s))

    def _save(self) -> None:
        """Persist edited fields to QSettings and refresh status labels."""
        s = self._settings

        s.set("client_id", self._client_id_edit.text().strip())
        s.set("client_secret", self._client_secret_edit.text().strip())
        s.set("redirect_uri", self._redirect_uri_edit.text().strip())
        s.set("refresh_token", self._refresh_token_edit.text().strip())

        s.set("mapbox_access_token", self._mapbox_token_edit.text().strip())
        s.set("mapbox_style_owner", self._mapbox_style_owner_edit.text().strip())
        s.set("mapbox_style_id", self._mapbox_style_id_edit.text().strip())
        s.set("tile_mode", self._tile_mode_combo.currentText())

        # Refresh status labels to reflect the just-saved values
        self._strava_status_label.setText(strava_status_text(s))
        self._mapbox_status_label.setText(mapbox_status_text(s))

    # -- Visibility ----------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        """Reload settings every time the dialog becomes visible."""
        super().showEvent(event)
        self._load()
