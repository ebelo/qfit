from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass

from qgis.core import QgsCoordinateReferenceSystem, QgsProfileRequest

from .profile_backend_policy import DEFAULT_PROFILE_BACKEND_POLICY
from .profile_item import (
    build_native_profile_curve,
    build_native_profile_curve_from_feature,
    configure_native_profile_plot_range,
)
from .profile_payload_resolver import PageProfilePayload as ResolverPageProfilePayload
from .profile_payload_resolver import build_page_profile_payload

logger = logging.getLogger(__name__)

try:  # pragma: no cover - availability depends on QGIS build
    from qgis.core import QgsProfilePlotRenderer
except ImportError:  # pragma: no cover - exercised in stubbed/unit-test mode
    QgsProfilePlotRenderer = None

_DEFAULT_PROFILE_CRS_AUTH_ID = "EPSG:3857"


@dataclass
class PageProfilePayload(ResolverPageProfilePayload):
    """Atlas-export payload that can derive native profile inputs on demand."""

    def native_inputs(self):
        return (
            build_native_profile_curve_from_feature(
                self.feature_geometry,
                feature=self.feature,
                altitudes=[altitude for _distance, altitude in self.page_points or []],
            ),
            None,
        )


class AtlasPageProfileWorkflow:
    """Dedicated component for page-profile payload resolution and rendering."""

    def __init__(
        self,
        *,
        profile_chart_width_mm: float,
        profile_chart_height_mm: float,
        default_profile_crs_auth_id: str = _DEFAULT_PROFILE_CRS_AUTH_ID,
    ):
        self.profile_chart_width_mm = profile_chart_width_mm
        self.profile_chart_height_mm = profile_chart_height_mm
        self.default_profile_crs_auth_id = default_profile_crs_auth_id

    def render_page_profile_svg(self, page_points, *, output_path: str) -> str | None:
        return _render_page_profile_svg(
            page_points,
            output_path=output_path,
            profile_chart_width_mm=self.profile_chart_width_mm,
            profile_chart_height_mm=self.profile_chart_height_mm,
        )

    def build_page_profile_payload(
        self,
        feat,
        filterable_layers,
        profile_altitude_lookup=None,
    ) -> PageProfilePayload:
        return _build_page_profile_payload(
            feat,
            filterable_layers,
            profile_altitude_lookup=profile_altitude_lookup,
        )

    def apply_page_profile_payload(
        self,
        profile_adapter,
        profile_payload: PageProfilePayload,
        *,
        output_path: str | None = None,
        profile_temp_files: list[str] | None = None,
    ) -> None:
        _apply_page_profile_payload(
            profile_adapter,
            profile_payload,
            output_path=output_path,
            profile_temp_files=profile_temp_files,
            render_page_profile_svg_fn=self.render_page_profile_svg,
            render_native_profile_image_fn=_render_native_profile_image,
            default_profile_crs_auth_id=self.default_profile_crs_auth_id,
        )


def _render_page_profile_svg(
    page_points,
    *,
    output_path: str,
    profile_chart_width_mm: float,
    profile_chart_height_mm: float,
) -> str | None:
    """Render the sampled SVG profile for a single atlas page."""
    from .profile_renderer import render_profile_to_file  # noqa: PLC0415

    return render_profile_to_file(
        page_points,
        width_mm=profile_chart_width_mm,
        height_mm=profile_chart_height_mm,
        directory=os.path.dirname(output_path) or None,
    )


def _build_native_renderer_mem_layer(native_curve, crs_str: str):
    """Build a temporary 3D memory layer from a native profile curve."""
    try:
        from qgis.core import (  # noqa: PLC0415
            Qgis,
            QgsFeature,
            QgsGeometry,
            QgsVectorLayer,
        )
        mem_layer = QgsVectorLayer(
            f"LineStringZ?crs={crs_str}",
            "_qfit_profile_temp",
            "memory",
        )
        clone_fn = getattr(native_curve, "clone", None)
        if callable(clone_fn):
            feat_mem = QgsFeature(mem_layer.fields())
            feat_mem.setGeometry(QgsGeometry(clone_fn()))
            mem_layer.dataProvider().addFeatures([feat_mem])

        ep = mem_layer.elevationProperties()
        if ep is not None and hasattr(Qgis, "VectorProfileType"):
            ep.setType(Qgis.VectorProfileType.ContinuousSurface)

        return mem_layer
    except Exception:  # noqa: BLE001
        logger.debug("Could not build temporary 3D layer for profile rendering", exc_info=True)
        return None


