import unittest
from types import SimpleNamespace

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_activity_controls import (
    build_current_activity_preview_request,
    configure_local_first_activity_preview_options,
)


class FakeComboBox:
    def __init__(self, parent=None):
        self._parent = parent
        self.items = []
        self.object_name = None
        self.tooltip = None
        self.cleared = False

    def addItem(self, label, data=None):
        self.items.append((label, data))

    def clear(self):
        self.cleared = True
        self.items.clear()

    def setObjectName(self, name):
        self.object_name = name

    def setToolTip(self, text):
        self.tooltip = text

    def parentWidget(self):
        return self._parent

    def currentText(self):
        if not self.items:
            return ""
        return self.items[0][0]

    def currentData(self):
        if not self.items:
            return None
        return self.items[0][1]


class FakeDate:
    def __init__(self, value, valid=True):
        self.value = value
        self.valid = valid

    def isValid(self):
        return self.valid

    def toString(self, format_string):
        self.format_string = format_string
        return self.value


class FakeDateEdit:
    def __init__(self, date):
        self._date = date

    def date(self):
        return self._date


class FakeLineEdit:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class FakeSpinBox:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


class LocalFirstActivityControlsTests(unittest.TestCase):
    def test_configure_preview_options_needs_no_route_detail_backing_controls(self):
        dock = SimpleNamespace()
        configure_local_first_activity_preview_options(dock)
        self.assertFalse(hasattr(dock, "detailedRouteStatusComboBox"))
        self.assertFalse(hasattr(dock, "detailedOnlyCheckBox"))

    def test_build_current_activity_preview_request_reads_local_first_backing_controls(self):
        activities = [SimpleNamespace(name="Morning Ride")]
        activity_type_combo = FakeComboBox()
        activity_type_combo.addItem("Ride", "ride")
        dock = SimpleNamespace(
            runtime_state=SimpleNamespace(activities=activities),
            activityTypeComboBox=activity_type_combo,
            dateFromEdit=FakeDateEdit(FakeDate("2026-05-01")),
            dateToEdit=FakeDateEdit(FakeDate("", valid=False)),
            minDistanceSpinBox=FakeSpinBox(12),
            maxDistanceSpinBox=FakeSpinBox(120),
            activitySearchLineEdit=FakeLineEdit("  gravel  "),
        )

        request = build_current_activity_preview_request(dock)

        self.assertIs(request.activities, activities)
        self.assertEqual(request.activity_type, "Ride")
        self.assertEqual(request.date_from, "2026-05-01")
        self.assertIsNone(request.date_to)
        self.assertEqual(request.min_distance_km, 12)
        self.assertEqual(request.max_distance_km, 120)
        self.assertEqual(request.search_text, "gravel")
        self.assertIsNone(request.detailed_route_filter)
        self.assertFalse(hasattr(request, "sort_label"))

        activity_type_combo.selectedTypes = lambda: ("Hike", "Walk")
        multiple = build_current_activity_preview_request(dock)
        self.assertEqual(multiple.activity_types, ("Hike", "Walk"))

    def test_build_current_activity_preview_request_uses_safe_defaults(self):
        activity_type_combo = FakeComboBox()
        dock = SimpleNamespace(
            runtime_state=SimpleNamespace(activities=[]),
            activityTypeComboBox=activity_type_combo,
            dateFromEdit=FakeDateEdit(FakeDate("", valid=False)),
            dateToEdit=FakeDateEdit(FakeDate("", valid=False)),
            minDistanceSpinBox=FakeSpinBox(0),
            maxDistanceSpinBox=FakeSpinBox(0),
            activitySearchLineEdit=FakeLineEdit(""),
        )

        request = build_current_activity_preview_request(dock)

        self.assertEqual(request.activity_type, "All")
        self.assertIsNone(request.date_from)
        self.assertIsNone(request.date_to)
        self.assertFalse(hasattr(request, "sort_label"))


if __name__ == "__main__":
    unittest.main()
