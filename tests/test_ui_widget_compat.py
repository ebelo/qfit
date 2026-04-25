import sys
import types
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401

from qgis.PyQt.QtCore import Qt

from qfit.ui.widgets.compat import checked_list_values, make_checkable_list, make_range_slider


class _FakeSignal:
    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)
        return slot

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)


class _FakeSignalDescriptor:
    def __init__(self, name):
        self.name = name

    def __get__(self, instance, _owner):
        if instance is None:
            return self
        return instance.base_signals[self.name]


class _FakeIntegerRangeSlider:
    rangeChanged = _FakeSignalDescriptor("rangeChanged")
    rangeLimitsChanged = _FakeSignalDescriptor("rangeLimitsChanged")

    def __init__(self, orientation=Qt.Horizontal, parent=None):
        self.orientation = orientation
        self.parent = parent
        self.base_signals = {
            "rangeChanged": _FakeSignal(),
            "rangeLimitsChanged": _FakeSignal(),
        }
        self.limit_values = None
        self.selected_values = None
        self.lower_raw = None
        self.upper_raw = None

    def setRangeLimits(self, minimum, maximum):  # noqa: N802
        self.limit_values = (minimum, maximum)
        self.minimum_raw = minimum
        self.maximum_raw = maximum
        self.base_signals["rangeLimitsChanged"].emit(minimum, maximum)

    def setMinimum(self, value):  # noqa: N802
        self.minimum_raw = value

    def setMaximum(self, value):  # noqa: N802
        self.maximum_raw = value

    def minimum(self):
        return self.minimum_raw

    def maximum(self):
        return self.maximum_raw

    def setRange(self, lower, upper):  # noqa: N802
        self.selected_values = (lower, upper)
        self.lower_raw = lower
        self.upper_raw = upper
        self.base_signals["rangeChanged"].emit(lower, upper)

    def setLowerValue(self, value):  # noqa: N802
        self.lower_raw = value

    def setUpperValue(self, value):  # noqa: N802
        self.upper_raw = value

    def lowerValue(self):  # noqa: N802
        return self.lower_raw

    def upperValue(self):  # noqa: N802
        return self.upper_raw


class _FakeDoubleRangeSlider(_FakeIntegerRangeSlider):
    pass


class _FakeParentOnlyDoubleRangeSlider:
    def __init__(self, parent=None):
        self.parent = parent
        self.orientation = None
        self.minimum_value = None
        self.maximum_value = None
        self.lower_value = None
        self.upper_value = None

    def setOrientation(self, orientation):  # noqa: N802
        self.orientation = orientation

    def setMinimum(self, value):  # noqa: N802
        self.minimum_value = value

    def setMaximum(self, value):  # noqa: N802
        self.maximum_value = value

    def setLowerValue(self, value):  # noqa: N802
        self.lower_value = value

    def setUpperValue(self, value):  # noqa: N802
        self.upper_value = value


class _FakeParentOnlyIntegerRangeSlider(_FakeIntegerRangeSlider):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.orientation_set_later = None

    def setOrientation(self, orientation):  # noqa: N802
        self.orientation_set_later = orientation


class _FakeListWidget:
    def __init__(self, parent=None):
        self.parent = parent
        self.items = []

    def addItem(self, item):  # noqa: N802
        self.items.append(item)

    def count(self):
        return len(self.items)

    def item(self, index):
        return self.items[index]


class _FakeListWidgetItem:
    def __init__(self, text):
        self.text = text
        self._flags = 0
        self._check_state = None
        self._data = {}

    def flags(self):
        return self._flags

    def setFlags(self, flags):  # noqa: N802
        self._flags = flags

    def setCheckState(self, check_state):  # noqa: N802
        self._check_state = check_state

    def checkState(self):  # noqa: N802
        return self._check_state

    def setData(self, role, value):  # noqa: N802
        self._data[role] = value

    def data(self, role):
        return self._data[role]


def _fake_qgis_gui(*, double_range_slider=None, range_slider=_FakeIntegerRangeSlider):
    module = types.ModuleType("qgis.gui")
    module.QgsRangeSlider = range_slider
    if double_range_slider is not None:
        module.QgsDoubleRangeSlider = double_range_slider
    return module


def _fake_qt_widgets():
    module = types.ModuleType("qgis.PyQt.QtWidgets")
    module.QListWidget = _FakeListWidget
    module.QListWidgetItem = _FakeListWidgetItem
    return module


