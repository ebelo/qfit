import unittest

from tests import _path  # noqa: F401

from qfit.activities.application.clear_database_messages import build_missing_output_path_error


class ClearDatabaseMessagesTests(unittest.TestCase):
    def test_build_missing_output_path_error(self):
        self.assertEqual(
            build_missing_output_path_error(),
            ("No database path", "Set a GeoPackage output path first."),
        )


if __name__ == "__main__":
    unittest.main()
