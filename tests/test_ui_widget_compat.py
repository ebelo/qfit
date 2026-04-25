import sys
import types
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401

from qgis.PyQt.QtCore import Qt

from qfit.ui.widgets.compat import (
    checked_list_values,
    datetime_range_values,
    file_widget_path,
    make_checkable_list,
    make_datetime_range_edits,
    make_file_widget,
    make_password_line_edit,
    make_range_slider,
)


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


class _FakePasswordLineEdit:
    def __init__(self, parent=None):
        self.parent = parent
        self.text_value = ""
        self.placeholder_text = ""

    def setText(self, text):  # noqa: N802
        self.text_value = text

    def text(self):
        return self.text_value

    def setPlaceholderText(self, text):  # noqa: N802
        self.placeholder_text = text


class _FakeFileWidget:
    def __init__(self, parent=None):
        self.parent = parent
        self.file_path = ""
        self.dialog_title = ""
        self.filter_text = ""
        self.storage_mode = None

    def setFilePath(self, file_path):  # noqa: N802
        self.file_path = file_path

    def filePath(self):  # noqa: N802
        return self.file_path

    def setDialogTitle(self, dialog_title):  # noqa: N802
        self.dialog_title = dialog_title

    def setFilter(self, filter_text):  # noqa: N802
        self.filter_text = filter_text

    def setStorageMode(self, storage_mode):  # noqa: N802
        self.storage_mode = storage_mode


class _FakeDateTimeEdit:
    def __init__(self, parent=None):
        self.parent = parent
        self.date_time = "constructor-default"
        self.display_format = ""
        self.calendar_popup = None

    def setDateTime(self, value):  # noqa: N802
        self.date_time = value

    def dateTime(self):  # noqa: N802
        return self.date_time

    def setDisplayFormat(self, value):  # noqa: N802
        self.display_format = value

    def setCalendarPopup(self, value):  # noqa: N802
        self.calendar_popup = value


class _FakeLineEdit(_FakePasswordLineEdit):
    Password = 2

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.echo_mode = None

    def setEchoMode(self, echo_mode):  # noqa: N802
        self.echo_mode = echo_mode


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


def _fake_qgis_gui(
    *,
    datetime_edit=None,
    double_range_slider=None,
    file_widget=None,
    password_line_edit=None,
    range_slider=_FakeIntegerRangeSlider,
):
    module = types.ModuleType("qgis.gui")
    module.QgsRangeSlider = range_slider
    if datetime_edit is not None:
        module.QgsDateTimeEdit = datetime_edit
    if double_range_slider is not None:
        module.QgsDoubleRangeSlider = double_range_slider
    if file_widget is not None:
        module.QgsFileWidget = file_widget
    if password_line_edit is not None:
        module.QgsPasswordLineEdit = password_line_edit
    return module


