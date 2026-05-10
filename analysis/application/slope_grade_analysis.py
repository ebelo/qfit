from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .analysis_models import RunAnalysisRequest, RunAnalysisResult

SLOPE_GRADE_MODE = "Slope grade lines"


@dataclass(frozen=True)
class SlopeGradeClass:
    """One deterministic percent-grade class for line slope visualization.

    The blue → neutral → warm ramp uses percent-grade breakpoints. Keeping
    -3%..+3% visually neutral prevents rolling terrain from reading as climb or
    descent noise. ``min_percent`` is inclusive; ``max_percent`` is exclusive
    unless it is ``None``.
    """

    key: str
    label: str
    color_hex: str
    min_percent: float | None = None
    max_percent: float | None = None


SLOPE_GRADE_CLASSES: tuple[SlopeGradeClass, ...] = (
    SlopeGradeClass(
        key="steep_descent",
        label="Steep descent (< -8%)",
        color_hex="#2c7fb8",
        max_percent=-8.0,
    ),
    SlopeGradeClass(
        key="descent",
        label="Descent (-8% to -3%)",
        color_hex="#7fcdbb",
        min_percent=-8.0,
        max_percent=-3.0,
    ),
    SlopeGradeClass(
        key="flat",
        label="Flat / rolling (-3% to +3%)",
        color_hex="#f0f0f0",
        min_percent=-3.0,
        max_percent=3.0,
    ),
    SlopeGradeClass(
        key="climb",
        label="Climb (+3% to +8%)",
        color_hex="#fdae61",
        min_percent=3.0,
        max_percent=8.0,
    ),
    SlopeGradeClass(
        key="steep_climb",
        label="Steep climb (≥ +8%)",
        color_hex="#d7191c",
        min_percent=8.0,
    ),
)


@dataclass(frozen=True)
class SlopeGradeLayerPlan:
    """Eligibility plan for one line layer targeted by slope-grade analysis."""

    key: str
    label: str
    layer: object = None
    enabled: bool = False
    source_fields: tuple[str, ...] = ()
    blocked_reason: str = ""


@dataclass(frozen=True)
class SlopeGradeSegment:
    """Pure per-distance segment classification for slope-grade styling."""

    start_distance_m: float
    end_distance_m: float
    grade_percent: float
    grade_class: SlopeGradeClass


@dataclass(frozen=True)
class SlopeGradeAnalysisPlan:
    """Render-neutral plan for #815 slope-grade line analysis."""

    layers: tuple[SlopeGradeLayerPlan, ...]
    grade_classes: tuple[SlopeGradeClass, ...] = SLOPE_GRADE_CLASSES

    @property
    def enabled_layers(self) -> tuple[SlopeGradeLayerPlan, ...]:
        return tuple(layer for layer in self.layers if layer.enabled)


@dataclass(frozen=True)
class SlopeGradeLayerResult:
    """Classified segment result for one slope-grade target layer."""

    key: str
    label: str
    segments: tuple[SlopeGradeSegment, ...] = ()

    @property
    def segment_count(self) -> int:
        return len(self.segments)


@dataclass(frozen=True)
class SlopeGradeAnalysisResult:
    """Render-neutral slope-grade execution result for eligible line layers."""

    plan: SlopeGradeAnalysisPlan
    layers: tuple[SlopeGradeLayerResult, ...] = ()

    @property
    def segment_count(self) -> int:
        return sum(layer.segment_count for layer in self.layers)


SLOPE_GRADE_LEGEND = tuple(grade_class.label for grade_class in SLOPE_GRADE_CLASSES)


ACTIVITY_TRACKS_LABEL = "activity tracks"
SAVED_ROUTE_TRACKS_LABEL = "saved route tracks"
_ACTIVITY_POINT_GRADE_FIELDS = ("grade_smooth_pct", "stream_distance_m")
_ROUTE_ELEVATION_SAMPLE_FIELDS = ("distance_m", "altitude_m")
_LINE_GEOMETRY_TYPE = 1
_LINE_WKB_TYPES = frozenset((2, 5))


