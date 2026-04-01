"""Helpers for atlas elevation profile layout items.

This module introduces a small abstraction layer so atlas export can swap the
legacy picture/SVG profile implementation for a future native QGIS elevation
profile item without rewriting the whole export loop at once.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from qgis.core import QgsLayoutItemPicture, QgsLayoutPoint, QgsLayoutSize, QgsUnitTypes

try:  # pragma: no cover - availability depends on QGIS build
    from qgis.core import QgsCoordinateReferenceSystem
except ImportError:  # pragma: no cover - exercised in stubbed/unit-test mode
    QgsCoordinateReferenceSystem = None

try:  # pragma: no cover - availability depends on QGIS build
    from qgis.core import QgsLayoutItemElevationProfile
except ImportError:  # pragma: no cover - exercised in stubbed/unit-test mode
    QgsLayoutItemElevationProfile = None

try:  # pragma: no cover - availability depends on QGIS build
    from qgis.core import QgsProfileRequest
except ImportError:  # pragma: no cover - exercised in stubbed/unit-test mode
    QgsProfileRequest = None

try:  # pragma: no cover - availability depends on QGIS build
    from qgis.core import QgsWkbTypes
except ImportError:  # pragma: no cover - exercised in stubbed/unit-test mode
    QgsWkbTypes = None


@dataclass
class ProfileItemAdapter:
    """Thin wrapper around the current layout item used for atlas profiles."""

    item: object
    kind: str = "picture"
    svg_fallback_item: object | None = None

    @property
    def supports_native_profile(self) -> bool:
        return self.kind == "native"

    def _refresh_item(self, item: object | None) -> None:
        refresh = getattr(item, "refresh", None)
        if callable(refresh):
            refresh()

    def _set_picture_path(self, item: object | None, path: str) -> None:
        set_picture_path = getattr(item, "setPicturePath", None)
        if callable(set_picture_path):
            set_picture_path(path)

    def _clear_native_curve(self) -> None:
        if not self.supports_native_profile:
            return

        set_profile_curve = getattr(self.item, "setProfileCurve", None)
        if callable(set_profile_curve):
            try:
                set_profile_curve(None)
            except Exception:  # noqa: BLE001
                pass

    def clear_profile(self) -> None:
        self._clear_native_curve()
        self._set_picture_path(self.item, "")
        self._set_picture_path(self.svg_fallback_item, "")
        self._refresh_item(self.item)
        self._refresh_item(self.svg_fallback_item)

    def set_svg_profile(self, svg_path: str) -> None:
        self._clear_native_curve()
        picture_item = self.svg_fallback_item or self.item
        self._set_picture_path(picture_item, svg_path)
        self._refresh_item(self.item)
        self._refresh_item(picture_item)

    def configure_native_defaults(
        self,
        *,
        crs_authid: str = "EPSG:3857",
        atlas_driven: bool = True,
        tolerance: float | None = None,
        layers: list[object] | None = None,
    ) -> None:
        if not self.supports_native_profile:
            return

        set_layers = getattr(self.item, "setLayers", None)
        if callable(set_layers) and layers is not None:
            set_layers(list(layers))

        set_crs = getattr(self.item, "setCrs", None)
        if callable(set_crs) and QgsCoordinateReferenceSystem is not None and crs_authid:
            set_crs(QgsCoordinateReferenceSystem(crs_authid))

        set_atlas_driven = getattr(self.item, "setAtlasDriven", None)
        if callable(set_atlas_driven):
            set_atlas_driven(bool(atlas_driven))

        set_tolerance = getattr(self.item, "setTolerance", None)
        if callable(set_tolerance) and tolerance is not None:
            set_tolerance(float(tolerance))

    def bind_native_profile(
        self,
        *,
        profile_curve=None,
    ) -> bool:
        """Bind native profile inputs when the underlying item supports them.

        Returns ``True`` when a native curve was actually bound. Picture-backed
        adapters intentionally ignore these calls so callers can prepare native
        curve binding logic before the atlas export loop switches away from the
        legacy SVG renderer. Native profile *request* objects are prepared
        separately, because supported QGIS versions expose ``profileRequest()``
        but not a matching public setter.
        """
        if not self.supports_native_profile:
            return False

        set_profile_curve = getattr(self.item, "setProfileCurve", None)
        if not callable(set_profile_curve) or profile_curve is None:
            return False

        self._set_picture_path(self.svg_fallback_item, "")
        set_profile_curve(profile_curve)
        self._refresh_item(self.svg_fallback_item)
        self._refresh_item(self.item)
        return True


@dataclass
class NativeProfileItemConfig:
    """Configuration for a native QGIS elevation profile layout item."""

    crs_auth_id: str = "EPSG:3857"
    atlas_driven: bool = True
    tolerance: float | None = None
    layers: list[object] | None = None


@dataclass
class NativeProfileRequestConfig:
    """Configuration for building a native QGIS profile request."""

    crs_auth_id: str = "EPSG:3857"
    tolerance: float | None = None
    step_distance: float | None = None


def _matches_line_geometry_type(geometry_type) -> bool:
    if geometry_type is None:
        return False

    line_geometry = getattr(QgsWkbTypes, "LineGeometry", None) if QgsWkbTypes is not None else None
    if line_geometry is not None and geometry_type == line_geometry:
        return True

    return "line" in str(geometry_type).lower()


def atlas_layer_supports_native_profile_atlas(atlas_layer) -> bool:
    """Return whether *atlas_layer* can drive a native layout profile item.

    QGIS only supports atlas-driven layout elevation profiles when the active
    coverage layer uses a line geometry type. Our current atlas coverage layer
    is polygon-based, so the native item must stay on the manual per-page path
    until a line-based atlas source exists.
    """
    if atlas_layer is None:
        return False

    geometry_type_getter = getattr(atlas_layer, "geometryType", None)
    if callable(geometry_type_getter):
        try:
            geometry_type = geometry_type_getter()
        except Exception:  # noqa: BLE001
            geometry_type = None
        else:
            return _matches_line_geometry_type(geometry_type)

    if QgsWkbTypes is None:
        return False

    wkb_type_getter = getattr(atlas_layer, "wkbType", None)
    geometry_type_resolver = getattr(QgsWkbTypes, "geometryType", None)
    if not callable(wkb_type_getter) or not callable(geometry_type_resolver):
        return False

    try:
        geometry_type = geometry_type_resolver(wkb_type_getter())
    except Exception:  # noqa: BLE001
        return False

    return _matches_line_geometry_type(geometry_type)


def build_profile_item(
    layout,
    *,
    item_id: str,
    x: float,
    y: float,
    w: float,
    h: float,
    native_config: NativeProfileItemConfig | None = None,
) -> ProfileItemAdapter:
    """Create the current profile layout item and return an adapter for it.

    Prefer a native ``QgsLayoutItemElevationProfile`` when the QGIS build
    exposes it, while keeping a hidden picture-backed fallback so atlas pages
    with unusable native curve input can still render the sampled SVG chart.
    """
    native_adapter = build_native_profile_item(
        layout,
        item_id=item_id,
        x=x,
        y=y,
        w=w,
        h=h,
        config=native_config,
    )
    if native_adapter is not None:
        fallback_item = QgsLayoutItemPicture(layout)
        fallback_item.setId(f"{item_id}_svg_fallback")
        fallback_item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
        fallback_item.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
        fallback_item.setResizeMode(QgsLayoutItemPicture.Zoom)
        layout.addLayoutItem(fallback_item)
        native_adapter.svg_fallback_item = fallback_item
        return native_adapter

    profile_item = QgsLayoutItemPicture(layout)
    profile_item.setId(item_id)
    profile_item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    profile_item.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
    profile_item.setResizeMode(QgsLayoutItemPicture.Zoom)
    layout.addLayoutItem(profile_item)
    return ProfileItemAdapter(item=profile_item, kind="picture")


def build_native_profile_item(
    layout,
    *,
    item_id: str,
    x: float,
    y: float,
    w: float,
    h: float,
    config: NativeProfileItemConfig | None = None,
) -> ProfileItemAdapter | None:
    """Create a native elevation-profile item when the QGIS build supports it.

    Returns ``None`` when the native item class is not available, so callers
    can keep using the picture-backed fallback path.
    """
    if not native_profile_item_available():
        return None

    profile_item = QgsLayoutItemElevationProfile(layout)
    profile_item.setId(item_id)
    profile_item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    profile_item.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(profile_item)

    adapter = ProfileItemAdapter(item=profile_item, kind="native")
    cfg = config or NativeProfileItemConfig()
    adapter.configure_native_defaults(
        crs_authid=cfg.crs_auth_id,
        atlas_driven=cfg.atlas_driven,
        tolerance=cfg.tolerance,
        layers=cfg.layers,
    )
    return adapter


def _find_svg_fallback_item(item) -> object | None:
    """Locate the hidden SVG fallback item paired with a native profile item."""
    item_id_getter = getattr(item, "id", None)
    layout_getter = getattr(item, "layout", None)
    if not callable(item_id_getter) or not callable(layout_getter):
        return None

    item_id = item_id_getter()
    if not item_id:
        return None

    layout = layout_getter()
    items_getter = getattr(layout, "items", None)
    if not callable(items_getter):
        return None

    fallback_id = f"{item_id}_svg_fallback"
    for candidate in items_getter():
        candidate_id_getter = getattr(candidate, "id", None)
        if callable(candidate_id_getter) and candidate_id_getter() == fallback_id:
            return candidate
    return None


def build_profile_item_adapter(item) -> ProfileItemAdapter:
    """Wrap an already-created layout item in the shared adapter type."""
    item_type = type(item).__name__.lower()
    kind = "native" if "elevationprofile" in item_type else "picture"
    fallback_item = _find_svg_fallback_item(item) if kind == "native" else None
    return ProfileItemAdapter(item=item, kind=kind, svg_fallback_item=fallback_item)


def native_profile_item_available() -> bool:
    return QgsLayoutItemElevationProfile is not None


def native_profile_request_available() -> bool:
    return QgsProfileRequest is not None


def _coerce_boolish(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _read_boolish_flag(candidate, method_name: str) -> bool | None:
    reader = getattr(candidate, method_name, None)
    if not callable(reader):
        return None

    try:
        return _coerce_boolish(reader())
    except Exception:  # noqa: BLE001
        return None


def _wkb_type_has_z_dimension(candidate) -> bool | None:
    if QgsWkbTypes is None:
        return None

    wkb_type = getattr(candidate, "wkbType", None)
    has_z = getattr(QgsWkbTypes, "hasZ", None)
    if not callable(wkb_type) or not callable(has_z):
        return None

    try:
        return _coerce_boolish(has_z(wkb_type()))
    except Exception:  # noqa: BLE001
        return None


def _candidate_has_z_dimension(candidate) -> bool:
    if candidate is None:
        return False

    for probe in (
        _read_boolish_flag(candidate, "is3D"),
        _wkb_type_has_z_dimension(candidate),
    ):
        if probe is not None:
            return probe

    return False


def _curve_point_count(curve) -> int | None:
    num_points = getattr(curve, "numPoints", None)
    if not callable(num_points):
        return None

    try:
        return max(0, int(num_points()))
    except (TypeError, ValueError):
        return None


def _point_has_z_value(point) -> bool:
    if _candidate_has_z_dimension(point):
        return True

    z_getter = getattr(point, "z", None)
    if not callable(z_getter):
        return False

    try:
        z_value = z_getter()
    except Exception:  # noqa: BLE001
        return False

    if z_value is None:
        return False

    try:
        return not math.isnan(z_value)
    except TypeError:
        return True


def _curve_points_have_z(curve) -> bool:
    point_count = _curve_point_count(curve)
    point_n = getattr(curve, "pointN", None)
    if point_count is None or not callable(point_n):
        return False

    for idx in range(point_count):
        try:
            point = point_n(idx)
        except Exception:  # noqa: BLE001
            return False
        if _point_has_z_value(point):
            return True

    return False


def _geometry_has_z_values(feature_geometry, curve) -> bool:
    return any(
        _candidate_has_z_dimension(candidate)
        for candidate in (feature_geometry, curve)
    ) or _curve_points_have_z(curve)


def build_native_profile_curve(feature_geometry):
    """Extract a native profile curve from a QGIS feature geometry when possible."""
    if feature_geometry is None:
        return None

    const_get = getattr(feature_geometry, "constGet", None)
    curve = const_get() if callable(const_get) else feature_geometry
    if curve is None:
        return None

    type_name = type(curve).__name__.lower()
    if "polygon" in type_name or "surface" in type_name:
        return None

    is_curve_type = any(
        callable(getattr(curve, name, None))
        for name in ("curveToLine", "numPoints", "pointN")
    )
    has_polygon_api = any(
        callable(getattr(curve, name, None))
        for name in ("exteriorRing", "interiorRing", "asPolygon")
    )
    if has_polygon_api and not is_curve_type:
        return None
    if not is_curve_type:
        return None
    if not _geometry_has_z_values(feature_geometry, curve):
        return None

    clone = getattr(curve, "clone", None)
    if callable(clone):
        return clone()

    return None


def build_native_profile_request(
    profile_curve,
    *,
    config: NativeProfileRequestConfig | None = None,
):
    """Create a configured QGIS native profile request when supported."""
    if not native_profile_request_available() or profile_curve is None:
        return None

    cfg = config or NativeProfileRequestConfig()
    request = QgsProfileRequest(profile_curve)

    set_crs = getattr(request, "setCrs", None)
    if callable(set_crs) and QgsCoordinateReferenceSystem is not None and cfg.crs_auth_id:
        set_crs(QgsCoordinateReferenceSystem(cfg.crs_auth_id))

    set_tolerance = getattr(request, "setTolerance", None)
    if callable(set_tolerance) and cfg.tolerance is not None:
        set_tolerance(float(cfg.tolerance))

    set_step_distance = getattr(request, "setStepDistance", None)
    if callable(set_step_distance) and cfg.step_distance is not None:
        set_step_distance(float(cfg.step_distance))

    return request


def build_native_profile_inputs(
    feature_geometry,
    *,
    request_config: NativeProfileRequestConfig | None = None,
):
    """Build the native profile curve/request pair for a feature geometry."""
    curve = build_native_profile_curve(feature_geometry)
    if curve is None:
        return None, None

    request = build_native_profile_request(curve, config=request_config)
    return curve, request
