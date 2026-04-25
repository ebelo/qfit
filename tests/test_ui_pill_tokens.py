import sys
import types
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401

from qfit.ui.widgets import (
    COLOR_ACCENT,
    PILL_TONES,
    PRIMARY_BTN_QSS,
    Pill,
    build_pill_stylesheet,
    make_pill,
    pill_tone,
    pill_tone_palette,
    set_pill_tone,
)


class UiPillTokensTests(unittest.TestCase):
    def test_tokens_match_wizard_spec_values(self):
        self.assertEqual(COLOR_ACCENT, "#589632")
        self.assertEqual(PILL_TONES["ok"], ("#dcefd0", "#2e6318"))
        self.assertEqual(PILL_TONES["info"], ("#d6e7f7", "#124c8c"))
        self.assertIn('QPushButton[role="primary"]', PRIMARY_BTN_QSS)
        self.assertIn("#3f6e22", PRIMARY_BTN_QSS)

    def test_pill_tone_palette_rejects_unknown_tones(self):
        with self.assertRaisesRegex(ValueError, "Unknown pill tone"):
            pill_tone_palette("missing")

    def test_pill_stylesheet_is_scoped_to_object_name_and_tone(self):
        stylesheet = build_pill_stylesheet("danger", object_name="connectionPill")

        self.assertIn("QLabel#connectionPill", stylesheet)
        self.assertIn("background: #f6d4d4", stylesheet)
        self.assertIn("color: #8a121b", stylesheet)
        self.assertIn("border-radius: 8px", stylesheet)

    def test_make_pill_configures_text_tone_and_scoped_stylesheet(self):
        with patch.dict(sys.modules, _fake_qt_modules()):
            pill = make_pill("● Strava", "ok")

        self.assertEqual(pill.text(), "● Strava")
        self.assertEqual(pill_tone(pill), "ok")
        self.assertEqual(pill.objectName(), "qfitPill")
        self.assertEqual(pill.property("tone"), "ok")
        self.assertEqual(pill.alignment, _FakeQt.AlignCenter)
        self.assertEqual(pill.minimum_height, 18)
        self.assertIn("#dcefd0", pill.styleSheet())

    def test_pill_constructor_alias_and_tone_update_keep_text(self):
        with patch.dict(sys.modules, _fake_qt_modules()):
            pill = Pill("— activités")
            set_pill_tone(pill, "info")

        self.assertEqual(pill.text(), "— activités")
        self.assertEqual(pill_tone(pill), "info")
        self.assertIn("#124c8c", pill.styleSheet())

    def test_set_pill_tone_updates_explicit_scoped_object_name(self):
        label = _FakeLabel("3 couches")

        set_pill_tone(label, "muted", object_name="layerCountPill")

        self.assertEqual(label.objectName(), "layerCountPill")
        self.assertIn("QLabel#layerCountPill", label.styleSheet())


class _FakeQt:
    AlignCenter = "align-center"


class _FakeLabel:
    def __init__(self, text="", parent=None):
        self._text = text
        self.parent = parent
        self._object_name = ""
        self._properties = {}
        self._stylesheet = ""
        self.alignment = None
        self.minimum_height = None

    def text(self):
        return self._text

    def setObjectName(self, object_name):  # noqa: N802
        self._object_name = object_name

    def objectName(self):  # noqa: N802
        return self._object_name

    def setAlignment(self, alignment):  # noqa: N802
        self.alignment = alignment

    def setMinimumHeight(self, minimum_height):  # noqa: N802
        self.minimum_height = minimum_height

    def setProperty(self, name, value):  # noqa: N802
        self._properties[name] = value

    def property(self, name):
        return self._properties.get(name)

    def setStyleSheet(self, stylesheet):  # noqa: N802
        self._stylesheet = stylesheet

    def styleSheet(self):  # noqa: N802
        return self._stylesheet


def _fake_qt_modules():
    qtcore = types.ModuleType("qgis.PyQt.QtCore")
    qtcore.Qt = _FakeQt
    qtwidgets = types.ModuleType("qgis.PyQt.QtWidgets")
    qtwidgets.QLabel = _FakeLabel
    return {
        "qgis.PyQt.QtCore": qtcore,
        "qgis.PyQt.QtWidgets": qtwidgets,
    }


if __name__ == "__main__":
    unittest.main()