def build_slope_grade_analysis_plan(
    *,
    activities_layer=None,
    points_layer=None,
    route_tracks_layer=None,
    route_points_layer=None,
    route_profile_samples_layer=None,
) -> SlopeGradeAnalysisPlan:
    """Build a pure eligibility plan for slope-grade line styling.

    The first #815 slice keeps the QGIS-facing styling work behind this
    render-neutral contract. It deliberately targets only the loaded activity
    track and saved-route track line layers, and documents why a target remains
    unchanged when the companion elevation/distance samples are unavailable.
    """

    return SlopeGradeAnalysisPlan(
        layers=(
            _activity_track_plan(activities_layer, points_layer),
            _route_track_plan(
                route_tracks_layer,
                route_profile_samples_layer or route_points_layer,
            ),
        )
    )


def run_slope_grade_analysis(request: RunAnalysisRequest) -> RunAnalysisResult:
    """Return clear feedback for slope-grade line-analysis eligibility."""

    result = build_slope_grade_analysis_result(
        activities_layer=request.activities_layer,
        points_layer=request.points_layer,
        route_tracks_layer=request.route_tracks_layer,
        route_points_layer=request.route_points_layer,
        route_profile_samples_layer=request.route_profile_samples_layer,
    )
    return RunAnalysisResult(status=build_slope_grade_status(result), layer=None)


def build_slope_grade_analysis_result(
    *,
    activities_layer=None,
    points_layer=None,
    route_tracks_layer=None,
    route_points_layer=None,
    route_profile_samples_layer=None,
) -> SlopeGradeAnalysisResult:
    """Classify slope-grade segments for eligible line-layer targets."""

    plan = build_slope_grade_analysis_plan(
        activities_layer=activities_layer,
        points_layer=points_layer,
        route_tracks_layer=route_tracks_layer,
        route_points_layer=route_points_layer,
        route_profile_samples_layer=route_profile_samples_layer,
    )
    layer_results = []
    for layer_plan in plan.enabled_layers:
        if layer_plan.key == "activity_tracks":
            segments = build_activity_slope_grade_segments(points_layer)
        elif layer_plan.key == "saved_route_tracks":
            segments = build_route_slope_grade_segments(
                route_profile_samples_layer or route_points_layer
            )
        else:
            segments = ()
        layer_results.append(
            SlopeGradeLayerResult(
                key=layer_plan.key,
                label=layer_plan.label,
                segments=segments,
            )
        )
    return SlopeGradeAnalysisResult(plan=plan, layers=tuple(layer_results))


def build_slope_grade_status(result_or_plan) -> str:
    """Summarize which line layers can be styled by slope-grade analysis."""

    if isinstance(result_or_plan, SlopeGradeAnalysisResult):
        return _build_slope_grade_result_status(result_or_plan)

    plan = result_or_plan
    enabled = plan.enabled_layers
    if enabled:
        labels = ", ".join(layer.label for layer in enabled)
        return f"Slope grade line analysis ready for {labels}."

    reasons = tuple(
        layer.blocked_reason
        for layer in plan.layers
        if layer.blocked_reason
    )
    if reasons:
        return "Slope grade line analysis unchanged: " + "; ".join(reasons)
    return "Slope grade line analysis unchanged: no eligible line layers found."


def _build_slope_grade_result_status(result: SlopeGradeAnalysisResult) -> str:
    if result.layers and result.segment_count > 0:
        summaries = ", ".join(
            "{label} ({count} {segment_word})".format(
                label=layer.label,
                count=layer.segment_count,
                segment_word="segment" if layer.segment_count == 1 else "segments",
            )
            for layer in result.layers
        )
        return f"Slope grade line analysis classified {summaries}."

    if result.plan.enabled_layers:
        labels = ", ".join(layer.label for layer in result.plan.enabled_layers)
        return (
            "Slope grade line analysis found eligible {labels}, but no grade "
            "segments could be classified."
        ).format(labels=labels)

    return build_slope_grade_status(result.plan)


def slope_grade_class_for_percent(grade_percent: float) -> SlopeGradeClass:
    """Return the deterministic legend class for a percent-grade value."""

    for grade_class in SLOPE_GRADE_CLASSES:
        if _grade_class_contains(grade_class, grade_percent):
            return grade_class
    return SLOPE_GRADE_CLASSES[-1]


