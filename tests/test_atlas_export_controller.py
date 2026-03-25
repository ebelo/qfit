import unittest
from unittest.mock import MagicMock

from tests import _path  # noqa: F401
from qfit.atlas.export_controller import AtlasExportController, AtlasExportValidationError


class ValidateAtlasLayerTests(unittest.TestCase):
    def test_raises_when_layer_is_none(self):
        with self.assertRaises(AtlasExportValidationError):
            AtlasExportController.validate_atlas_layer(None)

    def test_raises_when_layer_is_empty(self):
        layer = MagicMock()
        layer.featureCount.return_value = 0
        with self.assertRaises(AtlasExportValidationError):
            AtlasExportController.validate_atlas_layer(layer)

    def test_accepts_layer_with_features(self):
        layer = MagicMock()
        layer.featureCount.return_value = 5
        AtlasExportController.validate_atlas_layer(layer)


class NormalizePdfPathTests(unittest.TestCase):
    def test_raises_when_path_is_empty(self):
        with self.assertRaises(AtlasExportValidationError):
            AtlasExportController.normalize_pdf_path("")

    def test_appends_pdf_extension(self):
        path, changed = AtlasExportController.normalize_pdf_path("/tmp/atlas")
        self.assertEqual(path, "/tmp/atlas.pdf")
        self.assertTrue(changed)

    def test_keeps_existing_pdf_extension(self):
        path, changed = AtlasExportController.normalize_pdf_path("/tmp/atlas.pdf")
        self.assertEqual(path, "/tmp/atlas.pdf")
        self.assertFalse(changed)

    def test_case_insensitive_pdf_check(self):
        path, changed = AtlasExportController.normalize_pdf_path("/tmp/atlas.PDF")
        self.assertEqual(path, "/tmp/atlas.PDF")
        self.assertFalse(changed)
