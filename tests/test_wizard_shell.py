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


class _FakeWidget:
    def __init__(self, parent=None):
        self.parent = parent
        self._height = None
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

    def setText(self, value):
        self._text = value

    def text(self):
        return self._text


class _FakeFrame(_FakeWidget):
    HLine = 1
    Plain = 2
    NoFrame = 3

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


class _FakeLabel(_FakeWidget):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = text

    def setText(self, value):  # noqa: N802
        self._text = value

    def text(self):
        return self._text


class _FakeScrollArea(_FakeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget_resizable = False
        self.widget = None
        self.frame_shape = None

    def setWidgetResizable(self, value):  # noqa: N802
        self.widget_resizable = value

    def setWidget(self, widget):  # noqa: N802
        self.widget = widget

    def setFrameShape(self, value):  # noqa: N802
        self.frame_shape = value


class _FakeStackedWidget(_FakeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.widgets = []
        self.current_index = -1

    def addWidget(self, widget):  # noqa: N802
        self.widgets.append(widget)
        if self.current_index == -1:
            self.current_index = 0
        return len(self.widgets) - 1

    def count(self):
        return len(self.widgets)

    def setCurrentIndex(self, index):  # noqa: N802
        self.current_index = index

    def currentIndex(self):  # noqa: N802
        return self.current_index


class _FakeVBoxLayout:
    def __init__(self, parent=None):
        self.parent = parent
        self.object_name = ""
        self.contents_margins = None
        self.spacing = None
        self.widgets = []

    def setObjectName(self, value):  # noqa: N802
        self.object_name = value

    def setContentsMargins(self, *values):  # noqa: N802
        self.contents_margins = values

    def setSpacing(self, value):  # noqa: N802
        self.spacing = value

    def addWidget(self, widget):  # noqa: N802
        self.widgets.append(widget)


class _FakeHBoxLayout(_FakeVBoxLayout):
    pass


class _FakeSizePolicy:
    Expanding = 1
    Fixed = 2


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
    qtwidgets.QLabel = _FakeLabel
    qtwidgets.QScrollArea = _FakeScrollArea
    qtwidgets.QSizePolicy = _FakeSizePolicy
    qtwidgets.QStackedWidget = _FakeStackedWidget
    qtwidgets.QToolButton = _FakeToolButton
    qtwidgets.QVBoxLayout = _FakeVBoxLayout
    qtwidgets.QWidget = _FakeWidget
    qgis.PyQt = pyqt
    return {
        "qgis": qgis,
        "qgis.PyQt": pyqt,
        "qgis.PyQt.QtCore": qtcore,
        "qgis.PyQt.QtWidgets": qtwidgets,
    }


def _load_wizard_shell_module():
    for name in (
        "qfit.ui.dockwidget.wizard_shell",
        "qfit.ui.dockwidget.stepper_bar",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.wizard_shell")


class WizardShellTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wizard_shell = _load_wizard_shell_module()

    def test_builds_spec_shell_structure_with_empty_pages_stack(self):
        shell = self.wizard_shell.WizardShell(footer_text="Ready")

        self.assertEqual(shell.objectName(), "qfitWizardShell")
        self.assertEqual(shell.stepper_bar.objectName(), "qfitStepperBar")
        self.assertEqual(shell.separator.objectName(), "qfitWizardShellSeparator")
        self.assertEqual(shell.separator.frame_shape, _FakeFrame.HLine)
        self.assertEqual(shell.content_scroll.objectName(), "qfitWizardContentScroll")
        self.assertTrue(shell.content_scroll.widget_resizable)
        self.assertEqual(shell.content_scroll.frame_shape, _FakeFrame.NoFrame)
        self.assertIs(shell.content_scroll.widget, shell.pages_stack)
        self.assertEqual(shell.pages_stack.objectName(), "qfitWizardPagesStack")
        self.assertEqual(shell.page_count(), 0)
        self.assertEqual(shell.footer_bar.objectName(), "qfitWizardFooterBar")
        self.assertEqual(shell.footer_bar.height(), 28)
        self.assertEqual(shell.footer_bar.text(), "Ready")

    def test_outer_layout_matches_wizard_spec_order(self):
        shell = self.wizard_shell.WizardShell()
        layout = shell.outer_layout()

        self.assertEqual(layout.object_name, "qfitWizardOuterLayout")
        self.assertEqual(layout.contents_margins, (0, 0, 0, 0))
        self.assertEqual(layout.spacing, 0)
        self.assertEqual(
            layout.widgets,
            [shell.stepper_bar, shell.separator, shell.content_scroll, shell.footer_bar],
        )

    def test_delegates_stepper_state_and_page_selection(self):
        shell = self.wizard_shell.WizardShell()
        first_page = _FakeWidget()
        second_page = _FakeWidget()

        self.assertEqual(shell.add_page(first_page), 0)
        self.assertEqual(shell.add_page(second_page), 1)
        shell.set_step_states(["done", "current", "upcoming", "locked", "locked"])
        shell.set_current_step(1)

        self.assertEqual(shell.page_count(), 2)
        self.assertEqual(shell.stepper_bar.states(), ("upcoming", "current", "upcoming", "upcoming", "upcoming"))
        self.assertEqual(shell.pages_stack.currentIndex(), 1)

    def test_updates_footer_text_without_rebuilding_shell(self):
        shell = self.wizard_shell.WizardShell(footer_text="Starting")

        shell.set_footer_text("Connected · 42 activities")

        self.assertEqual(shell.footer_bar.text(), "Connected · 42 activities")


if __name__ == "__main__":
    unittest.main()
