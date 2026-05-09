from __future__ import annotations

from .local_first_control_moves import LocalFirstControlMove, LocalFirstWidgetMove


def install_local_first_group_controls(
    dock,
    composition,
    move: LocalFirstControlMove,
) -> bool:
    """Move one legacy-backed widget group into its audited local-first page."""

    content = getattr(composition, move.content_attr, None)
    group = getattr(dock, move.group_attr, None)
    if content is None or group is None:
        return False
    current_target = id(content)
    if getattr(dock, move.installed_attr, False) and (
        getattr(dock, move.installed_target_attr, None) == current_target
    ):
        return True
    if not local_first_control_move_required_widgets_available(dock, move):
        return False

    layout = local_first_control_move_layout(content, move)
    if layout is None or not hasattr(layout, "addWidget"):
        return False

    remove_widget_from_current_layout(group)
    parent_panel = local_first_control_move_parent_panel(content, move)
    if hasattr(group, "setParent"):
        group.setParent(parent_panel)
    if move.title is not None and hasattr(group, "setTitle"):
        group.setTitle(move.title)
    layout.addWidget(group)
    show_local_first_control_group(group, move)
    refresh_local_first_control_visibility(content, move)

    setattr(dock, move.installed_attr, True)
    setattr(dock, move.installed_target_attr, current_target)
    return True


def local_first_control_move_required_widgets_available(
    dock,
    move: LocalFirstControlMove,
) -> bool:
    """Return whether every audited backing widget for a move is present."""

    return all(getattr(dock, attr, None) is not None for attr in move.required_widget_attrs)


def local_first_control_move_layout(
    content,
    move: LocalFirstControlMove | LocalFirstWidgetMove,
):
    """Return the destination layout named by a local-first move spec."""

    layout_getter = getattr(content, move.layout_getter_attr, None)
    return layout_getter() if callable(layout_getter) else None


def local_first_control_move_parent_panel(
    content,
    move: LocalFirstControlMove | LocalFirstWidgetMove,
):
    """Return the destination parent panel for a local-first move spec."""

    if move.parent_panel_attr is None:
        return content
    return getattr(content, move.parent_panel_attr, content)


def show_local_first_control_group(group, move: LocalFirstControlMove) -> None:
    """Show a moved widget group when its local-first contract allows it."""

    if not move.show_after_move:
        return
    show_widget(group)


def refresh_local_first_control_visibility(
    content,
    move: LocalFirstControlMove | LocalFirstWidgetMove,
) -> None:
    """Run a destination page visibility refresh after moving controls."""

    if move.post_install_visible_attr is None:
        return
    set_visible = getattr(content, move.post_install_visible_attr, None)
    if callable(set_visible):
        set_visible()


def install_local_first_widget_controls(
    dock,
    composition,
    move: LocalFirstWidgetMove,
) -> bool:
    """Move one audited loose-widget set into its local-first page."""

    content = getattr(composition, move.content_attr, None)
    if content is None:
        return False
    current_target = id(content)
    if getattr(dock, move.installed_attr, False) and (
        getattr(dock, move.installed_target_attr, None) == current_target
    ):
        return True

    layout = local_first_control_move_layout(content, move)
    if layout is None or not hasattr(layout, "addWidget"):
        return False

    widgets = local_first_widget_move_widgets(dock, move)
    if widgets is None:
        return False

    parent_panel = local_first_control_move_parent_panel(content, move)
    for widget in widgets:
        remove_widget_from_current_layout(widget)
        if hasattr(widget, "setParent"):
            widget.setParent(parent_panel)
        layout.addWidget(widget)
        show_widget(widget)
    for attr in move.show_widget_attrs_after_move:
        widget = getattr(dock, attr, None)
        if widget is not None:
            show_widget(widget)
    refresh_local_first_control_visibility(content, move)

    setattr(dock, move.installed_attr, True)
    setattr(dock, move.installed_target_attr, current_target)
    return True


def local_first_widget_move_widgets(
    dock,
    move: LocalFirstWidgetMove,
):
    """Return audited loose widgets for a move, or None when required widgets miss."""

    widgets = []
    for attr in move.required_widget_attrs:
        widget = getattr(dock, attr, None)
        if widget is None:
            return None
        widgets.append(widget)
    for group in move.optional_widget_groups:
        group_widgets = [getattr(dock, attr, None) for attr in group]
        if all(widget is not None for widget in group_widgets):
            widgets.extend(group_widgets)
    for attr in move.optional_widget_attrs:
        widget = getattr(dock, attr, None)
        if widget is not None:
            widgets.append(widget)
    return widgets


def remove_widget_from_current_layout(widget) -> None:
    """Detach a widget from its current parent layout when one is available."""

    parent_widget = widget.parentWidget() if hasattr(widget, "parentWidget") else None
    parent_layout = parent_widget.layout() if parent_widget is not None else None
    if parent_layout is not None and hasattr(parent_layout, "removeWidget"):
        parent_layout.removeWidget(widget)


def show_widget(widget) -> None:
    """Show a widget using the most specific visibility API it exposes."""

    if hasattr(widget, "show"):
        widget.show()
    elif hasattr(widget, "setVisible"):
        widget.setVisible(True)


__all__ = [
    "install_local_first_group_controls",
    "install_local_first_widget_controls",
    "local_first_control_move_layout",
    "local_first_control_move_parent_panel",
    "local_first_control_move_required_widgets_available",
    "local_first_widget_move_widgets",
    "refresh_local_first_control_visibility",
    "remove_widget_from_current_layout",
    "show_local_first_control_group",
    "show_widget",
]
