from __future__ import annotations


NONE_ANALYSIS_MODE_LABEL = "None"


def bind_local_first_analysis_mode_controls(dock, composition) -> None:
    """Bind the local-first analysis page mode selector to dock state.

    The visible local-first analysis page owns mode selection, while the legacy
    combo remains the settings/workflow backing control during the dock
    consolidation. Keep that bridge in application code instead of embedding the
    binding policy in QfitDockWidget.
    """

    analysis_content = getattr(composition, "analysis_content", None)
    mode_combo = getattr(dock, "analysisModeComboBox", None)
    set_options = getattr(analysis_content, "set_analysis_mode_options", None)
    if mode_combo is None or not callable(set_options):
        return

    options = local_first_analysis_mode_options(mode_combo)
    if not options:
        return

    selected_mode = mode_combo.currentText()
    if selected_mode == NONE_ANALYSIS_MODE_LABEL or selected_mode not in options:
        selected_mode = options[0]

    set_options(options, selected=selected_mode)
    set_local_first_analysis_mode(dock, selected_mode)


def local_first_analysis_mode_options(mode_combo) -> tuple[str, ...]:
    """Return user-facing analysis modes from the backing combo box."""

    return tuple(
        mode
        for mode in (mode_combo.itemText(index) for index in range(mode_combo.count()))
        if mode != NONE_ANALYSIS_MODE_LABEL
    )


def set_local_first_analysis_mode(dock, mode: str) -> None:
    """Mirror the local-first analysis selection into the backing dock combo."""

    mode_combo = getattr(dock, "analysisModeComboBox", None)
    if mode_combo is None or not mode:
        return
    mode_combo.setCurrentText(mode)


__all__ = [
    "NONE_ANALYSIS_MODE_LABEL",
    "bind_local_first_analysis_mode_controls",
    "local_first_analysis_mode_options",
    "set_local_first_analysis_mode",
]
