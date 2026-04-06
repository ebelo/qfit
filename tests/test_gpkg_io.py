import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401

try:
    from qgis.core import QgsApplication
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None

if QgsApplication is not None:
    from qfit.activities.infrastructure.geopackage.gpkg_io import write_layer_to_gpkg
    from qfit.gpkg_io import write_layer_to_gpkg as legacy_write_layer_to_gpkg
    from qfit.gpkg_layer_builders import build_start_layer, build_track_layer
else:  # pragma: no cover
    write_layer_to_gpkg = None
    build_start_layer = None
    build_track_layer = None


_QGIS_APP = None


def _ensure_qgis_app():
    global _QGIS_APP
    if _QGIS_APP is None:
        _QGIS_APP = QgsApplication([], False)
        _QGIS_APP.initQgis()
    return _QGIS_APP


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class WriteLayerToGpkgTests(unittest.TestCase):
    def test_legacy_gpkg_io_shim_exports_same_writer(self):
        self.assertIs(legacy_write_layer_to_gpkg, write_layer_to_gpkg)

    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def _temp_gpkg(self):
        fd, path = tempfile.mkstemp(suffix=".gpkg")
        os.close(fd)
        os.unlink(path)  # remove so write starts fresh
        return path

    def test_creates_file_on_overwrite(self):
        path = self._temp_gpkg()
        try:
            layer = build_track_layer([])
            write_layer_to_gpkg(layer, path, "activity_tracks", overwrite_file=True)
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 0)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_adds_second_layer_without_overwrite(self):
        path = self._temp_gpkg()
        try:
            write_layer_to_gpkg(build_track_layer([]), path, "activity_tracks", overwrite_file=True)
            write_layer_to_gpkg(build_start_layer([]), path, "activity_starts", overwrite_file=False)
            # Both layers written; file must be non-empty and contain both layer names
            from qgis.core import QgsVectorLayer
            tracks = QgsVectorLayer(f"{path}|layername=activity_tracks", "tracks", "ogr")
            starts = QgsVectorLayer(f"{path}|layername=activity_starts", "starts", "ogr")
            self.assertTrue(tracks.isValid(), "activity_tracks layer should be valid")
            self.assertTrue(starts.isValid(), "activity_starts layer should be valid")
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_written_layer_feature_count_matches(self):
        records = [
            {
                "source": "strava",
                "source_activity_id": "42",
                "name": "Test Ride",
                "activity_type": "Ride",
                "start_date_local": "2026-03-25T08:00:00+01:00",
                "geometry_points": [(46.52, 6.62), (46.57, 6.74)],
            }
        ]
        path = self._temp_gpkg()
        try:
            layer = build_track_layer(records)
            self.assertEqual(layer.featureCount(), 1)
            write_layer_to_gpkg(layer, path, "activity_tracks", overwrite_file=True)
            from qgis.core import QgsVectorLayer
            read_back = QgsVectorLayer(f"{path}|layername=activity_tracks", "tracks", "ogr")
            self.assertTrue(read_back.isValid())
            self.assertEqual(read_back.featureCount(), 1)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_raises_on_bad_output_path(self):
        layer = build_track_layer([])
        with self.assertRaises(RuntimeError):
            write_layer_to_gpkg(layer, "/nonexistent/dir/output.gpkg", "activity_tracks", overwrite_file=True)


if __name__ == "__main__":
    unittest.main()
