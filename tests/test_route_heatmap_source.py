import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests import _path  # noqa: F401
from qfit.analysis.application.route_heatmap import RouteHeatmapRequest
from qfit.analysis.domain.route_density import HeatmapCancelled
from qfit.analysis.infrastructure.route_heatmap_source import (
    snapshot_tracks, source_revision, decode_geopackage_geometry, projected_crs, projected_parts, _line_parts,
)


class _Crs:
    def ImportFromWkt(self, text):
        self.text = text
        return 1 if text == "bad" else 0

    def ImportFromEPSG(self, value):
        self.text = str(value)
        return 0

    def SetAxisMappingStrategy(self, value):
        self.axis = value

    def ExportToWkt(self):
        return self.text


class _Geometry:
    def __init__(self, points=None, kind=2, children=()):
        self.points = [tuple(p) for p in points] if points else [(7.3, 46.2), (7.4, 46.3)]
        self.kind = kind
        self.children = children
        self.failure = False

    def IsEmpty(self):
        return False

    def ExportToWkb(self):
        return json.dumps(self.points).encode()

    def Clone(self):
        return self

    def Transform(self, transform):
        return int(self.failure)

    def GetEnvelope(self):
        xs, ys = zip(*self.points)
        return min(xs), max(xs), min(ys), max(ys)

    def GetGeometryType(self):
        return self.kind

    def GetPoints(self):
        return self.points

    def GetGeometryCount(self):
        return len(self.children)

    def GetGeometryRef(self, index):
        return self.children[index]


def _decode(wkb):
    return _Geometry(json.loads(bytes(wkb))) if wkb else None


class RouteHeatmapSourceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "tracks.gpkg"
        self.geometry = _Geometry()
        blob = b"GP\x00\x01" + b"\x00" * 4 + self.geometry.ExportToWkb()
        with sqlite3.connect(self.source) as db:
            db.executescript("CREATE TABLE gpkg_geometry_columns(table_name, column_name, srs_id);"
                             "INSERT INTO gpkg_geometry_columns VALUES('activity_tracks', 'geom', 4326);"
                             "CREATE TABLE gpkg_spatial_ref_sys(srs_id, definition);"
                             "INSERT INTO gpkg_spatial_ref_sys VALUES(4326, 'geographic');"
                             "CREATE TABLE activity_tracks(source, source_activity_id, name, geom);")
            db.executemany("INSERT INTO activity_tracks VALUES('test', ?, 'Name', ?)", [('1', blob), ('2', blob)])
        self.request = RouteHeatmapRequest(str(self.source), "", str(self.root / 'cache'))
        self.ogr = SimpleNamespace(CreateGeometryFromWkb=_decode, GT_Flatten=lambda x: x,
                                   wkbLineString=2, wkbMultiLineString=5)
        self.osr = SimpleNamespace(SpatialReference=_Crs, OAMS_TRADITIONAL_GIS_ORDER=0,
                                   CoordinateTransformation=lambda source, target: (source, target))
        self.modules = patch.dict('sys.modules', {'osgeo': SimpleNamespace(ogr=self.ogr, osr=self.osr)})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_readonly_filtered_snapshot_fingerprint_and_grouped_projection(self):
        before = self.source.read_bytes()
        snapshot, key, crs, bounds, count = snapshot_tracks(self.request, self.root, lambda: False)
        self.assertEqual(count, 2)
        self.assertEqual(bounds, (7.3, 7.4, 46.2, 46.3))
        self.assertEqual(self.source.read_bytes(), before)
        target, authid = projected_crs(bounds)
        self.assertEqual(authid, 'EPSG:32632')
        parts = list(projected_parts(snapshot, crs, target, lambda: False))
        self.assertEqual([identity for identity, _ in parts], [('test', '1'), ('test', '2')])
        self.assertEqual(parts[0][1], [self.geometry.points])
        snapshot.unlink()
        request = RouteHeatmapRequest(str(self.source), "source_activity_id = '1'", self.request.cache_dir)
        selected = snapshot_tracks(request, self.root, lambda: False)
        self.assertEqual(selected[-1], 1)
        self.assertNotEqual(key, selected[1])
        snapshot.unlink()
        with sqlite3.connect(self.source) as db:
            db.execute("UPDATE activity_tracks SET name='Renamed'")
        self.assertEqual(snapshot_tracks(self.request, self.root, lambda: False)[1], key)
        with self.assertRaises(HeatmapCancelled):
            list(projected_parts(snapshot, crs, target, lambda: True))

    def test_missing_metadata_invalid_crs_and_transform_failure(self):
        for mutation, message in (("DELETE FROM gpkg_geometry_columns", "no activity tracks"),
                                   ("DELETE FROM gpkg_spatial_ref_sys", "stored coordinate system"),
                                   ("UPDATE gpkg_spatial_ref_sys SET definition='bad'", "valid coordinate system")):
            with self.subTest(message=message):
                copy = self.root / 'broken.gpkg'
                copy.write_bytes(self.source.read_bytes())
                with sqlite3.connect(copy) as db:
                    db.execute(mutation)
                request = RouteHeatmapRequest(str(copy), '', '')
                with self.assertRaisesRegex(ValueError, message):
                    snapshot_tracks(request, self.root, lambda: False)
        self.geometry.failure = True
        with patch.object(self.ogr, 'CreateGeometryFromWkb', return_value=self.geometry), self.assertRaisesRegex(ValueError, 'transform'):
            snapshot_tracks(self.request, self.root, lambda: False)
        (self.root / "tracks.sqlite").unlink(missing_ok=True)
        with self.assertRaises(HeatmapCancelled):
            snapshot_tracks(self.request, self.root, lambda: True)

    def test_null_empty_and_invalid_geometry_headers(self):
        self.assertIsNone(decode_geopackage_geometry(None))
        self.assertIsNone(decode_geopackage_geometry(b'GP\x00\x11' + b'\x00'*4))
        for blob in (b'not-geometry', b'GP\x00\x0b' + b'\x00'*4, b'GP\x00\x01' + b'\x00'*4):
            with self.subTest(blob=blob), self.assertRaises(ValueError):
                decode_geopackage_geometry(blob)
        envelope = b'GP\x00\x03' + b'\x00'*36 + self.geometry.ExportToWkb()
        self.assertEqual(decode_geopackage_geometry(envelope).GetPoints(), self.geometry.points)
        with sqlite3.connect(self.source) as db:
            db.execute('UPDATE activity_tracks SET geom=NULL')
        self.assertEqual(snapshot_tracks(self.request, self.root, lambda: False)[-1], 0)

    def test_crs_choice_multipart_errors_and_source_wal_revision(self):
        for bounds, expected in (((7, 8, 46, 47), 'EPSG:32632'), ((18, 19, -34, -33), 'EPSG:32734'),
                                  ((-74, 8, 40, 47), 'EPSG:3857'), ((0, 1, 85, 86), 'EPSG:3857')):
            self.assertEqual(projected_crs(bounds)[1], expected)
        multi = _Geometry(kind=5, children=[self.geometry, self.geometry])
        self.assertEqual(_line_parts(multi), [self.geometry.points, self.geometry.points])
        with self.assertRaises(ValueError):
            _line_parts(_Geometry(kind=1))
        snapshot, _, crs, _, _ = snapshot_tracks(self.request, self.root, lambda: False)
        self.geometry.failure = True
        with patch.object(self.ogr, 'CreateGeometryFromWkb', return_value=self.geometry), self.assertRaisesRegex(ValueError, 'project'):
            list(projected_parts(snapshot, crs, crs, lambda: False))
        revision = source_revision(self.source)
        Path(str(self.source) + '-wal').write_bytes(b'wal write')
        self.assertNotEqual(source_revision(self.source), revision)
        self.assertEqual(source_revision(self.root / 'missing'), (0, 0, 0, 0))

    def test_snapshot_and_projection_close_all_sqlite_handles(self):
        real_connect = sqlite3.connect
        opened = []
        class TrackedConnection(sqlite3.Connection):
            was_closed = False
            def close(self):
                self.was_closed = True
                super().close()
        def connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs, factory=TrackedConnection)
            opened.append(connection)
            return connection
        with patch("qfit.analysis.infrastructure.route_heatmap_source.sqlite3.connect", side_effect=connect):
            snapshot, _, crs, _, _ = snapshot_tracks(self.request, self.root, lambda: False)
            self.assertTrue(all(connection.was_closed for connection in opened))
            list(projected_parts(snapshot, crs, crs, lambda: False))
            self.assertTrue(all(connection.was_closed for connection in opened))
