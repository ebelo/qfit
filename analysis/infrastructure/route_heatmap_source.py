"""Read-only, WAL-aware snapshot of selected GeoPackage tracks for a worker."""
import sqlite3
from contextlib import closing
from pathlib import Path

from ..application.route_heatmap import add_track_fingerprint, heatmap_fingerprint
from ..domain.route_density import check_cancelled


def source_revision(path):
    """Cheap stale-result guard, including WAL writes while QGIS holds the file."""
    values = []
    for candidate in (Path(path), Path(str(path) + "-wal")):
        try:
            info = candidate.stat()
            values.extend((info.st_size, info.st_mtime_ns))
        except FileNotFoundError:
            values.extend((0, 0))
    return tuple(values)


def snapshot_tracks(request, directory, cancelled):
    from osgeo import osr

    check_cancelled(cancelled)
    source_uri = Path(request.source_path).resolve().as_uri() + "?mode=ro"
    snapshot = directory / "tracks.sqlite"
    with closing(sqlite3.connect(source_uri, uri=True)) as source, closing(sqlite3.connect(snapshot)) as target, source, target:
        source.execute("BEGIN")
        meta = source.execute(
            "SELECT column_name, srs_id FROM gpkg_geometry_columns WHERE table_name = 'activity_tracks'"
        ).fetchone()
        if meta is None:
            raise ValueError("The selected GeoPackage has no activity tracks")
        column, srs_id = meta
        definition = source.execute(
            "SELECT definition FROM gpkg_spatial_ref_sys WHERE srs_id = ?", (srs_id,)
        ).fetchone()
        if definition is None:
            raise ValueError("Heatmap tracks require a stored coordinate system")
        definition = definition[0]
        crs = osr.SpatialReference()
        if crs.ImportFromWkt(definition) != 0:
            raise ValueError("Heatmap tracks require a valid coordinate system")
        crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        geographic = osr.SpatialReference()
        geographic.ImportFromEPSG(4326)
        geographic.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(crs, geographic)
        fingerprint = heatmap_fingerprint(request.parameters, crs.ExportToWkt())
        target.execute("CREATE TABLE tracks (source TEXT, activity_id TEXT, wkb BLOB)")
        geometry_column = '"' + column.replace('"', '""') + '"'
        query = f'SELECT source, source_activity_id, {geometry_column} FROM activity_tracks'
        if request.subset:
            query += " WHERE " + request.subset
        query += " ORDER BY source, source_activity_id"
        bounds = None
        for identity_source, activity_id, blob in source.execute(query):
            check_cancelled(cancelled)
            geometry = decode_geopackage_geometry(blob)
            if geometry is None or geometry.IsEmpty():
                continue
            wkb = bytes(geometry.ExportToWkb())
            identity = (str(identity_source), str(activity_id))
            add_track_fingerprint(fingerprint, identity, wkb)
            target.execute("INSERT INTO tracks VALUES (?, ?, ?)", (*identity, wkb))
            geographic_geometry = geometry.Clone()
            if geographic_geometry.Transform(transform) != 0:
                raise ValueError("Could not transform a heatmap track")
            envelope = geographic_geometry.GetEnvelope()
            bounds = envelope if bounds is None else (
                min(bounds[0], envelope[0]), max(bounds[1], envelope[1]),
                min(bounds[2], envelope[2]), max(bounds[3], envelope[3]),
            )
        count = target.execute("SELECT COUNT(*) FROM (SELECT DISTINCT source, activity_id FROM tracks)").fetchone()[0]
    return snapshot, fingerprint.hexdigest(), crs, bounds, count


def decode_geopackage_geometry(blob):
    from osgeo import ogr

    if not blob:
        return None
    if bytes(blob[:2]) != b"GP" or len(blob) < 8:
        raise ValueError("Invalid GeoPackage track geometry")
    flags = blob[3]
    if flags & 16:
        return None
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    envelope_size = envelope_sizes.get((flags >> 1) & 7)
    if envelope_size is None:
        raise ValueError("Invalid GeoPackage geometry envelope")
    geometry = ogr.CreateGeometryFromWkb(bytes(blob[8 + envelope_size:]))
    if geometry is None:
        raise ValueError("Could not decode a heatmap track")
    return geometry


def projected_crs(bounds):
    """Regional tracks use metres in UTM; widely separated tracks use Mercator."""
    from osgeo import osr

    lon = (bounds[0] + bounds[1]) / 2
    lat = (bounds[2] + bounds[3]) / 2
    regional = bounds[1] - bounds[0] <= 12 and bounds[3] - bounds[2] <= 12 and -80 <= lat <= 80
    zone = min(60, max(1, int((lon + 180) // 6) + 1))
    epsg = (32600 if lat >= 0 else 32700) + zone if regional else 3857
    crs = osr.SpatialReference()
    crs.ImportFromEPSG(epsg)
    crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return crs, f"EPSG:{epsg}"


def projected_parts(snapshot, source_crs, target_crs, cancelled):
    from itertools import groupby
    from osgeo import ogr, osr

    transform = osr.CoordinateTransformation(source_crs, target_crs)
    with closing(sqlite3.connect(snapshot)) as connection:
        rows = connection.execute("SELECT source, activity_id, wkb FROM tracks ORDER BY source, activity_id")
        for identity, group in groupby(rows, key=lambda row: row[:2]):
            parts = []
            for _, _, wkb in group:
                check_cancelled(cancelled)
                geometry = ogr.CreateGeometryFromWkb(wkb)
                if geometry.Transform(transform) != 0:
                    raise ValueError("Could not project a heatmap track")
                parts.extend(_line_parts(geometry))
            yield identity, parts


def _line_parts(geometry):
    from osgeo import ogr

    kind = ogr.GT_Flatten(geometry.GetGeometryType())
    if kind == ogr.wkbLineString:
        return [[(p[0], p[1]) for p in geometry.GetPoints()]]
    if kind == ogr.wkbMultiLineString:
        return [part for i in range(geometry.GetGeometryCount()) for part in _line_parts(geometry.GetGeometryRef(i))]
    raise ValueError("Heatmap input must contain line tracks")
