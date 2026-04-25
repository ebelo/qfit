from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module

from qgis.PyQt.QtCore import Qt

CheckableListOption = str | tuple[str, str]


@dataclass
class DateTimeRangeEdits:
    """Pair of native date-time edits for start/end range selection."""

    start: object
    end: object
    start_enabled: bool = False
    end_enabled: bool = False


class _ScaledSignal:
    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)
        return slot

    def disconnect(self, slot=None):
        if slot is None:
            self._slots.clear()
            return
        self._slots.remove(slot)

    def emit(self, *args) -> None:
        for slot in self._slots:
            slot(*args)


def make_collapsible_group_box(
    *,
    title: str = "",
    collapsed: bool = False,
    checkable: bool = True,
    parent=None,
):
    """Create a collapsible group box with a Qt fallback.

    The wizard spec calls for ``QgsCollapsibleGroupBox`` so sections expose a
    standard QGIS chevron. Minimal test environments and older installs may not
    provide it, so fallback to a checkable ``QGroupBox`` while preserving the
    same construction API for future wizard pages.
    """

    gui = _import_optional_qgis_gui()
    group_box_class = getattr(gui, "QgsCollapsibleGroupBox", None) if gui is not None else None
    if group_box_class is not None:
        group_box = _construct_group_box(group_box_class, title, parent)
    else:
        widgets = import_module("qgis.PyQt.QtWidgets")
        group_box = _construct_group_box(widgets.QGroupBox, title, parent)

    _configure_collapsible_group_box(
        group_box,
        title=title,
        collapsed=collapsed,
        checkable=checkable,
    )
    return group_box


def collapsible_group_box_expanded(group_box) -> bool:
    """Return whether a native or fallback collapsible group box is expanded."""

    if hasattr(group_box, "isCollapsed"):
        return not group_box.isCollapsed()
    if hasattr(group_box, "isCheckable") and not group_box.isCheckable():
        return True
    if hasattr(group_box, "isChecked"):
        return bool(group_box.isChecked())
    return True


