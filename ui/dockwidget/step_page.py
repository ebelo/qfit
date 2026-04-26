from __future__ import annotations

from collections.abc import Sequence

from qfit.ui.application.dock_workflow_sections import (
    DockWorkflowStepState,
    DockWorkflowStepStatus,
)
from qfit.ui.application.wizard_page_specs import (
    DockWizardPageSpec,
    build_default_wizard_page_specs,
)
from ._qt_compat import import_qt_module
from qfit.ui.widgets.pill import set_pill_tone
from qfit.ui.widgets.tokens import (
    COLOR_ACCENT,
    COLOR_ACCENT_DARK,
    COLOR_GROUP_BORDER,
    COLOR_MUTED,
    COLOR_PANEL,
    COLOR_TEXT,
)

_qtcore = import_qt_module("qgis.PyQt.QtCore", "PyQt5.QtCore", ("Qt", "pyqtSignal"))
_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    (
        "QBoxLayout",
        "QHBoxLayout",
        "QLabel",
        "QSizePolicy",
        "QToolButton",
        "QVBoxLayout",
        "QWidget",
    ),
)

Qt = _qtcore.Qt
pyqtSignal = _qtcore.pyqtSignal
QBoxLayout = _qtwidgets.QBoxLayout
QHBoxLayout = _qtwidgets.QHBoxLayout
QLabel = _qtwidgets.QLabel
QSizePolicy = _qtwidgets.QSizePolicy
QToolButton = _qtwidgets.QToolButton
QVBoxLayout = _qtwidgets.QVBoxLayout
QWidget = _qtwidgets.QWidget

STEP_PAGE_NARROW_WIDTH = 360


