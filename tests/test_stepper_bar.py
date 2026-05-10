import importlib
import sys
import types
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401


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
    def __set_name__(self, owner, name):
        self.name = f"_{name}_signal"

    def __get__(self, instance, _owner):
        if instance is None:
            return self
        signal = instance.__dict__.get(self.name)
        if signal is None:
            signal = _FakeSignal()
            instance.__dict__[self.name] = signal
        return signal


def _fake_pyqt_signal(*_args, **_kwargs):
    return _FakeSignalDescriptor()


class _FakeCursor:
    def __init__(self, shape):
        self._shape = shape

    def shape(self):
        return self._shape


class _FakeQt:
    ForbiddenCursor = 10
    PointingHandCursor = 11
    ToolButtonTextBesideIcon = 12
    Horizontal = 13
    Orientation = int


class _FakeWidget:
    def __init__(self, parent=None):
        self.parent = parent
        self._height = None
        self._minimum_width = None
        self._object_name = ""
        self._properties = {}
        self._enabled = True
        self._cursor = _FakeCursor(None)
        self._tooltip = ""
        self._stylesheet = ""

    def setFixedHeight(self, value):  # noqa: N802
        self._height = value

    def height(self):
        return self._height

    def setMinimumWidth(self, value):  # noqa: N802
        self._minimum_width = value

    def minimumWidth(self):  # noqa: N802
        return self._minimum_width

    def setObjectName(self, value):  # noqa: N802
        self._object_name = value

    def objectName(self):  # noqa: N802
        return self._object_name

    def setProperty(self, name, value):  # noqa: N802
        self._properties[name] = value

    def property(self, name):
        return self._properties.get(name)

    def setEnabled(self, enabled):  # noqa: N802
        self._enabled = enabled

    def isEnabled(self):  # noqa: N802
        return self._enabled

    def setCursor(self, shape):  # noqa: N802
        self._cursor = _FakeCursor(shape)

    def cursor(self):
        return self._cursor

    def setToolTip(self, value):  # noqa: N802
        self._tooltip = value

    def toolTip(self):  # noqa: N802
        return self._tooltip

    def setStyleSheet(self, value):  # noqa: N802
        self._stylesheet = value

    def styleSheet(self):  # noqa: N802
        return self._stylesheet


