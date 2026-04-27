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
    AlignCenter = 9
    ForbiddenCursor = 10
    Horizontal = 13
    Orientation = int
    PointingHandCursor = 11
    ToolButtonTextBesideIcon = 12
    Vertical = 14


class _FakeWidget:
    def __init__(self, parent=None):
        self.parent = parent
        self._height = None
        self._minimum_height = None
        self._minimum_width = None
        self._object_name = ""
        self._properties = {}
        self._enabled = True
        self._cursor = _FakeCursor(None)
        self._tooltip = ""
        self._stylesheet = ""
        self._alignment = None
        self._visible = True

    def setVisible(self, value):  # noqa: N802
        self._visible = value

    def isVisible(self):  # noqa: N802
        return self._visible

    def setFixedHeight(self, value):  # noqa: N802
        self._height = value

    def setMinimumHeight(self, value):  # noqa: N802
        self._minimum_height = value

    def minimumHeight(self):  # noqa: N802
        return self._minimum_height

    def setMinimumWidth(self, value):  # noqa: N802
        self._minimum_width = value

    def minimumWidth(self):  # noqa: N802
        return self._minimum_width

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

    def setAlignment(self, value):  # noqa: N802
        self._alignment = value

    def alignment(self):
        return self._alignment

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


class _FakeComboBox(_FakeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentTextChanged = _FakeSignal()
        self.items = []
        self._current_text = ""

    def addItem(self, text):  # noqa: N802
        self.items.append(text)
        if not self._current_text:
            self._current_text = text

    def clear(self):
        self.items = []
        self._current_text = ""

    def count(self):
        return len(self.items)

    def itemText(self, index):  # noqa: N802
        return self.items[index]

    def setCurrentText(self, text):  # noqa: N802
        self._current_text = text
        self.currentTextChanged.emit(text)

    def currentText(self):  # noqa: N802
        return self._current_text


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
        self.word_wrap = False

    def setText(self, value):  # noqa: N802
        self._text = value

    def text(self):
        return self._text

    def setWordWrap(self, value):  # noqa: N802
        self.word_wrap = value


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

    def widget(self, index):
        return self.widgets[index]


class _FakeVBoxLayout:
    def __init__(self, parent=None):
        self.parent = parent
        self.object_name = ""
        self.contents_margins = None
        self.spacing = None
        self.direction = None
        self.widgets = []
        self.stretches = []

    def setObjectName(self, value):  # noqa: N802
        self.object_name = value

    def setContentsMargins(self, *values):  # noqa: N802
        self.contents_margins = values

    def setSpacing(self, value):  # noqa: N802
        self.spacing = value

    def setDirection(self, value):  # noqa: N802
        self.direction = value

    def addWidget(self, widget):  # noqa: N802
        self.widgets.append(widget)

    def addStretch(self, stretch=0):  # noqa: N802
        self.stretches.append(stretch)


class _FakeHBoxLayout(_FakeVBoxLayout):
    pass


class _FakeBoxLayout:
    LeftToRight = 1
    TopToBottom = 2


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
    qtwidgets.QBoxLayout = _FakeBoxLayout
    qtwidgets.QComboBox = _FakeComboBox
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
        "qfit.ui.dockwidget.footer_status_bar",
        "qfit.ui.dockwidget.stepper_bar",
        "qfit.ui.widgets.pill",
        "qfit.ui.widgets.compat",
        "qfit.ui.widgets",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.wizard_shell")


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
        self.assertEqual(shell.footer_bar.path_label.text(), "Ready")

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
        self.assertEqual(shell.stepper_bar.states(), ("done", "current", "upcoming", "locked", "locked"))

        shell.set_current_step(1)

        self.assertEqual(shell.page_count(), 2)
        self.assertEqual(shell.stepper_bar.states(), ("upcoming", "current", "upcoming", "upcoming", "upcoming"))
        self.assertEqual(shell.pages_stack.currentIndex(), 1)

    def test_propagates_responsive_width_to_stepper_and_pages(self):
        class ResponsivePage(_FakeWidget):
            def __init__(self):
                super().__init__()
                self.widths = []

            def set_responsive_width(self, width):
                self.widths.append(width)

        shell = self.wizard_shell.WizardShell()
        page = ResponsivePage()
        shell.add_page(page)

        shell.set_responsive_width(320)

        self.assertEqual(shell.property("responsiveMode"), "narrow")
        self.assertEqual(shell.stepper_bar.property("responsiveMode"), "compact")
        self.assertEqual(page.widths, [320])

    def test_resize_event_propagates_responsive_width_to_pages(self):
        class ResponsivePage(_FakeWidget):
            def __init__(self):
                super().__init__()
                self.widths = []

            def set_responsive_width(self, width):
                self.widths.append(width)

        shell = self.wizard_shell.WizardShell()
        page = ResponsivePage()
        shell.add_page(page)

        shell.resizeEvent(_FakeResizeEvent(320))

        self.assertEqual(shell.property("responsiveMode"), "narrow")
        self.assertEqual(shell.stepper_bar.property("responsiveMode"), "compact")
        self.assertEqual(page.widths, [320])

    def test_new_pages_receive_current_responsive_width_after_resize(self):
        class ResponsivePage(_FakeWidget):
            def __init__(self):
                super().__init__()
                self.widths = []

            def set_responsive_width(self, width):
                self.widths.append(width)

        shell = self.wizard_shell.WizardShell()
        shell.set_responsive_width(320)
        page = ResponsivePage()

        shell.add_page(page)

        self.assertEqual(page.widths, [320])

    def test_updates_footer_text_without_rebuilding_shell(self):
        shell = self.wizard_shell.WizardShell(footer_text="Starting")

        shell.set_footer_text("Connected · 42 activities")

        self.assertEqual(shell.footer_bar.text(), "Connected · 42 activities")
        self.assertEqual(shell.footer_bar.path_label.text(), "Connected · 42 activities")
        self.assertEqual(shell.footer_bar.toolTip(), "Connected · 42 activities")

    def test_footer_bar_exposes_spec_pill_and_path_api(self):
        footer = self.wizard_shell.FooterStatusBar(footer_text="Ready")

        footer.set_strava(True)
        footer.set_activity_count(1)
        footer.set_sync_date("2026-04-16")
        footer.set_layer_count(3)
        footer.set_gpkg_path("/tmp/qfit-test/activities.gpkg")

        self.assertEqual(footer.strava_pill.objectName(), "qfitWizardFooterStravaPill")
        self.assertEqual(footer.strava_pill.text(), "● Strava")
        self.assertEqual(footer.strava_pill.property("tone"), "ok")
        self.assertEqual(footer.activity_pill.text(), "1 activity")
        self.assertEqual(footer.activity_pill.property("tone"), "info")
        self.assertEqual(footer.sync_pill.text(), "sync 2026-04-16")
        self.assertEqual(footer.sync_pill.property("tone"), "neutral")
        self.assertEqual(footer.layer_pill.text(), "3 layers")
        self.assertEqual(footer.layer_pill.property("tone"), "neutral")
        self.assertEqual(footer.path_label.text(), "activities.gpkg")
        self.assertEqual(footer.path_label.toolTip(), "/tmp/qfit-test/activities.gpkg")

    def test_footer_bar_keeps_windows_paths_compact_on_non_windows_hosts(self):
        footer = self.wizard_shell.FooterStatusBar(footer_text="Ready")

        footer.set_gpkg_path(r"C:\Users\Emman\qfit\activities.gpkg")

        self.assertEqual(footer.path_label.text(), "activities.gpkg")
        self.assertEqual(
            footer.path_label.toolTip(),
            r"C:\Users\Emman\qfit\activities.gpkg",
        )

    def test_footer_bar_uses_muted_copy_for_unknown_counts(self):
        footer = self.wizard_shell.FooterStatusBar()

        footer.set_strava(False)
        footer.set_activity_count(None)
        footer.set_sync_date(None)
        footer.set_layer_count(0)
        footer.set_gpkg_path(None)

        self.assertEqual(footer.strava_pill.property("tone"), "danger")
        self.assertEqual(footer.activity_pill.text(), "— activities")
        self.assertEqual(footer.activity_pill.property("tone"), "muted")
        self.assertEqual(footer.sync_pill.text(), "sync —")
        self.assertEqual(footer.sync_pill.property("tone"), "muted")
        self.assertEqual(footer.layer_pill.text(), "0 layers")
        self.assertEqual(footer.layer_pill.property("tone"), "muted")
        self.assertEqual(footer.path_label.text(), "qfit.gpkg")

    def test_footer_bar_uses_muted_tone_for_zero_activities(self):
        footer = self.wizard_shell.FooterStatusBar()

        footer.set_activity_count(0)

        self.assertEqual(footer.activity_pill.text(), "0 activities")
        self.assertEqual(footer.activity_pill.property("tone"), "muted")

    def test_footer_status_text_can_clear_compatibility_label(self):
        footer = self.wizard_shell.FooterStatusBar(footer_text="Ready")

        footer.set_status_text("")

        self.assertEqual(footer.text(), "")
        self.assertEqual(footer.path_label.text(), "")
        self.assertEqual(footer.toolTip(), "")

    def test_explicit_empty_gpkg_path_is_not_overwritten_by_status_refresh(self):
        footer = self.wizard_shell.FooterStatusBar(footer_text="Ready")

        footer.set_gpkg_path(None)
        footer.set_status_text("Connected · 42 activities")

        self.assertEqual(footer.text(), "Connected · 42 activities")
        self.assertEqual(footer.path_label.text(), "qfit.gpkg")


if __name__ == "__main__":
    unittest.main()
