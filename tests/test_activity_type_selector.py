"""Pure selection-policy checks with a controlled native widget boundary."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests import _path  # noqa: F401


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self, *args):
        for slot in self.slots:
            slot(*args)


class SignalDescriptor:
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.selection_signal


class NativeCombo:
    def __init__(self, parent=None):
        self.parent = parent
        self.items = []
        self.checked = []
        self.blocked = False
        self.selection_signal = Signal()
        self.checkedItemsChanged = Signal()

    def blockSignals(self, blocked):
        old, self.blocked = self.blocked, blocked
        return old

    def addItem(self, text):
        self.items.append(text)

    def addItems(self, values):
        self.items.extend(values)

    def clear(self):
        self.items.clear()
        self.checked.clear()

    def findText(self, text):
        return self.items.index(text) if text in self.items else -1

    def setCheckedItems(self, values):
        # QGIS checks these options without clearing existing checked items.
        self.checked = list(dict.fromkeys([*self.checked, *[v for v in values if v in self.items]]))
        # Native QGIS setters unblock their internal signals; exercise the
        # explicit reentrancy guard rather than trusting QObject blocking.
        self.checkedItemsChanged.emit(self.checked)

    def deselectAllOptions(self):
        self.checked = []
        self.checkedItemsChanged.emit(self.checked)

    def checkedItems(self):
        return self.checked

    def setDefaultText(self, text):
        self.default = text

    def setToolTip(self, text):
        self.tooltip = text

    def setObjectName(self, name):
        self.name = name


class ActivityTypeSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "ui/widgets/activity_type_selector.py"
        spec = importlib.util.spec_from_file_location("qfit.ui.widgets._selector_test", path)
        cls.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            "qgis.PyQt.QtCore": SimpleNamespace(pyqtSignal=lambda: SignalDescriptor()),
            "qgis.gui": SimpleNamespace(QgsCheckableComboBox=NativeCombo),
        }):
            spec.loader.exec_module(cls.module)

    def test_all_is_exclusive_and_last_unchecked_means_unrestricted(self):
        selector = self.module.ActivityTypeSelector()
        selector.setOptions(["All", "Hike", "Walk", "Run"])
        changed = []
        selector.selectionChanged.connect(lambda: changed.append(selector.selectedTypes()))
        selector.setCheckedItems(["Walk", "Hike"])
        self.assertEqual(selector.selectedTypes(), ("Hike", "Walk"))
        selector.setCheckedItems(["Walk", "Hike", "All"])
        self.assertEqual(selector.checkedItems(), ["All"])
        selector.setCheckedItems(["All", "Walk"])
        self.assertEqual(selector.checkedItems(), ["Walk"])
        selector.deselectAllOptions()
        self.assertEqual(changed, [("Hike", "Walk"), (), ("Walk",), ()])

    def test_restored_types_survive_option_refresh_including_missing_labels(self):
        selector = self.module.ActivityTypeSelector()
        selector.setSelectedTypes(["Hike", "Walk"])
        selector.setOptions(["All", "Run", "Hike"])
        self.assertEqual(selector.selectedTypes(), ("Hike", "Walk"))
        self.assertIn("Walk", selector.items)
        selector.setSelectedTypes("Run")
        self.assertEqual(selector.selectedTypes(), ("Run",))
        selector.setSelectedTypes(None)
        self.assertEqual(selector.selectedTypes(), ())

    def test_installer_replaces_legacy_control_and_is_idempotent(self):
        calls = []
        parent = SimpleNamespace(layout=lambda: SimpleNamespace(replaceWidget=lambda old, new: calls.append((old, new))))
        old = SimpleNamespace(parentWidget=lambda: parent, hide=lambda: calls.append("hide"),
                              setObjectName=lambda name: calls.append(name), deleteLater=lambda: calls.append("delete"))
        dock = SimpleNamespace(activityTypeComboBox=old)
        self.module.install_activity_type_selector(dock)
        self.assertEqual(dock.activityTypeComboBox.name, "activityTypeComboBox")
        self.assertEqual(calls[1:], ["hide", "legacyActivityTypeComboBox", "delete"])
        self.module.install_activity_type_selector(dock)
        self.assertEqual(len(calls), 4)


if __name__ == "__main__":
    unittest.main()
