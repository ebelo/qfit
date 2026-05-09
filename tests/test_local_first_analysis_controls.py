import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_analysis_controls import (
    bind_local_first_analysis_mode_controls,
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


class LocalFirstAnalysisControlsTests(unittest.TestCase):
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
        combo = FakeComboBox(current_text="None")
        combo.addItem("None")
        combo.addItem("Heatmap")
        dock = SimpleNamespace(analysisModeComboBox=combo)

        bind_local_first_analysis_mode_controls(dock, SimpleNamespace())

        self.assertEqual(combo.currentText(), "None")


if __name__ == "__main__":
    unittest.main()
