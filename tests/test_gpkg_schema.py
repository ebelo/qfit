import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _path  # noqa: F401

try:
    from qgis.core import QgsApplication
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    QgsApplication = None

if QgsApplication is not None:
    from qfit.gpkg_schema import (
        ATLAS_FIELDS,
        COVER_HIGHLIGHT_FIELDS,
        DOCUMENT_SUMMARY_FIELDS,
        GPKG_LAYER_SCHEMA,
        PAGE_DETAIL_ITEM_FIELDS,
        POINT_FIELDS,
        PROFILE_SAMPLE_FIELDS,
        START_FIELDS,
        TOC_FIELDS,
        TRACK_FIELDS,
        make_qgs_fields,
    )
    from qfit.sync_repository import REGISTRY_TABLE, SYNC_STATE_TABLE
else:  # pragma: no cover
    ATLAS_FIELDS = None
    COVER_HIGHLIGHT_FIELDS = None
    DOCUMENT_SUMMARY_FIELDS = None
    GPKG_LAYER_SCHEMA = None
    PAGE_DETAIL_ITEM_FIELDS = None
    POINT_FIELDS = None
    PROFILE_SAMPLE_FIELDS = None
    START_FIELDS = None
    TOC_FIELDS = None
    TRACK_FIELDS = None
    make_qgs_fields = None
    REGISTRY_TABLE = None
    SYNC_STATE_TABLE = None

_QGIS_APP = None


def _ensure_qgis_app():
    global _QGIS_APP
    if _QGIS_APP is None:
        _QGIS_APP = QgsApplication([], False)
        _QGIS_APP.initQgis()
    return _QGIS_APP


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings are not available")
class GpkgSchemaFieldsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_qgis_app()

    # ------------------------------------------------------------------
    # Field-definition constants
    # ------------------------------------------------------------------

    def _assert_unique_field_names(self, field_defs, label):
        names = [name for name, _ in field_defs]
        self.assertEqual(len(names), len(set(names)), f"{label} has duplicate field names: {names}")

    def test_track_fields_unique(self):
        self._assert_unique_field_names(TRACK_FIELDS, "TRACK_FIELDS")

    def test_start_fields_unique(self):
        self._assert_unique_field_names(START_FIELDS, "START_FIELDS")

    def test_point_fields_unique(self):
        self._assert_unique_field_names(POINT_FIELDS, "POINT_FIELDS")

    def test_atlas_fields_unique(self):
        self._assert_unique_field_names(ATLAS_FIELDS, "ATLAS_FIELDS")

    def test_document_summary_fields_unique(self):
        self._assert_unique_field_names(DOCUMENT_SUMMARY_FIELDS, "DOCUMENT_SUMMARY_FIELDS")

    def test_cover_highlight_fields_unique(self):
        self._assert_unique_field_names(COVER_HIGHLIGHT_FIELDS, "COVER_HIGHLIGHT_FIELDS")

    def test_page_detail_item_fields_unique(self):
        self._assert_unique_field_names(PAGE_DETAIL_ITEM_FIELDS, "PAGE_DETAIL_ITEM_FIELDS")

    def test_profile_sample_fields_unique(self):
        self._assert_unique_field_names(PROFILE_SAMPLE_FIELDS, "PROFILE_SAMPLE_FIELDS")

    def test_toc_fields_unique(self):
        self._assert_unique_field_names(TOC_FIELDS, "TOC_FIELDS")

    # ------------------------------------------------------------------
    # GPKG_LAYER_SCHEMA structure
    # ------------------------------------------------------------------

    def test_schema_contains_sync_tables(self):
        self.assertIn(REGISTRY_TABLE, GPKG_LAYER_SCHEMA)
        self.assertIn(SYNC_STATE_TABLE, GPKG_LAYER_SCHEMA)

    def test_schema_contains_expected_layer_names(self):
        expected = {
            "activity_tracks",
            "activity_starts",
            "activity_points",
            "activity_atlas_pages",
            "atlas_document_summary",
            "atlas_cover_highlights",
            "atlas_page_detail_items",
            "atlas_profile_samples",
            "atlas_toc_entries",
        }
        self.assertTrue(expected.issubset(GPKG_LAYER_SCHEMA.keys()))

    def test_schema_layer_entries_have_geometry_key(self):
        for name, entry in GPKG_LAYER_SCHEMA.items():
            self.assertIn("geometry", entry, f"{name!r} entry is missing 'geometry' key")

    def test_schema_layer_entries_have_kind_key(self):
        for name, entry in GPKG_LAYER_SCHEMA.items():
            self.assertIn("kind", entry, f"{name!r} entry is missing 'kind' key")

    def test_schema_field_lists_match_constants(self):
        pairs = [
            ("activity_tracks", TRACK_FIELDS),
            ("activity_starts", START_FIELDS),
            ("activity_points", POINT_FIELDS),
            ("activity_atlas_pages", ATLAS_FIELDS),
            ("atlas_document_summary", DOCUMENT_SUMMARY_FIELDS),
            ("atlas_cover_highlights", COVER_HIGHLIGHT_FIELDS),
            ("atlas_page_detail_items", PAGE_DETAIL_ITEM_FIELDS),
            ("atlas_profile_samples", PROFILE_SAMPLE_FIELDS),
            ("atlas_toc_entries", TOC_FIELDS),
        ]
        for layer_name, field_defs in pairs:
            expected = [name for name, _ in field_defs]
            self.assertEqual(
                GPKG_LAYER_SCHEMA[layer_name]["fields"],
                expected,
                f"Field list mismatch for {layer_name!r}",
            )

    # ------------------------------------------------------------------
    # make_qgs_fields
    # ------------------------------------------------------------------

    def test_make_qgs_fields_returns_correct_count(self):
        from qgis.PyQt.QtCore import QVariant

        field_defs = [("distance_m", QVariant.Double), ("name", QVariant.String)]
        fields = make_qgs_fields(field_defs)
        self.assertEqual(fields.count(), 2)

    def test_make_qgs_fields_preserves_names(self):
        from qgis.PyQt.QtCore import QVariant

        field_defs = [("distance_m", QVariant.Double), ("name", QVariant.String)]
        fields = make_qgs_fields(field_defs)
        self.assertEqual(fields.at(0).name(), "distance_m")
        self.assertEqual(fields.at(1).name(), "name")

    def test_make_qgs_fields_empty(self):
        fields = make_qgs_fields([])
        self.assertEqual(fields.count(), 0)

    def test_make_qgs_fields_for_track_layer(self):
        fields = make_qgs_fields(TRACK_FIELDS)
        self.assertEqual(fields.count(), len(TRACK_FIELDS))
        self.assertGreaterEqual(fields.indexOf("source"), 0)
        self.assertGreaterEqual(fields.indexOf("distance_m"), 0)


if __name__ == "__main__":
    unittest.main()
