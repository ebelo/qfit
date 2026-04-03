from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass

from .profile_item import build_native_profile_curve, build_native_profile_curve_from_feature

logger = logging.getLogger(__name__)


@dataclass
class PageProfilePayload:
    """Per-page profile inputs resolved for atlas export."""

    feature_geometry: object | None
    feature: object | None = None
    crs_auth_id: str | None = None
    page_points: list[tuple[float, float]] | None = None

    def native_inputs(self):
        return (
            build_native_profile_curve_from_feature(
                self.feature_geometry,
                feature=self.feature,
                altitudes=[altitude for _distance, altitude in self.page_points or []],
            ),
            None,
        )


class AtlasProfileSampleLookup:
    """GeoPackage-backed profile sample lookup used by atlas export."""

    def __init__(self, atlas_layer):
        source = getattr(atlas_layer, "source", None)
        source_value = source() if callable(source) else source
        self._gpkg_path = str(source_value).split("|", 1)[0] if source_value else None
        self._cache: dict[str, list[tuple[float, float]] | None] = {}

    def lookup(self, source_activity_id) -> list[tuple[float, float]] | None:
        if not self._gpkg_path or source_activity_id in (None, ""):
            return None

        cache_key = str(source_activity_id)
        if cache_key not in self._cache:
            self._cache[cache_key] = self._query_altitudes(cache_key)
        return self._cache[cache_key]

    def _query_altitudes(self, source_activity_id: str) -> list[tuple[float, float]] | None:
        try:
            with sqlite3.connect(f"file:{self._gpkg_path}?mode=ro", uri=True) as conn:
                rows = conn.execute(
                    """
                    SELECT distance_m, altitude_m
                    FROM atlas_profile_samples
                    WHERE source_activity_id = ?
                    ORDER BY profile_point_index
                    """,
                    (source_activity_id,),
                ).fetchall()
        except sqlite3.Error:
            logger.debug("Could not read atlas_profile_samples fallback altitudes", exc_info=True)
            return None

        points: list[tuple[float, float]] = []
        for distance_value, altitude_value in rows:
            try:
                points.append((float(distance_value), float(altitude_value)))
            except (TypeError, ValueError):
                return None

        return points or None


def feature_attribute(feature, field_name: str):
    if feature is None:
        return None

    attribute = getattr(feature, "attribute", None)
    if callable(attribute):
        try:
            return attribute(field_name)
        except Exception:  # noqa: BLE001
            return None

    try:
        return feature[field_name]
    except Exception:  # noqa: BLE001
        return None



def load_profile_points_from_feature(feature) -> list[tuple[float, float]] | None:
    raw_value = feature_attribute(feature, "details_json")
    if isinstance(raw_value, str):
        try:
            raw_value = json.loads(raw_value)
        except (TypeError, ValueError):
            raw_value = None

    if not isinstance(raw_value, dict):
        return None

    stream_metrics = raw_value.get("stream_metrics")
    if not isinstance(stream_metrics, dict):
        return None

    distances = stream_metrics.get("distance")
    altitudes = stream_metrics.get("altitude")
    if not isinstance(distances, list) or not isinstance(altitudes, list):
        return None
    if len(distances) != len(altitudes) or len(distances) < 2:
        return None

    points: list[tuple[float, float]] = []
    for distance_value, altitude_value in zip(distances, altitudes):
        try:
            points.append((float(distance_value), float(altitude_value)))
        except (TypeError, ValueError):
            return None

    return points


