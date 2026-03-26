import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401

try:
    from qgis.core import QgsApplication
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None

if QgsApplication is not None:
    from qfit.gpkg_atlas_table_builders import (
        build_cover_highlight_layer,
        build_document_summary_layer,
        build_page_detail_item_layer,
        build_profile_sample_layer,
        build_toc_layer,
    )
else:  # pragma: no cover
    build_cover_highlight_layer = None
    build_document_summary_layer = None
    build_page_detail_item_layer = None
    build_profile_sample_layer = None
    build_toc_layer = None

_QGIS_APP = None


def _ensure_qgis_app():
    global _QGIS_APP
    if _QGIS_APP is None:
        _QGIS_APP = QgsApplication([], False)
        _QGIS_APP.initQgis()
    return _QGIS_APP


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class BuildDocumentSummaryLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_empty_records_returns_valid_layer(self):
        layer = build_document_summary_layer(records=[])
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.name(), "atlas_document_summary")

    def test_empty_records_has_no_features(self):
        layer = build_document_summary_layer(records=[])
        self.assertEqual(layer.featureCount(), 0)

    def test_empty_plans_shortcut_has_no_features(self):
        layer = build_document_summary_layer(plans=[])
        self.assertEqual(layer.featureCount(), 0)

    def test_no_geometry(self):
        layer = build_document_summary_layer(records=[])
        # layer type should be "No geometry"
        self.assertFalse(layer.isSpatial())


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class BuildCoverHighlightLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_empty_records_returns_valid_layer(self):
        layer = build_cover_highlight_layer(records=[])
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.name(), "atlas_cover_highlights")

    def test_empty_records_has_no_features(self):
        layer = build_cover_highlight_layer(records=[])
        self.assertEqual(layer.featureCount(), 0)

    def test_empty_plans_shortcut_has_no_features(self):
        layer = build_cover_highlight_layer(plans=[])
        self.assertEqual(layer.featureCount(), 0)


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class BuildPageDetailItemLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_empty_records_returns_valid_layer(self):
        layer = build_page_detail_item_layer([])
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.name(), "atlas_page_detail_items")

    def test_empty_records_has_no_features(self):
        layer = build_page_detail_item_layer([])
        self.assertEqual(layer.featureCount(), 0)

    def test_empty_plans_shortcut_has_no_features(self):
        layer = build_page_detail_item_layer([], plans=[])
        self.assertEqual(layer.featureCount(), 0)


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class BuildProfileSampleLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_empty_records_returns_valid_layer(self):
        layer = build_profile_sample_layer([])
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.name(), "atlas_profile_samples")

    def test_empty_records_has_no_features(self):
        layer = build_profile_sample_layer([])
        self.assertEqual(layer.featureCount(), 0)

    def test_empty_plans_shortcut_has_no_features(self):
        layer = build_profile_sample_layer([], plans=[])
        self.assertEqual(layer.featureCount(), 0)


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class BuildTocLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    def test_empty_records_returns_valid_layer(self):
        layer = build_toc_layer([])
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.name(), "atlas_toc_entries")

    def test_empty_records_has_no_features(self):
        layer = build_toc_layer([])
        self.assertEqual(layer.featureCount(), 0)

    def test_empty_plans_shortcut_has_no_features(self):
        layer = build_toc_layer([], plans=[])
        self.assertEqual(layer.featureCount(), 0)


if __name__ == "__main__":
    unittest.main()
