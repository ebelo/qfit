import sys
import types
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401

from qgis.PyQt.QtCore import Qt

from qfit.ui.widgets.compat import make_range_slider


class _FakeIntegerRangeSlider:
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        self.orientation = orientation
        self.parent = parent
        self.limit_values = None
        self.selected_values = None
        self.lower_raw = None
        self.upper_raw = None

    def setRangeLimits(self, minimum, maximum):  # noqa: N802
        self.limit_values = (minimum, maximum)
        self.minimum_raw = minimum
        self.maximum_raw = maximum

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


def _fake_qgis_gui(*, double_range_slider=None):
    module = types.ModuleType("qgis.gui")
    module.QgsRangeSlider = _FakeIntegerRangeSlider
    if double_range_slider is not None:
        module.QgsDoubleRangeSlider = double_range_slider
    return module


class UiWidgetCompatTests(unittest.TestCase):
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

        slider.setLowerValue(6.75)
        slider.setUpperValue(20.5)

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


if __name__ == "__main__":
    unittest.main()
