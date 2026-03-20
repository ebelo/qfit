class StravaClient:
    """Minimal scaffold for future Strava API integration."""

    def __init__(self, client_id=None, client_secret=None, refresh_token=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token

    def fetch_activities(self, page=1, per_page=50):
        raise NotImplementedError("Strava activity download is not implemented yet")
