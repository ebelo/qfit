from __future__ import annotations

from dataclasses import dataclass


DEFAULT_RENDER_PRESET = "Simple lines"
BY_ACTIVITY_TYPE_PRESET = "By activity type"
HEATMAP_PRESET = "Heatmap"
TRACK_POINTS_PRESET = "Track points"
START_POINTS_PRESET = "Start points"
CLUSTERED_STARTS_PRESET = "Clustered starts"

RENDERER_SIMPLE_LINES = "simple_lines"
RENDERER_CATEGORIZED_LINES = "categorized_lines"
RENDERER_TRACK_POINTS = "track_points"
RENDERER_START_POINTS = "start_points"
RENDERER_CATEGORIZED_POINTS = "categorized_points"
RENDERER_HEATMAP = "heatmap"
RENDERER_CLUSTERISH = "clusterish"
RENDERER_ATLAS_PAGE = "atlas_page"

SOURCE_ROLE_STARTS = "starts"
SOURCE_ROLE_POINTS = "points"


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
    selected_source_role: str | None = None
    activities: LayerRenderPlan | None = None
    starts: LayerRenderPlan | None = None
    points: LayerRenderPlan | None = None
    atlas: LayerRenderPlan | None = LayerRenderPlan(RENDERER_ATLAS_PAGE)


def normalize_render_preset(preset_name: str | None) -> str:
    preset = (preset_name or "").strip()
    return preset or DEFAULT_RENDER_PRESET


def build_render_plan(
    preset_name: str | None,
    *,
    has_start_features: bool = False,
    has_point_features: bool = False,
    has_points_layer: bool = False,
    background_preset_name: str | None = None,
) -> RenderPlan:
    preset = normalize_render_preset(preset_name)

    if preset == HEATMAP_PRESET:
        return _build_heatmap_plan(
            preset,
            has_start_features=has_start_features,
            has_point_features=has_point_features,
            background_preset_name=background_preset_name,
        )

    if preset == TRACK_POINTS_PRESET:
        return RenderPlan(
            preset_name=preset,
            background_preset_name=background_preset_name,
            activities=LayerRenderPlan(RENDERER_SIMPLE_LINES, subtle=True),
            starts=LayerRenderPlan(RENDERER_START_POINTS, subtle=has_points_layer),
            points=LayerRenderPlan(RENDERER_TRACK_POINTS),
        )

    if preset == START_POINTS_PRESET:
        return RenderPlan(
            preset_name=preset,
            background_preset_name=background_preset_name,
            activities=LayerRenderPlan(RENDERER_SIMPLE_LINES),
            starts=LayerRenderPlan(RENDERER_START_POINTS),
            points=LayerRenderPlan(RENDERER_TRACK_POINTS, subtle=True),
        )

    if preset == CLUSTERED_STARTS_PRESET:
        return RenderPlan(
            preset_name=preset,
            background_preset_name=background_preset_name,
            activities=LayerRenderPlan(RENDERER_SIMPLE_LINES),
            starts=LayerRenderPlan(RENDERER_CLUSTERISH),
            points=LayerRenderPlan(RENDERER_TRACK_POINTS, subtle=True),
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


def _build_heatmap_plan(
    preset_name: str,
    *,
    has_start_features: bool,
    has_point_features: bool,
    background_preset_name: str | None,
) -> RenderPlan:
    selected_source_role = SOURCE_ROLE_STARTS
    starts = LayerRenderPlan(RENDERER_HEATMAP)
    points = LayerRenderPlan(RENDERER_TRACK_POINTS, subtle=True, visible=False)

    if has_point_features and not has_start_features:
        selected_source_role = SOURCE_ROLE_POINTS
        starts = LayerRenderPlan(RENDERER_START_POINTS, subtle=True, visible=False)
        points = LayerRenderPlan(RENDERER_HEATMAP)

    return RenderPlan(
        preset_name=preset_name,
        background_preset_name=background_preset_name,
        selected_source_role=selected_source_role,
        activities=LayerRenderPlan(RENDERER_SIMPLE_LINES, subtle=True, visible=False),
        starts=starts,
        points=points,
    )