def _finite_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    return result if math.isfinite(result) else None


def _range_from_values(values) -> tuple[float, float] | None:
    numeric_values = [value for value in (_finite_float(candidate) for candidate in values) if value is not None]
    if not numeric_values:
        return None

    lower = min(numeric_values)
    upper = max(numeric_values)
    if upper < lower:
        return None
    return lower, upper


def _resolve_renderer_z_range(renderer, page_points):
    """Derive a valid (z_min, z_max) tuple from *renderer* or *page_points*."""
    z_range_obj = renderer.zRange()
    z_lower = getattr(z_range_obj, "lower", lambda: None)()
    z_upper = getattr(z_range_obj, "upper", lambda: None)()
    z_min = _finite_float(z_lower)
    z_max = _finite_float(z_upper)

    if (z_min is None or z_max is None or z_max <= z_min) and page_points:
        alt_range = _range_from_values(alt for _d, alt in page_points)
        if alt_range is not None:
            z_min, z_max = alt_range

    if z_min is None or z_max is None or z_max < z_min:
        return None, None
    return z_min, z_max


def _resolve_renderer_x_range(native_curve, page_points):
    """Derive a valid (x_min, x_max) distance tuple."""
    if page_points:
        dist_range = _range_from_values(d for d, _a in page_points)
        if dist_range is not None:
            return dist_range

    length_getter = getattr(native_curve, "length", None)
    curve_length = _finite_float(length_getter()) if callable(length_getter) else None
    if curve_length is None or curve_length <= 0:
        return None, None
    return 0.0, curve_length


def _save_renderer_image(renderer, width_px, height_px, x_min, x_max, z_min, z_max, output_dir):
    """Render and persist a profile chart image. Returns the file path or ``None``."""
    img = renderer.renderToImage(width_px, height_px, x_min, x_max, z_min, z_max)
    if img is None or getattr(img, "isNull", lambda: True)():
        return None

    import tempfile  # noqa: PLC0415
    with tempfile.NamedTemporaryFile(suffix=".png", dir=output_dir, delete=False) as tmp:
        tmp_path = tmp.name

    save = getattr(img, "save", None)
    if not callable(save) or not save(tmp_path):
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return None
    return tmp_path


def _render_native_profile_image(
    native_curve,
    layers: list,
    *,
    crs_auth_id: str | None = None,
    tolerance: float | None = None,
    width_px: int = 1000,
    height_px: int = 220,
    output_dir: str | None = None,
    page_points: list[tuple[float, float]] | None = None,
    profile_request_cls=QgsProfileRequest,
    qgs_crs_factory=QgsCoordinateReferenceSystem,
    profile_plot_renderer_cls=QgsProfilePlotRenderer,
    build_native_renderer_mem_layer_fn=_build_native_renderer_mem_layer,
    save_renderer_image_fn=_save_renderer_image,
) -> str | None:
    """Render a profile chart using QgsProfilePlotRenderer synchronously."""
    if profile_plot_renderer_cls is None or native_curve is None or not layers:
        return None

    try:
        resolved_crs = crs_auth_id or _DEFAULT_PROFILE_CRS_AUTH_ID
        request = profile_request_cls(native_curve)
        request.setCrs(qgs_crs_factory(resolved_crs))
        if tolerance is not None:
            request.setTolerance(float(tolerance))

        crs_str = qgs_crs_factory(resolved_crs).authid()
        mem_layer = build_native_renderer_mem_layer_fn(native_curve, crs_str)
        profile_layers = [mem_layer] if mem_layer is not None else list(layers)

        renderer = profile_plot_renderer_cls(profile_layers, request)
        renderer.startGeneration()
        renderer.waitForFinished()

        z_min, z_max = _resolve_renderer_z_range(renderer, page_points)
        if z_min is None or z_max is None:
            return None

        x_min, x_max = _resolve_renderer_x_range(native_curve, page_points)
        if x_min is None or x_max is None:
            return None

        return save_renderer_image_fn(renderer, width_px, height_px, x_min, x_max, z_min, z_max, output_dir)
    except Exception:  # noqa: BLE001
        logger.debug("QgsProfilePlotRenderer render failed", exc_info=True)
        return None


