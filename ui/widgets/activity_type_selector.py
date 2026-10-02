"""QGIS-native checkable activity types with an exclusive All reset."""
from contextlib import contextmanager
from qgis.PyQt.QtCore import pyqtSignal
from qgis.gui import QgsCheckableComboBox

from ...activities.domain.activity_query import selected_activity_types


class ActivityTypeSelector(QgsCheckableComboBox):
    selectionChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_checked = ()
        self._updating = False
        self.setDefaultText("All")
        self.setToolTip("Check one or more types (for example Walk and Hike). All clears the restriction.")
        self.addItem("All")
        self.checkedItemsChanged.connect(self._on_checked_items_changed)

    def selectedTypes(self):
        return selected_activity_types(activity_types=self.checkedItems())

    def setSelectedTypes(self, values):
        selected = selected_activity_types(activity_types=values)
        self._set_checked(selected)
        self.selectionChanged.emit()

    def setOptions(self, options):
        selected = self.selectedTypes()
        with self._selection_update():
            self.clear()
            self.addItems(["All", *selected_activity_types(activity_types=[v for v in options if v != "All"])])
            self._set_checked(selected)
        self.selectionChanged.emit()

    @contextmanager
    def _selection_update(self):
        blocked = self.blockSignals(True)
        updating, self._updating = self._updating, True
        try:
            yield
        finally:
            self._updating = updating
            self.blockSignals(blocked)

    def _set_checked(self, values):
        # QGIS setters manage their own signal blocking, so an explicit
        # reentrancy guard is also needed during clear/recheck operations.
        with self._selection_update():
            # Retain missing saved labels rather than silently widening to All.
            for value in values:
                if self.findText(value) < 0:
                    self.addItem(value)
            self.deselectAllOptions()
            self.setCheckedItems(list(values))
            self._last_checked = tuple(values)

    def _on_checked_items_changed(self, values):
        if self._updating:
            return
        if "All" in values:
            values = [v for v in values if v != "All"] if "All" in self._last_checked else ["All"]
        self._set_checked(values)
        self.selectionChanged.emit()


def install_activity_type_selector(dock):
    old = dock.activityTypeComboBox
    if isinstance(old, ActivityTypeSelector):
        return
    selector = ActivityTypeSelector(old.parentWidget())
    selector.setObjectName("activityTypeComboBox")
    old.parentWidget().layout().replaceWidget(old, selector)
    old.hide()
    old.setObjectName("legacyActivityTypeComboBox")
    old.deleteLater()
    dock.activityTypeComboBox = selector
