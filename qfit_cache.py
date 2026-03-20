import json
import os
import time
from datetime import UTC, datetime


class QfitCache:
    def __init__(self, base_path=None):
        self.base_path = base_path or os.path.join(os.path.expanduser("~"), ".qfit-cache")

    def load_stream_bundle(self, source, activity_id, max_age_seconds=None):
        path = self._cache_path(source, "streams", activity_id)
        if not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        cached_at_epoch = payload.get("cached_at_epoch")
        if max_age_seconds and cached_at_epoch:
            age_seconds = max(0, int(time.time() - float(cached_at_epoch)))
            if age_seconds > int(max_age_seconds):
                return None

        streams = payload.get("streams")
        if isinstance(streams, dict):
            return streams

        # Backward compatibility for older point-only cache files.
        points = []
        for value in payload.get("points", []):
            if isinstance(value, list) and len(value) >= 2:
                points.append([float(value[0]), float(value[1])])
        if points:
            return {"latlng": points}
        return None

    def save_stream_bundle(self, source, activity_id, streams, metadata=None):
        path = self._cache_path(source, "streams", activity_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "source": source,
            "activity_id": str(activity_id),
            "cached_at": datetime.now(UTC).isoformat(),
            "cached_at_epoch": int(time.time()),
            "streams": streams or {},
            "metadata": metadata or {},
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return path

    def load_stream_points(self, source, activity_id, max_age_seconds=None):
        streams = self.load_stream_bundle(source, activity_id, max_age_seconds=max_age_seconds)
        if streams is None:
            return None

        points = []
        for value in streams.get("latlng", []):
            if isinstance(value, list) and len(value) >= 2:
                points.append((float(value[0]), float(value[1])))
        return points

    def save_stream_points(self, source, activity_id, points, metadata=None):
        latlng = [[float(lat), float(lon)] for lat, lon in points]
        return self.save_stream_bundle(source, activity_id, {"latlng": latlng}, metadata=metadata)

    def _cache_path(self, source, cache_kind, key):
        filename = "{key}.json".format(key=str(key))
        return os.path.join(self.base_path, source, cache_kind, filename)
