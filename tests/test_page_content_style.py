import unittest

from tests import _path  # noqa: F401

from qfit.ui.dockwidget.page_content_style import (
    style_detail_label,
    style_status_pill,
    style_summary_label,
)
from qfit.ui.tokens import COLOR_MUTED


class PageContentStyleTest(unittest.TestCase):
    def test_styles_detail_and_summary_labels_with_muted_tokens(self):
        detail = _FakeLabel(object_name="detailLabel")
        summary = _FakeLabel(object_name="summaryLabel")

        style_detail_label(detail)
        style_summary_label(summary)

        self.assertIn(COLOR_MUTED, detail.styleSheet())
        self.assertIn(COLOR_MUTED, summary.styleSheet())
        self.assertIn("padding: 1px 0", summary.styleSheet())

    def test_styles_status_labels_as_scoped_token_pills(self):
        label = _FakeLabel(object_name="statusLabel")

        style_status_pill(label, active=False)

        self.assertEqual(label.objectName(), "statusLabel")
        self.assertEqual(label.property("tone"), "warn")
        self.assertIn("QLabel#statusLabel", label.styleSheet())
        self.assertIn("#fbe7c3", label.styleSheet())

        style_status_pill(label, active=True)

        self.assertEqual(label.property("tone"), "ok")
        self.assertIn("#dcefd0", label.styleSheet())


class _FakeLabel:
    def __init__(self, *, object_name=""):
        self._object_name = object_name
        self._properties = {}
        self._stylesheet = ""

    def setObjectName(self, object_name):  # noqa: N802
        self._object_name = object_name

    def objectName(self):  # noqa: N802
        return self._object_name

    def setProperty(self, name, value):  # noqa: N802
        self._properties[name] = value

    def property(self, name):
        return self._properties.get(name)

    def setStyleSheet(self, stylesheet):  # noqa: N802
        self._stylesheet = stylesheet

    def styleSheet(self):  # noqa: N802
        return self._stylesheet


if __name__ == "__main__":
    unittest.main()
