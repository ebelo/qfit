from __future__ import annotations

from typing import Callable


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

    points_layer = None
    starts_layer = None
    background_layers: list = []
    for layer in visible_layers:
        try:
            name = layer.name()
        except (RuntimeError, AttributeError):
            continue
        if name == "qfit activity points":
            points_layer = layer
        elif name == "qfit activity starts":
            starts_layer = layer
        elif name == "qfit activities":
            pass
        else:
            background_layers.append(layer)

    heatmap_target = points_layer or starts_layer
    if heatmap_target is None:
        return None

    try:
        old_renderer = heatmap_target.renderer().clone()
    except (RuntimeError, AttributeError):
        old_renderer = None
    saved_state.append({
        "layer": heatmap_target,
        "renderer": old_renderer,
        "opacity": heatmap_target.opacity(),
        "subset": heatmap_target.subsetString(),
    })

    apply_cover_heatmap_renderer(heatmap_target)

    activity_ids = cover_data.get("_atlas_activity_ids", [])
    if activity_ids:
        safe_ids = ", ".join(
            "'" + str(activity_id).replace("'", "''") + "'"
            for activity_id in activity_ids
        )
        heatmap_target.setSubsetString(f'"source_activity_id" IN ({safe_ids})')

    if heatmap_target is points_layer and starts_layer is not None:
        saved_state.append({
            "layer": starts_layer,
            "renderer": None,
            "opacity": starts_layer.opacity(),
            "subset": starts_layer.subsetString(),
        })
        starts_layer.setOpacity(0.0)

    return [heatmap_target] + background_layers



def _restore_layer_state(saved_state: list[dict]) -> None:
    for state in saved_state:
        try:
            layer = state["layer"]
            if state.get("renderer") is not None:
                layer.setRenderer(state["renderer"])
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