def _native_curve_length(native_curve) -> float | None:
    length_getter = getattr(native_curve, "length", None)
    if not callable(length_getter):
        return None

    try:
        return _finite_float(length_getter())
    except Exception:  # noqa: BLE001
        return None


def _profile_distance_range(page_points, native_curve) -> tuple[float, float] | None:
    if page_points:
        distance_range = _range_from_values(distance for distance, _altitude in page_points)
        if distance_range is not None:
            return distance_range[0] / 1000.0, distance_range[1] / 1000.0

    curve_length = _native_curve_length(native_curve)
    if curve_length is None:
        return None

    return 0.0, curve_length


def _item_crs_authid(item) -> str | None:
    crs_getter = getattr(item, "crs", None)
    if not callable(crs_getter):
        return None
    try:
        item_crs = crs_getter()
    except Exception:  # noqa: BLE001
        return None
    authid_getter = getattr(item_crs, "authid", None)
    if not callable(authid_getter):
        return None
    try:
        return authid_getter()
    except Exception:  # noqa: BLE001
        return None


def _item_tolerance(item) -> float | None:
    tolerance_getter = getattr(item, "tolerance", None)
    if not callable(tolerance_getter):
        return None
    try:
        return _finite_float(tolerance_getter())
    except Exception:  # noqa: BLE001
        return None


def _profile_elevation_range_from_renderer(
    profile_adapter,
    native_curve,
    *,
    crs_auth_id: str | None = None,
    profile_request_cls=QgsProfileRequest,
    qgs_crs_factory=QgsCoordinateReferenceSystem,
    profile_plot_renderer_cls=QgsProfilePlotRenderer,
    item_crs_authid_fn=_item_crs_authid,
    item_tolerance_fn=_item_tolerance,
):
    if profile_plot_renderer_cls is None or native_curve is None:
        return None

    item = getattr(profile_adapter, "item", None)
    if item is None:
        return None

    layers_getter = getattr(item, "layers", None)
    if not callable(layers_getter):
        return None

    try:
        layers = list(layers_getter() or [])
    except Exception:  # noqa: BLE001
        return None

    if not layers:
        return None

    request = profile_request_cls(native_curve)
    resolved_crs = crs_auth_id or item_crs_authid_fn(item)
    if resolved_crs:
        request.setCrs(qgs_crs_factory(resolved_crs))

    tolerance_value = item_tolerance_fn(item)
    if tolerance_value is not None:
        request.setTolerance(tolerance_value)

    try:
        renderer = profile_plot_renderer_cls(layers, request)
        renderer.startGeneration()
        renderer.waitForFinished()
        z_range = renderer.zRange()
    except Exception:  # noqa: BLE001
        logger.debug("Could not derive native profile z-range from renderer", exc_info=True)
        return None

    lower = _finite_float(getattr(z_range, "lower", lambda: None)())
    upper = _finite_float(getattr(z_range, "upper", lambda: None)())
    if lower is None or upper is None or upper < lower:
        return None
    return lower, upper


def _resolve_native_profile_plot_ranges(
    profile_adapter,
    profile_payload,
    native_curve,
    *,
    profile_elevation_range_from_renderer_fn=_profile_elevation_range_from_renderer,
):
    x_range = _profile_distance_range(profile_payload.page_points, native_curve)
    y_range = _range_from_values(altitude for _distance, altitude in profile_payload.page_points or [])
    if y_range is None:
        y_range = profile_elevation_range_from_renderer_fn(
            profile_adapter,
            native_curve,
            crs_auth_id=profile_payload.crs_auth_id,
        )

    return x_range, y_range