def build_slope_grade_segments(
    samples: Iterable[object],
    *,
    distance_field: str = "distance_m",
    elevation_field: str | None = "altitude_m",
    grade_field: str | None = None,
) -> tuple[SlopeGradeSegment, ...]:
    """Build deterministic slope-grade segments from ordered sample rows.

    Activity samples can pass ``grade_field`` to reuse an existing smoothed
    grade, while saved-route samples can pass elevation/distance fields so the
    segment grade is computed from the elevation delta. Non-numeric or
    non-forward samples are skipped rather than aborting the whole analysis.
    """

    normalized = tuple(
        _normalize_slope_grade_sample(
            sample,
            distance_field,
            elevation_field,
            grade_field,
        )
        for sample in samples
    )
    segments: list[SlopeGradeSegment] = []
    previous = None
    for current in normalized:
        if current is None:
            continue
        if previous is None:
            previous = current
            continue
        start_distance, start_elevation, _start_grade = previous
        end_distance, end_elevation, end_grade = current
        distance_delta = end_distance - start_distance
        if distance_delta <= 0:
            continue
        grade_percent = end_grade
        if grade_percent is None:
            if start_elevation is None:
                previous = current
                continue
            if end_elevation is None:
                continue
            grade_percent = (
                (end_elevation - start_elevation) / distance_delta
            ) * 100.0
        segments.append(
            SlopeGradeSegment(
                start_distance_m=start_distance,
                end_distance_m=end_distance,
                grade_percent=grade_percent,
                grade_class=slope_grade_class_for_percent(grade_percent),
            )
        )
        previous = current
    return tuple(segments)


def build_activity_slope_grade_segments(points_layer) -> tuple[SlopeGradeSegment, ...]:
    """Build activity slope-grade segments from a point-sample layer."""

    return _build_grouped_slope_grade_segments(
        _layer_features(points_layer),
        group_field_sets=(("source", "source_activity_id"),),
        distance_field="stream_distance_m",
        elevation_field=None,
        grade_field="grade_smooth_pct",
    )


def build_route_slope_grade_segments(sample_layer) -> tuple[SlopeGradeSegment, ...]:
    """Build saved-route slope-grade segments from route profile samples."""

    return _build_grouped_slope_grade_segments(
        _layer_features(sample_layer),
        group_field_sets=(("sample_group_index",), ("source", "source_route_id")),
        distance_field="distance_m",
        elevation_field="altitude_m",
    )


def _build_grouped_slope_grade_segments(
    samples,
    *,
    group_field_sets,
    distance_field,
    elevation_field,
    grade_field=None,
):
    groups: dict[tuple[object, ...], list[object]] = {}
    for sample in samples:
        key = _sample_group_key(sample, group_field_sets)
        groups.setdefault(key, []).append(sample)

    segments: list[SlopeGradeSegment] = []
    for group_samples in groups.values():
        segments.extend(
            build_slope_grade_segments(
                group_samples,
                distance_field=distance_field,
                elevation_field=elevation_field,
                grade_field=grade_field,
            )
        )
    return tuple(segments)


def _grade_class_contains(grade_class: SlopeGradeClass, grade_percent: float) -> bool:
    if (
        grade_class.min_percent is not None
        and grade_percent < grade_class.min_percent
    ):
        return False
    if (
        grade_class.max_percent is not None
        and grade_percent >= grade_class.max_percent
    ):
        return False
    return True


def _normalize_slope_grade_sample(sample, distance_field, elevation_field, grade_field):
    distance = _numeric_value(_sample_value(sample, distance_field))
    if distance is None:
        return None
    elevation = None
    if elevation_field:
        elevation = _numeric_value(_sample_value(sample, elevation_field))
    grade = None
    if grade_field:
        grade = _numeric_value(_sample_value(sample, grade_field))
    return distance, elevation, grade


def _layer_features(layer):
    if layer is None:
        return ()
    features = getattr(layer, "getFeatures", None)
    if not callable(features):
        return ()
    return features()


def _sample_group_key(sample, group_field_sets):
    for group_fields in group_field_sets:
        values = tuple(_sample_value(sample, field_name) for field_name in group_fields)
        if any(value not in (None, "") for value in values):
            return values
    return (None,)


def _sample_value(sample, field_name):
    if isinstance(sample, dict):
        return sample.get(field_name)
    try:
        return sample[field_name]
    except (KeyError, IndexError, TypeError, AttributeError):
        pass
    value = getattr(sample, field_name, None)
    if callable(value):
        return value()
    return value


