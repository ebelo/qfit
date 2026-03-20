import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Activity


class StravaClientError(RuntimeError):
    pass


class StravaClient:
    AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
    TOKEN_URL = "https://www.strava.com/oauth/token"
    ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
    DEFAULT_SCOPE = "read,activity:read_all"
    DEFAULT_REDIRECT_URI = "http://localhost/exchange_token"

    def __init__(
        self,
        client_id=None,
        client_secret=None,
        refresh_token=None,
        access_token=None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = access_token

    def has_client_credentials(self):
        return bool(self.client_id and self.client_secret)

    def is_configured(self):
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def build_authorize_url(self, redirect_uri=None, scope=None, approval_prompt="force"):
        if not self.client_id:
            raise StravaClientError("Strava client ID is required before opening the authorization page")

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri or self.DEFAULT_REDIRECT_URI,
            "approval_prompt": approval_prompt,
            "scope": scope or self.DEFAULT_SCOPE,
        }
        return "{base}?{query}".format(base=self.AUTHORIZE_URL, query=urlencode(params))

    def exchange_code_for_tokens(self, authorization_code, redirect_uri=None):
        if not self.has_client_credentials():
            raise StravaClientError("Strava client ID and client secret are required")
        if not authorization_code:
            raise StravaClientError("Authorization code is required")

        data = urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": authorization_code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri or self.DEFAULT_REDIRECT_URI,
            }
        ).encode("utf-8")
        request = Request(self.TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        payload = self._request_json(request)
        self.access_token = payload.get("access_token")
        self.refresh_token = payload.get("refresh_token") or self.refresh_token
        return payload

    def fetch_activities(self, per_page=50, max_pages=1, before=None, after=None):
        token = self.get_access_token()
        activities = []
        for page in range(1, max_pages + 1):
            params = {"page": page, "per_page": per_page}
            if before is not None:
                params["before"] = int(before)
            if after is not None:
                params["after"] = int(after)

            url = "{base}?{query}".format(base=self.ACTIVITIES_URL, query=urlencode(params))
            request = Request(url, headers={"Authorization": "Bearer {token}".format(token=token), "Accept": "application/json"})
            payload = self._request_json(request)
            batch = [self.normalize_activity(item) for item in payload]
            activities.extend(batch)
            if len(payload) < per_page:
                break
        return activities

    def get_access_token(self):
        if self.access_token:
            return self.access_token
        self.refresh_access_token()
        return self.access_token

    def refresh_access_token(self):
        if not self.is_configured():
            raise StravaClientError("Strava credentials are incomplete")

        data = urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        request = Request(self.TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        payload = self._request_json(request)
        self.access_token = payload.get("access_token")
        self.refresh_token = payload.get("refresh_token") or self.refresh_token
        if not self.access_token:
            raise StravaClientError("Strava did not return an access token")
        return payload

    def normalize_activity(self, payload):
        start_lat, start_lon = self._extract_latlon(payload.get("start_latlng"))
        end_lat, end_lon = self._extract_latlon(payload.get("end_latlng"))
        return Activity(
            source="strava",
            source_activity_id=str(payload.get("id")),
            external_id=payload.get("external_id"),
            name=payload.get("name"),
            activity_type=payload.get("type") or payload.get("sport_type"),
            sport_type=payload.get("sport_type") or payload.get("type"),
            start_date=payload.get("start_date"),
            start_date_local=payload.get("start_date_local"),
            timezone=payload.get("timezone"),
            distance_m=payload.get("distance"),
            moving_time_s=payload.get("moving_time"),
            elapsed_time_s=payload.get("elapsed_time"),
            total_elevation_gain_m=payload.get("total_elevation_gain"),
            average_speed_mps=payload.get("average_speed"),
            max_speed_mps=payload.get("max_speed"),
            average_heartrate=payload.get("average_heartrate"),
            max_heartrate=payload.get("max_heartrate"),
            average_watts=payload.get("average_watts"),
            kilojoules=payload.get("kilojoules"),
            calories=payload.get("calories"),
            suffer_score=payload.get("suffer_score"),
            start_lat=start_lat,
            start_lon=start_lon,
            end_lat=end_lat,
            end_lon=end_lon,
            summary_polyline=((payload.get("map") or {}).get("summary_polyline")),
            details_json=self._extract_details_json(payload),
        )

    def _extract_details_json(self, payload):
        excluded = {
            "id",
            "external_id",
            "name",
            "type",
            "sport_type",
            "start_date",
            "start_date_local",
            "timezone",
            "distance",
            "moving_time",
            "elapsed_time",
            "total_elevation_gain",
            "average_speed",
            "max_speed",
            "average_heartrate",
            "max_heartrate",
            "average_watts",
            "kilojoules",
            "calories",
            "suffer_score",
            "start_latlng",
            "end_latlng",
            "map",
        }
        filtered = {key: value for key, value in payload.items() if key not in excluded}
        filtered["normalized_at"] = datetime.now(UTC).isoformat()
        return filtered

    def _extract_latlon(self, value):
        if not value or len(value) != 2:
            return None, None
        return value[0], value[1]

    def _request_json(self, request):
        try:
            with urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise StravaClientError("Strava API error {code}: {body}".format(code=exc.code, body=body)) from exc
        except URLError as exc:
            raise StravaClientError("Network error talking to Strava: {exc}".format(exc=exc)) from exc
        except json.JSONDecodeError as exc:
            raise StravaClientError("Invalid JSON returned by Strava: {exc}".format(exc=exc)) from exc

    @staticmethod
    def as_dict(activity):
        if hasattr(activity, "to_record"):
            return activity.to_record()
        return asdict(activity)