def make_checkable_list(
    options: Sequence[CheckableListOption],
    *,
    checked_values: Sequence[str] | None = None,
    parent=None,
):
    """Create a native Qt checkable list for multi-select wizard controls.

    QGIS does not provide a native checkable combo box. The wizard should use a
    ``QListWidget`` with ``Qt.ItemIsUserCheckable`` items instead; this helper
    keeps that construction consistent and stores stable option values in
    ``Qt.UserRole`` for later request builders.
    """

    widgets = import_module("qgis.PyQt.QtWidgets")
    checked = set(checked_values or ())
    list_widget = widgets.QListWidget(parent)

    for option in options:
        value, label = _normalise_checkable_list_option(option)
        item = widgets.QListWidgetItem(label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setData(Qt.UserRole, value)
        item.setCheckState(Qt.Checked if value in checked else Qt.Unchecked)
        list_widget.addItem(item)

    return list_widget


def checked_list_values(list_widget) -> list[str]:
    """Return stable values for checked items in list order."""

    values = []
    for index in range(list_widget.count()):
        item = list_widget.item(index)
        if item.checkState() == Qt.Checked:
            values.append(item.data(Qt.UserRole))
    return values


def make_file_widget(
    *,
    file_path: str = "",
    dialog_title: str = "",
    filter_text: str = "",
    storage_mode: object | None = None,
    parent=None,
):
    """Create a file path selector that prefers the native QGIS widget.

    The wizard spec uses ``QgsFileWidget`` for GeoPackage/PDF paths. Minimal
    test environments may not expose it, so fall back to a plain ``QLineEdit``
    while preserving a tiny construction API that wizard pages can share.
    Pass a real ``QgsFileWidget.StorageMode`` enum value as ``storage_mode``;
    string names are not converted.
    """

    gui = _import_optional_qgis_gui()
    file_widget_class = getattr(gui, "QgsFileWidget", None) if gui is not None else None
    if file_widget_class is not None:
        widget = file_widget_class(parent)
        _configure_native_file_widget(
            widget,
            file_path=file_path,
            dialog_title=dialog_title,
            filter_text=filter_text,
            storage_mode=storage_mode,
        )
        return widget

    widgets = import_module("qgis.PyQt.QtWidgets")
    widget = widgets.QLineEdit(parent)
    if file_path:
        widget.setText(file_path)
    if dialog_title:
        widget.setPlaceholderText(dialog_title)
    return widget


def file_widget_path(widget) -> str:
    """Return the selected path from a native or fallback file widget."""

    if hasattr(widget, "filePath"):
        return str(widget.filePath())
    if hasattr(widget, "text"):
        return str(widget.text())
    return ""


def make_password_line_edit(*, text: str = "", placeholder_text: str = "", parent=None):
    """Create a password field that prefers the native QGIS widget.

    QGIS provides ``QgsPasswordLineEdit`` for secret values. Older or minimal
    test environments may not expose it, so fall back to a ``QLineEdit`` with
    password echo mode while keeping the same simple construction API for
    wizard pages and configuration dialogs.
    """

    gui = import_module("qgis.gui")
    password_class = getattr(gui, "QgsPasswordLineEdit", None)
    if password_class is not None:
        widget = password_class(parent)
    else:
        widgets = import_module("qgis.PyQt.QtWidgets")
        widget = widgets.QLineEdit(parent)
        widget.setEchoMode(widgets.QLineEdit.Password)

    if text:
        widget.setText(text)
    if placeholder_text:
        widget.setPlaceholderText(placeholder_text)
    return widget


def make_datetime_range_edits(
    *,
    start_datetime=None,
    end_datetime=None,
    start_enabled: bool | None = None,
    end_enabled: bool | None = None,
    display_format: str = "yyyy-MM-dd HH:mm",
    calendar_popup: bool = True,
    parent=None,
) -> DateTimeRangeEdits:
    """Create paired date-time edits for wizard filter ranges.

    The wizard spec uses two native QGIS date-time edits side by side. Minimal
    test environments may not expose the QGIS widget, so fall back to Qt's
    ``QDateTimeEdit`` while keeping one construction API for future pages.
    """

    gui = _import_optional_qgis_gui()
    edit_class = getattr(gui, "QgsDateTimeEdit", None) if gui is not None else None
    if edit_class is None:
        widgets = import_module("qgis.PyQt.QtWidgets")
        edit_class = widgets.QDateTimeEdit

    start = edit_class(parent)
    end = edit_class(parent)
    _configure_datetime_edit(
        start,
        value=start_datetime,
        display_format=display_format,
        calendar_popup=calendar_popup,
    )
    _configure_datetime_edit(
        end,
        value=end_datetime,
        display_format=display_format,
        calendar_popup=calendar_popup,
    )
    range_edits = DateTimeRangeEdits(
        start=start,
        end=end,
        start_enabled=_resolve_datetime_bound_enabled(start_datetime, start_enabled),
        end_enabled=_resolve_datetime_bound_enabled(end_datetime, end_enabled),
    )
    _bind_datetime_bound_activation(start, range_edits, "start_enabled")
    _bind_datetime_bound_activation(end, range_edits, "end_enabled")
    return range_edits


def datetime_range_values(
    range_edits: DateTimeRangeEdits,
    *,
    start_enabled: bool | None = None,
    end_enabled: bool | None = None,
) -> tuple[object | None, object | None]:
    """Return active start/end date-time values, preserving unset bounds as ``None``."""

    start_is_enabled = range_edits.start_enabled if start_enabled is None else start_enabled
    end_is_enabled = range_edits.end_enabled if end_enabled is None else end_enabled
    start = _datetime_edit_value(range_edits.start) if start_is_enabled else None
    end = _datetime_edit_value(range_edits.end) if end_is_enabled else None
    return (start, end)


def _import_optional_qgis_gui():
    try:
        return import_module("qgis.gui")
    except ModuleNotFoundError as exc:
        if exc.name not in {"qgis", "qgis.gui"}:
            raise
        return None


def _construct_group_box(group_box_class, title: str, parent):
    try:
        return group_box_class(title, parent)
    except TypeError:
        group_box = group_box_class(parent)
        if title and hasattr(group_box, "setTitle"):
            group_box.setTitle(title)
        return group_box


def _configure_collapsible_group_box(
    group_box,
    *,
    title: str,
    collapsed: bool,
    checkable: bool,
) -> None:
    if title and hasattr(group_box, "setTitle"):
        group_box.setTitle(title)
    if hasattr(group_box, "setCheckable"):
        group_box.setCheckable(checkable or collapsed)
    if hasattr(group_box, "setCollapsed"):
        group_box.setCollapsed(collapsed)
    elif hasattr(group_box, "setChecked"):
        group_box.setChecked(not collapsed)


def _configure_native_file_widget(
    widget,
    *,
    file_path: str,
    dialog_title: str,
    filter_text: str,
    storage_mode: object | None,
) -> None:
    if storage_mode is not None and hasattr(widget, "setStorageMode"):
        widget.setStorageMode(storage_mode)
    if filter_text and hasattr(widget, "setFilter"):
        widget.setFilter(filter_text)
    if dialog_title and hasattr(widget, "setDialogTitle"):
        widget.setDialogTitle(dialog_title)
    if file_path:
        widget.setFilePath(file_path)


def _normalise_checkable_list_option(option: CheckableListOption) -> tuple[str, str]:
    if isinstance(option, tuple):
        if len(option) != 2:
            msg = f"Expected a (value, label) pair, got {option!r}"
            raise ValueError(msg)
        return option
    return option, option


def _configure_datetime_edit(
    widget,
    *,
    value,
    display_format: str,
    calendar_popup: bool,
) -> None:
    if value is not None and hasattr(widget, "setDateTime"):
        widget.setDateTime(value)
    if display_format and hasattr(widget, "setDisplayFormat"):
        widget.setDisplayFormat(display_format)
    if hasattr(widget, "setCalendarPopup"):
        widget.setCalendarPopup(calendar_popup)


def _datetime_edit_value(widget):
    if hasattr(widget, "dateTime"):
        return widget.dateTime()
    return None


def _resolve_datetime_bound_enabled(value, enabled: bool | None) -> bool:
    if enabled is not None:
        return enabled
    return value is not None


def _bind_datetime_bound_activation(widget, range_edits: DateTimeRangeEdits, field_name: str) -> None:
    signal = getattr(widget, "dateTimeChanged", None)
    if signal is None or not hasattr(signal, "connect"):
        return
    signal.connect(lambda *_args: setattr(range_edits, field_name, True))


def make_range_slider(
    *,
    minimum: float,
    maximum: float,
    lower: float | None = None,
    upper: float | None = None,
    decimals: int = 1,
    orientation: Qt.Orientation = Qt.Horizontal,
    parent=None,
):
    """Create a double range slider with a QGIS-version-safe fallback.

    QGIS 3.38+ provides QgsDoubleRangeSlider. Earlier supported versions only
    expose QgsRangeSlider, which stores integer values. The fallback scales
    values internally using ``decimals`` while keeping a float-oriented API for
    wizard/page code.
    """

    gui = import_module("qgis.gui")
    precision = _normalise_decimals(decimals)

    slider_class = getattr(gui, "QgsDoubleRangeSlider", None)
    if slider_class is not None:
        slider = _construct_slider(slider_class, orientation, parent)
        _configure_slider(slider, minimum, maximum, lower, upper)
        return slider

    fallback_class = _build_scaled_range_slider(getattr(gui, "QgsRangeSlider"))
    slider = fallback_class(orientation=orientation, parent=parent, decimals=precision)
    _configure_slider(slider, minimum, maximum, lower, upper)
    return slider


def _normalise_decimals(decimals: int) -> int:
    return max(0, int(decimals))


def _construct_slider(slider_class, orientation, parent):
    try:
        return slider_class(orientation, parent)
    except TypeError:
        slider = slider_class(parent)
        if hasattr(slider, "setOrientation"):
            slider.setOrientation(orientation)
        return slider


def _configure_slider(slider, minimum, maximum, lower, upper) -> None:
    lower_value = minimum if lower is None else lower
    upper_value = maximum if upper is None else upper

    if hasattr(slider, "setRangeLimits"):
        slider.setRangeLimits(minimum, maximum)
    else:
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)

    if hasattr(slider, "setRange"):
        slider.setRange(lower_value, upper_value)
    else:
        slider.setLowerValue(lower_value)
        slider.setUpperValue(upper_value)


