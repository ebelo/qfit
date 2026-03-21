import unittest

from tests import _path  # noqa: F401
from qfit.polyline_utils import decode_polyline


class DecodePolylineTests(unittest.TestCase):
    def test_decodes_known_google_example(self):
        encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
        self.assertEqual(
            decode_polyline(encoded),
            [
                (38.5, -120.2),
                (40.7, -120.95),
                (43.252, -126.453),
            ],
        )

    def test_returns_empty_list_for_empty_input(self):
        self.assertEqual(decode_polyline(""), [])
        self.assertEqual(decode_polyline(None), [])

    def test_returns_empty_list_for_truncated_input(self):
        self.assertEqual(decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvx"), [])


if __name__ == "__main__":
    unittest.main()
