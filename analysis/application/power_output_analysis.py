from __future__ import annotations

from dataclasses import dataclass

from .analysis_models import RunAnalysisRequest, RunAnalysisResult
from .sample_layer_helpers import (
    has_fields,
    is_line_layer,
    layer_features,
    numeric_value,
    sample_group_key,
    sample_value,
    sample_xy,
)

POWER_OUTPUT_MODE = "Power output lines"


@dataclass(frozen=True)
class PowerOutputClass:
    """One deterministic watts class for activity power visualization."""

    key: str
    label: str
    color_hex: str
    min_watts: float | None = None
    max_watts: float | None = None


POWER_OUTPUT_CLASSES: tuple[PowerOutputClass, ...] = (
    PowerOutputClass(
        key="recovery",
        label="Recovery (< 100 W)",
        color_hex="#2c7fb8",
        max_watts=100.0,
    ),
    PowerOutputClass(
        key="endurance",
        label="Endurance (100 W to 180 W)",
        color_hex="#1a9850",
        min_watts=100.0,
        max_watts=180.0,
    ),
    PowerOutputClass(
        key="tempo",
        label="Tempo (180 W to 260 W)",
        color_hex="#fee08b",
        min_watts=180.0,
        max_watts=260.0,
    ),
    PowerOutputClass(
        key="threshold",
        label="Threshold (260 W to 340 W)",
        color_hex="#f46d43",
        min_watts=260.0,
        max_watts=340.0,
    ),
    PowerOutputClass(
        key="anaerobic",
        label="Anaerobic (>= 340 W)",
        color_hex="#d73027",
        min_watts=340.0,
    ),
)


@dataclass(frozen=True)
class PowerOutputLayerPlan:
    """Eligibility plan for one line layer targeted by power analysis."""

    key: str
    label: str
    layer: object = None
    enabled: bool = False
    source_fields: tuple[str, ...] = ()
    blocked_reason: str = ""


@dataclass(frozen=True)
class PowerOutputSegment:
    """Pure per-distance segment classification for power-output styling."""

    start_distance_m: float
    end_distance_m: float
    watts: float
    power_class: PowerOutputClass


@dataclass(frozen=True)
class PowerOutputLineSegment:
    """Render-ready power-output line segment derived from adjacent samples."""

    layer_key: str
    layer_label: str
    source: object
    source_id: object
    start_xy: tuple[float, float]
    end_xy: tuple[float, float]
    start_distance_m: float
    end_distance_m: float
    watts: float
    power_class: PowerOutputClass


@dataclass(frozen=True)
class PowerOutputAnalysisPlan:
    """Render-neutral plan for activity power-output line analysis."""

    layers: tuple[PowerOutputLayerPlan, ...]
    power_classes: tuple[PowerOutputClass, ...] = POWER_OUTPUT_CLASSES

    @property
    def enabled_layers(self) -> tuple[PowerOutputLayerPlan, ...]:
        return tuple(layer for layer in self.layers if layer.enabled)


@dataclass(frozen=True)
class PowerOutputLayerResult:
    """Classified segment result for one power-output target layer."""

    key: str
    label: str
    segments: tuple[PowerOutputSegment, ...] = ()

    @property
    def segment_count(self) -> int:
        return len(self.segments)


@dataclass(frozen=True)
class PowerOutputAnalysisResult:
    """Render-neutral power-output result for eligible line layers."""

    plan: PowerOutputAnalysisPlan
    layers: tuple[PowerOutputLayerResult, ...] = ()

    @property
    def segment_count(self) -> int:
        return sum(layer.segment_count for layer in self.layers)


POWER_OUTPUT_LEGEND = tuple(
    power_class.label for power_class in POWER_OUTPUT_CLASSES
)

ACTIVITY_TRACKS_LABEL = "activity tracks"
_ACTIVITY_POINT_POWER_FIELDS = ("watts", "stream_distance_m")
_IGNORED_ROUTE_LAYER_KWARGS = frozenset(
    ("route_tracks_layer", "route_points_layer", "route_profile_samples_layer")
)


def build_power_output_analysis_plan(
    *,
    activities_layer=None,
    points_layer=None,
    **route_layers,
) -> PowerOutputAnalysisPlan:
    """Build a pure eligibility plan for power-output line styling."""

    _ignore_route_layer_kwargs(route_layers)
    return PowerOutputAnalysisPlan(
        layers=(_activity_track_plan(activities_layer, points_layer),)
    )


def run_power_output_analysis(
    request: RunAnalysisRequest,
) -> RunAnalysisResult:
    """Return clear feedback for power-output line-analysis execution."""

    result = build_power_output_analysis_result(
        activities_layer=request.activities_layer,
        points_layer=request.points_layer,
    )
    layer, _line_segments = _build_power_output_layer(request)
    return RunAnalysisResult(
        status=build_power_output_status(result),
        layer=layer,
    )


