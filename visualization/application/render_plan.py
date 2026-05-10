from __future__ import annotations

from dataclasses import dataclass


DEFAULT_RENDER_PRESET = "Simple lines"
BY_ACTIVITY_TYPE_PRESET = "By activity type"
TRACK_POINTS_PRESET = "Track points"
REMOVED_ANALYSIS_PRESETS = frozenset({"Heatmap", "Start points", "Clustered starts"})

RENDERER_SIMPLE_LINES = "simple_lines"
RENDERER_CATEGORIZED_LINES = "categorized_lines"
RENDERER_TRACK_POINTS = "track_points"
RENDERER_START_POINTS = "start_points"
RENDERER_CATEGORIZED_POINTS = "categorized_points"
RENDERER_ATLAS_PAGE = "atlas_page"


@dataclass(frozen=True)
class LayerRenderPlan:
    renderer_family: str
    visible: bool = True
    subtle: bool = False
    size: str | None = None


@dataclass(frozen=True)
class RenderPlan:
    preset_name: str
    background_preset_name: str | None = None
    activities: LayerRenderPlan | None = None
    starts: LayerRenderPlan | None = None
    points: LayerRenderPlan | None = None
    atlas: LayerRenderPlan | None = LayerRenderPlan(RENDERER_ATLAS_PAGE)


def normalize_render_preset(preset_name: str | None) -> str:
    preset = (preset_name or "").strip()
    if preset in REMOVED_ANALYSIS_PRESETS:
        return DEFAULT_RENDER_PRESET
    return preset or DEFAULT_RENDER_PRESET


def build_render_plan(
    preset_name: str | None,
    *,
    has_points_layer: bool = False,
    background_preset_name: str | None = None,
    **legacy_feature_flags,
) -> RenderPlan:
    preset = normalize_render_preset(preset_name)
    has_points_layer = has_points_layer or bool(
        legacy_feature_flags.get("has_point_features")
    )

    if preset == TRACK_POINTS_PRESET:
        return RenderPlan(
            preset_name=preset,
            background_preset_name=background_preset_name,
            activities=LayerRenderPlan(RENDERER_SIMPLE_LINES, subtle=True),
            starts=LayerRenderPlan(RENDERER_START_POINTS, subtle=has_points_layer),
            points=LayerRenderPlan(RENDERER_TRACK_POINTS),
        )

    if preset == BY_ACTIVITY_TYPE_PRESET:
        return RenderPlan(
            preset_name=preset,
            background_preset_name=background_preset_name,
            activities=LayerRenderPlan(RENDERER_CATEGORIZED_LINES),
            starts=LayerRenderPlan(RENDERER_CATEGORIZED_POINTS, size="3.0"),
            points=LayerRenderPlan(RENDERER_CATEGORIZED_POINTS),
        )

    return RenderPlan(
        preset_name=preset,
        background_preset_name=background_preset_name,
        activities=LayerRenderPlan(RENDERER_SIMPLE_LINES),
        starts=LayerRenderPlan(RENDERER_START_POINTS, subtle=has_points_layer),
        points=LayerRenderPlan(RENDERER_TRACK_POINTS, subtle=True),
    )
