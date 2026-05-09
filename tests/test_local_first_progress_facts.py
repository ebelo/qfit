import unittest
from types import SimpleNamespace

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_progress_facts import (
    current_local_first_activity_style_preset,
    current_local_first_background_facts,
    current_local_first_visual_temporal_mode,
)
from qfit.visualization.application import DEFAULT_TEMPORAL_MODE_LABEL


class _FakeCheckBox:
    def __init__(self, checked):
        self._checked = checked

    def isChecked(self):
        return self._checked


class _FakeComboBox:
    def __init__(self, text):
        self._text = text

    def currentText(self):
        return self._text


class _FailingComboBox:
    def currentText(self):
        raise RuntimeError("deleted widget")


class _FakeLayer:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class TestLocalFirstProgressFacts(unittest.TestCase):
    def test_activity_style_preset_reads_trimmed_combo_text(self):
        dock = SimpleNamespace(stylePresetComboBox=_FakeComboBox(" Simple lines "))

        self.assertEqual(
            current_local_first_activity_style_preset(dock),
            "Simple lines",
        )

    def test_activity_style_preset_handles_missing_or_deleted_combo(self):
        self.assertIsNone(current_local_first_activity_style_preset(SimpleNamespace()))
        self.assertIsNone(
            current_local_first_activity_style_preset(
                SimpleNamespace(stylePresetComboBox=_FailingComboBox())
            )
        )

    def test_background_facts_report_disabled_basemap(self):
        dock = SimpleNamespace(
            backgroundMapCheckBox=_FakeCheckBox(False),
            backgroundPresetComboBox=_FakeComboBox("Outdoors"),
        )
        runtime_state = SimpleNamespace(background_layer=None)

        self.assertEqual(
            current_local_first_background_facts(dock, runtime_state),
            (False, False, None),
        )

    def test_background_facts_prefer_loaded_layer_over_pending_ui(self):
        dock = SimpleNamespace(
            backgroundMapCheckBox=_FakeCheckBox(False),
            backgroundPresetComboBox=_FakeComboBox("Outdoors"),
        )
        runtime_state = SimpleNamespace(background_layer=_FakeLayer("Satellite"))

        self.assertEqual(
            current_local_first_background_facts(dock, runtime_state),
            (True, True, "Satellite"),
        )

    def test_background_facts_report_enabled_basemap_name(self):
        dock = SimpleNamespace(
            backgroundMapCheckBox=_FakeCheckBox(True),
            backgroundPresetComboBox=_FakeComboBox(" Satellite "),
        )
        runtime_state = SimpleNamespace(background_layer=None)

        self.assertEqual(
            current_local_first_background_facts(dock, runtime_state),
            (True, False, "Satellite"),
        )

    def test_visual_temporal_mode_reads_trimmed_combo_text(self):
        dock = SimpleNamespace(temporalModeComboBox=_FakeComboBox(" Activity time "))

        self.assertEqual(
            current_local_first_visual_temporal_mode(dock),
            "Activity time",
        )

    def test_visual_temporal_mode_falls_back_to_default_for_missing_blank_or_deleted_combo(self):
        self.assertEqual(
            current_local_first_visual_temporal_mode(SimpleNamespace()),
            DEFAULT_TEMPORAL_MODE_LABEL,
        )
        self.assertEqual(
            current_local_first_visual_temporal_mode(
                SimpleNamespace(temporalModeComboBox=_FakeComboBox("   "))
            ),
            DEFAULT_TEMPORAL_MODE_LABEL,
        )
        self.assertEqual(
            current_local_first_visual_temporal_mode(
                SimpleNamespace(temporalModeComboBox=_FailingComboBox())
            ),
            DEFAULT_TEMPORAL_MODE_LABEL,
        )


if __name__ == "__main__":
    unittest.main()
