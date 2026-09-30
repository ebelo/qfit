"""Publish name-only edits without rebuilding geometries or sampled data."""

import struct

from ....atlas.publish_atlas import atlas_sort_key, build_page_name, build_page_toc_label


_ACTIVITY_TABLES = ("activity_tracks", "activity_starts", "activity_points", "activity_atlas_pages")
_ATLAS_TABLES = ("atlas_page_detail_items", "atlas_profile_samples", "atlas_toc_entries")


def _columns(connection, table):
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}


def publish_activity_name(connection, record):
    """Update only name/label columns in existing qfit-owned derived tables."""
    identity = (record["source"], record["source_activity_id"])
    title = (record["name"] or "Untitled activity").strip()
    labels = {
        "page_sort_key": _stable_page_sort_key(connection, identity, atlas_sort_key(record)),
        "page_title": title,
        "page_name": build_page_name(record),
        "page_toc_label": build_page_toc_label(record),
    }
    _publish_activity_tables(connection, record, identity, title, labels)
    _publish_atlas_tables(connection, identity, labels)



def _stable_page_sort_key(connection, identity, candidate):
    """Keep current numbered page order when a title edit would cross a neighbor."""
    columns = _columns(connection, "activity_atlas_pages")
    if not {"source", "source_activity_id", "page_number", "page_sort_key"}.issubset(columns):
        return candidate
    page = connection.execute(
        "SELECT page_number, page_sort_key FROM activity_atlas_pages "
        "WHERE source = ? AND source_activity_id = ?", identity,
    ).fetchone()
    if page is None:
        return candidate
    previous = connection.execute(
        "SELECT page_sort_key FROM activity_atlas_pages WHERE page_number < ? "
        "ORDER BY page_number DESC LIMIT 1", (page[0],),
    ).fetchone()
    following = connection.execute(
        "SELECT page_sort_key FROM activity_atlas_pages WHERE page_number > ? "
        "ORDER BY page_number LIMIT 1", (page[0],),
    ).fetchone()
    if ((previous and previous[0] is not None and candidate <= previous[0])
            or (following and following[0] is not None and candidate >= following[0])):
        return page[1]
    return candidate

def _publish_activity_tables(connection, record, identity, title, labels):
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


def _publish_atlas_tables(connection, identity, labels):
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
    data = bytes(blob)
    if data[:2] != b"GP" or len(data) < 8:
        raise ValueError("Invalid GeoPackage geometry header")
    empty = bool(data[3] & 16)
    if operation == "empty":
        return int(empty)
    if empty:
        return None
    bounds = _geometry_bounds(data)
    return bounds[{"xMinimum": 0, "xMaximum": 1, "yMinimum": 2, "yMaximum": 3}[operation]]


def _geometry_bounds(data):
    envelope_code = (data[3] >> 1) & 7
    if envelope_code in (1, 2, 3, 4):
        endian = "<" if data[3] & 1 else ">"
        return struct.unpack_from(endian + "4d", data, 8)
    if envelope_code != 0:
        raise ValueError("Invalid GeoPackage geometry envelope")
    wkb = data[8:]
    if len(wkb) < 5 or wkb[0] not in (0, 1):
        raise ValueError("Invalid GeoPackage geometry payload")
    endian = "<" if wkb[0] else ">"
    geometry_type = struct.unpack_from(endian + "I", wkb, 1)[0]
    if geometry_type in (1, 1001, 2001, 3001):
        x, y = struct.unpack_from(endian + "2d", wkb, 5)
        return x, x, y, y
    return _wkb_bounds(wkb)


def _wkb_bounds(wkb):
    from qgis.core import QgsGeometry

    geometry = QgsGeometry()
    if not geometry.fromWkb(wkb):
        raise ValueError("Invalid GeoPackage geometry payload")
    rectangle = geometry.boundingBox()
    return rectangle.xMinimum(), rectangle.xMaximum(), rectangle.yMinimum(), rectangle.yMaximum()