class _FakeToolButton(_FakeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.clicked = _FakeSignal()
        self._text = ""
        self.tool_button_style = None
        self.size_policy = None

    def setToolButtonStyle(self, value):  # noqa: N802
        self.tool_button_style = value

    def setSizePolicy(self, horizontal, vertical):  # noqa: N802
        self.size_policy = (horizontal, vertical)

    def setText(self, value):  # noqa: N802
        self._text = value

    def text(self):
        return self._text

    def click(self):
        if self.isEnabled():
            self.clicked.emit(False)


class _FakeFrame(_FakeWidget):
    HLine = 1
    Plain = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame_shape = None
        self.frame_shadow = None
        self.fixed_width = None

    def setFrameShape(self, value):  # noqa: N802
        self.frame_shape = value

    def setFrameShadow(self, value):  # noqa: N802
        self.frame_shadow = value

    def setFixedWidth(self, value):  # noqa: N802
        self.fixed_width = value


class _FakeHBoxLayout:
    def __init__(self, parent=None):
        self.parent = parent
        self.contents_margins = None
        self.spacing = None
        self.widgets = []

    def setContentsMargins(self, *values):  # noqa: N802
        self.contents_margins = values

    def setSpacing(self, value):  # noqa: N802
        self.spacing = value

    def addWidget(self, widget):  # noqa: N802
        self.widgets.append(widget)


class _FakeSizePolicy:
    Expanding = 1
    Fixed = 2
    Ignored = 3
    Preferred = 4


def _fake_qt_modules():
    qgis = types.ModuleType("qgis")
    pyqt = types.ModuleType("qgis.PyQt")
    pyqt.__path__ = []
    qtcore = types.ModuleType("qgis.PyQt.QtCore")
    qtcore.Qt = _FakeQt
    qtcore.pyqtSignal = _fake_pyqt_signal
    qtwidgets = types.ModuleType("qgis.PyQt.QtWidgets")
    qtwidgets.QFrame = _FakeFrame
    qtwidgets.QHBoxLayout = _FakeHBoxLayout
    qtwidgets.QSizePolicy = _FakeSizePolicy
    qtwidgets.QToolButton = _FakeToolButton
    qtwidgets.QWidget = _FakeWidget
    qgis.PyQt = pyqt
    return {
        "qgis": qgis,
        "qgis.PyQt": pyqt,
        "qgis.PyQt.QtCore": qtcore,
        "qgis.PyQt.QtWidgets": qtwidgets,
    }


def _load_stepper_module():
    for name in ("qfit.ui.dockwidget.stepper_bar", "qfit.ui.dockwidget"):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.stepper_bar")


class _FakeSize:
    def __init__(self, width):
        self._width = width

    def width(self):
        return self._width


class _FakeResizeEvent:
    def __init__(self, width):
        self._size = _FakeSize(width)

    def size(self):
        return self._size


class StepperBarTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stepper = _load_stepper_module()

    def test_initial_state_matches_first_launch_spec(self):
        bar = self.stepper.StepperBar()

        self.assertEqual(bar.states(), ("current", "locked", "locked", "locked", "locked"))
        self.assertEqual(len(bar.step_buttons()), 5)
        self.assertEqual(
            [button.toolTip() for button in bar.step_buttons()],
            [
                "Connection",
                "Complete Connection before opening Synchronization.",
                "Complete Synchronization before opening Map & filters.",
                "Complete Map & filters before opening Spatial analysis (optional).",
                "Complete Map & filters before opening Atlas PDF.",
            ],
        )
        self.assertEqual(bar.height(), 36)

    def test_labels_come_from_shared_workflow_metadata(self):
        self.assertEqual(
            self.stepper.STEPPER_LABELS,
            (
                "Connection",
                "Synchronization",
                "Map & filters",
                "Spatial analysis (optional)",
                "Atlas PDF",
            ),
        )

    def test_qt_import_guard_requires_all_widget_classes(self):
        incomplete_qtwidgets = types.ModuleType("qgis.PyQt.QtWidgets")
        incomplete_qtwidgets.QWidget = object
        fallback_qtwidgets = types.ModuleType("fallback.QtWidgets")
        fallback_qtwidgets.QWidget = object
        fallback_qtwidgets.QFrame = object
        with patch.dict(
            sys.modules,
            {
                "qgis.PyQt.QtWidgets": incomplete_qtwidgets,
                "fallback.QtWidgets": fallback_qtwidgets,
            },
        ):
            module = self.stepper.import_qt_module(
                "qgis.PyQt.QtWidgets",
                "fallback.QtWidgets",
                ("QWidget", "QFrame"),
            )

        self.assertIs(module, fallback_qtwidgets)

    def test_set_state_does_not_require_python310_zip_strict_keyword(self):
        original_zip = zip

        def python39_zip(*args, **kwargs):
            if kwargs:
                raise TypeError("zip() takes no keyword arguments")
            return original_zip(*args)

        bar = self.stepper.StepperBar()
        with patch("builtins.zip", python39_zip):
            bar.set_state(["done", "current", "upcoming", "locked", "upcoming"])

        self.assertEqual(bar.states(), ("done", "current", "upcoming", "locked", "upcoming"))

    def test_applies_state_properties_and_labels(self):
        bar = self.stepper.StepperBar()

        bar.set_state(["done", "current", "upcoming", "locked", "upcoming"])

        buttons = bar.step_buttons()
        self.assertEqual(bar.states(), ("done", "current", "upcoming", "locked", "upcoming"))
        self.assertTrue(buttons[0].text().startswith("✓"))
        self.assertEqual(buttons[1].property("workflowState"), "current")
        self.assertEqual(buttons[1].property("wizardState"), "current")
        self.assertTrue(buttons[2].isEnabled())
        self.assertEqual(buttons[2].toolTip(), "Map & filters")
        self.assertFalse(buttons[3].isEnabled())
        self.assertEqual(
            buttons[3].toolTip(),
            "Complete Map & filters before opening Spatial analysis (optional).",
        )
        self.assertEqual(buttons[3].cursor().shape(), _FakeQt.ForbiddenCursor)
        self.assertEqual(
            [connector.property("workflowState") for connector in bar._connectors],
            ["done", "upcoming", "upcoming", "upcoming"],
        )
        self.assertEqual(
            [connector.property("wizardState") for connector in bar._connectors],
            ["done", "upcoming", "upcoming", "upcoming"],
        )

    def test_set_current_marks_other_steps_upcoming(self):
        bar = self.stepper.StepperBar()

        bar.set_current(2)

        self.assertEqual(bar.states(), ("upcoming", "upcoming", "current", "upcoming", "upcoming"))

    def test_locked_first_step_gets_generic_unavailable_tooltip(self):
        bar = self.stepper.StepperBar()

        bar.set_state(["locked", "locked", "locked", "locked", "locked"])

        self.assertEqual(
            bar.step_buttons()[0].toolTip(),
            "This step is not yet available.",
        )

    def test_rejects_invalid_state_payloads(self):
        bar = self.stepper.StepperBar()

        with self.assertRaisesRegex(ValueError, "requires 5 states"):
            bar.set_state(["current"])

        with self.assertRaisesRegex(ValueError, "Unknown stepper state"):
            bar.set_state(["current", "done", "waiting", "locked", "upcoming"])

        with self.assertRaisesRegex(ValueError, "outside 0..4"):
            bar.set_current(5)

    def test_emits_requested_index_only_for_unlocked_steps(self):
        bar = self.stepper.StepperBar()
        requested = []
        bar.stepRequested.connect(requested.append)
        bar.set_state(["done", "current", "upcoming", "locked", "upcoming"])

        buttons = bar.step_buttons()
        buttons[0].click()
        buttons[2].click()
        buttons[3].click()

        self.assertEqual(requested, [0, 2])

    def test_compacts_step_labels_for_narrow_docks(self):
        bar = self.stepper.StepperBar()
        bar.set_state(["done", "current", "upcoming", "locked", "upcoming"])

        bar.set_responsive_width(320)

        self.assertEqual(bar.property("responsiveMode"), "compact")
        self.assertEqual(bar.height(), self.stepper.STEPPER_COMPACT_HEIGHT)
        self.assertEqual(
            [button.text() for button in bar.step_buttons()],
            ["✓", "2", "3", "4", "5"],
        )
        self.assertEqual(
            [button.property("responsiveMode") for button in bar.step_buttons()],
            ["compact"] * 5,
        )
        self.assertEqual([connector.fixed_width for connector in bar._connectors], [4, 4, 4, 4])
        self.assertEqual(bar._layout.contents_margins, (2, 2, 6, 2))
        self.assertEqual(bar._layout.spacing, 2)

        bar.set_responsive_width(800)

        self.assertEqual(bar.property("responsiveMode"), "wide")
        self.assertEqual(bar.height(), self.stepper.STEPPER_WIDE_HEIGHT)
        self.assertEqual(bar.step_buttons()[1].text(), "2  Synchronization")
        self.assertEqual([connector.fixed_width for connector in bar._connectors], [8, 8, 8, 8])

    def test_resize_event_drives_compact_stepper_mode(self):
        bar = self.stepper.StepperBar()

        bar.resizeEvent(_FakeResizeEvent(320))

        self.assertEqual(bar.property("responsiveMode"), "compact")
        self.assertEqual(bar.height(), self.stepper.STEPPER_COMPACT_HEIGHT)


if __name__ == "__main__":
    unittest.main()
