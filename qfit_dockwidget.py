import os
from datetime import date, datetime, time

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QDate, QSettings, QStandardPaths, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QDockWidget, QMessageBox

from .gpkg_writer import GeoPackageWriter
from .layer_manager import LayerManager
from .qfit_cache import QfitCache
from .strava_client import StravaClient, StravaClientError

FORM_CLASS, _ = uic.loadUiType(
    __import__("os").path.join(__import__("os").path.dirname(__file__), "qfit_dockwidget_base.ui")
)


class QfitDockWidget(QDockWidget, FORM_CLASS):
    SETTINGS_PREFIX = "QFIT"

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.activities = []
        self.output_path = None
        self.activities_layer = None
        self.starts_layer = None
        self.points_layer = None
        self.last_fetch_context = {}
        self.layer_manager = LayerManager(iface)
        self.cache = self._build_cache()
        self.setupUi(self)
        self._load_settings()
        self._wire_events()
        self._set_default_dates()

    def _wire_events(self):
        self.openAuthorizeButton.clicked.connect(self.on_open_authorize_clicked)
        self.exchangeCodeButton.clicked.connect(self.on_exchange_code_clicked)
        self.browseButton.clicked.connect(self.on_browse_clicked)
        self.refreshButton.clicked.connect(self.on_refresh_clicked)
        self.loadButton.clicked.connect(self.on_load_clicked)
        self.applyFiltersButton.clicked.connect(self.on_apply_filters_clicked)

    def _build_cache(self):
        base_path = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not base_path:
            base_path = os.path.join(os.path.expanduser("~"), ".qfit")
        return QfitCache(os.path.join(base_path, "QFIT", "cache"))

    def _load_settings(self):
        settings = QSettings()
        self.clientIdLineEdit.setText(settings.value(f"{self.SETTINGS_PREFIX}/client_id", ""))
        self.clientSecretLineEdit.setText(settings.value(f"{self.SETTINGS_PREFIX}/client_secret", ""))
        self.redirectUriLineEdit.setText(
            settings.value(
                f"{self.SETTINGS_PREFIX}/redirect_uri",
                StravaClient.DEFAULT_REDIRECT_URI,
            )
        )
        self.authCodeLineEdit.setText("")
        self.refreshTokenLineEdit.setText(settings.value(f"{self.SETTINGS_PREFIX}/refresh_token", ""))
        default_output = settings.value(
            f"{self.SETTINGS_PREFIX}/output_path",
            os.path.join(os.path.expanduser("~"), "qfit_activities.gpkg"),
        )
        self.outputPathLineEdit.setText(default_output)
        self.perPageSpinBox.setValue(int(settings.value(f"{self.SETTINGS_PREFIX}/per_page", 50)))
        self.maxPagesSpinBox.setValue(int(settings.value(f"{self.SETTINGS_PREFIX}/max_pages", 2)))
        self.detailedStreamsCheckBox.setChecked(
            self._settings_bool(settings, f"{self.SETTINGS_PREFIX}/use_detailed_streams", False)
        )
        self.maxDetailedActivitiesSpinBox.setValue(
            int(settings.value(f"{self.SETTINGS_PREFIX}/max_detailed_activities", 25))
        )
        self.writeActivityPointsCheckBox.setChecked(
            self._settings_bool(settings, f"{self.SETTINGS_PREFIX}/write_activity_points", False)
        )
        self.pointSamplingStrideSpinBox.setValue(
            int(settings.value(f"{self.SETTINGS_PREFIX}/point_sampling_stride", 5))
        )

    def _save_settings(self):
        settings = QSettings()
        settings.setValue(f"{self.SETTINGS_PREFIX}/client_id", self.clientIdLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/client_secret", self.clientSecretLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/redirect_uri", self.redirectUriLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/refresh_token", self.refreshTokenLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/output_path", self.outputPathLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/per_page", self.perPageSpinBox.value())
        settings.setValue(f"{self.SETTINGS_PREFIX}/max_pages", self.maxPagesSpinBox.value())
        settings.setValue(f"{self.SETTINGS_PREFIX}/use_detailed_streams", self.detailedStreamsCheckBox.isChecked())
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/max_detailed_activities",
            self.maxDetailedActivitiesSpinBox.value(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/write_activity_points",
            self.writeActivityPointsCheckBox.isChecked(),
        )
        settings.setValue(
            f"{self.SETTINGS_PREFIX}/point_sampling_stride",
            self.pointSamplingStrideSpinBox.value(),
        )

    def _settings_bool(self, settings, key, default=False):
        value = settings.value(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes", "on")
        return bool(value)

    def _set_default_dates(self):
        if not self.dateFromEdit.date().isValid():
            self.dateFromEdit.setDate(QDate.currentDate().addYears(-1))
        if not self.dateToEdit.date().isValid():
            self.dateToEdit.setDate(QDate.currentDate())

    def on_open_authorize_clicked(self):
        self._save_settings()
        try:
            client = self._build_client(require_refresh_token=False)
            redirect_uri = self._redirect_uri()
            url = client.build_authorize_url(redirect_uri=redirect_uri)
            if not QDesktopServices.openUrl(QUrl(url)):
                clipboard = QApplication.clipboard()
                if clipboard is not None:
                    clipboard.setText(url)
                self._show_info(
                    "Open Strava authorize page manually",
                    "QFIT could not open the browser automatically. The authorization URL was copied to your clipboard.\n\nOpen this URL in a browser and continue the flow there:\n\n{url}".format(
                        url=url
                    ),
                )
                self._set_status(
                    "Could not open browser automatically. Authorization URL copied to clipboard."
                )
                return
            self._set_status(
                "Strava authorization opened in your browser. Approve access, copy the returned code, then paste it here and click Exchange code."
            )
        except StravaClientError as exc:
            self._show_error("Strava authorization failed", str(exc))
            self._set_status("Could not start the Strava authorization flow")

    def on_exchange_code_clicked(self):
        self._save_settings()
        authorization_code = self.authCodeLineEdit.text().strip()
        if not authorization_code:
            self._show_error("Missing authorization code", "Paste the code returned by Strava first.")
            return

        try:
            client = self._build_client(require_refresh_token=False)
            payload = client.exchange_code_for_tokens(
                authorization_code=authorization_code,
                redirect_uri=self._redirect_uri(),
            )
            refresh_token = payload.get("refresh_token")
            if not refresh_token:
                raise StravaClientError("Strava returned no refresh token")
            self.refreshTokenLineEdit.setText(refresh_token)
            self.authCodeLineEdit.clear()
            self._save_settings()
            athlete = payload.get("athlete") or {}
            athlete_name = " ".join(
                part for part in [athlete.get("firstname"), athlete.get("lastname")] if part
            ).strip()
            if athlete_name:
                self._set_status(
                    "Strava connected for {name}. Refresh token saved locally in QGIS settings.".format(
                        name=athlete_name
                    )
                )
            else:
                self._set_status("Strava refresh token saved locally in QGIS settings.")
        except StravaClientError as exc:
            self._show_error("Token exchange failed", str(exc))
            self._set_status("Could not exchange the Strava authorization code")

    def on_browse_clicked(self):
        path, _selected = QFileDialog.getSaveFileName(
            self,
            "Choose GeoPackage output",
            self.outputPathLineEdit.text(),
            "GeoPackage (*.gpkg)",
        )
        if path:
            if not path.lower().endswith(".gpkg"):
                path = "{path}.gpkg".format(path=path)
            self.outputPathLineEdit.setText(path)

    def on_refresh_clicked(self):
        self._save_settings()
        self._set_status("Connecting to Strava…")
        try:
            client = self._build_client(require_refresh_token=True)
            before, after = self._build_fetch_epoch_range()
            self.activities = client.fetch_activities(
                per_page=self.perPageSpinBox.value(),
                max_pages=self.maxPagesSpinBox.value(),
                before=before,
                after=after,
                use_detailed_streams=self.detailedStreamsCheckBox.isChecked(),
                max_detailed_activities=self.maxDetailedActivitiesSpinBox.value(),
            )
            detailed_count = sum(1 for activity in self.activities if activity.geometry_source == "stream")
            self.last_fetch_context = {
                "provider": "strava",
                "before_epoch": before,
                "after_epoch": after,
                "fetched_count": len(self.activities),
                "detailed_count": detailed_count,
                "stream_stats": client.last_stream_enrichment_stats,
                "rate_limit": client.last_rate_limit,
                "is_full_sync": self._is_full_sync_window(before, after),
            }
            self._populate_activity_types()
            self.countLabel.setText(
                "Activities fetched: {count} (detailed tracks: {detailed})".format(
                    count=len(self.activities),
                    detailed=detailed_count,
                )
            )
            self._set_status(self._fetch_status_text(client, len(self.activities), detailed_count))
        except StravaClientError as exc:
            self._show_error("Strava import failed", str(exc))
            self._set_status("Strava fetch failed")
        except Exception as exc:  # noqa: BLE001
            self._show_error("Unexpected error", str(exc))
            self._set_status("Unexpected error during refresh")

    def on_load_clicked(self):
        if not self.activities:
            self._show_error("Nothing to load", "Fetch activities from Strava first.")
            return

        self._save_settings()
        output_path = self.outputPathLineEdit.text().strip()
        if not output_path:
            self._show_error("Missing output path", "Choose a GeoPackage output path first.")
            return

        self._set_status("Writing GeoPackage…")
        try:
            writer = GeoPackageWriter(
                output_path=output_path,
                write_activity_points=self.writeActivityPointsCheckBox.isChecked(),
                point_stride=self.pointSamplingStrideSpinBox.value(),
            )
            result = writer.write_activities(self.activities, sync_metadata=self.last_fetch_context)
            self.output_path = result["path"]
            self.activities_layer, self.starts_layer, self.points_layer = self.layer_manager.load_output_layers(
                self.output_path
            )
            self.on_apply_filters_clicked()
            sync = result.get("sync") or {}
            self._set_status(
                "Synced {fetched} fetched activities into GeoPackage: inserted {inserted}, updated {updated}, unchanged {unchanged}, stored total {total}. Loaded {track_count} tracks, {start_count} starts, and {point_count} activity points into QGIS".format(
                    fetched=result.get("fetched_count", len(self.activities)),
                    inserted=sync.get("inserted", 0),
                    updated=sync.get("updated", 0),
                    unchanged=sync.get("unchanged", 0),
                    total=sync.get("total_count", 0),
                    track_count=result.get("track_count", 0),
                    start_count=result.get("start_count", 0),
                    point_count=result.get("point_count", 0),
                )
            )
        except Exception as exc:  # noqa: BLE001
            self._show_error("GeoPackage export failed", str(exc))
            self._set_status("GeoPackage export failed")

    def on_apply_filters_clicked(self):
        if self.activities_layer is None and self.starts_layer is None and self.points_layer is None:
            return

        activity_type = self.activityTypeComboBox.currentText()
        date_from = self.dateFromEdit.date().toString("yyyy-MM-dd") if self.dateFromEdit.date().isValid() else None
        date_to = self.dateToEdit.date().toString("yyyy-MM-dd") if self.dateToEdit.date().isValid() else None
        min_distance_km = self.minDistanceSpinBox.value()
        preset = self.stylePresetComboBox.currentText()

        self.layer_manager.apply_filters(self.activities_layer, activity_type, date_from, date_to, min_distance_km)
        self.layer_manager.apply_filters(self.starts_layer, activity_type, date_from, date_to, min_distance_km)
        self.layer_manager.apply_filters(self.points_layer, activity_type, date_from, date_to, min_distance_km)
        self.layer_manager.apply_style(self.activities_layer, self.starts_layer, self.points_layer, preset)
        self._set_status("Applied filters and styling")

    def _build_client(self, require_refresh_token=True):
        client = StravaClient(
            client_id=self.clientIdLineEdit.text().strip(),
            client_secret=self.clientSecretLineEdit.text().strip(),
            refresh_token=self.refreshTokenLineEdit.text().strip(),
            cache=self.cache,
        )
        if not client.has_client_credentials():
            raise StravaClientError("Enter Strava client ID and client secret first.")
        if require_refresh_token and not client.refresh_token:
            raise StravaClientError(
                "Enter a refresh token, or use the built-in authorization flow to generate one."
            )
        return client

    def _redirect_uri(self):
        return self.redirectUriLineEdit.text().strip() or StravaClient.DEFAULT_REDIRECT_URI

    def _build_fetch_epoch_range(self):
        local_tz = datetime.now().astimezone().tzinfo
        after = None
        before = None

        if self.dateFromEdit.date().isValid():
            start_date = self._qdate_to_date(self.dateFromEdit.date())
            after = int(datetime.combine(start_date, time(0, 0, 0), tzinfo=local_tz).timestamp())

        if self.dateToEdit.date().isValid():
            end_date = self._qdate_to_date(self.dateToEdit.date())
            before = int(datetime.combine(end_date, time(23, 59, 59), tzinfo=local_tz).timestamp())

        return before, after

    def _qdate_to_date(self, value):
        return date(value.year(), value.month(), value.day())

    def _is_full_sync_window(self, before_epoch, after_epoch):
        if before_epoch is None or after_epoch is None:
            return False
        return (before_epoch - after_epoch) >= 365 * 24 * 60 * 60

    def _populate_activity_types(self):
        values = sorted({activity.activity_type for activity in self.activities if activity.activity_type})
        self.activityTypeComboBox.clear()
        self.activityTypeComboBox.addItem("All")
        for value in values:
            self.activityTypeComboBox.addItem(value)

    def _fetch_status_text(self, client, activity_count, detailed_count):
        stream_stats = client.last_stream_enrichment_stats or {}
        rate_limit_note = self._rate_limit_note(client.last_rate_limit)
        return (
            "Fetched {activity_count} activities from Strava, detailed tracks: {detailed_count}, "
            "cached streams: {cached}, downloaded streams: {downloaded}, rate-limit skips: {skipped}.{rate_note}"
        ).format(
            activity_count=activity_count,
            detailed_count=detailed_count,
            cached=stream_stats.get("cached", 0),
            downloaded=stream_stats.get("downloaded", 0),
            skipped=stream_stats.get("skipped_rate_limit", 0),
            rate_note=rate_limit_note,
        )

    def _rate_limit_note(self, rate_limit):
        if not rate_limit:
            return ""
        short_remaining = rate_limit.get("short_remaining")
        long_remaining = rate_limit.get("long_remaining")
        if short_remaining is None and long_remaining is None:
            return ""
        return " Remaining rate limit: short={short}, long={long}.".format(
            short=short_remaining if short_remaining is not None else "?",
            long=long_remaining if long_remaining is not None else "?",
        )

    def _set_status(self, text):
        self.statusLabel.setText(text)

    def _show_info(self, title, message):
        QMessageBox.information(self, title, message)

    def _show_error(self, title, message):
        QMessageBox.critical(self, title, message)
