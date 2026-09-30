import struct
import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

from tests import _path  # noqa: F401
from qfit.activities.infrastructure.geopackage.activity_name_publication import _geometry_value


class NamePublicationGeometryTests(unittest.TestCase):
    def test_point_bounds_use_binary_coordinates_without_qgis(self):
        for endian, flag in (("<", 1), (">", 0)):
            for geometry_type in (1, 1001, 2001, 3001):
                with self.subTest(endian=endian, geometry_type=geometry_type):
                    header = b"GP\x00" + bytes([flag]) + struct.pack(endian + "i", 4326)
                    wkb = bytes([flag]) + struct.pack(endian + "I2d", geometry_type, 6.5, 46.5)
                    blob = header + wkb
                    with patch.dict(sys.modules, {"qgis.core": None}):
                        self.assertEqual(_geometry_value(blob, "empty"), 0)
                        self.assertEqual(_geometry_value(blob, "xMinimum"), 6.5)
                        self.assertEqual(_geometry_value(blob, "xMaximum"), 6.5)
                        self.assertEqual(_geometry_value(blob, "yMinimum"), 46.5)
                        self.assertEqual(_geometry_value(blob, "yMaximum"), 46.5)

    def test_envelope_bounds_and_empty_geometry(self):
        for code in (1, 2, 3, 4):
            header = b"GP\x00" + bytes([1 | (code << 1)]) + struct.pack("<i", 4326)
            blob = header + struct.pack("<4d", 1, 2, 3, 4)
            self.assertEqual(_geometry_value(blob, "xMinimum"), 1)
            self.assertEqual(_geometry_value(blob, "yMaximum"), 4)
        empty = b"GP\x00\x11" + struct.pack("<i", 4326)
        self.assertEqual(_geometry_value(empty, "empty"), 1)
        self.assertIsNone(_geometry_value(empty, "xMinimum"))
        self.assertIsNone(_geometry_value(None, "empty"))

    def test_invalid_header_envelope_and_wkb_are_rejected(self):
        blobs = (b"bad", b"GP\x00\x0b" + struct.pack("<i", 4326),
                 b"GP\x00\x01" + struct.pack("<i", 4326) + b"bad")
        for blob in blobs:
            with self.subTest(blob=blob), self.assertRaises(ValueError):
                _geometry_value(blob, "xMinimum")

    def test_nonpoint_without_envelope_uses_real_geometry_adapter(self):
        core = ModuleType("qgis.core")
        geometry = Mock()
        geometry.fromWkb.return_value = True
        bounds = geometry.boundingBox.return_value
        bounds.xMinimum.return_value = 1
        bounds.xMaximum.return_value = 2
        bounds.yMinimum.return_value = 3
        bounds.yMaximum.return_value = 4
        core.QgsGeometry = Mock(return_value=geometry)
        wkb = b"\x01" + struct.pack("<I", 2)
        blob = b"GP\x00\x01" + struct.pack("<i", 4326) + wkb
        with patch.dict(sys.modules, {"qgis.core": core}):
            self.assertEqual(_geometry_value(blob, "yMinimum"), 3)
            geometry.fromWkb.assert_called_once_with(wkb)
            geometry.fromWkb.return_value = False
            with self.assertRaises(ValueError):
                _geometry_value(blob, "xMinimum")
