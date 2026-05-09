import unittest
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_analysis_controls import (
    ANALYSIS_MODE_LABELS,
    NONE_ANALYSIS_MODE_LABEL,
    bind_local_first_analysis_mode_controls,
    configure_local_first_analysis_mode_backing_controls,
    local_first_analysis_mode_options,
    set_local_first_analysis_mode,
)


class FakeComboBox:
    def __init__(self, current_text=""):
        self.items = []
        self.current_text = current_text

    def addItem(self, item):
        self.items.append(item)
        if not self.current_text:
            self.current_text = item

    def count(self):
        return len(self.items)

    def itemText(self, index):
        return self.items[index]

    def currentText(self):
        return self.current_text

    def setCurrentText(self, text):
        self.current_text = text


class FakeLayout:
    def __init__(self):
        self.inserted = []
        self.children = []
        self.contents_margins = None
        self.spacing = None

    def insertWidget(self, index, widget):
        self.inserted.append((index, widget))

    def addWidget(self, widget):
        self.children.append(widget)

    def addStretch(self, stretch):
        self.children.append(("stretch", stretch))

    def setContentsMargins(self, *margins):
        self.contents_margins = margins

    def setSpacing(self, spacing):
        self.spacing = spacing


class FakeWidget:
    def __init__(self, parent=None):
        self._parent = parent
        self._object_name = None
        self._layout = None

    def setObjectName(self, name):
        self._object_name = name

    def objectName(self):
        return self._object_name

    def parentWidget(self):
        return self._parent

    def setLayout(self, layout):
        self._layout = layout

    def layout(self):
        return self._layout


class FakeHBoxLayout(FakeLayout):
    def __init__(self, widget):
        super().__init__()
        widget.setLayout(self)


class FakeLabel(FakeWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._text = text

    def text(self):
        return self._text


class FakeQtComboBox(FakeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []

    def addItem(self, item):
        self.items.append(item)


class FakeButton(FakeWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._text = text

    def text(self):
        return self._text


def install_fake_qtwidgets():
    qgis = ModuleType("qgis")
    pyqt = ModuleType("qgis.PyQt")
    qtwidgets = ModuleType("qgis.PyQt.QtWidgets")
    qtwidgets.QWidget = FakeWidget
    qtwidgets.QHBoxLayout = FakeHBoxLayout
    qtwidgets.QLabel = FakeLabel
    qtwidgets.QComboBox = FakeQtComboBox
    qtwidgets.QPushButton = FakeButton
    qgis.PyQt = pyqt
    pyqt.QtWidgets = qtwidgets
    return {
        "qgis": qgis,
        "qgis.PyQt": pyqt,
        "qgis.PyQt.QtWidgets": qtwidgets,
    }


class LocalFirstAnalysisControlsTests(unittest.TestCase):
    def test_configure_analysis_mode_backing_controls_inserts_hidden_row(self):
        content_layout = FakeLayout()
        dock = SimpleNamespace(analysisWorkflowGroupBox=FakeWidget())
        dock.analysisWorkflowGroupBox.setLayout(content_layout)

        with unittest.mock.patch.dict(sys.modules, install_fake_qtwidgets()):
            configure_local_first_analysis_mode_backing_controls(dock)

        self.assertEqual(len(content_layout.inserted), 1)
        index, row = content_layout.inserted[0]
        self.assertEqual(index, 0)
        self.assertEqual(row.objectName(), "analysisModeRow")
        self.assertIs(row.parentWidget(), dock.analysisWorkflowGroupBox)
        self.assertEqual(dock.analysisModeLabel.text(), "Analysis")
        self.assertEqual(dock.analysisModeComboBox.items, list(ANALYSIS_MODE_LABELS))
        self.assertEqual(dock.runAnalysisButton.text(), "Run analysis")

    def test_mode_options_exclude_legacy_none_sentinel(self):
        combo = FakeComboBox()
        for mode in ("None", "Heatmap", "Most frequent starting points"):
            combo.addItem(mode)

        self.assertEqual(
            local_first_analysis_mode_options(combo),
            ("Heatmap", "Most frequent starting points"),
        )

    def test_bind_exposes_user_facing_modes_and_selects_first_real_mode(self):
        combo = FakeComboBox(current_text="None")
        for mode in ("None", "Heatmap", "Most frequent starting points"):
            combo.addItem(mode)
        dock = SimpleNamespace(analysisModeComboBox=combo)
        analysis_content = SimpleNamespace(set_analysis_mode_options=MagicMock())

        bind_local_first_analysis_mode_controls(
            dock,
            SimpleNamespace(analysis_content=analysis_content),
        )

        analysis_content.set_analysis_mode_options.assert_called_once_with(
            ("Heatmap", "Most frequent starting points"),
            selected="Heatmap",
        )
        self.assertEqual(combo.currentText(), "Heatmap")

    def test_bind_preserves_supported_current_mode(self):
        combo = FakeComboBox(current_text="Most frequent starting points")
        for mode in ("None", "Heatmap", "Most frequent starting points"):
            combo.addItem(mode)
        dock = SimpleNamespace(analysisModeComboBox=combo)
        analysis_content = SimpleNamespace(set_analysis_mode_options=MagicMock())

        bind_local_first_analysis_mode_controls(
            dock,
            SimpleNamespace(analysis_content=analysis_content),
        )

        analysis_content.set_analysis_mode_options.assert_called_once_with(
            ("Heatmap", "Most frequent starting points"),
            selected="Most frequent starting points",
        )
        self.assertEqual(combo.currentText(), "Most frequent starting points")

    def test_set_local_first_analysis_mode_updates_backing_combo(self):
        combo = FakeComboBox(current_text="None")
        dock = SimpleNamespace(analysisModeComboBox=combo)

        set_local_first_analysis_mode(dock, "Most frequent starting points")

        self.assertEqual(combo.currentText(), "Most frequent starting points")

    def test_bind_skips_missing_analysis_content(self):
        combo = FakeComboBox(current_text=NONE_ANALYSIS_MODE_LABEL)
        combo.addItem(NONE_ANALYSIS_MODE_LABEL)
        combo.addItem("Heatmap")
        dock = SimpleNamespace(analysisModeComboBox=combo)

        bind_local_first_analysis_mode_controls(dock, SimpleNamespace())

        self.assertEqual(combo.currentText(), NONE_ANALYSIS_MODE_LABEL)

    def test_bind_skips_empty_user_facing_mode_options(self):
        combo = FakeComboBox(current_text=NONE_ANALYSIS_MODE_LABEL)
        combo.addItem(NONE_ANALYSIS_MODE_LABEL)
        dock = SimpleNamespace(analysisModeComboBox=combo)
        analysis_content = SimpleNamespace(set_analysis_mode_options=MagicMock())

        bind_local_first_analysis_mode_controls(
            dock,
            SimpleNamespace(analysis_content=analysis_content),
        )

        analysis_content.set_analysis_mode_options.assert_not_called()
        self.assertEqual(combo.currentText(), NONE_ANALYSIS_MODE_LABEL)


if __name__ == "__main__":
    unittest.main()
