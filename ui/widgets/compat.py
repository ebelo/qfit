from __future__ import annotations

from functools import lru_cache
from importlib import import_module

from qgis.PyQt.QtCore import Qt


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
        for slot in list(self._slots):
            slot(*args)


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