class StepPage(QWidget):
    """Shared #609 wizard page chrome: header, content area, and navigation.

    Concrete pages can add controls to :meth:`content_layout` while reusing the
    specified step header, status pill, back button, and single primary next CTA.
    Keeping this as a standalone widget avoids further investment in the legacy
    long-scroll dock while providing the base class named by the Option B spec.
    """

    backRequested = pyqtSignal()
    nextRequested = pyqtSignal()

    def __init__(
        self,
        step_num: int,
        step_total: int,
        title: str,
        subtitle: str,
        status_pill=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.step_num = step_num
        self.step_total = step_total
        self.setObjectName("qfitWizardStepPage")
        self.step_label = self._build_step_label(step_num, step_total)
        self.title_label = self._build_title_label(title)
        self.subtitle_label = self._build_subtitle_label(subtitle)
        self.status_pill = status_pill or self._build_status_pill()
        self.content_container = QWidget(self)
        self.content_container.setObjectName("qfitWizardStepContent")
        _allow_horizontal_shrink(self.content_container)
        self._content_layout = self._build_content_layout(self.content_container)
        self._responsive_mode = "wide"
        self.setProperty("responsiveMode", "wide")
        self._back_label = "Précédent"
        self._next_label = "Suivant"
        self._next_icon = "→"
        self.back_button = self._build_back_button()
        self.next_button = self._build_next_button()
        self._extra_left_layout = self._build_extra_button_layout("qfitWizardStepLeftExtraLayout")
        self._extra_right_layout = self._build_extra_button_layout("qfitWizardStepRightExtraLayout")
        self._header_layout = self._build_header_layout()
        self._nav_layout = self._build_nav_layout()
        self._layout = self._build_layout()
        self.set_status(None)
        self.set_back()
        self.set_next("Suivant", icon="→")

    def set_status(self, text: str | None, tone: str = "muted") -> None:
        """Update the optional header status pill and hide it when text is blank."""

        label = (text or "").strip()
        self.status_pill.setText(label)
        set_pill_tone(self.status_pill, tone, object_name="qfitWizardStepStatusPill")
        self.status_pill.setVisible(bool(label))

    def set_next(
        self,
        label: str,
        icon: str = "",
        primary: bool = True,
        enabled: bool = True,
        visible: bool = True,
    ) -> None:
        """Configure the right-side next/primary wizard action."""

        self._next_label = label
        self._next_icon = icon
        self._apply_navigation_button_texts()
        self.next_button.setEnabled(enabled)
        self.next_button.setVisible(visible)
        self.next_button.setProperty("wizardActionRole", "primary" if primary else "secondary")
        self.next_button.setStyleSheet(
            _primary_button_stylesheet() if primary else _ghost_button_stylesheet()
        )

    def set_back(self, label: str = "Précédent", enabled: bool = True) -> None:
        """Configure the left-side back navigation action."""

        self._back_label = label
        self._apply_navigation_button_texts()
        self.back_button.setEnabled(enabled)
        self.back_button.setProperty("wizardActionRole", "back")
        self.back_button.setStyleSheet(_ghost_button_stylesheet())

    def _apply_navigation_button_texts(self) -> None:
        narrow = self._responsive_mode == "narrow"
        self.back_button.setText("←" if narrow else self._back_label)
        self.back_button.setToolTip(self._back_label)
        self.next_button.setText(
            _compact_button_text(self._next_label, self._next_icon)
            if narrow
            else _button_text(self._next_label, self._next_icon)
        )
        self.next_button.setToolTip(_button_text(self._next_label, self._next_icon))

    def add_extra_button(self, btn, align: str = "right") -> None:
        """Add a page-specific secondary button to the navigation row."""

        btn.setProperty("wizardActionRole", "extra")
        _configure_responsive_button(btn)
        if align == "left":
            self._extra_left_layout.addWidget(btn)
            return
        if align == "right":
            self._extra_right_layout.addWidget(btn)
            return
        raise ValueError("align must be 'left' or 'right'")

    def content_layout(self):
        """Return the layout where concrete step pages install their controls."""

        return self._content_layout

    def set_responsive_width(self, width: int) -> None:
        """Stack/compact page chrome when the dock is narrowed."""

        narrow = int(width) < STEP_PAGE_NARROW_WIDTH
        mode = "narrow" if narrow else "wide"
        if mode == self._responsive_mode:
            return
        self._responsive_mode = mode
        self.setProperty("responsiveMode", mode)
        if hasattr(self._nav_layout, "setDirection"):
            self._nav_layout.setDirection(
                QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight
            )
        self._nav_layout.setSpacing(6 if narrow else 8)
        self._layout.setContentsMargins(
            8 if narrow else 12,
            10 if narrow else 12,
            8 if narrow else 12,
            10 if narrow else 12,
        )
        self._apply_navigation_button_texts()

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Respond to live dock resizes instead of preserving wide size hints."""

        size = event.size() if hasattr(event, "size") else None
        if size is not None and hasattr(size, "width"):
            self.set_responsive_width(size.width())
        elif hasattr(self, "width"):
            self.set_responsive_width(self.width())
        parent_resize = getattr(super(), "resizeEvent", None)
        if parent_resize is not None:
            parent_resize(event)

    def outer_layout(self):
        """Expose the full page layout for adapter wiring and pure tests."""

        return self._layout

    def _build_step_label(self, step_num: int, step_total: int):
        label = QLabel(f"ÉTAPE {step_num}/{step_total}", self)
        label.setObjectName("qfitWizardStepKickerLabel")
        _allow_horizontal_shrink(label)
        label.setStyleSheet(_step_kicker_label_stylesheet(label.objectName()))
        return label

    def _build_title_label(self, title: str):
        label = QLabel(title, self)
        label.setObjectName("qfitWizardStepTitleLabel")
        _allow_label_wrap(label)
        label.setStyleSheet(_step_title_label_stylesheet(label.objectName()))
        return label

    def _build_subtitle_label(self, subtitle: str):
        label = QLabel(subtitle, self)
        label.setObjectName("qfitWizardStepSubtitleLabel")
        _allow_label_wrap(label)
        label.setStyleSheet(
            _step_subtitle_label_stylesheet(label.objectName())
        )
        return label

    def _build_status_pill(self):
        label = QLabel("", self)
        label.setObjectName("qfitWizardStepStatusPill")
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumHeight(18)
        _allow_horizontal_shrink(label)
        return label

    def _build_back_button(self):
        button = QToolButton(self)
        button.setObjectName("qfitWizardStepBackButton")
        _configure_responsive_button(button)
        _apply_wizard_navigation_cursor(button)
        button.clicked.connect(self.backRequested.emit)
        return button

    def _build_next_button(self):
        button = QToolButton(self)
        button.setObjectName("qfitWizardStepNextButton")
        _configure_responsive_button(button)
        _apply_wizard_navigation_cursor(button)
        button.clicked.connect(self.nextRequested.emit)
        return button

    def _build_content_layout(self, parent):
        layout = QVBoxLayout(parent)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardStepContentLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        return layout

    def _build_header_layout(self):
        layout = QHBoxLayout()
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardStepHeaderLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.step_label)
        layout.addWidget(self.title_label)
        layout.addStretch(1)
        layout.addWidget(self.status_pill)
        return layout

    def _build_extra_button_layout(self, object_name: str):
        layout = QHBoxLayout()
        if hasattr(layout, "setObjectName"):
            layout.setObjectName(object_name)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        return layout

    def _build_nav_layout(self):
        layout = QHBoxLayout()
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardStepNavLayout")
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.back_button)
        layout.addWidget(_LayoutWidget(self._extra_left_layout, self))
        layout.addStretch(1)
        layout.addWidget(_LayoutWidget(self._extra_right_layout, self))
        layout.addWidget(self.next_button)
        return layout

    def _build_layout(self):
        layout = QVBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardStepPageLayout")
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(_LayoutWidget(self._header_layout, self))
        layout.addWidget(self.subtitle_label)
        layout.addWidget(self.content_container)
        layout.addWidget(_LayoutWidget(self._nav_layout, self))
        return layout


class WizardStepPage(StepPage):
    """Step-page adapter backed by the canonical #609 page spec.

    ``WizardPage`` still powers the current placeholder shell, but the final
    dock swap needs spec-keyed pages with the richer ``StepPage`` chrome. This
    adapter keeps that future page shape compatible with the existing
    ``body_layout()`` and ``retire_primary_action_hint()`` seams used by the
    concrete page-content installers, without making the old long-scroll dock
    any more permanent.
    """

    def __init__(
        self,
        spec: DockWizardPageSpec,
        *,
        step_num: int,
        step_total: int,
        parent=None,
    ) -> None:
        super().__init__(
            step_num,
            step_total,
            spec.title,
            spec.summary,
            parent=parent,
        )
        self.spec = spec
        self.setObjectName(spec.page_object_name)
        self.title_label.setObjectName(spec.title_object_name)
        self.title_label.setStyleSheet(
            _step_title_label_stylesheet(spec.title_object_name)
        )
        self.summary_label = self.subtitle_label
        self.summary_label.setObjectName(spec.summary_object_name)
        self.summary_label.setStyleSheet(
            _step_subtitle_label_stylesheet(spec.summary_object_name)
        )
        self.body_container = self.content_container
        self.body_container.setObjectName(spec.body_object_name)
        self.primary_hint_label = self._build_primary_hint_label(spec.primary_action_hint)

    def body_layout(self):
        """Expose the content seam expected by concrete wizard page installers."""

        return self.content_layout()

    def retire_primary_action_hint(self) -> None:
        """Keep compatibility with placeholder pages while avoiding extra copy."""

        self.primary_hint_label.setText("")
        self.primary_hint_label.setProperty("wizardPlaceholderHint", "retired")
        self.primary_hint_label.setVisible(False)

    def _build_primary_hint_label(self, text: str):
        label = QLabel(text, self)
        label.setObjectName(self.spec.primary_hint_object_name)
        label.setProperty("wizardPlaceholderHint", "retired")
        label.setVisible(False)
        return label


def build_wizard_step_pages(
    *,
    parent=None,
    specs: Sequence[DockWizardPageSpec] | None = None,
) -> tuple[WizardStepPage, ...]:
    """Build StepPage-backed pages in stable #609 wizard order."""

    page_specs = build_default_wizard_page_specs() if specs is None else tuple(specs)
    step_total = len(page_specs)
    return tuple(
        WizardStepPage(
            spec,
            step_num=index + 1,
            step_total=step_total,
            parent=parent,
        )
        for index, spec in enumerate(page_specs)
    )


def install_wizard_step_pages(
    shell,
    specs: Sequence[DockWizardPageSpec] | None = None,
) -> tuple[WizardStepPage, ...]:
    """Create StepPage-backed wizard pages and append them to a shell."""

    pages = build_wizard_step_pages(parent=shell, specs=specs)
    for page in pages:
        shell.add_page(page)
    return pages


def apply_wizard_step_page_statuses(
    pages: Sequence[WizardStepPage],
    statuses: Sequence[DockWorkflowStepStatus],
) -> None:
    """Render progress status pills on StepPage-backed wizard pages.

    The stepper remains the source of truth for current-step navigation state.
    Header pills are therefore reserved for non-current states, avoiding a
    redundant "Current" badge on the active page while preserving Done/Locked
    context on neighbouring pages.
    """

    statuses_by_key = {status.key: status for status in statuses}
    for page in pages:
        status = statuses_by_key.get(page.spec.key)
        if status is None:
            continue
        text, tone = _step_status_pill(status.state)
        page.set_status(text, tone=tone)


class _LayoutWidget(QWidget):
    """Small wrapper so fake and real Qt layouts can be inserted as widgets."""

    def __init__(self, layout, parent=None) -> None:
        super().__init__(parent)
        if hasattr(self, "setLayout"):
            self.setLayout(layout)


def _allow_horizontal_shrink(widget) -> None:
    if hasattr(widget, "setMinimumWidth"):
        widget.setMinimumWidth(0)
    if hasattr(widget, "setSizePolicy"):
        widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)


