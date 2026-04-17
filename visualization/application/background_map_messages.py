from __future__ import annotations


def build_background_map_cleared_status() -> str:
    return "Background map cleared"


def build_background_map_failure_status() -> str:
    return "Background map could not be updated"


def build_background_map_failure_title() -> str:
    return "Background map failed"


def build_background_map_loaded_status() -> str:
    return "Background map loaded below the qfit activity layers"


def build_background_map_result_status(enabled: bool, background_loaded: bool) -> str:
    if enabled and background_loaded:
        return build_background_map_loaded_status()
    return build_background_map_cleared_status()


def build_styled_background_map_failure_status() -> str:
    return "Loaded layers with styling, but the background map could not be updated"


def build_styled_background_map_loaded_status() -> str:
    return "Applied styling and loaded the background map below the qfit activity layers"


def build_styled_visual_apply_status() -> str:
    return "Applied styling to the loaded qfit layers"
