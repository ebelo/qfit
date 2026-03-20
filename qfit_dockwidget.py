from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDockWidget

FORM_CLASS, _ = uic.loadUiType(
    __import__("os").path.join(__import__("os").path.dirname(__file__), "qfit_dockwidget_base.ui")
)


class QfitDockWidget(QDockWidget, FORM_CLASS):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._wire_events()

    def _wire_events(self):
        self.refreshButton.clicked.connect(self.on_refresh_clicked)
        self.loadButton.clicked.connect(self.on_load_clicked)

    def on_refresh_clicked(self):
        self.statusLabel.setText("Refresh not implemented yet")

    def on_load_clicked(self):
        self.statusLabel.setText("Load not implemented yet")
