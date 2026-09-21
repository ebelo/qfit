"""Source-neutral activity reconciliation rules for the canonical registry."""

from __future__ import annotations

from dataclasses import fields

from .models import Activity


def reconcile_activity_records(incoming: dict, existing: dict | None) -> dict:
    """Preserve local data and prevent a lower-fidelity geometry downgrade."""

    if existing is None:
        return dict(incoming)
    merged = dict(incoming)
    for model_field in fields(Activity):
        name = model_field.name
        if name in ("details_json", "geometry_points"):
            continue
        if merged.get(name) is None:
            merged[name] = existing.get(name)

    incoming_details = dict(incoming.get("details_json") or {})
    existing_details = dict(existing.get("details_json") or {})
    keep_existing_geometry = (
        _geometry_quality(existing, existing_details)
        > _geometry_quality(incoming, incoming_details)
    )
    _merge_geometry(merged, incoming, existing, keep_existing_geometry)
    merged["details_json"] = _merge_details(
        incoming_details,
        existing_details,
        keep_existing_geometry,
    )
    return merged


def _merge_geometry(merged, incoming, existing, keep_existing_geometry):
    if keep_existing_geometry:
        for name in (
            "geometry_source",
            "geometry_points",
            "start_lat",
            "start_lon",
            "end_lat",
            "end_lon",
        ):
            merged[name] = existing.get(name)
    else:
        merged["geometry_points"] = list(incoming.get("geometry_points") or [])


def _merge_details(incoming_details, existing_details, keep_existing_geometry):
    details = dict(existing_details)
    details.update(incoming_details)
    if keep_existing_geometry and existing_details.get("stream_metrics"):
        details["stream_metrics"] = existing_details["stream_metrics"]
        details["geometry_ingest_source"] = existing_details.get(
            "geometry_ingest_source"
        )
    ingest_sources = _merged_ingest_sources(existing_details, incoming_details)
    if ingest_sources:
        details["ingest_sources"] = ingest_sources
    else:
        details.pop("ingest_sources", None)
    return details


def _geometry_quality(record, details):
    points = record.get("geometry_points") or []
    source = record.get("geometry_source")
    if not points:
        rank = 0
    elif source == "stream" and len(points) >= 2:
        rank = 3
    elif source == "summary_polyline":
        rank = 2
    else:
        rank = 1
    metrics = details.get("stream_metrics") or {}
    metric_count = sum(
        isinstance(values, list) and any(value is not None for value in values)
        for values in metrics.values()
    )
    has_profile = bool(
        any(value is not None for value in (metrics.get("distance") or []))
        and sum(value is not None for value in (metrics.get("altitude") or [])) >= 2
    )
    return rank, int(has_profile), metric_count, len(points)


def _merged_ingest_sources(existing_details, incoming_details):
    sources = []
    for details in (existing_details, incoming_details):
        candidates = list(details.get("ingest_sources") or [])
        candidates.append(details.get("ingest_source"))
        for value in candidates:
            if value and value not in sources:
                sources.append(value)
    return sources


__all__ = ["reconcile_activity_records"]
