from __future__ import annotations

from qfit.ui.application.local_first_navigation import (
    LocalFirstDockNavigationState,
    LocalFirstDockPageState,
    build_local_first_dock_navigation_state,
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
        "QSizePolicy",
        "QStackedWidget",
        "QToolButton",
        "QVBoxLayout",
        "QWidget",
    ),
)

Qt = _qtcore.Qt
pyqtSignal = _qtcore.pyqtSignal
QFrame = _qtwidgets.QFrame
QHBoxLayout = _qtwidgets.QHBoxLayout
QSizePolicy = _qtwidgets.QSizePolicy
QStackedWidget = _qtwidgets.QStackedWidget
QToolButton = _qtwidgets.QToolButton
QVBoxLayout = _qtwidgets.QVBoxLayout
QWidget = _qtwidgets.QWidget


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
        self._buttons_by_key: dict[str, QToolButton] = {}
        self.navigation_container = self._build_navigation_container()
        self.separator = self._build_separator()
        self.pages_stack = self._build_pages_stack()
        self.main_container = self._build_main_container()
        self.footer_bar = self._build_footer_bar(footer_text)
        self._outer_layout = self._build_outer_layout()
        self._install_navigation_buttons(self._navigation_state.pages)
        self.set_navigation_state(self._navigation_state)

    def add_page(self, key: str, page: QWidget) -> int:
        """Append a page widget for a stable local-first navigation key."""

        index = self.pages_stack.addWidget(page)
        self._page_indices_by_key[key] = index
        if key == self.current_key():
            self.pages_stack.setCurrentIndex(index)
        return index

    def button_for_key(self, key: str):
        """Return the navigation button for tests and adapter wiring."""

        return self._buttons_by_key[key]

    def current_key(self) -> str:
        """Return the currently selected local-first page key."""

        return self._navigation_state.current_key

    def navigation_buttons(self) -> tuple[QToolButton, ...]:
        """Return navigation buttons in rendered order."""

        return tuple(self._buttons_by_key[page.key] for page in self._navigation_state.pages)

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
            button = self._buttons_by_key.get(page_state.key)
            if button is not None:
                self._apply_button_state(button, page_state)
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

    def _apply_button_state(self, button: QToolButton, page_state: LocalFirstDockPageState) -> None:
        button.setText(page_state.title)
        button.setEnabled(page_state.enabled)
        button.setProperty("pageKey", page_state.key)
        button.setProperty("current", page_state.current)
        button.setProperty("ready", page_state.ready)
        button.setProperty("navTone", _nav_tone(page_state))
        button.setToolTip(f"{page_state.title}: {page_state.status_text}")
        button.setCursor(Qt.PointingHandCursor if page_state.enabled else Qt.ForbiddenCursor)

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

    def _install_navigation_buttons(self, pages: tuple[LocalFirstDockPageState, ...]) -> None:
        for page_state in pages:
            button = self._new_navigation_button(page_state)
            self._buttons_by_key[page_state.key] = button
            self._navigation_layout.addWidget(button)
        self._navigation_layout.addStretch(1)

    def _new_navigation_button(self, page_state: LocalFirstDockPageState):
        button = QToolButton(self.navigation_container)
        button.setObjectName(f"qfitLocalFirstDockNav_{page_state.key}")
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.clicked.connect(lambda _checked=False, key=page_state.key: self.show_page_key(key))
        return button

    def _page_state_for_key(self, key: str) -> LocalFirstDockPageState | None:
        return next((page for page in self._navigation_state.pages if page.key == key), None)

    def _show_page_for_key(self, key: str) -> None:
        index = self._page_indices_by_key.get(key)
        if index is not None:
            self.pages_stack.setCurrentIndex(index)


def _nav_tone(page_state: LocalFirstDockPageState) -> str:
    if page_state.current:
        return "current"
    if page_state.ready:
        return "ready"
    return "available"


__all__ = ["LocalFirstDockShell"]
