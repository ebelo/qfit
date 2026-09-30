"""Publish name-only edits without rebuilding geometries or sampled data."""

from ....atlas.publish_atlas import build_page_name, build_page_toc_label


_ACTIVITY_TABLES = ("activity_tracks", "activity_starts", "activity_points", "activity_atlas_pages")
_ATLAS_TABLES = ("atlas_page_detail_items", "atlas_profile_samples", "atlas_toc_entries")


def _columns(connection, table):
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}


def publish_activity_name(connection, record):
    """Update only name/label columns in existing qfit-owned derived tables."""
    identity = (record["source"], record["source_activity_id"])
    title = (record["name"] or "Untitled activity").strip()
    labels = {
        "page_title": title,
        "page_name": build_page_name(record),
        "page_toc_label": build_page_toc_label(record),
    }
    for table in _ACTIVITY_TABLES:
        columns = _columns(connection, table)
        if not {"source", "source_activity_id", "name"}.issubset(columns):
            continue
        values = {"name": title if table == "activity_atlas_pages" else record["name"]}
        if table == "activity_atlas_pages":
            values.update({key: value for key, value in labels.items() if key in columns})
        assignments = ", ".join(f'"{key}" = ?' for key in values)
        connection.execute(
            f'UPDATE "{table}" SET {assignments} WHERE source = ? AND source_activity_id = ?',
            (*values.values(), *identity),
        )
    atlas_columns = _columns(connection, "activity_atlas_pages")
    if not {"source", "source_activity_id", "page_number"}.issubset(atlas_columns):
        return
    pages = connection.execute(
        "SELECT page_number FROM activity_atlas_pages WHERE source = ? AND source_activity_id = ?",
        identity,
    ).fetchall()
    for table in _ATLAS_TABLES:
        columns = _columns(connection, table)
        if "page_number" not in columns:
            continue
        for page in pages:
            values = {key: value for key, value in labels.items() if key in columns}
            if "toc_entry_label" in columns:
                values["toc_entry_label"] = f"{page[0]}. {labels['page_toc_label'] or labels['page_name']}"
            if not values:
                continue
            assignments = ", ".join(f'"{key}" = ?' for key in values)
            connection.execute(
                f'UPDATE "{table}" SET {assignments} WHERE page_number = ?',
                (*values.values(), page[0]),
            )


def register_name_publication_functions(connection):
    """Supply GeoPackage trigger geometry functions without changing index policy."""
    for name, operation in (
        ("ST_IsEmpty", "empty"), ("ST_MinX", "xMinimum"), ("ST_MaxX", "xMaximum"),
        ("ST_MinY", "yMinimum"), ("ST_MaxY", "yMaximum"),
    ):
        connection.create_function(
            name, 1, lambda blob, operation=operation: _geometry_value(blob, operation),
        )


def _geometry_value(blob, operation):
    if blob is None:
        return None
    from qgis.core import QgsGeometry

    data = bytes(blob)
    if data[:2] != b"GP" or len(data) < 8:
        raise ValueError("Invalid GeoPackage geometry header")
    envelope_code = (data[3] >> 1) & 7
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    if envelope_code not in envelope_sizes:
        raise ValueError("Invalid GeoPackage geometry envelope")
    geometry = QgsGeometry()
    if not geometry.fromWkb(data[8 + envelope_sizes[envelope_code]:]):
        raise ValueError("Invalid GeoPackage geometry payload")
    if operation == "empty":
        return int(geometry.isEmpty())
    return getattr(geometry.boundingBox(), operation)()
