from __future__ import annotations

from typing import Callable

ACTIVITY_LAYER_NAME = "qfit activities"
POINTS_LAYER_NAME = "qfit activity points"
STARTS_LAYER_NAME = "qfit activity starts"


def export_cover_page(
    atlas_layer,
    output_path: str,
    *,
    project=None,
    get_project_instance: Callable[[], object],
    build_cover_data: Callable[[object], dict],
    apply_cover_heatmap_renderer: Callable[[object], None],
    build_cover_layout_fn: Callable[..., object | None],
    layout_exporter_cls,
    logger,
) -> str | None:
    """Export a single cover-page PDF and return its path, or None on failure."""
    saved_state: list[dict] = []
    try:
        proj = project or get_project_instance()

        cover_data = build_cover_data(atlas_layer)
        if not cover_data:
            return None

        cover_map_layers = _build_cover_map_layers(
            proj=proj,
            atlas_layer=atlas_layer,
            cover_data=cover_data,
            apply_cover_heatmap_renderer=apply_cover_heatmap_renderer,
            saved_state=saved_state,
        )

        cover_layout = build_cover_layout_fn(
            atlas_layer,
            project=project,
            map_layers=cover_map_layers,
            cover_data=cover_data,
        )
        if cover_layout is None:
            return None

        cover_path = f"{output_path}.cover.pdf"
        exporter = layout_exporter_cls(cover_layout)
        settings = _build_pdf_export_settings(layout_exporter_cls)
        result = exporter.exportToPdf(cover_path, settings)
        if result != layout_exporter_cls.Success:
            return None
        return cover_path
    except (RuntimeError, OSError):
        logger.exception("Cover page export failed")
        return None
    finally:
        _restore_layer_state(saved_state)



def export_toc_page(
    atlas_layer,
    output_path: str,
    *,
    project=None,
    build_toc_layout_fn: Callable[..., object | None],
    layout_exporter_cls,
    logger,
) -> str | None:
    """Export a single TOC PDF and return its path, or None on failure."""
    try:
        toc_layout = build_toc_layout_fn(atlas_layer, project=project)
        if toc_layout is None:
            return None

        toc_path = f"{output_path}.toc.pdf"
        exporter = layout_exporter_cls(toc_layout)
        settings = _build_pdf_export_settings(layout_exporter_cls)
        result = exporter.exportToPdf(toc_path, settings)
        if result != layout_exporter_cls.Success:
            return None
        return toc_path
    except (RuntimeError, OSError):
        logger.exception("TOC page export failed")
        return None



def _build_cover_map_layers(
    *,
    proj,
    atlas_layer,
    cover_data: dict,
    apply_cover_heatmap_renderer: Callable[[object], None],
    saved_state: list[dict],
):
    extent_bounds = (
        cover_data.get("_cover_extent_xmin"),
        cover_data.get("_cover_extent_ymin"),
        cover_data.get("_cover_extent_xmax"),
        cover_data.get("_cover_extent_ymax"),
    )
    has_extent = all(value is not None for value in extent_bounds)
    if not has_extent:
        return None

    try:
        root = proj.layerTreeRoot()
        visible_layers = [
            node.layer()
            for node in root.findLayers()
            if node.isVisible()
            and node.layer() is not None
            and node.layer() is not atlas_layer
        ]
    except (RuntimeError, AttributeError, TypeError):
        visible_layers = []

    if not visible_layers:
        return None

    activities_layer = None
    points_layer = None
    starts_layer = None
    background_layers: list = []
    for layer in visible_layers:
        try:
            name = layer.name()
        except (RuntimeError, AttributeError):
            continue
        if name == ACTIVITY_LAYER_NAME:
            activities_layer = layer
        elif name == POINTS_LAYER_NAME:
            points_layer = layer
        elif name == STARTS_LAYER_NAME:
            starts_layer = layer
        else:
            background_layers.append(layer)

    activity_ids = cover_data.get("_atlas_activity_ids", [])
    if activities_layer is not None and _layer_has_field(activities_layer, "source_activity_id"):
        _save_layer_state(saved_state, activities_layer)
        _filter_layer_to_activity_ids(activities_layer, activity_ids)
        _apply_activity_route_render_order(activities_layer)
        return [activities_layer] + background_layers

    heatmap_target = points_layer or starts_layer
    if heatmap_target is None:
        return None

    _save_layer_state(saved_state, heatmap_target)

    apply_cover_heatmap_renderer(heatmap_target)

    _filter_layer_to_activity_ids(heatmap_target, activity_ids)

    if heatmap_target is points_layer and starts_layer is not None:
        _save_layer_state(saved_state, starts_layer, save_renderer=False)
        starts_layer.setOpacity(0.0)

    return [heatmap_target] + background_layers



