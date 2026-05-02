from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class RouteProfilePoint:
    point_index: int
    lat: float
    lon: float
    distance_m: float
    altitude_m: Optional[float] = None


@dataclass
class SavedRoute:
    source: str
    source_route_id: str
    external_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    private: Optional[bool] = None
    starred: Optional[bool] = None
    distance_m: Optional[float] = None
    elevation_gain_m: Optional[float] = None
    estimated_moving_time_s: Optional[int] = None
    route_type: Optional[int] = None
    sub_type: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    summary_polyline: Optional[str] = None
    geometry_source: Optional[str] = None
    geometry_points: List[Tuple[float, float]] = field(default_factory=list)
    profile_points: List[RouteProfilePoint] = field(default_factory=list)
    details_json: Dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> Dict[str, Any]:
        return asdict(self)
