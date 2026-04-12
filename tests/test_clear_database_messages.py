import unittest

from tests import _path  # noqa: F401

from qfit.activities.application.clear_database_messages import (
    build_clear_database_confirmation_title,
    build_clear_database_delete_failure_error_title,
    build_clear_database_delete_failure_status,
    build_clear_database_load_workflow_error_title,
    build_missing_output_path_error,
)


class ClearDatabaseMessagesTests(unittest.TestCase):
    def test_build_clear_database_confirmation_title(self):
        self.assertEqual(
            build_clear_database_confirmation_title(),
            "Clear database",
        )

    def test_build_clear_database_delete_failure_error_title(self):
        self.assertEqual(
            build_clear_database_delete_failure_error_title(),
            "Could not delete database",
        )

    def test_build_clear_database_delete_failure_status(self):
        self.assertEqual(
            build_clear_database_delete_failure_status(),
            "Failed to delete the GeoPackage file",
        )

    def test_build_clear_database_load_workflow_error_title(self):
        self.assertEqual(
            build_clear_database_load_workflow_error_title(),
            "No database path",
        )

    def test_build_missing_output_path_error(self):
        self.assertEqual(
            build_missing_output_path_error(),
            ("No database path", "Set a GeoPackage output path first."),
        )


if __name__ == "__main__":
    unittest.main()
