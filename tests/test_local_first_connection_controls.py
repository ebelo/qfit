import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.ui.application.local_first_connection_controls import (
    CONFIGURATION_MENU_STATUS,
    CONFIGURATION_OPENED_STATUS,
    CONFIGURE_CONNECTION_BODY,
    CONFIGURE_CONNECTION_TITLE,
    request_local_first_connection_configuration,
)


class LocalFirstConnectionControlsTests(unittest.TestCase):
    def test_request_opens_configuration_when_callback_is_available(self):
        open_configuration = MagicMock()
        set_status = MagicMock()
        show_info = MagicMock()

        request_local_first_connection_configuration(
            open_configuration=open_configuration,
            set_status=set_status,
            show_info=show_info,
        )

        open_configuration.assert_called_once_with()
        show_info.assert_not_called()
        set_status.assert_called_once_with(CONFIGURATION_OPENED_STATUS)

    def test_request_reports_menu_path_when_callback_is_unavailable(self):
        set_status = MagicMock()
        show_info = MagicMock()

        request_local_first_connection_configuration(
            open_configuration=None,
            set_status=set_status,
            show_info=show_info,
        )

        show_info.assert_called_once_with(
            CONFIGURE_CONNECTION_TITLE,
            CONFIGURE_CONNECTION_BODY,
        )
        set_status.assert_called_once_with(CONFIGURATION_MENU_STATUS)


if __name__ == "__main__":
    unittest.main()
