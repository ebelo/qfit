import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests import _path  # noqa: F401

from qfit.activities.application.activity_preview import ActivityPreviewRequest
from qfit.activities.application.activity_preview_service import ActivityPreviewService


class ActivityPreviewServiceTests(unittest.TestCase):
    def test_build_result_request_delegates_to_preview_builder(self):
        request = ActivityPreviewRequest(activities=[SimpleNamespace(name="Ride")])
        service = ActivityPreviewService()

        with patch(
            "qfit.activities.application.activity_preview_service.build_activity_preview",
            return_value="preview-result",
        ) as build_preview:
            result = service.build_result_request(request)

        self.assertEqual(result, "preview-result")
        build_preview.assert_called_once_with(request)

    def test_build_result_builds_request_from_legacy_kwargs(self):
        service = ActivityPreviewService()

        with patch(
            "qfit.activities.application.activity_preview_service.build_activity_preview",
            return_value="preview-result",
        ) as build_preview:
            result = service.build_result(
                activities=[],
                activity_type="Run",
                sort_label="Name (A–Z)",
            )

        self.assertEqual(result, "preview-result")
        request = build_preview.call_args.args[0]
        self.assertIsInstance(request, ActivityPreviewRequest)
        self.assertEqual(request.activity_type, "Run")
        self.assertFalse(hasattr(request, "sort_label"))


if __name__ == "__main__":
    unittest.main()