class PageProfilePayloadResolver:
    """Resolve geometry, feature, CRS, and sampled points for one atlas page."""

    def __init__(self, *, profile_altitude_lookup=None):
        self._profile_altitude_lookup = profile_altitude_lookup

    def resolve(self, feat, filterable_layers) -> PageProfilePayload:
        geometry, source_feature, crs_auth_id = self._resolve_page_profile_source(feat, filterable_layers)
        source_activity_id = feature_attribute(source_feature, "source_activity_id")
        if source_activity_id in (None, ""):
            source_activity_id = feature_attribute(feat, "source_activity_id")
        page_points = (
            self._profile_altitude_lookup(source_activity_id)
            if callable(self._profile_altitude_lookup)
            else None
        )
        if not page_points:
            page_points = load_profile_points_from_feature(source_feature)
        if not page_points:
            page_points = load_profile_points_from_feature(feat)
        if not page_points:
            page_points = self._load_profile_points_from_layers(filterable_layers)
        return PageProfilePayload(
            feature_geometry=geometry,
            feature=source_feature,
            crs_auth_id=crs_auth_id,
            page_points=page_points,
        )

    def _load_profile_points_from_layers(self, filterable_layers) -> list[tuple[float, float]] | None:
        for layer, _original_subset in filterable_layers or []:
            get_features = getattr(layer, "getFeatures", None)
            if not callable(get_features):
                continue
            try:
                layer_features = get_features()
            except Exception:  # noqa: BLE001
                logger.debug("Could not inspect filtered layer features for profile points", exc_info=True)
                continue
            for layer_feature in layer_features:
                points = load_profile_points_from_feature(layer_feature)
                if points:
                    return points
        return None

    def _scan_layer_for_profile_source(self, layer):
        """Yield (geometry, feature, crs_authid) for each line-like feature in *layer*."""
        get_features = getattr(layer, "getFeatures", None)
        if not callable(get_features):
            return

        try:
            layer_features = get_features()
        except Exception:  # noqa: BLE001
            logger.debug("Could not inspect filtered layer features for native profile geometry", exc_info=True)
            return

        line_like: list[tuple] = []
        for layer_feature in layer_features:
            geometry_getter = getattr(layer_feature, "geometry", None)
            geometry = geometry_getter() if callable(geometry_getter) else None
            if build_native_profile_curve(geometry) is not None:
                yield geometry, layer_feature, self._layer_crs_authid(layer)
                return
            if self._geometry_looks_line_like(geometry):
                line_like.append((geometry, layer_feature, self._layer_crs_authid(layer)))

        yield from line_like

    def _resolve_page_profile_source(self, feat, filterable_layers) -> tuple[object | None, object | None, str | None]:
        line_like_candidates: list[tuple[object, object, str | None]] = []

        for layer, _original_subset in filterable_layers:
            for geom, layer_feature, crs_id in self._scan_layer_for_profile_source(layer):
                if build_native_profile_curve(geom) is not None:
                    return geom, layer_feature, crs_id
                line_like_candidates.append((geom, layer_feature, crs_id))

        geometry_getter = getattr(feat, "geometry", None)
        geometry = geometry_getter() if callable(geometry_getter) else None
        if build_native_profile_curve(geometry) is not None:
            return geometry, feat, None

        if line_like_candidates:
            return line_like_candidates[0]

        return geometry, feat, None

    @staticmethod
    def _geometry_looks_line_like(feature_geometry) -> bool:
        if feature_geometry is None:
            return False

        if build_native_profile_curve(feature_geometry) is not None:
            return True

        const_get = getattr(feature_geometry, "constGet", None)
        curve = const_get() if callable(const_get) else feature_geometry
        if curve is None:
            return False

        type_name = type(curve).__name__.lower()
        if "line" in type_name or "curve" in type_name:
            return True

        return any(callable(getattr(curve, name, None)) for name in ("curveToLine", "numPoints", "pointN"))

    @staticmethod
    def _layer_crs_authid(layer) -> str | None:
        crs_getter = getattr(layer, "crs", None)
        if not callable(crs_getter):
            return None

        try:
            layer_crs = crs_getter()
        except Exception:  # noqa: BLE001
            return None

        authid_getter = getattr(layer_crs, "authid", None)
        if not callable(authid_getter):
            return None

        try:
            return authid_getter()
        except Exception:  # noqa: BLE001
            return None


def build_page_profile_payload(feat, filterable_layers, profile_altitude_lookup=None) -> PageProfilePayload:
    return PageProfilePayloadResolver(profile_altitude_lookup=profile_altitude_lookup).resolve(
        feat,
        filterable_layers,
    )
