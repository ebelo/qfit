"""Local-first Settings page connection-control policies."""

from collections.abc import Callable

CONFIGURE_CONNECTION_TITLE = "Configure qfit connection"
CONFIGURE_CONNECTION_BODY = (
    "Open qfit → Configuration from the QGIS plugin menu to edit Strava "
    "credentials, then return to the dock to continue the workflow."
)
CONFIGURATION_OPENED_STATUS = (
    "qfit configuration opened; save credentials to continue."
)
CONFIGURATION_MENU_STATUS = "Open qfit → Configuration to edit Strava credentials."


def request_local_first_connection_configuration(
    *,
    open_configuration: Callable[[], None] | None,
    set_status: Callable[[str], None],
    show_info: Callable[[str, str], None],
) -> None:
    """Handle the local-first Settings page Configure action."""

    if open_configuration is not None:
        open_configuration()
        set_status(CONFIGURATION_OPENED_STATUS)
        return

    show_info(CONFIGURE_CONNECTION_TITLE, CONFIGURE_CONNECTION_BODY)
    set_status(CONFIGURATION_MENU_STATUS)


__all__ = [
    "CONFIGURATION_MENU_STATUS",
    "CONFIGURATION_OPENED_STATUS",
    "CONFIGURE_CONNECTION_BODY",
    "CONFIGURE_CONNECTION_TITLE",
    "request_local_first_connection_configuration",
]