def _allow_label_wrap(label) -> None:
    if hasattr(label, "setWordWrap"):
        label.setWordWrap(True)
    _allow_horizontal_shrink(label)


def _configure_responsive_button(button) -> None:
    if hasattr(button, "setToolButtonStyle"):
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    if hasattr(button, "setMinimumWidth"):
        button.setMinimumWidth(0)
    if hasattr(button, "setSizePolicy"):
        button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)


def _apply_wizard_navigation_cursor(button) -> None:
    if hasattr(button, "setCursor"):
        button.setCursor(Qt.PointingHandCursor)


def _button_text(label: str, icon: str) -> str:
    stripped_label = label.strip()
    stripped_icon = icon.strip()
    if not stripped_icon:
        return stripped_label
    return f"{stripped_label} {stripped_icon}"


def _compact_button_text(label: str, icon: str = "", *, max_chars: int = 14) -> str:
    stripped_icon = icon.strip()
    if stripped_icon:
        return stripped_icon
    stripped_label = label.strip()
    if len(stripped_label) <= max_chars:
        return stripped_label
    return f"{stripped_label[: max_chars - 1].rstrip()}…"


def _step_status_pill(state: DockWorkflowStepState) -> tuple[str, str]:
    if state == DockWorkflowStepState.DONE:
        return "Done", "ok"
    if state == DockWorkflowStepState.CURRENT:
        return "", "muted"
    if state == DockWorkflowStepState.UNLOCKED:
        return "Available", "neutral"
    return "Locked", "muted"