def _build_power_output_layer(request: RunAnalysisRequest):
    try:
        from ..infrastructure.power_output_layer import (
            build_power_output_layer,
        )
    except ImportError:
        return None, ()

    return build_power_output_layer(
        activities_layer=request.activities_layer,
        points_layer=request.points_layer,
    )


def build_power_output_analysis_result(
    *,
    activities_layer=None,
    points_layer=None,
    **route_layers,
) -> PowerOutputAnalysisResult:
    """Classify activity power-output segments."""

    _ignore_route_layer_kwargs(route_layers)
    plan = build_power_output_analysis_plan(
        activities_layer=activities_layer,
        points_layer=points_layer,
    )
    layer_results = []
    for layer_plan in plan.enabled_layers:
        if layer_plan.key == "activity_tracks":
            segments = build_activity_power_output_segments(points_layer)
        else:
            raise ValueError(
                "Unsupported power-output layer key: {key}".format(
                    key=layer_plan.key
                )
            )
        layer_results.append(
            PowerOutputLayerResult(
                key=layer_plan.key,
                label=layer_plan.label,
                segments=segments,
            )
        )
    return PowerOutputAnalysisResult(plan=plan, layers=tuple(layer_results))


def build_power_output_status(result_or_plan) -> str:
    """Summarize which line layers can be styled by power-output analysis."""

    if isinstance(result_or_plan, PowerOutputAnalysisResult):
        return _build_power_output_result_status(result_or_plan)

    plan = result_or_plan
    enabled = plan.enabled_layers
    if enabled:
        labels = ", ".join(layer.label for layer in enabled)
        return f"Power output line analysis ready for {labels}."

    reasons = tuple(
        layer.blocked_reason
        for layer in plan.layers
        if layer.blocked_reason
    )
    if reasons:
        return "Power output line analysis unchanged: " + "; ".join(reasons)
    return (
        "Power output line analysis unchanged: no eligible line layers found."
    )


def _build_power_output_result_status(
    result: PowerOutputAnalysisResult,
) -> str:
    if result.layers and result.segment_count > 0:
        classified_layers = tuple(
            layer for layer in result.layers if layer.segment_count > 0
        )
        summaries = ", ".join(
            "{label} ({count} {segment_word})".format(
                label=layer.label,
                count=layer.segment_count,
                segment_word=(
                    "segment" if layer.segment_count == 1 else "segments"
                ),
            )
            for layer in classified_layers
        )
        return f"Power output line analysis classified {summaries}."

    if result.plan.enabled_layers:
        labels = ", ".join(layer.label for layer in result.plan.enabled_layers)
        return (
            "Power output line analysis found eligible {labels}, but no power "
            "segments could be classified."
        ).format(labels=labels)

    return build_power_output_status(result.plan)


def power_output_class_for_watts(watts: float) -> PowerOutputClass:
    """Return the deterministic legend class for a watts value."""

    for power_class in POWER_OUTPUT_CLASSES:
        if _power_class_contains(power_class, watts):
            return power_class
    return POWER_OUTPUT_CLASSES[-1]


def build_power_output_segments(
    samples,
    *,
    distance_field: str = "stream_distance_m",
    watts_field: str = "watts",
) -> tuple[PowerOutputSegment, ...]:
    """Build deterministic power-output segments from ordered sample rows."""

    normalized = tuple(
        _normalize_power_output_sample(sample, distance_field, watts_field)
        for sample in samples
    )
    segments: list[PowerOutputSegment] = []
    previous = None
    for current in normalized:
        if current is None:
            continue
        if previous is None:
            previous = current
            continue
        start_distance, _start_watts = previous
        end_distance, watts = current
        if end_distance - start_distance <= 0:
            continue
        segments.append(
            PowerOutputSegment(
                start_distance_m=start_distance,
                end_distance_m=end_distance,
                watts=watts,
                power_class=power_output_class_for_watts(watts),
            )
        )
        previous = current
    return tuple(segments)


def build_activity_power_output_segments(
    points_layer,
) -> tuple[PowerOutputSegment, ...]:
    """Build activity power-output segments from a point-sample layer."""

    groups = _group_activity_samples(points_layer)
    segments: list[PowerOutputSegment] = []
    for group_samples in groups.values():
        segments.extend(build_power_output_segments(group_samples))
    return tuple(segments)


def build_activity_power_output_line_segments(
    points_layer,
) -> tuple[PowerOutputLineSegment, ...]:
    """Build render-ready activity line segments from point samples."""

    groups = _group_activity_samples(points_layer)
    line_segments: list[PowerOutputLineSegment] = []
    for group_samples in groups.values():
        line_segments.extend(_build_power_output_line_segments(group_samples))
    return tuple(line_segments)


