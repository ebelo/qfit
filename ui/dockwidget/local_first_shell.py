from __future__ import annotations

from qfit.ui.application.local_first_navigation import (
    LocalFirstDockNavigationState,
    LocalFirstDockPageState,
    build_local_first_dock_navigation_state,
)
from qfit.ui.tokens import (
    COLOR_GROUP_BORDER,
    COLOR_HOVER,
    COLOR_MUTED,
    COLOR_TEXT,
    COLOR_TITLE_BAR,
)

from ._qt_compat import import_qt_module
from .footer_status_bar import FooterStatusBar

_qtcore = import_qt_module(
    "qgis.PyQt.QtCore",
    "PyQt5.QtCore",
    ("Qt", "pyqtSignal"),
)
_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    (
        "QFrame",
        "QHBoxLayout",
        "QLabel",
        "QSizePolicy",
        "QStackedWidget",
        "QVBoxLayout",
        "QWidget",
    ),
)

Qt = _qtcore.Qt
pyqtSignal = _qtcore.pyqtSignal
QFrame = _qtwidgets.QFrame
QHBoxLayout = _qtwidgets.QHBoxLayout
QLabel = _qtwidgets.QLabel
QSizePolicy = _qtwidgets.QSizePolicy
QStackedWidget = _qtwidgets.QStackedWidget
QVBoxLayout = _qtwidgets.QVBoxLayout
QWidget = _qtwidgets.QWidget


