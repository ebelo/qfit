"""Strava implementation of the :class:`ActivityProvider` protocol.

Wraps :class:`StravaClient` and translates Strava-specific errors into the
provider-neutral :class:`ProviderError`.
"""

from ..domain.provider import ProviderError
from ...detailed_route_strategy import DEFAULT_DETAILED_ROUTE_STRATEGY
from .strava_client import StravaClient, StravaClientError


class StravaProvider:
    """ActivityProvider backed by the Strava API.

    Wraps :class:`StravaClient`, exposing the provider-neutral interface
    defined by :class:`ActivityProvider` while also making Strava-specific
    authorisation helpers available for the UI layer.
    """

    source_name = "strava"
    DEFAULT_REDIRECT_URI = StravaClient.DEFAULT_REDIRECT_URI

    def __init__(self, client_id=None, client_secret=None, refresh_token=None, cache=None):
        self._client = StravaClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            cache=cache,
        )

    # ------------------------------------------------------------------
    # ActivityProvider protocol
    # ------------------------------------------------------------------

    @property
    def last_stream_enrichment_stats(self):
        return self._client.last_stream_enrichment_stats

    @property
    def last_rate_limit(self):
        return self._client.last_rate_limit

    @property
    def last_fetch_notice(self):
        return self._client.last_fetch_notice

    def fetch_activities(
        self,
        per_page=200,
        max_pages=0,
        before=None,
        after=None,
        use_detailed_streams=False,
        max_detailed_activities=None,
        detailed_route_strategy=DEFAULT_DETAILED_ROUTE_STRATEGY,
    ):
        """Fetch activities from Strava.

        Delegates to :meth:`StravaClient.fetch_activities` and translates any
        :class:`StravaClientError` into a provider-neutral :class:`ProviderError`.
        """
        try:
            return self._client.fetch_activities(
                per_page=per_page,
                max_pages=max_pages,
                before=before,
                after=after,
                use_detailed_streams=use_detailed_streams,
                max_detailed_activities=max_detailed_activities,
                detailed_route_strategy=detailed_route_strategy,
            )
        except StravaClientError as exc:
            raise ProviderError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Strava-specific: OAuth authorisation helpers
    # ------------------------------------------------------------------

    def has_client_credentials(self):
        """Return True if both client_id and client_secret are set."""
        return self._client.has_client_credentials()

    def has_refresh_token(self):
        """Return True if a refresh token is available."""
        return bool(self._client.refresh_token)

    def build_authorize_url(self, redirect_uri=None):
        """Build the Strava OAuth authorisation URL."""
        try:
            return self._client.build_authorize_url(redirect_uri=redirect_uri)
        except StravaClientError as exc:
            raise ProviderError(str(exc)) from exc

    def exchange_code_for_tokens(self, authorization_code, redirect_uri=None):
        """Exchange an authorisation code for access and refresh tokens."""
        try:
            return self._client.exchange_code_for_tokens(
                authorization_code=authorization_code,
                redirect_uri=redirect_uri,
            )
        except StravaClientError as exc:
            raise ProviderError(str(exc)) from exc
