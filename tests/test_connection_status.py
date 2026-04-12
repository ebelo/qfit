import unittest

from tests import _path  # noqa: F401

from qfit.configuration.application.connection_status import build_strava_connection_status


class ConnectionStatusTests(unittest.TestCase):
    def test_ready_when_client_credentials_and_refresh_token_exist(self):
        self.assertEqual(
            build_strava_connection_status(
                client_id="client-id",
                client_secret="client-secret",
                refresh_token="refresh-token",
            ),
            "Strava connection: ready to fetch activities",
        )

    def test_requests_refresh_token_when_only_client_credentials_exist(self):
        self.assertEqual(
            build_strava_connection_status(
                client_id="client-id",
                client_secret="client-secret",
                refresh_token="",
            ),
            "Strava connection: app credentials saved; add a refresh token in Configuration to fetch activities",
        )

    def test_requests_configuration_when_credentials_missing(self):
        self.assertEqual(
            build_strava_connection_status(
                client_id="",
                client_secret="client-secret",
                refresh_token="refresh-token",
            ),
            "Strava connection: open qfit → Configuration to add your Strava credentials",
        )

    def test_ignores_whitespace_only_values(self):
        self.assertEqual(
            build_strava_connection_status(
                client_id="  ",
                client_secret=" client-secret ",
                refresh_token="  refresh-token  ",
            ),
            "Strava connection: open qfit → Configuration to add your Strava credentials",
        )


if __name__ == "__main__":
    unittest.main()
