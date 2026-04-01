"""Helpers for atlas elevation profile layout items.

This module introduces a small abstraction layer so atlas export can swap the
legacy picture/SVG profile implementation for a future native QGIS elevation
profile item without rewriting the whole export loop at once.
"""

from __future__ import annotations

from dataclasses import dataclass

from qgis.core import QgsLayoutItemPicture, QgsLayoutPoint, QgsLayoutSize, QgsUnitTypes

try:  # pragma: no cover - availability depends on QGIS build
    from qgis.core import QgsCoordinateReferenceSystem, QgsLayoutItemElevationProfile
except ImportError:  # pragma: no cover - exercised in stubbed/unit-test mode
    QgsCoordinateReferenceSystem = None
    QgsLayoutItemElevationProfile = None


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

    Today this continues to use the legacy picture-backed SVG item.  The
    adapter exists so a future slice can switch to a native
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


def build_profile_item_adapter(item) -> ProfileItemAdapter:
    """Wrap an already-created layout item in the shared adapter type."""
    item_type = type(item).__name__.lower()
    kind = "native" if "elevationprofile" in item_type else "picture"
    return ProfileItemAdapter(item=item, kind=kind)


def _native_profile_item_available() -> bool:
    return QgsLayoutItemElevationProfile is not None
