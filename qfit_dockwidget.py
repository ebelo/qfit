import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QDate, QSettings
from qgis.PyQt.QtWidgets import QFileDialog, QDockWidget, QMessageBox

from .gpkg_writer import GeoPackageWriter
from .layer_manager import LayerManager
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
        self.layer_manager = LayerManager(iface)
        self.setupUi(self)
        self._load_settings()
        self._wire_events()
        self._set_default_dates()

    def _wire_events(self):
        self.browseButton.clicked.connect(self.on_browse_clicked)
        self.refreshButton.clicked.connect(self.on_refresh_clicked)
        self.loadButton.clicked.connect(self.on_load_clicked)
        self.applyFiltersButton.clicked.connect(self.on_apply_filters_clicked)

    def _load_settings(self):
        settings = QSettings()
        self.clientIdLineEdit.setText(settings.value(f"{self.SETTINGS_PREFIX}/client_id", ""))
        self.clientSecretLineEdit.setText(settings.value(f"{self.SETTINGS_PREFIX}/client_secret", ""))
        self.refreshTokenLineEdit.setText(settings.value(f"{self.SETTINGS_PREFIX}/refresh_token", ""))
        default_output = settings.value(
            f"{self.SETTINGS_PREFIX}/output_path",
            os.path.join(os.path.expanduser("~"), "qfit_activities.gpkg"),
        )
        self.outputPathLineEdit.setText(default_output)
        self.perPageSpinBox.setValue(int(settings.value(f"{self.SETTINGS_PREFIX}/per_page", 50)))
        self.maxPagesSpinBox.setValue(int(settings.value(f"{self.SETTINGS_PREFIX}/max_pages", 2)))

    def _save_settings(self):
        settings = QSettings()
        settings.setValue(f"{self.SETTINGS_PREFIX}/client_id", self.clientIdLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/client_secret", self.clientSecretLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/refresh_token", self.refreshTokenLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/output_path", self.outputPathLineEdit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/per_page", self.perPageSpinBox.value())
        settings.setValue(f"{self.SETTINGS_PREFIX}/max_pages", self.maxPagesSpinBox.value())

    def _set_default_dates(self):
        if not self.dateFromEdit.date().isValid():
            self.dateFromEdit.setDate(QDate.currentDate().addYears(-1))
        if not self.dateToEdit.date().isValid():
            self.dateToEdit.setDate(QDate.currentDate())

    def on_browse_clicked(self):
        path, _selected = QFileDialog.getSaveFileName(self, "Choose GeoPackage output", self.outputPathLineEdit.text(), "GeoPackage (*.gpkg)")
        if path:
            if not path.lower().endswith(".gpkg"):
                path = f"{path}.gpkg"
            self.outputPathLineEdit.setText(path)

    def on_refresh_clicked(self):
        self._save_settings()
        self._set_status("Connecting to Strava…")
        try:
            client = self._build_client()
            self.activities = client.fetch_activities(
                per_page=self.perPageSpinBox.value(),
                max_pages=self.maxPagesSpinBox.value(),
            )
            self._populate_activity_types()
            self.countLabel.setText(f"Activities fetched: {len(self.activities)}")
            self._set_status(f"Fetched {len(self.activities)} activities from Strava")
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
            writer = GeoPackageWriter(output_path=output_path)
            result = writer.write_activities(self.activities)
            self.output_path = result["path"]
            self.activities_layer, self.starts_layer = self.layer_manager.load_output_layers(self.output_path)
            self.on_apply_filters_clicked()
            self._set_status(
                f"Loaded {result['activity_count']} activities and {result['start_count']} start points into QGIS"
            )
        except Exception as exc:  # noqa: BLE001
            self._show_error("GeoPackage export failed", str(exc))
            self._set_status("GeoPackage export failed")

    def on_apply_filters_clicked(self):
        if self.activities_layer is None and self.starts_layer is None:
            return

        activity_type = self.activityTypeComboBox.currentText()
        date_from = self.dateFromEdit.date().toString("yyyy-MM-dd") if self.dateFromEdit.date().isValid() else None
        date_to = self.dateToEdit.date().toString("yyyy-MM-dd") if self.dateToEdit.date().isValid() else None
        min_distance_km = self.minDistanceSpinBox.value()
        preset = self.stylePresetComboBox.currentText()

        self.layer_manager.apply_filters(self.activities_layer, activity_type, date_from, date_to, min_distance_km)
        self.layer_manager.apply_filters(self.starts_layer, activity_type, date_from, date_to, min_distance_km)
        self.layer_manager.apply_style(self.activities_layer, self.starts_layer, preset)
        self._set_status("Applied filters and styling")

    def _build_client(self):
        client = StravaClient(
            client_id=self.clientIdLineEdit.text().strip(),
            client_secret=self.clientSecretLineEdit.text().strip(),
            refresh_token=self.refreshTokenLineEdit.text().strip(),
        )
        if not client.is_configured():
            raise StravaClientError("Enter Strava client id, client secret, and refresh token.")
        return client

    def _populate_activity_types(self):
        values = sorted({activity.activity_type for activity in self.activities if activity.activity_type})
        self.activityTypeComboBox.clear()
        self.activityTypeComboBox.addItem("All")
        for value in values:
            self.activityTypeComboBox.addItem(value)

    def _set_status(self, text):
        self.statusLabel.setText(text)

    def _show_error(self, title, message):
        QMessageBox.critical(self, title, message)
