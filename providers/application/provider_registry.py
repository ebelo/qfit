from __future__ import annotations

from dataclasses import dataclass

from ..domain.provider import ProviderError
from ..infrastructure.strava_provider import StravaProvider

DEFAULT_PROVIDER_NAME = "strava"


@dataclass(frozen=True)
class BuildProviderRequest:
    provider_name: str = DEFAULT_PROVIDER_NAME
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    cache: object = None
    require_refresh_token: bool = True


class ProviderRegistry:
    """Centralizes activity-provider construction behind a small registry seam."""

    def __init__(self, builders: dict[str, object] | None = None):
        self._builders = dict(builders or {})

    def build_provider(self, request: BuildProviderRequest):
        provider_name = (request.provider_name or DEFAULT_PROVIDER_NAME).strip().lower()
        builder = self._builders.get(provider_name)
        if builder is None:
            raise ProviderError(
                "Unsupported activity provider: {name}".format(
                    name=request.provider_name or DEFAULT_PROVIDER_NAME
                )
            )

        provider = builder(request)
        if not provider.has_client_credentials():
            raise ProviderError(
                "Open qfit → Configuration and enter your Strava client ID and client secret first."
            )
        if request.require_refresh_token and not provider.has_refresh_token():
            raise ProviderError(
                "Open qfit → Configuration and enter a Strava refresh token first."
            )
        return provider


def build_default_provider_registry() -> ProviderRegistry:
    return ProviderRegistry(
        builders={
            DEFAULT_PROVIDER_NAME: _build_strava_provider,
        }
    )


def _build_strava_provider(request: BuildProviderRequest) -> StravaProvider:
    return StravaProvider(
        request.client_id,
        request.client_secret,
        request.refresh_token,
        cache=request.cache,
    )
