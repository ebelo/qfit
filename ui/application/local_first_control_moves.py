from __future__ import annotations

from dataclasses import dataclass


REFRESH_CONDITIONAL_VISIBILITY_HOOK = "refresh_conditional_visibility"
HIDE_LEGACY_ATLAS_EXPORT_BUTTON_HOOK = "hide_legacy_atlas_export_button"


@dataclass(frozen=True)
class LocalFirstControlMove:
    """Legacy-backed control group that is explicitly surfaced in local-first UI.

    ``post_install_visible_attr`` names an optional content method that refreshes
    local-first visibility after a move. Keep it explicit instead of deriving it
    from the layout name so inventory entries fail review when their contracts
    drift.
    """

    key: str
    content_attr: str
    group_attr: str
    installed_attr: str
    installed_target_attr: str
    required_widget_attrs: tuple[str, ...] = ()
    title: str | None = None
    show_after_move: bool = True
    layout_getter_attr: str = "outer_layout"
    parent_panel_attr: str | None = None
    post_install_visible_attr: str | None = None
    after_install_hook_key: str | None = None


@dataclass(frozen=True)
class LocalFirstWidgetMove:
    """Legacy-backed loose widgets that are surfaced in local-first UI.

    Some remaining controls were not wrapped in a single group box in the old
    dock. Keep their widget contracts audited here so local-first parity does
    not depend on ad-hoc installer methods with wizard-era naming.
    """

    key: str
    content_attr: str
    required_widget_attrs: tuple[str, ...]
    installed_attr: str
    installed_target_attr: str
    optional_widget_groups: tuple[tuple[str, ...], ...] = ()
    optional_widget_attrs: tuple[str, ...] = ()
    show_widget_attrs_after_move: tuple[str, ...] = ()
    layout_getter_attr: str = "outer_layout"
    parent_panel_attr: str | None = None
    post_install_visible_attr: str | None = None


LOCAL_FIRST_WIDGET_MOVES: tuple[LocalFirstWidgetMove, ...] = (
    LocalFirstWidgetMove(
        key="activity_style",
        content_attr="map_content",
        required_widget_attrs=("stylePresetLabel", "stylePresetComboBox"),
        installed_attr="_local_first_activity_style_controls_installed",
        installed_target_attr="_local_first_activity_style_controls_installed_target",
        optional_widget_groups=(("previewSortLabel", "previewSortComboBox"),),
        layout_getter_attr="style_controls_layout",
        parent_panel_attr="style_controls_panel",
        post_install_visible_attr="set_style_controls_visible",
    ),
    LocalFirstWidgetMove(
        key="analysis_temporal",
        content_attr="analysis_content",
        required_widget_attrs=("analysisTemporalModeRow", "temporalHelpLabel"),
        installed_attr="_local_first_analysis_temporal_controls_installed",
        installed_target_attr="_local_first_analysis_temporal_controls_installed_target",
        show_widget_attrs_after_move=("temporalModeLabel", "temporalModeComboBox"),
        layout_getter_attr="temporal_controls_layout",
        parent_panel_attr="temporal_controls_panel",
        post_install_visible_attr="set_temporal_controls_visible",
    ),
)


