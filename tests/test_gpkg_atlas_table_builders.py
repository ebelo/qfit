import importlib.util
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401
from tests.qgis_app import get_shared_qgis_app

try:
    _REAL_QGIS_PRESENT = importlib.util.find_spec("qgis") is not None
except ValueError:
    _REAL_QGIS_PRESENT = any(
        os.path.isdir(os.path.join(p, "qgis")) for p in sys.path if p
    )

try:
    from qgis.core import QgsApplication
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None

if QgsApplication is not None and _REAL_QGIS_PRESENT:
    from qfit.activities.infrastructure.geopackage.gpkg_atlas_table_builders import (
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

def _ensure_qgis_app():
    if not _REAL_QGIS_PRESENT:
        raise unittest.SkipTest("QGIS Python bindings are not available")

    global QgsApplication
    global build_cover_highlight_layer
    global build_document_summary_layer
    global build_page_detail_item_layer
    global build_profile_sample_layer
    global build_toc_layer
    if QgsApplication is None and _REAL_QGIS_PRESENT:
        for module_name in [
            "qgis.core",
            "qgis.gui",
            "qgis.PyQt",
            "qgis.PyQt.QtCore",
            "qgis.PyQt.QtGui",
            "qgis",
        ]:
            sys.modules.pop(module_name, None)
        from qgis.core import QgsApplication as RealQgsApplication  # type: ignore

        QgsApplication = RealQgsApplication
    if build_document_summary_layer is None:
        sys.modules.pop(
            "qfit.activities.infrastructure.geopackage.gpkg_atlas_table_builders",
            None,
        )
        from qfit.activities.infrastructure.geopackage.gpkg_atlas_table_builders import (
            build_cover_highlight_layer as real_build_cover_highlight_layer,
            build_document_summary_layer as real_build_document_summary_layer,
            build_page_detail_item_layer as real_build_page_detail_item_layer,
            build_profile_sample_layer as real_build_profile_sample_layer,
            build_toc_layer as real_build_toc_layer,
        )

        build_cover_highlight_layer = real_build_cover_highlight_layer
        build_document_summary_layer = real_build_document_summary_layer
        build_page_detail_item_layer = real_build_page_detail_item_layer
        build_profile_sample_layer = real_build_profile_sample_layer
        build_toc_layer = real_build_toc_layer
    return get_shared_qgis_app(QgsApplication)


@unittest.skipIf(not _REAL_QGIS_PRESENT, "QGIS Python bindings are not available")
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


@unittest.skipIf(not _REAL_QGIS_PRESENT, "QGIS Python bindings are not available")
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


@unittest.skipIf(not _REAL_QGIS_PRESENT, "QGIS Python bindings are not available")
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


@unittest.skipIf(not _REAL_QGIS_PRESENT, "QGIS Python bindings are not available")
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


@unittest.skipIf(not _REAL_QGIS_PRESENT, "QGIS Python bindings are not available")
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
