from __future__ import annotations

from typing import Sequence

from .stepper_bar import STEPPER_LABELS, StepperBar, _import_qt_module

_qtwidgets = _import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    (
        "QFrame",
        "QLabel",
        "QScrollArea",
        "QStackedWidget",
        "QVBoxLayout",
        "QWidget",
    ),
)

QFrame = _qtwidgets.QFrame
QLabel = _qtwidgets.QLabel
QScrollArea = _qtwidgets.QScrollArea
QStackedWidget = _qtwidgets.QStackedWidget
QVBoxLayout = _qtwidgets.QVBoxLayout
QWidget = _qtwidgets.QWidget


class WizardShell(QWidget):
    """Reusable dock shell matching the #609 wizard page structure.

    The shell intentionally owns only the structural chrome: stepper, separator,
    scrollable stacked pages, and compact footer. Page content remains external so
    the future wizard can migrate one page at a time without binding the current
    long-scroll dock to another round of cosmetic changes.
    """

    def __init__(self, parent=None, *, footer_text: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("qfitWizardShell")
        self.stepper_bar = StepperBar(self)
        self.separator = self._build_separator()
        self.content_scroll = self._build_content_scroll()
        self.pages_stack = self._build_pages_stack()
        self.footer_bar = self._build_footer_bar(footer_text)
        self.content_scroll.setWidget(self.pages_stack)
        self._outer_layout = self._build_layout()

    def set_step_states(self, states: Sequence[str]) -> None:
        """Delegate validated step state rendering to the shared stepper."""

        self.stepper_bar.set_state(states)

    def set_current_step(self, index: int) -> None:
        """Mark the active step and show the matching page when it exists."""

        self.stepper_bar.set_current(index)
        if index < self.pages_stack.count():
            self.pages_stack.setCurrentIndex(index)

    def add_page(self, page: QWidget) -> int:
        """Append a wizard page and return its stack index."""

        return self.pages_stack.addWidget(page)

    def page_count(self) -> int:
        """Return the number of pages currently installed in the shell."""

        return self.pages_stack.count()

    def set_footer_text(self, text: str) -> None:
        """Update the compact persistent status/footer text."""

        self.footer_bar.setText(text)

    def outer_layout(self):
        """Expose the structural layout for adapter wiring and pure tests."""

        return self._outer_layout

    def _build_layout(self):
        layout = QVBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardOuterLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.stepper_bar)
        layout.addWidget(self.separator)
        layout.addWidget(self.content_scroll)
        layout.addWidget(self.footer_bar)
        return layout

    def _build_separator(self):
        separator = QFrame(self)
        separator.setObjectName("qfitWizardShellSeparator")
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setFixedHeight(1)
        return separator

    def _build_content_scroll(self):
        scroll = QScrollArea(self)
        scroll.setObjectName("qfitWizardContentScroll")
        scroll.setWidgetResizable(True)
        if hasattr(QFrame, "NoFrame") and hasattr(scroll, "setFrameShape"):
            scroll.setFrameShape(QFrame.NoFrame)
        return scroll

    def _build_pages_stack(self):
        stack = QStackedWidget(self)
        stack.setObjectName("qfitWizardPagesStack")
        return stack

    def _build_footer_bar(self, footer_text: str):
        footer = QLabel(footer_text, self)
        footer.setObjectName("qfitWizardFooterBar")
        footer.setFixedHeight(28)
        footer.setStyleSheet(
            "QLabel#qfitWizardFooterBar { "
            "border-top: 1px solid palette(mid); "
            "padding: 4px 8px; "
            "}"
        )
        return footer


__all__ = ["STEPPER_LABELS", "WizardShell"]