LOCAL_FIRST_CONTROL_MOVES: tuple[LocalFirstControlMove, ...] = (
    LocalFirstControlMove(
        key="activity_preview",
        content_attr="sync_content",
        group_attr="previewGroupBox",
        required_widget_attrs=("querySummaryLabel", "activityPreviewPlainTextEdit"),
        installed_attr="_local_first_activity_preview_controls_installed",
        installed_target_attr="_local_first_activity_preview_controls_installed_target",
        title="Fetched activity preview",
    ),
    LocalFirstControlMove(
        key="backfill_routes",
        content_attr="sync_content",
        group_attr="backfillMissingDetailedRoutesButton",
        installed_attr="_local_first_backfill_controls_installed",
        installed_target_attr="_local_first_backfill_controls_installed_target",
        show_after_move=False,
        after_install_hook_key=REFRESH_CONDITIONAL_VISIBILITY_HOOK,
    ),
    LocalFirstControlMove(
        key="map_filters",
        content_attr="map_content",
        group_attr="filterGroupBox",
        required_widget_attrs=(
            "activityTypeComboBox",
            "activitySearchLineEdit",
            "dateFromEdit",
            "dateToEdit",
            "minDistanceSpinBox",
            "maxDistanceSpinBox",
            "detailedRouteStatusComboBox",
        ),
        installed_attr="_local_first_filter_controls_installed",
        installed_target_attr="_local_first_filter_controls_installed_target",
        title="Map filters",
        layout_getter_attr="filter_controls_layout",
        parent_panel_attr="filter_controls_panel",
        post_install_visible_attr="set_filter_controls_visible",
    ),
    LocalFirstControlMove(
        key="atlas_pdf",
        content_attr="atlas_content",
        group_attr="atlasPdfGroupBox",
        required_widget_attrs=("atlasPdfPathLineEdit", "atlasPdfBrowseButton"),
        installed_attr="_local_first_atlas_pdf_controls_installed",
        installed_target_attr="_local_first_atlas_pdf_controls_installed_target",
        title="PDF output",
        after_install_hook_key=HIDE_LEGACY_ATLAS_EXPORT_BUTTON_HOOK,
    ),
    LocalFirstControlMove(
        key="strava_credentials",
        content_attr="settings_content",
        group_attr="credentialsGroupBox",
        required_widget_attrs=(
            "clientIdLineEdit",
            "clientSecretLineEdit",
            "redirectUriLineEdit",
            "authCodeLineEdit",
            "refreshTokenLineEdit",
            "openAuthorizeButton",
            "exchangeCodeButton",
        ),
        installed_attr="_local_first_strava_credentials_controls_installed",
        installed_target_attr="_local_first_strava_credentials_controls_installed_target",
        title="Strava connection",
    ),
    LocalFirstControlMove(
        key="basemap",
        content_attr="settings_content",
        group_attr="backgroundGroupBox",
        required_widget_attrs=(
            "backgroundMapCheckBox",
            "backgroundPresetComboBox",
            "mapboxStyleOwnerLineEdit",
            "mapboxStyleIdLineEdit",
            "tileModeComboBox",
            "loadBackgroundButton",
        ),
        installed_attr="_local_first_basemap_controls_installed",
        installed_target_attr="_local_first_basemap_controls_installed_target",
        title="Mapbox basemap",
        after_install_hook_key=REFRESH_CONDITIONAL_VISIBILITY_HOOK,
    ),
    LocalFirstControlMove(
        key="storage",
        content_attr="settings_content",
        group_attr="outputGroupBox",
        required_widget_attrs=(
            "outputPathLineEdit",
            "browseButton",
            "writeActivityPointsCheckBox",
            "pointSamplingStrideSpinBox",
        ),
        installed_attr="_local_first_storage_controls_installed",
        installed_target_attr="_local_first_storage_controls_installed_target",
        title="Data storage",
        after_install_hook_key=REFRESH_CONDITIONAL_VISIBILITY_HOOK,
    ),
)


def local_first_control_move_for_key(key: str) -> LocalFirstControlMove:
    """Return the local-first control move spec for a supported control area."""

    for move in LOCAL_FIRST_CONTROL_MOVES:
        if move.key == key:
            return move
    raise KeyError(key)


def local_first_control_move_keys() -> tuple[str, ...]:
    """Return stable audit keys for legacy-backed local-first control moves."""

    return tuple(move.key for move in LOCAL_FIRST_CONTROL_MOVES)


def local_first_widget_move_for_key(key: str) -> LocalFirstWidgetMove:
    """Return the local-first loose-widget move spec for a supported area."""

    for move in LOCAL_FIRST_WIDGET_MOVES:
        if move.key == key:
            return move
    raise KeyError(key)


def local_first_widget_move_keys() -> tuple[str, ...]:
    """Return stable audit keys for loose local-first widget moves."""

    return tuple(move.key for move in LOCAL_FIRST_WIDGET_MOVES)


__all__ = [
    "LOCAL_FIRST_CONTROL_MOVES",
    "LOCAL_FIRST_WIDGET_MOVES",
    "HIDE_LEGACY_ATLAS_EXPORT_BUTTON_HOOK",
    "LocalFirstControlMove",
    "LocalFirstWidgetMove",
    "REFRESH_CONDITIONAL_VISIBILITY_HOOK",
    "local_first_control_move_for_key",
    "local_first_control_move_keys",
    "local_first_widget_move_for_key",
    "local_first_widget_move_keys",
]
