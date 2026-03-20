from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Activity:
    source: str
    source_activity_id: str
    external_id: str | None = None
    name: str | None = None
    activity_type: str | None = None
    sport_type: str | None = None
    start_date: str | None = None
    start_date_local: str | None = None
    timezone: str | None = None
    distance_m: float | None = None
    moving_time_s: int | None = None
    elapsed_time_s: int | None = None
    total_elevation_gain_m: float | None = None
    average_speed_mps: float | None = None
    max_speed_mps: float | None = None
    average_heartrate: float | None = None
    max_heartrate: float | None = None
    average_watts: float | None = None
    kilojoules: float | None = None
    calories: float | None = None
    suffer_score: float | None = None
    start_lat: float | None = None
    start_lon: float | None = None
    end_lat: float | None = None
    end_lon: float | None = None
    summary_polyline: str | None = None
    details_json: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)