def _step_kicker_label_stylesheet(object_name: str) -> str:
    return (
        f"QLabel#{object_name} {{ color: {COLOR_MUTED}; "
        "font-size: 10.5pt; font-weight: 600; letter-spacing: .5px; }}"
    )


def _step_title_label_stylesheet(object_name: str) -> str:
    return (
        f"QLabel#{object_name} {{ color: {COLOR_TEXT}; "
        "font-size: 14pt; font-weight: 600; }}"
    )


def _step_subtitle_label_stylesheet(object_name: str) -> str:
    return (
        f"QLabel#{object_name} {{ color: {COLOR_MUTED}; "
        "font-size: 11pt; margin-top: 3px; line-height: 1.45; }}"
    )


def _primary_button_stylesheet() -> str:
    return (
        "QToolButton { "
        f"background: {COLOR_ACCENT}; color: white; font-weight: 600; "
        f"border: 1px solid {COLOR_ACCENT_DARK}; border-radius: 2px; "
        "padding: 4px 12px; min-height: 22px; "
        "}"
    )


def _ghost_button_stylesheet() -> str:
    return (
        "QToolButton { "
        f"background: {COLOR_PANEL}; color: {COLOR_TEXT}; "
        f"border: 1px solid {COLOR_GROUP_BORDER}; border-radius: 2px; "
        "padding: 4px 12px; min-height: 22px; "
        "}"
    )


__all__ = [
    "StepPage",
    "WizardStepPage",
    "apply_wizard_step_page_statuses",
    "build_wizard_step_pages",
    "install_wizard_step_pages",
]
