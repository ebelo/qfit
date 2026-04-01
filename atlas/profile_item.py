"""Helpers for atlas elevation profile layout items.

This module introduces a small abstraction layer so atlas export can swap the
legacy picture/SVG profile implementation for a future native QGIS elevation
profile item without rewriting the whole export loop at once.
"""

from __future__ import annotations

from dataclasses import dataclass

from qgis.core import QgsLayoutItemPicture, QgsLayoutPoint, QgsLayoutSize, QgsUnitTypes

try:  # pragma: no cover - availability depends on QGIS build
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsLayoutItemElevationProfile,
        QgsProfileRequest,
    )
except ImportError:  # pragma: no cover - exercised in stubbed/unit-test mode
    QgsCoordinateReferenceSystem = None
    QgsLayoutItemElevationProfile = None
    QgsProfileRequest = None


@dataclass
class ProfileItemAdapter:
    """Thin wrapper around the current layout item used for atlas profiles."""

    item: object
    kind: str = "picture"

    @property
    def supports_native_profile(self) -> bool:
        return self.kind == "native"

    def clear_profile(self) -> None:
        set_picture_path = getattr(self.item, "setPicturePath", None)
        if callable(set_picture_path):
            set_picture_path("")
        refresh = getattr(self.item, "refresh", None)
        if callable(refresh):
            refresh()

    def set_svg_profile(self, svg_path: str) -> None:
        set_picture_path = getattr(self.item, "setPicturePath", None)
        if callable(set_picture_path):
            set_picture_path(svg_path)
        refresh = getattr(self.item, "refresh", None)
        if callable(refresh):
            refresh()

    def configure_native_defaults(
        self,
        *,
        crs_authid: str = "EPSG:3857",
        atlas_driven: bool = True,
        tolerance: float | None = None,
    ) -> None:
        if not self.supports_native_profile:
            return

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
        profile_request=None,
    ) -> None:
        """Bind native profile inputs when the underlying item supports them.

        Picture-backed adapters intentionally ignore these calls so callers can
        prepare native binding logic before the atlas export loop switches away
        from the legacy SVG renderer.
        """
        if not self.supports_native_profile:
            return

        set_profile_curve = getattr(self.item, "setProfileCurve", None)
        if callable(set_profile_curve) and profile_curve is not None:
            set_profile_curve(profile_curve)

        set_profile_request = getattr(self.item, "setProfileRequest", None)
        if callable(set_profile_request) and profile_request is not None:
            set_profile_request(profile_request)


@dataclass
class NativeProfileItemConfig:
    """Configuration for a native QGIS elevation profile layout item."""

    crs_auth_id: str = "EPSG:3857"
    atlas_driven: bool = True
    tolerance: float | None = None


@dataclass
class NativeProfileRequestConfig:
    """Configuration for building a native QGIS profile request."""

    crs_auth_id: str = "EPSG:3857"
    tolerance: float | None = None
    step_distance: float | None = None


def build_profile_item(layout, *, item_id: str, x: float, y: float, w: float, h: float) -> ProfileItemAdapter:
    """Create the current profile layout item and return an adapter for it.

    Today this continues to use the legacy picture-backed SVG item. The adapter
    exists so a future slice can switch to a native
    ``QgsLayoutItemElevationProfile`` implementation without rewriting atlas
    export again.
    """
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
    )
    return adapter


def build_profile_item_adapter(item) -> ProfileItemAdapter:
    """Wrap an already-created layout item in the shared adapter type."""
    item_type = type(item).__name__.lower()
    kind = "native" if "elevationprofile" in item_type else "picture"
    return ProfileItemAdapter(item=item, kind=kind)


def native_profile_item_available() -> bool:
    return QgsLayoutItemElevationProfile is not None


def native_profile_request_available() -> bool:
    return QgsProfileRequest is not None


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