def _bind_base_signal(signal_owner, signal_name: str, instance):
    signal = getattr(signal_owner, signal_name, None)
    if signal is None:
        return None
    if hasattr(signal, "__get__"):
        signal = signal.__get__(instance, type(instance))
    if not hasattr(signal, "connect"):
        return None
    return signal


@lru_cache(maxsize=None)
def _build_scaled_range_slider(range_slider_class):
    class ScaledRangeSlider(range_slider_class):
        def __init__(self, orientation=Qt.Horizontal, parent=None, *, decimals: int = 1):
            self._scale = 10 ** decimals
            try:
                super().__init__(orientation, parent)
            except TypeError:
                super().__init__(parent)
                if hasattr(self, "setOrientation"):
                    self.setOrientation(orientation)
            self._wire_scaled_signals(range_slider_class)

        def _wire_scaled_signals(self, range_slider_base_class) -> None:
            base_range_changed = _bind_base_signal(
                range_slider_base_class,
                "rangeChanged",
                self,
            )
            base_range_limits_changed = _bind_base_signal(
                range_slider_base_class,
                "rangeLimitsChanged",
                self,
            )
            self.rangeChanged = _ScaledSignal()
            self.rangeLimitsChanged = _ScaledSignal()
            if base_range_changed is not None:
                base_range_changed.connect(self._emit_scaled_range_changed)
            if base_range_limits_changed is not None:
                base_range_limits_changed.connect(self._emit_scaled_range_limits_changed)

        def _emit_scaled_range_changed(self, lower: int, upper: int) -> None:
            self.rangeChanged.emit(
                self._from_slider_value(lower),
                self._from_slider_value(upper),
            )

        def _emit_scaled_range_limits_changed(self, minimum: int, maximum: int) -> None:
            self.rangeLimitsChanged.emit(
                self._from_slider_value(minimum),
                self._from_slider_value(maximum),
            )

        def setRangeLimits(self, minimum: float, maximum: float) -> None:  # noqa: N802
            super().setRangeLimits(self._to_slider_value(minimum), self._to_slider_value(maximum))

        def setMinimum(self, value: float) -> None:  # noqa: N802
            super().setMinimum(self._to_slider_value(value))

        def setMaximum(self, value: float) -> None:  # noqa: N802
            super().setMaximum(self._to_slider_value(value))

        def minimum(self) -> float:
            return self._from_slider_value(super().minimum())

        def maximum(self) -> float:
            return self._from_slider_value(super().maximum())

        def setRange(self, lower: float, upper: float) -> None:  # noqa: N802
            super().setRange(self._to_slider_value(lower), self._to_slider_value(upper))

        def setLowerValue(self, value: float) -> None:  # noqa: N802
            super().setLowerValue(self._to_slider_value(value))

        def setUpperValue(self, value: float) -> None:  # noqa: N802
            super().setUpperValue(self._to_slider_value(value))

        def lowerValue(self) -> float:  # noqa: N802
            return self._from_slider_value(super().lowerValue())

        def upperValue(self) -> float:  # noqa: N802
            return self._from_slider_value(super().upperValue())

        def _to_slider_value(self, value: float) -> int:
            return int(round(float(value) * self._scale))

        def _from_slider_value(self, value: int) -> float:
            return float(value) / self._scale

    return ScaledRangeSlider