def _build_power_output_line_segments(
    samples,
) -> tuple[PowerOutputLineSegment, ...]:
    normalized = tuple(
        _normalize_power_output_line_sample(sample)
        for sample in samples
    )
    line_segments: list[PowerOutputLineSegment] = []
    previous = None
    for sample, current in zip(samples, normalized):
        if current is None:
            continue
        if previous is None:
            previous = current
            continue

        start_distance, _start_watts, start_xy = previous
        end_distance, watts, end_xy = current
        if end_distance - start_distance <= 0:
            continue

        line_segments.append(
            PowerOutputLineSegment(
                layer_key="activity_tracks",
                layer_label=ACTIVITY_TRACKS_LABEL,
                source=sample_value(sample, "source"),
                source_id=sample_value(
                    sample,
                    "source_activity_id",
                ),
                start_xy=start_xy,
                end_xy=end_xy,
                start_distance_m=start_distance,
                end_distance_m=end_distance,
                watts=watts,
                power_class=power_output_class_for_watts(watts),
            )
        )
        previous = current
    return tuple(line_segments)


def _group_activity_samples(
    points_layer,
) -> dict[tuple[object, ...], list[object]]:
    groups: dict[tuple[object, ...], list[object]] = {}
    for sample in layer_features(points_layer):
        key = sample_group_key(
            sample,
            (("source", "source_activity_id"),),
        )
        groups.setdefault(key, []).append(sample)
    return groups


def _normalize_power_output_sample(sample, distance_field, watts_field):
    distance = numeric_value(sample_value(sample, distance_field))
    watts = numeric_value(sample_value(sample, watts_field))
    if distance is None or watts is None or watts < 0:
        return None
    return distance, watts


def _normalize_power_output_line_sample(sample):
    normalized = _normalize_power_output_sample(
        sample,
        "stream_distance_m",
        "watts",
    )
    if normalized is None:
        return None
    xy = sample_xy(sample)
    if xy is None:
        return None
    distance, watts = normalized
    return distance, watts, xy


def _power_class_contains(power_class: PowerOutputClass, watts: float) -> bool:
    if power_class.min_watts is not None and watts < power_class.min_watts:
        return False
    if power_class.max_watts is not None and watts >= power_class.max_watts:
        return False
    return True


def _activity_track_plan(
    activities_layer,
    points_layer,
) -> PowerOutputLayerPlan:
    if activities_layer is None:
        return PowerOutputLayerPlan(
            key="activity_tracks",
            label=ACTIVITY_TRACKS_LABEL,
            blocked_reason="activity track lines are not loaded",
        )
    if not is_line_layer(activities_layer):
        return PowerOutputLayerPlan(
            key="activity_tracks",
            label=ACTIVITY_TRACKS_LABEL,
            layer=activities_layer,
            blocked_reason="activity track target is not a line layer",
        )
    has_power_fields = has_fields(
        points_layer,
        _ACTIVITY_POINT_POWER_FIELDS,
    )
    if not has_power_fields:
        return PowerOutputLayerPlan(
            key="activity_tracks",
            label=ACTIVITY_TRACKS_LABEL,
            layer=activities_layer,
            blocked_reason=(
                "activity tracks need point samples with watts and "
                "stream_distance_m"
            ),
        )
    return PowerOutputLayerPlan(
        key="activity_tracks",
        label=ACTIVITY_TRACKS_LABEL,
        layer=activities_layer,
        enabled=True,
        source_fields=_ACTIVITY_POINT_POWER_FIELDS,
    )


def _ignore_route_layer_kwargs(route_layers):
    unexpected = set(route_layers) - _IGNORED_ROUTE_LAYER_KWARGS
    if unexpected:
        unexpected_names = ", ".join(sorted(unexpected))
        raise TypeError(
            f"Unexpected power-output layer kwargs: {unexpected_names}"
        )


__all__ = [
    "POWER_OUTPUT_CLASSES",
    "POWER_OUTPUT_LEGEND",
    "POWER_OUTPUT_MODE",
    "PowerOutputAnalysisPlan",
    "PowerOutputAnalysisResult",
    "PowerOutputClass",
    "PowerOutputLayerPlan",
    "PowerOutputLayerResult",
    "PowerOutputLineSegment",
    "PowerOutputSegment",
    "build_activity_power_output_line_segments",
    "build_activity_power_output_segments",
    "build_power_output_analysis_result",
    "build_power_output_analysis_plan",
    "build_power_output_segments",
    "build_power_output_status",
    "power_output_class_for_watts",
    "run_power_output_analysis",
]
