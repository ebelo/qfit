import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from tests import _path  # noqa: F401

from qfit.activities.domain.activity_query import (
    DEFAULT_SORT_LABEL,
    DETAILED_ROUTE_FILTER_ANY,
    DETAILED_ROUTE_FILTER_MISSING,
    DETAILED_ROUTE_FILTER_PRESENT,
    SORT_OPTIONS,
)
from qfit.detailed_route_strategy import detailed_route_strategy_labels
from qfit.ui.application.local_first_activity_controls import (
    build_current_activity_preview_request,
    configure_detailed_route_filter_options,
    configure_detailed_route_strategy_options,
    configure_local_first_activity_preview_options,
    configure_preview_sort_options,
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


class FakeLayout:
    def __init__(self):
        self.replacements = []

    def replaceWidget(self, old_widget, new_widget):
        self.replacements.append((old_widget, new_widget))


class FakeParent:
    def __init__(self):
        self._layout = FakeLayout()

    def layout(self):
        return self._layout


class FakeLegacyCheckBox:
    def __init__(self, parent):
        self._parent = parent
        self.hidden = False

    def parentWidget(self):
        return self._parent

    def hide(self):
        self.hidden = True


def install_fake_qtwidgets():
    qgis = ModuleType("qgis")
    pyqt = ModuleType("qgis.PyQt")
    qtwidgets = ModuleType("qgis.PyQt.QtWidgets")
    qtwidgets.QComboBox = FakeComboBox
    qgis.PyQt = pyqt
    pyqt.QtWidgets = qtwidgets
    return {
        "qgis": qgis,
        "qgis.PyQt": pyqt,
        "qgis.PyQt.QtWidgets": qtwidgets,
    }


class LocalFirstActivityControlsTests(unittest.TestCase):
    def test_configure_detailed_route_filter_replaces_legacy_checkbox(self):
        parent = FakeParent()
        legacy_checkbox = FakeLegacyCheckBox(parent)
        dock = SimpleNamespace(detailedOnlyCheckBox=legacy_checkbox)

        with patch.dict(sys.modules, install_fake_qtwidgets()):
            configure_detailed_route_filter_options(dock)

        combo = dock.detailedRouteStatusComboBox
        self.assertIs(combo.parentWidget(), parent)
        self.assertEqual(combo.object_name, "detailedRouteStatusComboBox")
        self.assertEqual(
            parent.layout().replacements,
            [(legacy_checkbox, combo)],
        )
        self.assertTrue(legacy_checkbox.hidden)
        self.assertEqual(
            combo.items,
            [
                ("Any routes", DETAILED_ROUTE_FILTER_ANY),
                ("Detailed routes only", DETAILED_ROUTE_FILTER_PRESENT),
                ("Missing detailed routes", DETAILED_ROUTE_FILTER_MISSING),
            ],
        )
        self.assertEqual(
            combo.tooltip,
            "Filter activities by detailed-route availability",
        )

    def test_configure_detailed_route_filter_reuses_existing_combo(self):
        combo = FakeComboBox()
        combo.addItem("stale", "value")
        dock = SimpleNamespace(detailedRouteStatusComboBox=combo)

        configure_detailed_route_filter_options(dock)

        self.assertTrue(combo.cleared)
        self.assertEqual(
            combo.items,
            [
                ("Any routes", DETAILED_ROUTE_FILTER_ANY),
                ("Detailed routes only", DETAILED_ROUTE_FILTER_PRESENT),
                ("Missing detailed routes", DETAILED_ROUTE_FILTER_MISSING),
            ],
        )

    def test_configure_detailed_route_strategy_populates_when_present(self):
        combo = FakeComboBox()
        combo.addItem("stale")
        dock = SimpleNamespace(detailedRouteStrategyComboBox=combo)

        configure_detailed_route_strategy_options(dock)

        self.assertTrue(combo.cleared)
        self.assertEqual(
            combo.items,
            [(label, None) for label in detailed_route_strategy_labels()],
        )

    def test_configure_detailed_route_strategy_skips_missing_combo(self):
        configure_detailed_route_strategy_options(SimpleNamespace())

    def test_configure_preview_sort_populates_sort_options(self):
        combo = FakeComboBox()
        combo.addItem("stale")
        dock = SimpleNamespace(previewSortComboBox=combo)

        configure_preview_sort_options(dock)

        self.assertTrue(combo.cleared)
        self.assertEqual(
            combo.items,
            [(label, None) for label in SORT_OPTIONS],
        )
        self.assertEqual(combo.items[0], (DEFAULT_SORT_LABEL, None))

    def test_configure_activity_preview_options_populates_backing_combos(self):
        route_status_combo = FakeComboBox()
        strategy_combo = FakeComboBox()
        sort_combo = FakeComboBox()
        dock = SimpleNamespace(
            detailedRouteStatusComboBox=route_status_combo,
            detailedRouteStrategyComboBox=strategy_combo,
            previewSortComboBox=sort_combo,
        )

        configure_local_first_activity_preview_options(dock)

        self.assertEqual(route_status_combo.items[0], ("Any routes", "any"))
        self.assertEqual(
            strategy_combo.items,
            [(label, None) for label in detailed_route_strategy_labels()],
        )
        self.assertEqual(
            sort_combo.items,
            [(label, None) for label in SORT_OPTIONS],
        )

    def test_build_current_activity_preview_request_reads_local_first_backing_controls(self):
        activities = [SimpleNamespace(name="Morning Ride")]
        activity_type_combo = FakeComboBox()
        activity_type_combo.addItem("Ride", "ride")
        detailed_route_status_combo = FakeComboBox()
        detailed_route_status_combo.addItem(
            "Detailed routes only",
            DETAILED_ROUTE_FILTER_PRESENT,
        )
        preview_sort_combo = FakeComboBox()
        preview_sort_combo.addItem("Newest first")
        dock = SimpleNamespace(
            runtime_state=SimpleNamespace(activities=activities),
            activityTypeComboBox=activity_type_combo,
            dateFromEdit=FakeDateEdit(FakeDate("2026-05-01")),
            dateToEdit=FakeDateEdit(FakeDate("", valid=False)),
            minDistanceSpinBox=FakeSpinBox(12),
            maxDistanceSpinBox=FakeSpinBox(120),
            activitySearchLineEdit=FakeLineEdit("  gravel  "),
            detailedRouteStatusComboBox=detailed_route_status_combo,
            previewSortComboBox=preview_sort_combo,
        )

        request = build_current_activity_preview_request(dock)

        self.assertIs(request.activities, activities)
        self.assertEqual(request.activity_type, "Ride")
        self.assertEqual(request.date_from, "2026-05-01")
        self.assertIsNone(request.date_to)
        self.assertEqual(request.min_distance_km, 12)
        self.assertEqual(request.max_distance_km, 120)
        self.assertEqual(request.search_text, "gravel")
        self.assertEqual(request.detailed_route_filter, DETAILED_ROUTE_FILTER_PRESENT)
        self.assertEqual(request.sort_label, "Newest first")

    def test_build_current_activity_preview_request_uses_safe_defaults(self):
        activity_type_combo = FakeComboBox()
        detailed_route_status_combo = FakeComboBox()
        detailed_route_status_combo.addItem("Any routes", DETAILED_ROUTE_FILTER_ANY)
        preview_sort_combo = FakeComboBox()
        dock = SimpleNamespace(
            runtime_state=SimpleNamespace(activities=[]),
            activityTypeComboBox=activity_type_combo,
            dateFromEdit=FakeDateEdit(FakeDate("", valid=False)),
            dateToEdit=FakeDateEdit(FakeDate("", valid=False)),
            minDistanceSpinBox=FakeSpinBox(0),
            maxDistanceSpinBox=FakeSpinBox(0),
            activitySearchLineEdit=FakeLineEdit(""),
            detailedRouteStatusComboBox=detailed_route_status_combo,
            previewSortComboBox=preview_sort_combo,
        )

        request = build_current_activity_preview_request(dock)

        self.assertEqual(request.activity_type, "All")
        self.assertIsNone(request.date_from)
        self.assertIsNone(request.date_to)
        self.assertEqual(request.sort_label, DEFAULT_SORT_LABEL)


if __name__ == "__main__":
    unittest.main()