class LocalFirstNavigationItem(QWidget):
    """Selectable local-first navigation row that is not an action button."""

    clicked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._checked = False
        self._keyboard_pressed = False
        self._pressed_inside = False
        self._label = QLabel("", self)
        self._layout = QHBoxLayout(self)
        if hasattr(self._layout, "setContentsMargins"):
            self._layout.setContentsMargins(0, 0, 0, 0)
        if hasattr(self._layout, "setSpacing"):
            self._layout.setSpacing(0)
        self._layout.addWidget(self._label)
        if hasattr(self, "setSizePolicy"):
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if hasattr(self, "setAttribute") and hasattr(Qt, "WA_StyledBackground"):
            self.setAttribute(Qt.WA_StyledBackground, True)
        if hasattr(self, "setFocusPolicy"):
            self.setFocusPolicy(Qt.StrongFocus)

    def setText(self, value: str) -> None:  # noqa: N802
        self._label.setText(value)

    def text(self) -> str:
        return self._label.text()

    def setChecked(self, value: bool) -> None:  # noqa: N802
        self._checked = bool(value)

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def label(self):
        """Expose the inner label for pure UI tests."""

        return self._label

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = _event_key(event)
        if self.isEnabled() and _is_activation_key(key):
            if not _event_is_auto_repeat(event):
                self._keyboard_pressed = True
            if hasattr(event, "accept"):
                event.accept()
            return
        self._keyboard_pressed = False
        parent_key_press = getattr(super(), "keyPressEvent", None)
        if parent_key_press is not None:
            parent_key_press(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        key = _event_key(event)
        if self.isEnabled() and _is_activation_key(key):
            if _event_is_auto_repeat(event):
                if hasattr(event, "accept"):
                    event.accept()
                return
            should_activate = self._keyboard_pressed
            self._keyboard_pressed = False
            if should_activate:
                self.clicked.emit()
            if hasattr(event, "accept"):
                event.accept()
            return
        self._keyboard_pressed = False
        parent_key_release = getattr(super(), "keyReleaseEvent", None)
        if parent_key_release is not None:
            parent_key_release(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._pressed_inside = (
            self.isEnabled()
            and _event_button(event) == Qt.LeftButton
            and _event_position_inside_widget(event, self)
        )
        parent_press = getattr(super(), "mousePressEvent", None)
        if parent_press is not None:
            parent_press(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        should_activate = (
            self.isEnabled()
            and self._pressed_inside
            and _event_button(event) == Qt.LeftButton
            and _event_position_inside_widget(event, self)
        )
        self._pressed_inside = False
        if should_activate:
            self.clicked.emit()
        parent_release = getattr(super(), "mouseReleaseEvent", None)
        if parent_release is not None:
            parent_release(event)


class LocalFirstDockShell(QWidget):
    """Standard-Qt shell for the #748 local-first dock navigation."""

    pageRequested = pyqtSignal(str)

    def __init__(
        self,
        parent=None,
        *,
        navigation_state: LocalFirstDockNavigationState | None = None,
        footer_text: str = "",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("qfitLocalFirstDockShell")
        self._navigation_state = navigation_state or build_local_first_dock_navigation_state()
        self._page_indices_by_key: dict[str, int] = {}
        self._navigation_items_by_key: dict[str, LocalFirstNavigationItem] = {}
        self.navigation_container = self._build_navigation_container()
        self.separator = self._build_separator()
        self.pages_stack = self._build_pages_stack()
        self.main_container = self._build_main_container()
        self.footer_bar = self._build_footer_bar(footer_text)
        self._outer_layout = self._build_outer_layout()
        self._install_navigation_items(self._navigation_state.pages)
        self.set_navigation_state(self._navigation_state)

    def add_page(self, key: str, page: QWidget) -> int:
        """Append a page widget for a stable local-first navigation key."""

        index = self.pages_stack.addWidget(page)
        self._page_indices_by_key[key] = index
        if key == self.current_key():
            self.pages_stack.setCurrentIndex(index)
        return index

    def navigation_item_for_key(self, key: str) -> LocalFirstNavigationItem:
        """Return the selection-list item for a local-first page key."""

        try:
            return self._navigation_items_by_key[key]
        except KeyError:
            msg = (
                f"No navigation item registered for key {key!r}. "
                f"Available keys: {list(self._navigation_items_by_key)}"
            )
            raise KeyError(msg) from None

    def current_key(self) -> str:
        """Return the currently selected local-first page key."""

        return self._navigation_state.current_key

    def navigation_items(self) -> tuple[LocalFirstNavigationItem, ...]:
        """Return selection-list navigation items in rendered order."""

        return tuple(
            self._navigation_items_by_key[page.key] for page in self._navigation_state.pages
        )

    def page_count(self) -> int:
        """Return the number of page widgets currently installed."""

        return self.pages_stack.count()

    def set_footer_text(self, text: str) -> None:
        """Update the compact persistent status/footer text."""

        self.footer_bar.set_status_text(text)

    def set_navigation_state(self, state: LocalFirstDockNavigationState) -> None:
        """Apply render-neutral local-first navigation state to the shell."""

        self._navigation_state = state
        for page_state in state.pages:
            item = self._navigation_items_by_key.get(page_state.key)
            if item is not None:
                self._apply_navigation_item_state(item, page_state)
        self._show_page_for_key(state.current_key)

    def show_page_key(self, key: str) -> None:
        """Select an enabled page by stable local-first key."""

        page_state = self._page_state_for_key(key)
        if page_state is None or not page_state.enabled:
            return
        updated_pages = tuple(
            LocalFirstDockPageState(
                key=page.key,
                title=page.title,
                description=page.description,
                status_text=page.status_text,
                ready=page.ready,
                enabled=page.enabled,
                current=page.key == key,
            )
            for page in self._navigation_state.pages
        )
        self.set_navigation_state(
            LocalFirstDockNavigationState(current_key=key, pages=updated_pages)
        )
        self.pageRequested.emit(key)

    def outer_layout(self):
        """Expose the structural layout for pure tests."""

        return self._outer_layout

    def main_layout(self):
        """Expose the main navigation/content layout for pure tests."""

        return self._main_layout

    def _apply_navigation_item_state(
        self,
        item: LocalFirstNavigationItem,
        page_state: LocalFirstDockPageState,
    ) -> None:
        tone = _nav_tone(page_state)
        item.setText(page_state.title)
        item.setEnabled(page_state.enabled)
        item.setChecked(page_state.current)
        item.setProperty("pageKey", page_state.key)
        item.setProperty("current", page_state.current)
        item.setProperty("ready", page_state.ready)
        item.setProperty("navTone", tone)
        item.setProperty("qfitNavItem", True)
        item.setToolTip(f"{page_state.title}: {page_state.status_text}")
        item.setCursor(Qt.PointingHandCursor if page_state.enabled else Qt.ForbiddenCursor)
        if hasattr(item, "setStyleSheet"):
            item.setStyleSheet(_navigation_item_stylesheet(tone, item.objectName()))
        _refresh_dynamic_qss(item)

    def _build_footer_bar(self, footer_text: str):
        return FooterStatusBar(self, footer_text=footer_text)

    def _build_main_container(self):
        container = QWidget(self)
        container.setObjectName("qfitLocalFirstDockMain")
        self._main_layout = QHBoxLayout(container)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        self._main_layout.addWidget(self.navigation_container)
        self._main_layout.addWidget(self.separator)
        self._main_layout.addWidget(self.pages_stack)
        return container

    def _build_navigation_container(self):
        container = QWidget(self)
        container.setObjectName("qfitLocalFirstDockNavigation")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(4)
        self._navigation_layout = layout
        return container

    def _build_outer_layout(self):
        layout = QVBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitLocalFirstDockOuterLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.main_container)
        layout.addWidget(self.footer_bar)
        return layout

    def _build_pages_stack(self):
        stack = QStackedWidget(self)
        stack.setObjectName("qfitLocalFirstDockPagesStack")
        return stack

    def _build_separator(self):
        separator = QFrame(self)
        separator.setObjectName("qfitLocalFirstDockSeparator")
        separator.setFrameShape(getattr(QFrame, "VLine", QFrame.HLine))
        separator.setFrameShadow(QFrame.Plain)
        separator.setFixedWidth(1)
        return separator

    def _install_navigation_items(self, pages: tuple[LocalFirstDockPageState, ...]) -> None:
        for page_state in pages:
            item = self._new_navigation_item(page_state)
            self._navigation_items_by_key[page_state.key] = item
            self._navigation_layout.addWidget(item)
        self._navigation_layout.addStretch(1)

    def _new_navigation_item(self, page_state: LocalFirstDockPageState):
        item = LocalFirstNavigationItem(self.navigation_container)
        item.setObjectName(f"qfitLocalFirstDockNav_{page_state.key}")
        if hasattr(item, "setMinimumWidth"):
            item.setMinimumWidth(88)
        item.clicked.connect(lambda key=page_state.key: self.show_page_key(key))
        return item

    def _page_state_for_key(self, key: str) -> LocalFirstDockPageState | None:
        return next((page for page in self._navigation_state.pages if page.key == key), None)

    def _show_page_for_key(self, key: str) -> None:
        index = self._page_indices_by_key.get(key)
        if index is not None:
            self.pages_stack.setCurrentIndex(index)


def _refresh_dynamic_qss(widget) -> None:
    style_getter = getattr(widget, "style", None)
    style = style_getter() if callable(style_getter) else None
    if style is not None:
        if hasattr(style, "unpolish"):
            style.unpolish(widget)
        if hasattr(style, "polish"):
            style.polish(widget)
    if hasattr(widget, "update"):
        widget.update()


def _event_button(event):
    button_getter = getattr(event, "button", None)
    return button_getter() if callable(button_getter) else None


def _event_is_auto_repeat(event) -> bool:
    auto_repeat_getter = getattr(event, "isAutoRepeat", None)
    return bool(auto_repeat_getter()) if callable(auto_repeat_getter) else False


def _event_key(event):
    key_getter = getattr(event, "key", None)
    return key_getter() if callable(key_getter) else None


def _event_position_inside_widget(event, widget) -> bool:
    pos_getter = getattr(event, "pos", None)
    rect_getter = getattr(widget, "rect", None)
    if not callable(pos_getter) or not callable(rect_getter):
        return True
    rect = rect_getter()
    contains = getattr(rect, "contains", None)
    if not callable(contains):
        return True
    return contains(pos_getter())


def _is_activation_key(key) -> bool:
    return key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space)


def _nav_tone(page_state: LocalFirstDockPageState) -> str:
    if page_state.current:
        return "current"
    if page_state.ready:
        return "ready"
    return "available"


def _navigation_item_stylesheet(tone: str, object_name: str) -> str:
    if tone == "current":
        background = COLOR_TITLE_BAR
        color = COLOR_TEXT
        font_weight = "700"
    elif tone == "ready":
        background = "transparent"
        color = COLOR_TEXT
        font_weight = "500"
    else:
        background = "transparent"
        color = COLOR_MUTED
        font_weight = "500"
    selector = f"#{object_name}"
    return (
        f"{selector} {{ "
        f"background-color: {background}; "
        "border: none; "
        "border-radius: 0px; "
        "} "
        f"{selector} QLabel {{ "
        "padding: 4px 8px; "
        f"color: {color}; "
        f"font-weight: {font_weight}; "
        "} "
        f"{selector}:hover:enabled {{ background-color: {COLOR_HOVER}; }} "
        f"{selector}:hover:enabled QLabel {{ color: {COLOR_TEXT}; }} "
        f"{selector}[navTone='current']:hover:enabled {{ background-color: {COLOR_GROUP_BORDER}; }} "
        f"{selector}:disabled QLabel {{ color: {COLOR_MUTED}; }}"
    )


__all__ = ["LocalFirstDockShell", "LocalFirstNavigationItem"]
