"""Dedicated configuration dialog for persistent qfit plugin settings.

This dialog is the second step toward separating setup concerns
(Strava/Mapbox credentials and connection checks) from the day-to-day activity
workflow in the main dock widget. It intentionally avoids visualization-
specific Mapbox styling options, which belong in the main map workflow.
"""

import logging

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config_connection_service import validate_mapbox_connection, validate_strava_connection
from .config_status import mapbox_status_text, strava_status_text
from .settings_service import SettingsService
from .strava_client import StravaClient
from .ui_settings_binding import UIFieldBinding, load_bindings, save_bindings

logger = logging.getLogger(__name__)


class QfitConfigDialog(QDialog):
    """Editable configuration dialog for qfit plugin connection settings.

    Allows the user to view and edit Strava credentials plus the Mapbox
    access token, and to run provider-specific connection tests before
    saving. Changes are persisted to QSettings on save.
    """

    def __init__(self, settings_service: SettingsService | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = settings_service or SettingsService()
        self.setWindowTitle("qfit — Configuration")
        self.setMinimumWidth(420)
        self._build_ui()
        self._bindings = self._make_bindings()
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

        self._strava_test_status_label = QLabel("Not tested")
        self._strava_test_status_label.setObjectName("stravaTestStatusLabel")
        self._strava_test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Last test:", self._strava_test_status_label)

        self._test_strava_button = QPushButton("Test connection")
        self._test_strava_button.setObjectName("testStravaConnectionButton")
        self._test_strava_button.clicked.connect(self._test_strava)
        form.addRow("", self._test_strava_button)

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

        self._mapbox_test_status_label = QLabel("Not tested")
        self._mapbox_test_status_label.setObjectName("mapboxTestStatusLabel")
        self._mapbox_test_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Last test:", self._mapbox_test_status_label)

        self._test_mapbox_button = QPushButton("Test connection")
        self._test_mapbox_button.setObjectName("testMapboxConnectionButton")
        self._test_mapbox_button.clicked.connect(self._test_mapbox)
        form.addRow("", self._test_mapbox_button)

        return group

    # -- Data load / save ----------------------------------------------------

    def _make_bindings(self) -> list[UIFieldBinding]:
        """Build the explicit UI field → settings key mapping for this dialog."""

        return [
            UIFieldBinding(
                "client_id", "",
                lambda w=self._client_id_edit: w.text().strip(),
                self._client_id_edit.setText,
            ),
            UIFieldBinding(
                "client_secret", "",
                lambda w=self._client_secret_edit: w.text().strip(),
                self._client_secret_edit.setText,
            ),
            UIFieldBinding(
                "redirect_uri", StravaClient.DEFAULT_REDIRECT_URI,
                lambda w=self._redirect_uri_edit: w.text().strip(),
                self._redirect_uri_edit.setText,
            ),
            UIFieldBinding(
                "refresh_token", "",
                lambda w=self._refresh_token_edit: w.text().strip(),
                self._refresh_token_edit.setText,
            ),
            UIFieldBinding(
                "mapbox_access_token", "",
                lambda w=self._mapbox_token_edit: w.text().strip(),
                self._mapbox_token_edit.setText,
            ),
        ]

    def _load(self) -> None:
        """Read current settings and populate all fields."""
        load_bindings(self._bindings, self._settings)
        self._refresh_status_labels()
        self._strava_test_status_label.setText("Not tested")
        self._mapbox_test_status_label.setText("Not tested")

    def _save(self) -> None:
        """Persist edited fields to QSettings and refresh status labels."""
        save_bindings(self._bindings, self._settings)
        self._refresh_status_labels()

    def _refresh_status_labels(self) -> None:
        self._strava_status_label.setText(strava_status_text(self._settings))
        self._mapbox_status_label.setText(mapbox_status_text(self._settings))

    def _test_strava(self) -> None:
        result = validate_strava_connection(
            self._client_id_edit.text(),
            self._client_secret_edit.text(),
            self._refresh_token_edit.text(),
        )
        self._strava_test_status_label.setText(result.message)

    def _test_mapbox(self) -> None:
        result = validate_mapbox_connection(self._mapbox_token_edit.text())
        self._mapbox_test_status_label.setText(result.message)

    # -- Visibility ----------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        """Reload settings every time the dialog becomes visible."""
        super().showEvent(event)
        self._load()
