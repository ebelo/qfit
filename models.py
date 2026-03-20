from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Activity:
    source: str
    source_activity_id: str
    external_id: Optional[str] = None
    name: Optional[str] = None
    activity_type: Optional[str] = None
    sport_type: Optional[str] = None
    start_date: Optional[str] = None
    start_date_local: Optional[str] = None
    timezone: Optional[str] = None
    distance_m: Optional[float] = None
    moving_time_s: Optional[int] = None
    elapsed_time_s: Optional[int] = None
    total_elevation_gain_m: Optional[float] = None
    average_speed_mps: Optional[float] = None
    max_speed_mps: Optional[float] = None
    average_heartrate: Optional[float] = None
    max_heartrate: Optional[float] = None
    average_watts: Optional[float] = None
    kilojoules: Optional[float] = None
    calories: Optional[float] = None
    suffer_score: Optional[float] = None
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None
    summary_polyline: Optional[str] = None
    details_json: Dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> Dict[str, Any]:
        return asdict(self)