class UiWidgetCompatTests(unittest.TestCase):
    def test_creates_native_checkable_list_with_stable_values(self):
        parent = object()
        with patch.dict(sys.modules, {"qgis.PyQt.QtWidgets": _fake_qt_widgets()}):
            list_widget = make_checkable_list(
                [("run", "Run"), ("ride", "Ride"), ("hike", "Hike")],
                checked_values=["ride", "hike"],
                parent=parent,
            )

        self.assertIs(list_widget.parent, parent)
        self.assertEqual([item.text for item in list_widget.items], ["Run", "Ride", "Hike"])
        self.assertTrue(list_widget.items[0].flags() & Qt.ItemIsUserCheckable)
        self.assertEqual(list_widget.items[0].data(Qt.UserRole), "run")
        self.assertEqual(list_widget.items[0].checkState(), Qt.Unchecked)
        self.assertEqual(list_widget.items[1].checkState(), Qt.Checked)
        self.assertEqual(checked_list_values(list_widget), ["ride", "hike"])

    def test_checkable_list_uses_string_options_as_labels_and_values(self):
        with patch.dict(sys.modules, {"qgis.PyQt.QtWidgets": _fake_qt_widgets()}):
            list_widget = make_checkable_list(["Run", "Ride"])

        self.assertEqual([item.text for item in list_widget.items], ["Run", "Ride"])
        self.assertEqual([item.data(Qt.UserRole) for item in list_widget.items], ["Run", "Ride"])
        self.assertEqual([item.checkState() for item in list_widget.items], [Qt.Unchecked, Qt.Unchecked])
        self.assertEqual(checked_list_values(list_widget), [])

    def test_checkable_list_rejects_malformed_tuple_options(self):
        with patch.dict(sys.modules, {"qgis.PyQt.QtWidgets": _fake_qt_widgets()}):
            with self.assertRaisesRegex(ValueError, "Expected a \\(value, label\\) pair"):
                make_checkable_list([("run", "Run", "extra")])

    def test_uses_native_double_range_slider_when_qgis_provides_it(self):
        with patch.dict(
            sys.modules,
            {"qgis.gui": _fake_qgis_gui(double_range_slider=_FakeDoubleRangeSlider)},
        ):
            slider = make_range_slider(minimum=0.5, maximum=42.5, lower=5.5, upper=21.25)

        self.assertIsInstance(slider, _FakeDoubleRangeSlider)
        self.assertEqual(slider.limit_values, (0.5, 42.5))
        self.assertEqual(slider.selected_values, (5.5, 21.25))

    def test_scales_float_values_when_falling_back_to_integer_qgs_range_slider(self):
        with patch.dict(sys.modules, {"qgis.gui": _fake_qgis_gui()}):
            slider = make_range_slider(
                minimum=0.0,
                maximum=42.5,
                lower=5.5,
                upper=21.25,
                decimals=2,
            )

        self.assertEqual(slider.limit_values, (0, 4250))
        self.assertEqual(slider.selected_values, (550, 2125))
        self.assertEqual(slider.minimum(), 0.0)
        self.assertEqual(slider.maximum(), 42.5)
        self.assertEqual(slider.lowerValue(), 5.5)
        self.assertEqual(slider.upperValue(), 21.25)

        slider.setMinimum(1.25)
        slider.setMaximum(40.75)
        slider.setLowerValue(6.75)
        slider.setUpperValue(20.5)

        self.assertEqual(slider.minimum_raw, 125)
        self.assertEqual(slider.maximum_raw, 4075)
        self.assertEqual(slider.lower_raw, 675)
        self.assertEqual(slider.upper_raw, 2050)
        self.assertEqual(slider.lowerValue(), 6.75)
        self.assertEqual(slider.upperValue(), 20.5)

    def test_defaults_selected_range_to_limits(self):
        with patch.dict(sys.modules, {"qgis.gui": _fake_qgis_gui()}):
            slider = make_range_slider(minimum=1.0, maximum=2.5, decimals=1)

        self.assertEqual(slider.selected_values, (10, 25))
        self.assertEqual(slider.lowerValue(), 1.0)
        self.assertEqual(slider.upperValue(), 2.5)

    def test_reuses_fallback_class_for_consistent_slider_types(self):
        with patch.dict(sys.modules, {"qgis.gui": _fake_qgis_gui()}):
            first_slider = make_range_slider(minimum=1.0, maximum=2.5, decimals=1)
            second_slider = make_range_slider(minimum=2.0, maximum=5.0, decimals=2)

        self.assertIs(type(first_slider), type(second_slider))

    def test_fallback_signals_emit_logical_float_values(self):
        with patch.dict(sys.modules, {"qgis.gui": _fake_qgis_gui()}):
            slider = make_range_slider(minimum=1.0, maximum=2.5, decimals=2)

        range_changes = []
        range_limit_changes = []
        slider.rangeChanged.connect(lambda lower, upper: range_changes.append((lower, upper)))
        slider.rangeLimitsChanged.connect(
            lambda minimum, maximum: range_limit_changes.append((minimum, maximum)),
        )

        slider.setRange(6.75, 20.5)
        slider.setRangeLimits(1.25, 40.75)

        self.assertEqual(range_changes, [(6.75, 20.5)])
        self.assertEqual(range_limit_changes, [(1.25, 40.75)])

    def test_configures_parent_only_native_slider_api(self):
        parent = object()
        with patch.dict(
            sys.modules,
            {"qgis.gui": _fake_qgis_gui(double_range_slider=_FakeParentOnlyDoubleRangeSlider)},
        ):
            slider = make_range_slider(
                minimum=1.5,
                maximum=9.5,
                lower=2.5,
                upper=8.5,
                orientation=Qt.Vertical,
                parent=parent,
            )

        self.assertIs(slider.parent, parent)
        self.assertEqual(slider.orientation, Qt.Vertical)
        self.assertEqual(slider.minimum_value, 1.5)
        self.assertEqual(slider.maximum_value, 9.5)
        self.assertEqual(slider.lower_value, 2.5)
        self.assertEqual(slider.upper_value, 8.5)

    def test_configures_parent_only_fallback_slider_api(self):
        parent = object()
        with patch.dict(
            sys.modules,
            {"qgis.gui": _fake_qgis_gui(range_slider=_FakeParentOnlyIntegerRangeSlider)},
        ):
            slider = make_range_slider(
                minimum=1.5,
                maximum=9.5,
                lower=2.5,
                upper=8.5,
                decimals=1,
                orientation=Qt.Vertical,
                parent=parent,
            )

        self.assertIs(slider.parent, parent)
        self.assertEqual(slider.orientation_set_later, Qt.Vertical)
        self.assertEqual(slider.limit_values, (15, 95))
        self.assertEqual(slider.selected_values, (25, 85))


if __name__ == "__main__":
    unittest.main()
