import json
import socket
import time
from dataclasses import asdict
from datetime import UTC, datetime
from urllib.parse import urlencode
from urllib.error import HTTPError as UrllibHTTPError, URLError
from urllib.request import Request as UrllibRequest, urlopen

try:
    import requests as _requests
except ModuleNotFoundError:  # pragma: no cover - exercised in CI fallback path
    _requests = None


class _FallbackRequestException(Exception):
    pass


class _FallbackHTTPError(_FallbackRequestException):
    def __init__(self, response):
        super().__init__(str(getattr(response, "status_code", "HTTP error")))
        self.response = response


class _FallbackConnectionError(_FallbackRequestException):
    pass


class _FallbackResponse:
    def __init__(self, body, headers, status_code, url):
        self._body = body
        self.headers = headers
        self.status_code = status_code
        self.url = url
        self.text = body.decode("utf-8", errors="replace")

    def raise_for_status(self):
        if int(self.status_code) >= 400:
            raise _FallbackHTTPError(self)

    def json(self):
        return json.loads(self.text)


class _FallbackSession:
    def request(self, method, url, data=None, headers=None, timeout=60):
        request = UrllibRequest(url, data=data, headers=headers or {}, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                return _FallbackResponse(
                    body=response.read(),
                    headers=response.headers,
                    status_code=getattr(response, "status", 200),
                    url=url,
                )
        except UrllibHTTPError as exc:
            return _FallbackResponse(
                body=exc.read(),
                headers=exc.headers,
                status_code=exc.code,
                url=url,
            )
        except (URLError, OSError, TimeoutError) as exc:
            raise _FallbackConnectionError(exc) from exc


class _RequestsCompat:
    Session = _requests.Session if _requests is not None else _FallbackSession
    RequestException = _requests.RequestException if _requests is not None else _FallbackRequestException
    HTTPError = _requests.HTTPError if _requests is not None else _FallbackHTTPError
    ConnectionError = _requests.ConnectionError if _requests is not None else _FallbackConnectionError


requests = _RequestsCompat()

from ...activities.domain.models import Activity
from ...detailed_route_strategy import (
    DEFAULT_DETAILED_ROUTE_STRATEGY,
    DETAILED_ROUTE_STRATEGY_RECENT,
)


class StravaClientError(RuntimeError):
    pass


class StravaClient:
    AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
    TOKEN_URL = "https://www.strava.com/oauth/token"
    ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
    STREAMS_URL_TEMPLATE = "https://www.strava.com/api/v3/activities/{activity_id}/streams"
    DEFAULT_NETWORK_RETRY_ATTEMPTS = 3
    MIN_ACTIVITY_PAGE_SIZE = 5
    FULL_SYNC_MIN_SHORT_REMAINING = 3
    FULL_SYNC_MIN_LONG_REMAINING = 15
    PAGE_REQUEST_DELAY_SECONDS = 0.2
    RETRYABLE_ERRNOS = {104}
    RETRYABLE_WINERRORS = {10054}
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
        self.last_fetch_notice = None
        self.session = requests.Session()

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
        payload = self._request_json(
            self.TOKEN_URL,
            method="POST",
            data=data,
            headers=self._build_request_headers(content_type="application/x-www-form-urlencoded"),
            operation="Exchanging Strava authorization code for tokens",
        )
        self.access_token = payload.get("access_token")
        self.refresh_token = payload.get("refresh_token") or self.refresh_token
        return payload

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
        """Fetch activities from Strava, paginating until all results are returned.

        Parameters
        ----------
        per_page:
            Number of activities per API request (1–200).  Defaults to 200
            (Strava's maximum) so as few round-trips as possible are needed.
        max_pages:
            Maximum number of pages to fetch.  ``0`` (the default) means
            "fetch all pages" — the loop stops when Strava returns fewer
            results than ``per_page``, indicating the last page.
        """
        token = self.get_access_token()
        activities = []
        current_before = before
        current_per_page = max(1, int(per_page))
        self.last_fetch_notice = None
        page = 1
        while not max_pages or page <= max_pages:
            payload, current_per_page = self._fetch_activity_page(
                token=token,
                page=page,
                per_page=current_per_page,
                current_before=current_before,
                after=after,
                max_pages=max_pages,
            )
            batch = [self.normalize_activity(item) for item in payload]
            activities.extend(batch)
            if len(payload) < current_per_page:
                break
            if max_pages == 0 and self._should_pause_full_sync_for_rate_limit():
                self.last_fetch_notice = self._rate_limit_pause_notice()
                break
            current_before = self._next_full_sync_before(current_before, batch, max_pages)
            self._sleep_between_activity_pages()
            page += 1

        if use_detailed_streams and activities:
            self.enrich_activities_with_streams(
                activities,
                max_activities=max_detailed_activities,
                strategy=detailed_route_strategy,
            )
        else:
            self.last_stream_enrichment_stats = {
                "requested": 0,
                "already_detailed": 0,
                "missing_before": 0,
                "cached": 0,
                "downloaded": 0,
                "skipped_rate_limit": 0,
                "errors": 0,
                "empty": 0,
                "remaining_missing": 0,
            }

        return activities

    def _fetch_activity_page(self, token, page, per_page, current_before, after, max_pages):
        while True:
            payload = None
            url = self._activity_page_url(page, per_page, current_before, after, max_pages)
            try:
                payload = self._request_json(
                    url,
                    headers=self._build_request_headers(token=token),
                    operation="Fetching Strava activities page {page}".format(page=page),
                )
                return payload, per_page
            except StravaClientError as exc:
                reduced_per_page = self._reduced_activity_page_size(per_page, exc, max_pages=max_pages)
                if reduced_per_page is None:
                    raise
                per_page = reduced_per_page
                self._sleep_between_activity_pages()

    def _activity_page_url(self, page, per_page, current_before, after, max_pages):
        params = {"page": 1 if max_pages == 0 else page, "per_page": per_page}
        if current_before is not None:
            params["before"] = int(current_before)
        if after is not None:
            params["after"] = int(after)
        return "{base}?{query}".format(base=self.ACTIVITIES_URL, query=urlencode(params))

    def _next_full_sync_before(self, current_before, batch, max_pages):
        if max_pages != 0:
            return current_before
        next_before = self._next_activities_before(batch)
        if next_before is None:
            return current_before
        return next_before

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
        payload = self._request_json(
            self.TOKEN_URL,
            method="POST",
            data=data,
            headers=self._build_request_headers(content_type="application/x-www-form-urlencoded"),
            operation="Refreshing Strava access token",
        )
        self.access_token = payload.get("access_token")
        self.refresh_token = payload.get("refresh_token") or self.refresh_token
        if not self.access_token:
            raise StravaClientError("Strava did not return an access token")
        return payload

    def enrich_activities_with_streams(
        self,
        activities,
        max_activities=None,
        strategy=DEFAULT_DETAILED_ROUTE_STRATEGY,
    ):
        stats = {
            "requested": 0,
            "already_detailed": 0,
            "missing_before": 0,
            "cached": 0,
            "downloaded": 0,
            "skipped_rate_limit": 0,
            "errors": 0,
            "empty": 0,
            "remaining_missing": 0,
        }

        if strategy == DETAILED_ROUTE_STRATEGY_RECENT:
            stats["already_detailed"] = sum(1 for activity in activities if self._activity_has_detailed_route(activity))
            for activity in activities:
                if self._activity_has_detailed_route(activity):
                    self._set_detailed_route_status(activity, "downloaded")
            stats["missing_before"] = sum(
                1 for activity in activities if self._activity_needs_detailed_route(activity)
            )
            limit = self._stream_request_limit(activities, max_activities)
            stats["requested"] = limit

            for activity in activities[:limit]:
                if self._activity_has_detailed_route(activity):
                    continue

                cached_bundle = self._load_cached_stream_bundle(activity)
                if cached_bundle is not None:
                    if self._apply_stream_bundle_to_activity(activity, cached_bundle):
                        activity.details_json["stream_cache"] = "hit"
                        self._set_detailed_route_status(activity, "cached")
                        stats["cached"] += 1
                    else:
                        activity.details_json["stream_cache"] = "hit-empty"
                        self._set_detailed_route_status(activity, "empty")
                        stats["empty"] += 1
                    continue

                self._enrich_single_activity_with_streams(activity, stats)

            stats["remaining_missing"] = sum(
                1 for activity in activities if self._activity_needs_detailed_route(activity)
            )
            self.last_stream_enrichment_stats = stats
            return activities

        candidates = []
        for activity in activities:
            if self._activity_has_detailed_route(activity):
                stats["already_detailed"] += 1
                self._set_detailed_route_status(activity, "downloaded")
                continue

            cached_bundle = self._load_cached_stream_bundle(activity)
            if cached_bundle is not None:
                if self._apply_stream_bundle_to_activity(activity, cached_bundle):
                    activity.details_json["stream_cache"] = "hit"
                    self._set_detailed_route_status(activity, "cached")
                    stats["cached"] += 1
                else:
                    activity.details_json["stream_cache"] = "hit-empty"
                    self._set_detailed_route_status(activity, "empty")
                    stats["empty"] += 1
                continue

            candidates.append(activity)

        stats["missing_before"] = len(candidates)
        limit = self._stream_request_limit(candidates, max_activities)
        stats["requested"] = limit

        for activity in candidates[:limit]:
            self._enrich_single_activity_with_streams(activity, stats)

        stats["remaining_missing"] = sum(
            1 for activity in activities if self._activity_needs_detailed_route(activity)
        )
        self.last_stream_enrichment_stats = stats
        return activities

    @staticmethod
    def _stream_request_limit(activities, max_activities):
        if max_activities is None or max_activities <= 0:
            return len(activities)
        return min(int(max_activities), len(activities))

    def _enrich_single_activity_with_streams(self, activity, stats):
        if self._approaching_rate_limit():
            activity.details_json["stream_skipped_reason"] = "rate_limit_guard"
            self._set_detailed_route_status(activity, "skipped_rate_limit")
            stats["skipped_rate_limit"] += 1
            return

        try:
            stream_bundle = self.fetch_activity_stream_bundle(activity.source_activity_id)
        except StravaClientError as exc:
            activity.details_json["stream_error"] = str(exc)
            self._set_detailed_route_status(activity, "error")
            stats["errors"] += 1
            return

        self._save_cached_stream_bundle(activity, stream_bundle)
        if self._apply_stream_bundle_to_activity(activity, stream_bundle):
            activity.details_json["stream_cache"] = "miss"
            self._set_detailed_route_status(activity, "downloaded")
            stats["downloaded"] += 1
        else:
            activity.details_json["stream_cache"] = "miss-empty"
            self._set_detailed_route_status(activity, "empty")
            stats["empty"] += 1

    @staticmethod
    def _activity_has_detailed_route(activity):
        return getattr(activity, "geometry_source", None) == "stream"

    @staticmethod
    def _activity_needs_detailed_route(activity):
        if getattr(activity, "geometry_source", None) == "stream":
            return False
        status = (getattr(activity, "details_json", None) or {}).get("detailed_route_status")
        return status not in {"cached", "downloaded", "empty"}

    @staticmethod
    def _set_detailed_route_status(activity, status):
        activity.details_json["detailed_route_status"] = status

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
        payload = self._request_json(
            url,
            headers=self._build_request_headers(token=token),
            operation="Fetching Strava detailed stream for activity {activity_id}".format(activity_id=activity_id),
        )
        return self._extract_stream_bundle(payload)

    def _build_request_headers(self, token=None, content_type=None):
        headers = {
            "Accept": "application/json",
            "Connection": "close",
            "User-Agent": "qfit/{version}".format(version=self._plugin_version()),
        }
        if token:
            headers["Authorization"] = "Bearer {token}".format(token=token)
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _plugin_version(self):
        return "0.42.0"

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

    def _next_activities_before(self, activities):
        if not activities:
            return None

        oldest_epoch = None
        for activity in activities:
            start_epoch = self._activity_start_epoch(activity)
            if start_epoch is None:
                continue
            if oldest_epoch is None or start_epoch < oldest_epoch:
                oldest_epoch = start_epoch

        if oldest_epoch is None:
            return None
        return oldest_epoch - 1

    def _activity_start_epoch(self, activity):
        start_value = getattr(activity, "start_date", None) or getattr(activity, "start_date_local", None)
        if not start_value:
            return None

        try:
            parsed = datetime.fromisoformat(str(start_value).replace("Z", "+00:00"))
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return int(parsed.timestamp())

    def _extract_latlon(self, value):
        if not value or len(value) != 2:
            return None, None
        return value[0], value[1]

    def _request_json(self, url, method="GET", data=None, headers=None, operation="Request to Strava"):
        attempts = max(1, int(self.DEFAULT_NETWORK_RETRY_ATTEMPTS))
        last_error = None

        for attempt in range(1, attempts + 1):
            try:
                response = self.session.request(method=method, url=url, data=data, headers=headers, timeout=60)
                self.last_rate_limit = self._extract_rate_limit(response.headers)
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as exc:
                response = getattr(exc, "response", None)
                status_code = response.status_code if response is not None else "unknown"
                body = response.text if response is not None else str(exc)
                if response is not None and int(status_code) == 429:
                    raise StravaClientError(self._format_rate_limit_error(operation, response)) from exc
                raise StravaClientError(
                    "{operation} failed with Strava API error {code}: {body}".format(
                        operation=operation,
                        code=status_code,
                        body=body,
                    )
                ) from exc
            except (requests.RequestException, OSError, TimeoutError) as exc:
                last_error = exc
                if attempt < attempts and self._is_retryable_network_error(exc):
                    time.sleep(self._retry_delay_seconds(attempt))
                    continue
                raise StravaClientError(self._format_network_error(operation, exc, attempts)) from exc
            except ValueError as exc:
                raise StravaClientError(
                    "{operation} returned invalid JSON: {exc}".format(operation=operation, exc=exc)
                ) from exc

        raise StravaClientError(self._format_network_error(operation, last_error, attempts))

    def _is_retryable_network_error(self, exc):
        for error in self._iter_network_errors(exc):
            if isinstance(error, ConnectionResetError):
                return True
            if isinstance(error, (socket.timeout, TimeoutError)):
                return True

            errno_value = getattr(error, "errno", None)
            if errno_value in self.RETRYABLE_ERRNOS:
                return True

            winerror_value = getattr(error, "winerror", None)
            if winerror_value in self.RETRYABLE_WINERRORS:
                return True

        return False

    def _iter_network_errors(self, exc):
        seen = set()
        stack = [exc]
        while stack:
            current = stack.pop()
            if current is None or id(current) in seen:
                continue
            seen.add(id(current))
            yield current
            for next_error in (
                getattr(current, "reason", None),
                getattr(current, "__cause__", None),
                getattr(current, "__context__", None),
            ):
                if next_error is not None:
                    stack.append(next_error)
            for arg in getattr(current, "args", ()):
                if isinstance(arg, BaseException):
                    stack.append(arg)

    def _retry_delay_seconds(self, attempt):
        return min(8.0, float(2 ** (attempt - 1)))

    def _sleep_between_activity_pages(self):
        delay = float(self.PAGE_REQUEST_DELAY_SECONDS)
        if delay > 0:
            time.sleep(delay)

    def _reduced_activity_page_size(self, current_per_page, exc, *, max_pages):
        if max_pages != 0:
            return None
        if not self._is_transient_network_message(str(exc)):
            return None
        if current_per_page <= self.MIN_ACTIVITY_PAGE_SIZE:
            return None
        return max(self.MIN_ACTIVITY_PAGE_SIZE, current_per_page // 2)

    def _is_transient_network_message(self, message):
        return "transient network error" in str(message).lower()

    def _should_pause_full_sync_for_rate_limit(self):
        if not self.last_rate_limit:
            return False
        short_remaining = self.last_rate_limit.get("short_remaining")
        long_remaining = self.last_rate_limit.get("long_remaining")
        if short_remaining is not None and short_remaining <= self.FULL_SYNC_MIN_SHORT_REMAINING:
            return True
        if long_remaining is not None and long_remaining <= self.FULL_SYNC_MIN_LONG_REMAINING:
            return True
        return False

    def _rate_limit_pause_notice(self):
        rate_limit = self.last_rate_limit or {}
        short_remaining = rate_limit.get("short_remaining")
        long_remaining = rate_limit.get("long_remaining")
        guidance = self._rate_limit_retry_guidance(rate_limit)
        return (
            "Stopped early to avoid hitting the Strava rate limit. Remaining read quota: short={short}, long={long}. {guidance}"
        ).format(
            short=short_remaining if short_remaining is not None else "?",
            long=long_remaining if long_remaining is not None else "?",
            guidance=guidance,
        )

    def _format_rate_limit_error(self, operation, response):
        rate_limit = self._extract_rate_limit(response.headers)
        self.last_rate_limit = rate_limit
        guidance = self._rate_limit_retry_guidance(rate_limit)
        short_limit = rate_limit.get("short_limit")
        long_limit = rate_limit.get("long_limit")
        short_remaining = rate_limit.get("short_remaining")
        long_remaining = rate_limit.get("long_remaining")
        return (
            "{operation} hit the Strava rate limit (read limit {short_limit}/15 min, {long_limit}/day; remaining short={short_remaining}, long={long_remaining}). {guidance}"
        ).format(
            operation=operation,
            short_limit=short_limit if short_limit is not None else "?",
            long_limit=long_limit if long_limit is not None else "?",
            short_remaining=short_remaining if short_remaining is not None else "?",
            long_remaining=long_remaining if long_remaining is not None else "?",
            guidance=guidance,
        )

    def _rate_limit_retry_guidance(self, rate_limit):
        long_remaining = rate_limit.get("long_remaining") if rate_limit else None
        short_remaining = rate_limit.get("short_remaining") if rate_limit else None
        if long_remaining is not None and long_remaining <= 0:
            return "The daily quota looks exhausted; wait until Strava resets the day limit before retrying."
        if short_remaining is not None and short_remaining <= 0:
            return "Wait about 15 minutes before retrying the full sync."
        return "Retry with a smaller window or wait a bit before continuing the full sync."

    def _format_network_error(self, operation, exc, attempts):
        detail = self._describe_network_error(exc)
        if exc is not None and self._is_retryable_network_error(exc) and attempts > 1:
            return "{operation} failed after {attempts} attempts due to a transient network error: {detail}".format(
                operation=operation,
                attempts=attempts,
                detail=detail,
            )
        return "{operation} failed due to a network error: {detail}".format(operation=operation, detail=detail)

    def _describe_network_error(self, exc):
        if exc is None:
            return "unknown network error"

        parts = []
        for error in self._iter_network_errors(exc):
            text = str(error).strip()
            if not text:
                continue
            if not parts or parts[-1] != text:
                parts.append(text)

        if parts:
            return ": ".join(parts)
        return exc.__class__.__name__

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
