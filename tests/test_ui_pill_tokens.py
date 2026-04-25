import os
import unittest

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
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from qgis.PyQt.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        self.addCleanup(lambda: app.processEvents())

        pill = make_pill("● Strava", "ok")

        self.assertEqual(pill.text(), "● Strava")
        self.assertEqual(pill_tone(pill), "ok")
        self.assertEqual(pill.objectName(), "qfitPill")
        self.assertEqual(pill.property("tone"), "ok")
        self.assertIn("#dcefd0", pill.styleSheet())

    def test_pill_constructor_alias_and_tone_update_keep_text(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from qgis.PyQt.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        self.addCleanup(lambda: app.processEvents())

        pill = Pill("— activités")
        set_pill_tone(pill, "info")

        self.assertEqual(pill.text(), "— activités")
        self.assertEqual(pill_tone(pill), "info")
        self.assertIn("#124c8c", pill.styleSheet())


if __name__ == "__main__":
    unittest.main()
