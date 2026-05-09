import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_atlas_controls import (
    hide_legacy_atlas_export_button,
    update_local_first_atlas_document_settings,
)


class _FakeLineEdit:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text

    def setText(self, text):
        self._text = text


class LocalFirstAtlasControlsTests(unittest.TestCase):
    def test_updates_backing_fields_and_marks_export_stale_when_changed(self):
        dock = SimpleNamespace(
            atlasTitleLineEdit=_FakeLineEdit("Old title"),
            atlasSubtitleLineEdit=_FakeLineEdit("Old subtitle"),
            _mark_atlas_export_stale=MagicMock(),
            _refresh_summary_status=MagicMock(),
        )

        update_local_first_atlas_document_settings(
            dock,
            "Spring Atlas",
            "Road and trail",
        )

        self.assertEqual(dock.atlasTitleLineEdit.text(), "Spring Atlas")
        self.assertEqual(dock.atlasSubtitleLineEdit.text(), "Road and trail")
        dock._mark_atlas_export_stale.assert_called_once_with()
        dock._refresh_summary_status.assert_called_once_with()

    def test_keeps_export_current_when_fields_are_unchanged(self):
        dock = SimpleNamespace(
            atlasTitleLineEdit=_FakeLineEdit("Spring Atlas"),
            atlasSubtitleLineEdit=_FakeLineEdit("Road and trail"),
            _mark_atlas_export_stale=MagicMock(),
            _refresh_summary_status=MagicMock(),
        )

        update_local_first_atlas_document_settings(
            dock,
            "Spring Atlas",
            "Road and trail",
        )

        dock._mark_atlas_export_stale.assert_not_called()
        dock._refresh_summary_status.assert_not_called()

    def test_missing_backing_field_does_not_block_available_field_update(self):
        dock = SimpleNamespace(
            atlasTitleLineEdit=_FakeLineEdit("Old title"),
            _mark_atlas_export_stale=MagicMock(),
            _refresh_summary_status=MagicMock(),
        )

        update_local_first_atlas_document_settings(
            dock,
            "Spring Atlas",
            "Road and trail",
        )

        self.assertEqual(dock.atlasTitleLineEdit.text(), "Spring Atlas")
        dock._mark_atlas_export_stale.assert_called_once_with()
        dock._refresh_summary_status.assert_called_once_with()

    def test_hides_legacy_export_button_when_present(self):
        dock = SimpleNamespace(generateAtlasPdfButton=MagicMock())

        hide_legacy_atlas_export_button(dock)

        dock.generateAtlasPdfButton.hide.assert_called_once_with()

    def test_hiding_legacy_export_button_tolerates_missing_button(self):
        hide_legacy_atlas_export_button(SimpleNamespace())


if __name__ == "__main__":
    unittest.main()
