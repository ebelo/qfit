from __future__ import annotations

from typing import Sequence

from ._qt_compat import import_qt_module
from .footer_status_bar import FooterStatusBar
from .step_page import STEP_PAGE_NARROW_WIDTH
from .stepper_bar import STEPPER_COMPACT_WIDTH, STEPPER_LABELS, StepperBar

_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    (
        "QFrame",
        "QScrollArea",
        "QStackedWidget",
        "QVBoxLayout",
        "QWidget",
    ),
)

QFrame = _qtwidgets.QFrame
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
        self._responsive_mode = "wide"
        self._stepper_responsive_mode = "wide"
        self._responsive_width: int | None = None
        self.setProperty("responsiveMode", "wide")

    def set_step_states(self, states: Sequence[str]) -> None:
        """Delegate validated step state rendering to the shared stepper."""

        self.stepper_bar.set_state(states)

    def set_current_step(self, index: int) -> None:
        """Mark the active step and show the matching page when it exists."""

        self.stepper_bar.set_current(index)
        self.show_page(index)

    def show_page(self, index: int) -> None:
        """Show a page by stack index when that page has been installed."""

        if index < self.pages_stack.count():
            self.pages_stack.setCurrentIndex(index)

    def add_page(self, page: QWidget) -> int:
        """Append a wizard page and return its stack index."""

        index = self.pages_stack.addWidget(page)
        if self._responsive_width is not None and hasattr(page, "set_responsive_width"):
            page.set_responsive_width(self._responsive_width)
        return index

    def page_count(self) -> int:
        """Return the number of pages currently installed in the shell."""

        return self.pages_stack.count()

    def set_footer_text(self, text: str) -> None:
        """Update the compact persistent status/footer text."""

        self.footer_bar.set_status_text(text)

    def set_responsive_width(self, width: int) -> None:
        """Propagate dock width changes to responsive wizard chrome."""

        width = int(width)
        self._responsive_width = width
        mode = "narrow" if width < STEP_PAGE_NARROW_WIDTH else "wide"
        stepper_mode = "compact" if width < STEPPER_COMPACT_WIDTH else "wide"
        if mode == self._responsive_mode and stepper_mode == self._stepper_responsive_mode:
            return
        self._responsive_mode = mode
        self._stepper_responsive_mode = stepper_mode
        self.setProperty("responsiveMode", mode)
        self.stepper_bar.set_responsive_width(width)
        for index in range(self.pages_stack.count()):
            page = self.pages_stack.widget(index) if hasattr(self.pages_stack, "widget") else None
            if page is not None and hasattr(page, "set_responsive_width"):
                page.set_responsive_width(width)

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Let the shell react to dock resizes without wide-page size hints."""

        size = event.size() if hasattr(event, "size") else None
        if size is not None and hasattr(size, "width"):
            self.set_responsive_width(size.width())
        elif hasattr(self, "width"):
            self.set_responsive_width(self.width())
        parent_resize = getattr(super(), "resizeEvent", None)
        if parent_resize is not None:
            parent_resize(event)

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
        scroll.setFrameShape(QFrame.NoFrame)
        return scroll

    def _build_pages_stack(self):
        stack = QStackedWidget(self)
        stack.setObjectName("qfitWizardPagesStack")
        return stack

    def _build_footer_bar(self, footer_text: str):
        return FooterStatusBar(self, footer_text=footer_text)


__all__ = ["STEPPER_LABELS", "WizardShell"]
