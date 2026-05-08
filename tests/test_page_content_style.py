import importlib
import sys
import unittest
from unittest.mock import patch

from tests import _path  # noqa: F401
from tests.test_wizard_shell import _fake_qt_modules

from qfit.ui.tokens import COLOR_DANGER, COLOR_MUTED, COLOR_WARN


def _load_page_content_style_module():
    for name in (
        "qfit.ui.dockwidget.page_content_style",
        "qfit.ui.dockwidget.stepper_bar",
        "qfit.ui.dockwidget",
    ):
        sys.modules.pop(name, None)
    with patch.dict(sys.modules, _fake_qt_modules()):
        return importlib.import_module("qfit.ui.dockwidget.page_content_style")


class PageContentStyleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page_content_style = _load_page_content_style_module()

    def test_styles_instruction_and_feedback_labels_by_voice(self):
        detail = _FakeLabel(object_name="detailLabel")
        feedback = _FakeLabel(object_name="feedbackLabel")

        self.page_content_style.style_detail_label(detail)
        self.page_content_style.style_feedback_label(feedback)

        self.assertIn(COLOR_MUTED, detail.styleSheet())
        self.assertNotIn("font-style: italic", detail.styleSheet())
        self.assertIn(COLOR_MUTED, feedback.styleSheet())
        self.assertIn("font-style: italic", feedback.styleSheet())
        self.assertIn("padding: 1px 0", feedback.styleSheet())

    def test_summary_label_style_remains_feedback_compatible(self):
        summary = _FakeLabel(object_name="summaryLabel")

        self.page_content_style.style_summary_label(summary)

        self.assertIn(COLOR_MUTED, summary.styleSheet())
        self.assertIn("font-style: italic", summary.styleSheet())

    def test_styles_problem_labels_with_semantic_color_without_italic(self):
        warning = _FakeLabel(object_name="warningLabel")
        error = _FakeLabel(object_name="errorLabel")

        self.page_content_style.style_warning_label(warning)
        self.page_content_style.style_error_label(error)

        self.assertIn(COLOR_WARN, warning.styleSheet())
        self.assertNotIn("font-style: italic", warning.styleSheet())
        self.assertIn(COLOR_DANGER, error.styleSheet())
        self.assertNotIn("font-style: italic", error.styleSheet())

    def test_styles_status_labels_as_scoped_token_pills(self):
        label = _FakeLabel(object_name="statusLabel")

        self.page_content_style.style_status_pill(label, active=False)

        self.assertEqual(label.objectName(), "statusLabel")
        self.assertEqual(label.property("tone"), "warn")
        self.assertIn("QLabel#statusLabel", label.styleSheet())
        self.assertIn("#fbe7c3", label.styleSheet())

        self.page_content_style.style_status_pill(label, active=True)

        self.assertEqual(label.property("tone"), "ok")
        self.assertIn("#dcefd0", label.styleSheet())

    def test_configures_fluid_text_labels_for_wrapping_and_shrink(self):
        label = _FakeLabel(object_name="summaryLabel")

        self.page_content_style.configure_fluid_text_label(label)

        self.assertTrue(label.word_wrap)
        self.assertEqual(label.minimumWidth(), 0)
        self.assertEqual(
            label.size_policy,
            (
                self.page_content_style.QSizePolicy.Ignored,
                self.page_content_style.QSizePolicy.Preferred,
            ),
        )


class _FakeLabel:
    def __init__(self, *, object_name=""):
        self._object_name = object_name
        self._properties = {}
        self._stylesheet = ""
        self._minimum_width = None
        self.word_wrap = False
        self.size_policy = None

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

    def setWordWrap(self, value):  # noqa: N802
        self.word_wrap = value

    def setMinimumWidth(self, value):  # noqa: N802
        self._minimum_width = value

    def minimumWidth(self):  # noqa: N802
        return self._minimum_width

    def setSizePolicy(self, horizontal, vertical):  # noqa: N802
        self.size_policy = (horizontal, vertical)


if __name__ == "__main__":
    unittest.main()