def _fake_qt_widgets():
    module = types.ModuleType("qgis.PyQt.QtWidgets")
    module.QDateTimeEdit = _FakeDateTimeEdit
    module.QLineEdit = _FakeLineEdit
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

    def test_uses_native_file_widget_when_qgis_provides_it(self):
        parent = object()
        storage_mode = object()
        with patch.dict(sys.modules, {"qgis.gui": _fake_qgis_gui(file_widget=_FakeFileWidget)}):
            widget = make_file_widget(
                file_path="/tmp/activities.gpkg",
                dialog_title="Select GeoPackage",
                filter_text="GeoPackage (*.gpkg)",
                storage_mode=storage_mode,
                parent=parent,
            )

        self.assertIsInstance(widget, _FakeFileWidget)
        self.assertIs(widget.parent, parent)
        self.assertEqual(widget.file_path, "/tmp/activities.gpkg")
        self.assertEqual(widget.dialog_title, "Select GeoPackage")
        self.assertEqual(widget.filter_text, "GeoPackage (*.gpkg)")
        self.assertIs(widget.storage_mode, storage_mode)
        self.assertEqual(file_widget_path(widget), "/tmp/activities.gpkg")

    def test_file_widget_falls_back_to_line_edit(self):
        parent = object()
        with patch.dict(
            sys.modules,
            {
                "qgis.gui": _fake_qgis_gui(),
                "qgis.PyQt.QtWidgets": _fake_qt_widgets(),
            },
        ):
            widget = make_file_widget(
                file_path="/tmp/export.pdf",
                dialog_title="Export PDF",
                parent=parent,
            )

        self.assertIsInstance(widget, _FakeLineEdit)
        self.assertIs(widget.parent, parent)
        self.assertEqual(widget.text_value, "/tmp/export.pdf")
        self.assertEqual(widget.placeholder_text, "Export PDF")
        self.assertEqual(file_widget_path(widget), "/tmp/export.pdf")

    def test_file_widget_falls_back_when_qgis_gui_module_is_missing(self):
        def import_module_side_effect(name):
            if name == "qgis.gui":
                raise ModuleNotFoundError(name=name)
            if name == "qgis.PyQt.QtWidgets":
                return _fake_qt_widgets()
            raise AssertionError(name)

        with patch("qfit.ui.widgets.compat.import_module", side_effect=import_module_side_effect):
            widget = make_file_widget(file_path="/tmp/fallback.gpkg")

        self.assertIsInstance(widget, _FakeLineEdit)
        self.assertEqual(file_widget_path(widget), "/tmp/fallback.gpkg")

    def test_uses_native_password_line_edit_when_qgis_provides_it(self):
        parent = object()
        with patch.dict(
            sys.modules,
            {"qgis.gui": _fake_qgis_gui(password_line_edit=_FakePasswordLineEdit)},
        ):
            widget = make_password_line_edit(
                text="secret",
                placeholder_text="Access token",
                parent=parent,
            )

        self.assertIsInstance(widget, _FakePasswordLineEdit)
        self.assertIs(widget.parent, parent)
        self.assertEqual(widget.text_value, "secret")
        self.assertEqual(widget.placeholder_text, "Access token")

    def test_password_line_edit_falls_back_to_qlineedit_password_mode(self):
        parent = object()
        with patch.dict(
            sys.modules,
            {
                "qgis.gui": _fake_qgis_gui(),
                "qgis.PyQt.QtWidgets": _fake_qt_widgets(),
            },
        ):
            widget = make_password_line_edit(placeholder_text="Client secret", parent=parent)

        self.assertIsInstance(widget, _FakeLineEdit)
        self.assertIs(widget.parent, parent)
        self.assertEqual(widget.echo_mode, _FakeLineEdit.Password)
        self.assertEqual(widget.placeholder_text, "Client secret")

    def test_uses_native_datetime_edits_for_range_filters(self):
        parent = object()
        with patch.dict(sys.modules, {"qgis.gui": _fake_qgis_gui(datetime_edit=_FakeDateTimeEdit)}):
            edits = make_datetime_range_edits(
                start_datetime="2026-04-01T08:00:00",
                end_datetime="2026-04-30T18:30:00",
                display_format="dd.MM.yyyy HH:mm",
                calendar_popup=False,
                parent=parent,
            )

        self.assertIsInstance(edits.start, _FakeDateTimeEdit)
        self.assertIsInstance(edits.end, _FakeDateTimeEdit)
        self.assertIs(edits.start.parent, parent)
        self.assertIs(edits.end.parent, parent)
        self.assertTrue(edits.start_enabled)
        self.assertTrue(edits.end_enabled)
        self.assertEqual(edits.start.date_time, "2026-04-01T08:00:00")
        self.assertEqual(edits.end.date_time, "2026-04-30T18:30:00")
        self.assertEqual(edits.start.display_format, "dd.MM.yyyy HH:mm")
        self.assertEqual(edits.end.display_format, "dd.MM.yyyy HH:mm")
        self.assertFalse(edits.start.calendar_popup)
        self.assertFalse(edits.end.calendar_popup)
        self.assertEqual(
            datetime_range_values(edits),
            ("2026-04-01T08:00:00", "2026-04-30T18:30:00"),
        )

    def test_datetime_range_edits_fall_back_to_qt_widgets(self):
        def import_module_side_effect(name):
            if name == "qgis.gui":
                raise ModuleNotFoundError(name=name)
            if name == "qgis.PyQt.QtWidgets":
                return _fake_qt_widgets()
            raise AssertionError(name)

        with patch("qfit.ui.widgets.compat.import_module", side_effect=import_module_side_effect):
            edits = make_datetime_range_edits(start_datetime="start", end_datetime="end")

        self.assertIsInstance(edits.start, _FakeDateTimeEdit)
        self.assertEqual(edits.start.date_time, "start")
        self.assertEqual(edits.end.date_time, "end")
        self.assertEqual(edits.start.display_format, "yyyy-MM-dd HH:mm")
        self.assertTrue(edits.start.calendar_popup)

    def test_datetime_range_values_preserve_unset_bounds(self):
        with patch.dict(sys.modules, {"qgis.gui": _fake_qgis_gui(datetime_edit=_FakeDateTimeEdit)}):
            edits = make_datetime_range_edits(end_datetime="2026-04-30T18:30:00")

        self.assertFalse(edits.start_enabled)
        self.assertTrue(edits.end_enabled)
        self.assertEqual(edits.start.date_time, "constructor-default")
        self.assertEqual(
            datetime_range_values(edits),
            (None, "2026-04-30T18:30:00"),
        )

    def test_datetime_range_enabled_flags_override_initial_values(self):
        with patch.dict(sys.modules, {"qgis.gui": _fake_qgis_gui(datetime_edit=_FakeDateTimeEdit)}):
            edits = make_datetime_range_edits(
                start_datetime="2026-04-01T08:00:00",
                end_datetime="2026-04-30T18:30:00",
                start_enabled=False,
                end_enabled=True,
            )

        self.assertEqual(
            datetime_range_values(edits),
            (None, "2026-04-30T18:30:00"),
        )

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