def _numeric_value(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _activity_track_plan(activities_layer, points_layer) -> SlopeGradeLayerPlan:
    if activities_layer is None:
        return SlopeGradeLayerPlan(
            key="activity_tracks",
            label=ACTIVITY_TRACKS_LABEL,
            blocked_reason="activity track lines are not loaded",
        )
    if not _is_line_layer(activities_layer):
        return SlopeGradeLayerPlan(
            key="activity_tracks",
            label=ACTIVITY_TRACKS_LABEL,
            layer=activities_layer,
            blocked_reason="activity track target is not a line layer",
        )
    if not _has_fields(points_layer, _ACTIVITY_POINT_GRADE_FIELDS):
        return SlopeGradeLayerPlan(
            key="activity_tracks",
            label=ACTIVITY_TRACKS_LABEL,
            layer=activities_layer,
            blocked_reason=(
                "activity tracks need point samples with grade_smooth_pct and "
                "stream_distance_m"
            ),
        )
    return SlopeGradeLayerPlan(
        key="activity_tracks",
        label=ACTIVITY_TRACKS_LABEL,
        layer=activities_layer,
        enabled=True,
        source_fields=_ACTIVITY_POINT_GRADE_FIELDS,
    )


def _route_track_plan(route_tracks_layer, sample_layer) -> SlopeGradeLayerPlan:
    if route_tracks_layer is None:
        return SlopeGradeLayerPlan(
            key="saved_route_tracks",
            label=SAVED_ROUTE_TRACKS_LABEL,
            blocked_reason="saved route track lines are not loaded",
        )
    if not _is_line_layer(route_tracks_layer):
        return SlopeGradeLayerPlan(
            key="saved_route_tracks",
            label=SAVED_ROUTE_TRACKS_LABEL,
            layer=route_tracks_layer,
            blocked_reason="saved route target is not a line layer",
        )
    if not _has_fields(sample_layer, _ROUTE_ELEVATION_SAMPLE_FIELDS):
        return SlopeGradeLayerPlan(
            key="saved_route_tracks",
            label=SAVED_ROUTE_TRACKS_LABEL,
            layer=route_tracks_layer,
            blocked_reason=(
                "saved routes need profile or route point samples with "
                "distance_m and altitude_m"
            ),
        )
    return SlopeGradeLayerPlan(
        key="saved_route_tracks",
        label=SAVED_ROUTE_TRACKS_LABEL,
        layer=route_tracks_layer,
        enabled=True,
        source_fields=_ROUTE_ELEVATION_SAMPLE_FIELDS,
    )


def _has_fields(layer, expected: Iterable[str]) -> bool:
    field_names = _field_names(layer)
    return all(field_name in field_names for field_name in expected)


def _field_names(layer) -> frozenset[str]:
    if layer is None:
        return frozenset()
    fields = layer.fields() if callable(getattr(layer, "fields", None)) else ()
    names: list[str] = []
    for field in fields or ():
        name = field.name() if callable(getattr(field, "name", None)) else field
        if name:
            names.append(str(name))
    return frozenset(names)


def _is_line_layer(layer) -> bool:
    geometry_type = _call_if_present(layer, "geometryType")
    if _looks_like_line_geometry_type(geometry_type):
        return True
    wkb_type = _call_if_present(layer, "wkbType")
    return _looks_like_line_wkb_type(wkb_type)


def _call_if_present(obj, attr: str):
    method = getattr(obj, attr, None)
    if callable(method):
        return method()
    return None


def _looks_like_line_geometry_type(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        lowered = value.lower()
        return "line" in lowered and "polygon" not in lowered
    # QgsWkbTypes.LineGeometry is 1 in QGIS, but keep this module QGIS-free.
    return value == _LINE_GEOMETRY_TYPE


def _looks_like_line_wkb_type(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        lowered = value.lower()
        return "line" in lowered and "polygon" not in lowered
    # Common QgsWkbTypes values: LineString=2 and MultiLineString=5.
    return value in _LINE_WKB_TYPES


__all__ = [
    "SLOPE_GRADE_CLASSES",
    "SLOPE_GRADE_LEGEND",
    "SLOPE_GRADE_MODE",
    "SlopeGradeAnalysisPlan",
    "SlopeGradeAnalysisResult",
    "SlopeGradeClass",
    "SlopeGradeLayerPlan",
    "SlopeGradeLayerResult",
    "SlopeGradeSegment",
    "build_activity_slope_grade_segments",
    "build_slope_grade_analysis_result",
    "build_slope_grade_analysis_plan",
    "build_slope_grade_segments",
    "build_slope_grade_status",
    "build_route_slope_grade_segments",
    "run_slope_grade_analysis",
    "slope_grade_class_for_percent",
]
