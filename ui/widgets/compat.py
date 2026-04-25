from __future__ import annotations

from importlib import import_module

from qgis.PyQt.QtCore import Qt


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
    values internally while keeping a float-oriented API for wizard/page code.
    """

    gui = import_module("qgis.gui")

    slider_class = getattr(gui, "QgsDoubleRangeSlider", None)
    if slider_class is not None:
        slider = _construct_slider(slider_class, orientation, parent)
        _configure_slider(slider, minimum, maximum, lower, upper)
        return slider

    fallback_class = _build_scaled_range_slider(getattr(gui, "QgsRangeSlider"))
    slider = fallback_class(orientation=orientation, parent=parent, decimals=decimals)
    _configure_slider(slider, minimum, maximum, lower, upper)
    return slider


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


def _build_scaled_range_slider(range_slider_class):
    class ScaledRangeSlider(range_slider_class):
        def __init__(self, orientation=Qt.Horizontal, parent=None, *, decimals: int = 1):
            self._scale = 10 ** max(0, int(decimals))
            try:
                super().__init__(orientation, parent)
            except TypeError:
                super().__init__(parent)
                if hasattr(self, "setOrientation"):
                    self.setOrientation(orientation)

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
