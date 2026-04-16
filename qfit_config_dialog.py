"""Dedicated configuration dialog for persistent qfit plugin settings.

This dialog is the second step toward separating setup concerns
(Strava/Mapbox credentials and connection checks) from the day-to-day activity
workflow in the main dock widget. It intentionally avoids visualization-
specific Mapbox styling options, which belong in the main map workflow.
"""

import logging

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .activities.application.sync_controller import SyncController
from .configuration.application.config_connection_service import (
    build_mapbox_connection_test_request,
    build_strava_connection_test_request,
    validate_mapbox_connection_request,
    validate_strava_connection_request,
)
from .configuration.application.config_status import mapbox_status_text, strava_status_text
from .configuration.application.settings_port import SettingsPort
from .configuration.application.settings_service import SettingsService
from .providers.domain.provider import ProviderError
from .providers.infrastructure.strava_client import StravaClient
from .configuration.application.ui_settings_binding import UIFieldBinding, load_bindings, save_bindings

logger = logging.getLogger(__name__)

_NOT_TESTED_LABEL = "Not tested"
_OAUTH_NOT_STARTED_LABEL = "Not started"


class QfitConfigDialog(QDialog):
    """Editable configuration dialog for qfit plugin connection settings.

    Allows the user to view and edit Strava credentials plus the Mapbox
    access token, run the Strava OAuth helper flow, and test provider
    connections before saving. Changes are persisted to QSettings on save.
    """

    def __init__(
        self,
        settings_service: SettingsPort | None = None,
        sync_controller: SyncController | None = None,
        cache: object | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._settings = settings_service or SettingsService()
        self._sync_controller = sync_controller or SyncController()
        self._cache = cache
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

        self._oauth_help_label = QLabel(
            "Use qfit's OAuth helper below to generate the refresh token. Do not paste the token shown on the Strava API application page."
        )
        self._oauth_help_label.setObjectName("stravaOAuthHelpLabel")
        self._oauth_help_label.setWordWrap(True)
        self._oauth_help_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("", self._oauth_help_label)

        self._authorization_code_edit = QLineEdit()
        self._authorization_code_edit.setObjectName("cfgAuthorizationCodeEdit")
        self._authorization_code_edit.setPlaceholderText(
            "Paste the code returned by Strava after approval"
        )
        form.addRow("Authorization code:", self._authorization_code_edit)

        oauth_button_row = QWidget(group)
        oauth_button_layout = QHBoxLayout(oauth_button_row)
        oauth_button_layout.setContentsMargins(0, 0, 0, 0)
        oauth_button_layout.setSpacing(6)

        self._open_authorize_button = QPushButton("Open Strava authorize page")
        self._open_authorize_button.setObjectName("cfgOpenAuthorizeButton")
        self._open_authorize_button.clicked.connect(self._open_strava_authorize_page)
        oauth_button_layout.addWidget(self._open_authorize_button)

        self._exchange_code_button = QPushButton("Exchange code")
        self._exchange_code_button.setObjectName("cfgExchangeCodeButton")
        self._exchange_code_button.clicked.connect(self._exchange_strava_code)
        oauth_button_layout.addWidget(self._exchange_code_button)
        oauth_button_layout.addStretch(1)
        form.addRow("", oauth_button_row)

        self._strava_oauth_status_label = QLabel(_OAUTH_NOT_STARTED_LABEL)
        self._strava_oauth_status_label.setObjectName("stravaOAuthStatusLabel")
        self._strava_oauth_status_label.setWordWrap(True)
        self._strava_oauth_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("OAuth helper:", self._strava_oauth_status_label)

        self._refresh_token_edit = QLineEdit()
        self._refresh_token_edit.setObjectName("cfgRefreshTokenEdit")
        self._refresh_token_edit.setEchoMode(QLineEdit.Password)
        self._refresh_token_edit.setPlaceholderText(
            "Generated by qfit's OAuth flow, not the Strava app page"
        )
        form.addRow("Refresh token:", self._refresh_token_edit)

        self._strava_test_status_label = QLabel(_NOT_TESTED_LABEL)
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

        self._mapbox_test_status_label = QLabel(_NOT_TESTED_LABEL)
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
        self._authorization_code_edit.clear()
        self._refresh_status_labels()
        self._strava_oauth_status_label.setText(_OAUTH_NOT_STARTED_LABEL)
        self._strava_test_status_label.setText(_NOT_TESTED_LABEL)
        self._mapbox_test_status_label.setText(_NOT_TESTED_LABEL)

    def _save(self) -> None:
        """Persist edited fields to QSettings and refresh status labels."""
        save_bindings(self._bindings, self._settings)
        self._refresh_status_labels()

    def _refresh_status_labels(self) -> None:
        self._strava_status_label.setText(strava_status_text(self._settings))
        self._mapbox_status_label.setText(mapbox_status_text(self._settings))

    def _redirect_uri(self) -> str:
        return self._redirect_uri_edit.text().strip() or StravaClient.DEFAULT_REDIRECT_URI

    def _open_strava_authorize_page(self) -> None:
        self._save()
        try:
            authorize_request = self._sync_controller.build_authorize_request(
                client_id=self._client_id_edit.text().strip(),
                client_secret=self._client_secret_edit.text().strip(),
                refresh_token=self._refresh_token_edit.text().strip(),
                cache=self._cache,
                redirect_uri=self._redirect_uri(),
            )
            url = self._sync_controller.build_authorize_url(authorize_request)
            if not QDesktopServices.openUrl(QUrl(url)):
                clipboard = QApplication.clipboard()
                if clipboard is not None:
                    clipboard.setText(url)
                self._show_info(
                    "Open Strava authorize page manually",
                    "qfit could not open the browser automatically. The authorization URL was copied to your clipboard.\n\nOpen this URL in a browser and continue the flow there:\n\n{url}".format(
                        url=url
                    ),
                )
                self._strava_oauth_status_label.setText(
                    "Could not open browser automatically. Authorization URL copied to clipboard."
                )
                return
            self._strava_oauth_status_label.setText(
                "Strava authorization opened in your browser. Approve access, copy the returned code, then paste it here and click Exchange code."
            )
        except ProviderError as exc:
            self._show_error("Strava authorization failed", str(exc))
            self._strava_oauth_status_label.setText(
                "Could not start the Strava authorization flow"
            )

    def _exchange_strava_code(self) -> None:
        self._save()
        authorization_code = self._authorization_code_edit.text().strip()
        if not authorization_code:
            self._show_error(
                "Missing authorization code",
                "Paste the code returned by Strava first.",
            )
            self._strava_oauth_status_label.setText(
                "Paste the returned Strava code before exchanging it."
            )
            return

        try:
            exchange_request = self._sync_controller.build_exchange_code_request(
                client_id=self._client_id_edit.text().strip(),
                client_secret=self._client_secret_edit.text().strip(),
                refresh_token=self._refresh_token_edit.text().strip(),
                cache=self._cache,
                authorization_code=authorization_code,
                redirect_uri=self._redirect_uri(),
            )
            payload = self._sync_controller.exchange_code_for_tokens(exchange_request)
            refresh_token = payload["refresh_token"]
            self._refresh_token_edit.setText(refresh_token)
            self._authorization_code_edit.clear()
            self._save()

            athlete = payload.get("athlete") or {}
            athlete_name = " ".join(
                part for part in [athlete.get("firstname"), athlete.get("lastname")] if part
            ).strip()
            if athlete_name:
                self._strava_oauth_status_label.setText(
                    "Strava connected for {name}. Refresh token saved locally in QGIS settings.".format(
                        name=athlete_name
                    )
                )
            else:
                self._strava_oauth_status_label.setText(
                    "Strava refresh token saved locally in QGIS settings."
                )
            self._strava_test_status_label.setText(_NOT_TESTED_LABEL)
        except ProviderError as exc:
            self._show_error("Token exchange failed", str(exc))
            self._strava_oauth_status_label.setText(
                "Could not exchange the Strava authorization code"
            )

    def _test_strava(self) -> None:
        request = build_strava_connection_test_request(
            self._client_id_edit.text(),
            self._client_secret_edit.text(),
            self._refresh_token_edit.text(),
        )
        result = validate_strava_connection_request(request)
        self._strava_test_status_label.setText(result.message)

    def _test_mapbox(self) -> None:
        request = build_mapbox_connection_test_request(self._mapbox_token_edit.text())
        result = validate_mapbox_connection_request(request)
        self._mapbox_test_status_label.setText(result.message)

    def _show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    # -- Visibility ----------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        """Reload settings every time the dialog becomes visible."""
        super().showEvent(event)
        self._load()
