import unittest

from tests import _path  # noqa: F401
from qfit.provider import ProviderError
from qfit.providers.application import (
    BuildProviderRequest,
    ProviderRegistry,
    build_default_provider_registry,
)
from qfit.strava_provider import StravaProvider


class TestProviderRegistry(unittest.TestCase):
    def test_default_registry_builds_strava_provider(self):
        registry = build_default_provider_registry()
        request = BuildProviderRequest(
            provider_name="strava",
            client_id="client-id",
            client_secret="client-secret",
            refresh_token="refresh-token",
        )

        provider = registry.build_provider(request)

        self.assertIsInstance(provider, StravaProvider)

    def test_registry_rejects_unknown_provider_name(self):
        registry = ProviderRegistry(builders={})
        request = BuildProviderRequest(provider_name="unknown")

        with self.assertRaises(ProviderError):
            registry.build_provider(request)

    def test_registry_validates_provider_configuration(self):
        registry = build_default_provider_registry()
        request = BuildProviderRequest(
            provider_name="strava",
            client_id="",
            client_secret="",
            refresh_token="",
        )

        with self.assertRaises(ProviderError):
            registry.build_provider(request)


if __name__ == "__main__":
    unittest.main()
