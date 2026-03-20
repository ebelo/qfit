import json
from dataclasses import asdict
from datetime import UTC, datetime
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
    STREAMS_URL_TEMPLATE = "https://www.strava.com/api/v3/activities/{activity_id}/streams"
    STREAM_KEYS = [
        "latlng",
        "time",
        "distance",
        "altitude",
        "heartrate",
        "cadence",
        "watts",
        "velocity_smooth",
        "moving",
        "temp",
        "grade_smooth",
    ]
    DEFAULT_SCOPE = "read,activity:read_all"
    DEFAULT_REDIRECT_URI = "http://localhost/exchange_token"

    def __init__(
        self,
        client_id=None,
        client_secret=None,
        refresh_token=None,
        access_token=None,
        cache=None,
        stream_cache_ttl_seconds=7 * 24 * 60 * 60,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.cache = cache
        self.stream_cache_ttl_seconds = stream_cache_ttl_seconds
        self.last_rate_limit = None
        self.last_stream_enrichment_stats = {}

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

    def fetch_activities(
        self,
        per_page=50,
        max_pages=1,
        before=None,
        after=None,
        use_detailed_streams=False,
        max_detailed_activities=None,
    ):
        token = self.get_access_token()
        activities = []
        for page in range(1, max_pages + 1):
            params = {"page": page, "per_page": per_page}
            if before is not None:
                params["before"] = int(before)
            if after is not None:
                params["after"] = int(after)

            url = "{base}?{query}".format(base=self.ACTIVITIES_URL, query=urlencode(params))
            request = Request(
                url,
                headers={"Authorization": "Bearer {token}".format(token=token), "Accept": "application/json"},
            )
            payload = self._request_json(request)
            batch = [self.normalize_activity(item) for item in payload]
            activities.extend(batch)
            if len(payload) < per_page:
                break

        if use_detailed_streams and activities:
            self.enrich_activities_with_streams(activities, max_activities=max_detailed_activities)
        else:
            self.last_stream_enrichment_stats = {
                "requested": 0,
                "cached": 0,
                "downloaded": 0,
                "skipped_rate_limit": 0,
                "errors": 0,
                "empty": 0,
            }

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

    def enrich_activities_with_streams(self, activities, max_activities=None):
        if max_activities is None or max_activities <= 0:
            limit = len(activities)
        else:
            limit = min(int(max_activities), len(activities))

        stats = {
            "requested": limit,
            "cached": 0,
            "downloaded": 0,
            "skipped_rate_limit": 0,
            "errors": 0,
            "empty": 0,
        }

        for activity in activities[:limit]:
            cached_bundle = self._load_cached_stream_bundle(activity)
            if cached_bundle is not None:
                if self._apply_stream_bundle_to_activity(activity, cached_bundle):
                    activity.details_json["stream_cache"] = "hit"
                    stats["cached"] += 1
                else:
                    activity.details_json["stream_cache"] = "hit-empty"
                    stats["empty"] += 1
                continue

            if self._approaching_rate_limit():
                activity.details_json["stream_skipped_reason"] = "rate_limit_guard"
                stats["skipped_rate_limit"] += 1
                continue

            try:
                stream_bundle = self.fetch_activity_stream_bundle(activity.source_activity_id)
            except StravaClientError as exc:
                activity.details_json["stream_error"] = str(exc)
                stats["errors"] += 1
                continue

            self._save_cached_stream_bundle(activity, stream_bundle)
            if self._apply_stream_bundle_to_activity(activity, stream_bundle):
                activity.details_json["stream_cache"] = "miss"
                stats["downloaded"] += 1
            else:
                activity.details_json["stream_cache"] = "miss-empty"
                stats["empty"] += 1

        self.last_stream_enrichment_stats = stats
        return activities

    def fetch_activity_stream_points(self, activity_id):
        stream_bundle = self.fetch_activity_stream_bundle(activity_id)
        return self._extract_stream_points(stream_bundle)

    def fetch_activity_stream_bundle(self, activity_id):
        token = self.get_access_token()
        params = {
            "keys": ",".join(self.STREAM_KEYS),
            "key_by_type": "true",
            "resolution": "high",
            "series_type": "distance",
        }
        url = "{base}?{query}".format(
            base=self.STREAMS_URL_TEMPLATE.format(activity_id=activity_id),
            query=urlencode(params),
        )
        request = Request(
            url,
            headers={"Authorization": "Bearer {token}".format(token=token), "Accept": "application/json"},
        )
        payload = self._request_json(request)
        return self._extract_stream_bundle(payload)

    def normalize_activity(self, payload):
        start_lat, start_lon = self._extract_latlon(payload.get("start_latlng"))
        end_lat, end_lon = self._extract_latlon(payload.get("end_latlng"))
        summary_polyline = (payload.get("map") or {}).get("summary_polyline")
        geometry_source = self._default_geometry_source(summary_polyline, start_lat, start_lon, end_lat, end_lon)
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
            summary_polyline=summary_polyline,
            geometry_source=geometry_source,
            details_json=self._extract_details_json(payload),
        )

    def _load_cached_stream_bundle(self, activity):
        if self.cache is None:
            return None
        return self.cache.load_stream_bundle(
            activity.source,
            activity.source_activity_id,
            max_age_seconds=self.stream_cache_ttl_seconds,
        )

    def _save_cached_stream_bundle(self, activity, stream_bundle):
        if self.cache is None:
            return None
        return self.cache.save_stream_bundle(
            activity.source,
            activity.source_activity_id,
            stream_bundle,
            metadata={
                "name": activity.name,
                "activity_type": activity.activity_type,
                "distance_m": activity.distance_m,
            },
        )

    def _apply_stream_bundle_to_activity(self, activity, stream_bundle):
        points = self._extract_stream_points(stream_bundle)
        if not points:
            return False

        activity.geometry_points = points
        activity.geometry_source = "stream"
        activity.details_json["stream_point_count"] = len(points)
        activity.details_json["stream_enriched_at"] = datetime.now(UTC).isoformat()
        metrics = self._extract_stream_metrics(stream_bundle)
        if metrics:
            activity.details_json["stream_metrics"] = metrics
            activity.details_json["stream_metric_keys"] = sorted(metrics.keys())
        else:
            activity.details_json.pop("stream_metrics", None)
            activity.details_json.pop("stream_metric_keys", None)
        return True

    def _extract_stream_metrics(self, stream_bundle):
        metrics = {}
        for key, values in (stream_bundle or {}).items():
            if key == "latlng":
                continue
            if isinstance(values, list) and values:
                metrics[key] = values
        return metrics

    def _approaching_rate_limit(self):
        if not self.last_rate_limit:
            return False
        short_remaining = self.last_rate_limit.get("short_remaining")
        long_remaining = self.last_rate_limit.get("long_remaining")
        if short_remaining is not None and short_remaining <= 5:
            return True
        if long_remaining is not None and long_remaining <= 25:
            return True
        return False

    def _default_geometry_source(self, summary_polyline, start_lat, start_lon, end_lat, end_lon):
        if summary_polyline:
            return "summary_polyline"
        if None not in (start_lat, start_lon, end_lat, end_lon):
            return "start_end"
        return None

    def _extract_stream_bundle(self, payload):
        streams = {}
        if isinstance(payload, dict):
            for key, stream_object in payload.items():
                if isinstance(stream_object, dict) and isinstance(stream_object.get("data"), list):
                    streams[key] = stream_object.get("data") or []
            return streams

        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and item.get("type") and isinstance(item.get("data"), list):
                    streams[item.get("type")] = item.get("data") or []
        return streams

    def _extract_stream_points(self, stream_bundle):
        points = []
        for value in (stream_bundle or {}).get("latlng", []):
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                points.append((float(value[0]), float(value[1])))
        return points

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
                self.last_rate_limit = self._extract_rate_limit(response.headers)
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise StravaClientError("Strava API error {code}: {body}".format(code=exc.code, body=body)) from exc
        except URLError as exc:
            raise StravaClientError("Network error talking to Strava: {exc}".format(exc=exc)) from exc
        except json.JSONDecodeError as exc:
            raise StravaClientError("Invalid JSON returned by Strava: {exc}".format(exc=exc)) from exc

    def _extract_rate_limit(self, headers):
        limit_short, limit_long = self._parse_rate_limit_pair(headers.get("X-RateLimit-Limit"))
        usage_short, usage_long = self._parse_rate_limit_pair(headers.get("X-RateLimit-Usage"))
        return {
            "short_limit": limit_short,
            "long_limit": limit_long,
            "short_usage": usage_short,
            "long_usage": usage_long,
            "short_remaining": self._remaining(limit_short, usage_short),
            "long_remaining": self._remaining(limit_long, usage_long),
        }

    def _parse_rate_limit_pair(self, value):
        if not value:
            return None, None
        parts = [part.strip() for part in str(value).split(",")]
        if len(parts) != 2:
            return None, None
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None, None

    def _remaining(self, limit_value, usage_value):
        if limit_value is None or usage_value is None:
            return None
        return max(0, int(limit_value) - int(usage_value))

    @staticmethod
    def as_dict(activity):
        if hasattr(activity, "to_record"):
            return activity.to_record()
        return asdict(activity)
