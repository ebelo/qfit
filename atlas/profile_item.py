"""Helpers for atlas elevation profile layout items.

This module introduces a small abstraction layer so atlas export can swap the
legacy picture/SVG profile implementation for a future native QGIS elevation
profile item without rewriting the whole export loop at once.
"""

from __future__ import annotations

from dataclasses import dataclass

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsLayoutItemElevationProfile,
    QgsLayoutItemPicture,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsUnitTypes,
)


@dataclass
class ProfileItemAdapter:
    """Thin wrapper around the current layout item used for atlas profiles."""

    item: object
    kind: str = "picture"

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


def build_profile_item(layout, *, item_id: str, x: float, y: float, w: float, h: float) -> ProfileItemAdapter:
    """Create the current profile layout item and return an adapter for it.

    Prefer a native :class:`QgsLayoutItemElevationProfile` when QGIS exposes
    it; otherwise fall back to the legacy picture-backed SVG item.
    """
    if _native_profile_item_available():
        profile_item = QgsLayoutItemElevationProfile(layout)
        profile_item.setId(item_id)
        profile_item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
        profile_item.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
        set_crs = getattr(profile_item, "setCrs", None)
        if callable(set_crs):
            set_crs(QgsCoordinateReferenceSystem("EPSG:3857"))
        set_atlas_driven = getattr(profile_item, "setAtlasDriven", None)
        if callable(set_atlas_driven):
            set_atlas_driven(True)
        layout.addLayoutItem(profile_item)
        return ProfileItemAdapter(item=profile_item, kind="native")

    profile_item = QgsLayoutItemPicture(layout)
    profile_item.setId(item_id)
    profile_item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    profile_item.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
    profile_item.setResizeMode(QgsLayoutItemPicture.Zoom)
    layout.addLayoutItem(profile_item)
    return ProfileItemAdapter(item=profile_item, kind="picture")


def build_profile_item_adapter(item) -> ProfileItemAdapter:
    """Wrap an already-created layout item in the shared adapter type."""
    item_type = type(item).__name__.lower()
    kind = "native" if "elevationprofile" in item_type else "picture"
    return ProfileItemAdapter(item=item, kind=kind)


def _native_profile_item_available() -> bool:
    return QgsLayoutItemElevationProfile is not None
