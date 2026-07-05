import os
import sqlite3
import tempfile
import unittest

from tests import _path  # noqa: F401

from qfit.activities.application.storage_selection import (
    EXISTING_QFIT_DATABASE_STATUS,
    NON_QFIT_GEOPACKAGE_STATUS,
    PATH_CHANGED_STATUS,
    ROUTE_ONLY_QFIT_DATABASE_STATUS,
    STORAGE_INTENT_EXISTING,
    STORAGE_INTENT_INVALID,
    STORAGE_INTENT_NEW,
    StoragePathProbe,
    normalize_storage_path,
    resolve_storage_selection,
)


class StorageSelectionTests(unittest.TestCase):
    def test_empty_path_is_invalid(self):
        result = resolve_storage_selection("")

        self.assertEqual(result.intent, STORAGE_INTENT_INVALID)
        self.assertFalse(result.can_load)
        self.assertFalse(result.can_store)
        self.assertIn("Choose a GeoPackage path", result.validation_reason)

    def test_bare_basename_gets_gpkg_extension(self):
        result = resolve_storage_selection(
            "qfit_test",
            probe=StoragePathProbe(
                path_exists=lambda path: path == ".",
                is_dir=lambda path: path == ".",
            ),
        )

        self.assertEqual(result.intent, STORAGE_INTENT_NEW)
        self.assertEqual(result.normalized_path, "qfit_test.gpkg")
        self.assertFalse(result.can_load)
        self.assertTrue(result.can_store)

    def test_explicit_gpkg_path_is_preserved(self):
        self.assertEqual(
            normalize_storage_path("/tmp/qfit_test.gpkg"),
            "/tmp/qfit_test.gpkg",
        )

    def test_existing_qfit_geopackage_can_load_and_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "existing.gpkg")
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE activity_registry (id TEXT)")

            result = resolve_storage_selection(path)

        self.assertEqual(result.intent, STORAGE_INTENT_EXISTING)
        self.assertTrue(result.can_load)
        self.assertTrue(result.can_store)
        self.assertEqual(result.status_text, EXISTING_QFIT_DATABASE_STATUS)

    def test_existing_qfit_geopackage_path_allows_uri_metacharacters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "existing?test#1.gpkg")
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE activity_registry (id TEXT)")

            result = resolve_storage_selection(path)

        self.assertEqual(result.intent, STORAGE_INTENT_EXISTING)
        self.assertTrue(result.can_load)
        self.assertTrue(result.can_store)

    def test_existing_non_qfit_geopackage_is_specific_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "other.gpkg")
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE gpkg_contents (id TEXT)")

            result = resolve_storage_selection(path)

        self.assertEqual(result.intent, STORAGE_INTENT_EXISTING)
        self.assertFalse(result.can_load)
        self.assertFalse(result.can_store)
        self.assertEqual(result.status_text, NON_QFIT_GEOPACKAGE_STATUS)
        self.assertIn("qfit's activity schema", result.validation_reason)

    def test_existing_route_only_qfit_geopackage_can_store_activities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "routes.gpkg")
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE route_registry (id TEXT)")

            result = resolve_storage_selection(path)

        self.assertEqual(result.intent, STORAGE_INTENT_EXISTING)
        self.assertFalse(result.can_load)
        self.assertTrue(result.can_store)
        self.assertEqual(result.status_text, ROUTE_ONLY_QFIT_DATABASE_STATUS)

    def test_missing_parent_directory_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "missing", "qfit.gpkg")

            result = resolve_storage_selection(path)

        self.assertEqual(result.intent, STORAGE_INTENT_INVALID)
        self.assertIn("parent directory", result.validation_reason)

    def test_switching_from_loaded_database_marks_layers_stale(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_path = os.path.join(tmpdir, "old.gpkg")
            new_path = os.path.join(tmpdir, "new.gpkg")
            for path in (old_path, new_path):
                with sqlite3.connect(path) as connection:
                    connection.execute("CREATE TABLE activity_registry (id TEXT)")

            result = resolve_storage_selection(
                new_path,
                loaded_dataset_path=old_path,
            )

        self.assertTrue(result.can_load)
        self.assertEqual(result.status_text, PATH_CHANGED_STATUS)


if __name__ == "__main__":
    unittest.main()