def _save_layer_state(saved_state: list[dict], layer, *, save_renderer: bool = True) -> None:
    old_renderer = None
    renderer = None
    renderer_order_by = None
    renderer_order_by_enabled = None
    if save_renderer:
        try:
            renderer = layer.renderer()
            old_renderer = renderer.clone()
        except (RuntimeError, AttributeError):
            old_renderer = None
        if renderer is not None:
            try:
                renderer_order_by = renderer.orderBy()
            except (RuntimeError, AttributeError):
                renderer_order_by = None
            try:
                renderer_order_by_enabled = renderer.orderByEnabled()
            except (RuntimeError, AttributeError):
                renderer_order_by_enabled = None
    saved_state.append({
        "layer": layer,
        "renderer": old_renderer,
        "renderer_ref": renderer,
        "renderer_order_by": renderer_order_by,
        "renderer_order_by_enabled": renderer_order_by_enabled,
        "opacity": layer.opacity(),
        "subset": layer.subsetString(),
    })


def _filter_layer_to_activity_ids(layer, activity_ids: list[str]) -> None:
    if not activity_ids or not _layer_has_field(layer, "source_activity_id"):
        return
    safe_ids = ", ".join(
        "'" + str(activity_id).replace("'", "''") + "'"
        for activity_id in activity_ids
    )
    layer.setSubsetString(f'"source_activity_id" IN ({safe_ids})')


def _layer_has_field(layer, field_name: str) -> bool:
    try:
        return layer.fields().indexOf(field_name) >= 0
    except (RuntimeError, AttributeError):
        return False


def _apply_activity_route_render_order(layer) -> None:
    """Draw older cover routes first so newer selected routes remain visible."""
    feature_request_cls = _qgs_feature_request_cls()
    if feature_request_cls is None:
        return

    try:
        renderer = layer.renderer()
    except (RuntimeError, AttributeError):
        return
    if renderer is None:
        return

    clauses = _activity_route_order_by_clauses(layer, feature_request_cls)
    if not clauses:
        return

    set_order_by = getattr(renderer, "setOrderBy", None)
    set_order_by_enabled = getattr(renderer, "setOrderByEnabled", None)
    if not callable(set_order_by):
        return

    try:
        set_order_by(feature_request_cls.OrderBy(clauses))
        if callable(set_order_by_enabled):
            set_order_by_enabled(True)
    except (RuntimeError, AttributeError, TypeError):
        return


def _qgs_feature_request_cls():
    try:
        from qgis.core import QgsFeatureRequest  # noqa: PLC0415
    except ImportError:
        return None
    return QgsFeatureRequest


def _activity_route_order_by_clauses(layer, feature_request_cls) -> list:
    clauses = []
    date_expression = _activity_route_date_order_expression(layer)
    if date_expression is not None:
        clauses.append(feature_request_cls.OrderByClause(date_expression, True))
    if _layer_has_field(layer, "source_activity_id"):
        clauses.append(feature_request_cls.OrderByClause('"source_activity_id"', True))
    return clauses


def _activity_route_date_order_expression(layer) -> str | None:
    has_local_date = _layer_has_field(layer, "start_date_local")
    has_utc_date = _layer_has_field(layer, "start_date")
    if has_local_date and has_utc_date:
        return 'coalesce(nullif("start_date_local", \'\'), nullif("start_date", \'\'), \'\')'
    if has_local_date:
        return 'coalesce(nullif("start_date_local", \'\'), \'\')'
    if has_utc_date:
        return 'coalesce(nullif("start_date", \'\'), \'\')'
    return None


def _restore_layer_state(saved_state: list[dict]) -> None:
    for state in saved_state:
        try:
            layer = state["layer"]
            if state.get("renderer") is not None:
                layer.setRenderer(state["renderer"])
            elif state.get("renderer_ref") is not None:
                renderer = state["renderer_ref"]
                if state.get("renderer_order_by") is not None:
                    renderer.setOrderBy(state["renderer_order_by"])
                if state.get("renderer_order_by_enabled") is not None:
                    renderer.setOrderByEnabled(state["renderer_order_by_enabled"])
            layer.setOpacity(state["opacity"])
            layer.setSubsetString(state["subset"])
        except (RuntimeError, AttributeError):
            pass



def _build_pdf_export_settings(layout_exporter_cls):
    settings = layout_exporter_cls.PdfExportSettings()
    settings.dpi = 150
    settings.rasterizeWholeImage = False
    settings.forceVectorOutput = True
    return settings