def _apply_picture_profile(
    profile_adapter,
    profile_payload: PageProfilePayload,
    output_path: str | None,
    profile_temp_files: list[str] | None,
    *,
    render_page_profile_svg_fn,
    render_native_profile_image_fn,
    default_profile_crs_auth_id: str,
) -> None:
    """Render and bind the SVG profile for picture-backed adapters."""
    page_points = profile_payload.page_points or []
    if DEFAULT_PROFILE_BACKEND_POLICY.should_render_svg(profile_adapter) and len(page_points) >= 2:
        try:
            svg_path = render_page_profile_svg_fn(page_points, output_path=output_path or "")
        except Exception:  # noqa: BLE001
            logger.debug("Profile chart render failed", exc_info=True)
            svg_path = None

        if svg_path:
            profile_adapter.set_svg_profile(svg_path)
            if profile_temp_files is not None:
                profile_temp_files.append(svg_path)
            return

    native_curve, _ = profile_payload.native_inputs()
    if DEFAULT_PROFILE_BACKEND_POLICY.should_try_native_image_fallback(profile_adapter, native_curve):
        output_dir = os.path.dirname(output_path) if output_path else None
        native_img = render_native_profile_image_fn(
            native_curve,
            [],
            crs_auth_id=profile_payload.crs_auth_id or default_profile_crs_auth_id,
            output_dir=output_dir,
            page_points=page_points if page_points else None,
        )
        if native_img:
            profile_adapter.set_svg_profile(native_img)
            if profile_temp_files is not None:
                profile_temp_files.append(native_img)
            return

    profile_adapter.clear_profile()


def _apply_native_profile(
    profile_adapter,
    profile_payload: PageProfilePayload,
    *,
    resolve_native_profile_plot_ranges_fn=_resolve_native_profile_plot_ranges,
    configure_native_profile_plot_range_fn=configure_native_profile_plot_range,
) -> None:
    """Bind the native curve and configure axis ranges for native-backed adapters."""
    native_curve, _native_request = profile_payload.native_inputs()
    if native_curve is None:
        profile_adapter.clear_profile()
        return

    if profile_payload.crs_auth_id:
        set_crs = getattr(profile_adapter.item, "setCrs", None)
        if callable(set_crs):
            try:
                set_crs(QgsCoordinateReferenceSystem(profile_payload.crs_auth_id))
            except Exception:  # noqa: BLE001
                logger.debug("Could not apply page profile CRS to native layout item", exc_info=True)

    if not profile_adapter.bind_native_profile(profile_curve=native_curve, profile_request=None):
        profile_adapter.clear_profile()
        return

    x_range, y_range = resolve_native_profile_plot_ranges_fn(profile_adapter, profile_payload, native_curve)
    configure_native_profile_plot_range_fn(
        profile_adapter.item,
        x_min=x_range[0] if x_range else None,
        x_max=x_range[1] if x_range else None,
        y_min=y_range[0] if y_range else None,
        y_max=y_range[1] if y_range else None,
    )
    refresh_item = getattr(profile_adapter.item, "refresh", None)
    if callable(refresh_item):
        refresh_item()


def _apply_page_profile_payload(
    profile_adapter,
    profile_payload: PageProfilePayload,
    *,
    output_path: str | None = None,
    profile_temp_files: list[str] | None = None,
    render_page_profile_svg_fn,
    render_native_profile_image_fn,
    default_profile_crs_auth_id: str,
    apply_picture_profile_fn=_apply_picture_profile,
    apply_native_profile_fn=_apply_native_profile,
) -> None:
    """Apply per-page profile data to the active layout profile backend."""
    if DEFAULT_PROFILE_BACKEND_POLICY.should_render_svg(profile_adapter):
        apply_picture_profile_fn(
            profile_adapter,
            profile_payload,
            output_path,
            profile_temp_files,
            render_page_profile_svg_fn=render_page_profile_svg_fn,
            render_native_profile_image_fn=render_native_profile_image_fn,
            default_profile_crs_auth_id=default_profile_crs_auth_id,
        )
        return

    if DEFAULT_PROFILE_BACKEND_POLICY.should_configure_atlas_native_ranges(profile_adapter):
        return

    if DEFAULT_PROFILE_BACKEND_POLICY.requires_manual_native_binding(profile_adapter):
        apply_native_profile_fn(profile_adapter, profile_payload)


def _build_page_profile_payload(
    feat,
    filterable_layers,
    profile_altitude_lookup=None,
) -> PageProfilePayload:
    payload = build_page_profile_payload(
        feat,
        filterable_layers,
        profile_altitude_lookup=profile_altitude_lookup,
    )
    return PageProfilePayload(
        feature_geometry=payload.feature_geometry,
        feature=payload.feature,
        crs_auth_id=payload.crs_auth_id,
        page_points=payload.page_points,
    )
