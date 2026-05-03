import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests import _path  # noqa: F401

from qfit.activities.application import build_activity_preview_request
from qfit.ui.application import (
    DockActivityWorkflowCoordinator,
    DockFetchCompletionRequest,
    DockFetchRequest,
)


class DockActivityWorkflowCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.sync_controller = MagicMock()
        self.fetch_result_service = MagicMock()
        self.activity_preview_service = MagicMock()
        self.coordinator = DockActivityWorkflowCoordinator(
            sync_controller=self.sync_controller,
            fetch_result_service=self.fetch_result_service,
            activity_preview_service=self.activity_preview_service,
        )

    def test_build_fetch_task_uses_defaults_when_advanced_fetch_is_disabled(self):
        self.sync_controller.build_fetch_task_request.return_value = "fetch-request"
        self.sync_controller.build_fetch_task.return_value = "fetch-task"

        result = self.coordinator.build_fetch_task(
            DockFetchRequest(
                client_id="cid",
                client_secret="secret",
                refresh_token="token",
                cache=object(),
                detailed_route_strategy="missing",
                on_finished=object(),
                advanced_fetch_enabled=False,
                detailed_streams_checked=True,
                per_page_value=50,
                max_pages_value=7,
                max_detailed_activities_value=12,
            )
        )

        self.assertEqual(result, "fetch-task")
        self.sync_controller.build_fetch_task_request.assert_called_once()
        _, kwargs = self.sync_controller.build_fetch_task_request.call_args
        self.assertEqual(kwargs["per_page"], 200)
        self.assertEqual(kwargs["max_pages"], 0)
        self.assertFalse(kwargs["use_detailed_streams"])
        self.assertEqual(kwargs["max_detailed_activities"], 25)
        self.assertIsNone(kwargs["before"])
        self.assertIsNone(kwargs["after"])
        self.sync_controller.build_fetch_task.assert_called_once_with("fetch-request")

    def test_build_fetch_task_respects_advanced_fetch_values(self):
        self.sync_controller.build_fetch_task_request.return_value = "fetch-request"
        self.sync_controller.build_fetch_task.return_value = "fetch-task"

        self.coordinator.build_fetch_task(
            DockFetchRequest(
                client_id="cid",
                client_secret="secret",
                refresh_token="token",
                cache=object(),
                detailed_route_strategy="all",
                on_finished=object(),
                advanced_fetch_enabled=True,
                detailed_streams_checked=True,
                per_page_value=75,
                max_pages_value=4,
                max_detailed_activities_value=30,
                before_epoch=200,
                after_epoch=100,
            )
        )

        _, kwargs = self.sync_controller.build_fetch_task_request.call_args
        self.assertEqual(kwargs["per_page"], 75)
        self.assertEqual(kwargs["max_pages"], 4)
        self.assertTrue(kwargs["use_detailed_streams"])
        self.assertEqual(kwargs["max_detailed_activities"], 30)
        self.assertEqual(kwargs["before"], 200)
        self.assertEqual(kwargs["after"], 100)

    def test_build_fetch_completion_result_returns_cancelled_status_without_preview(self):
        fetch_result = SimpleNamespace(cancelled=True, error=None, status_text="Fetch cancelled.")
        self.fetch_result_service.build_request.return_value = "fetch-request"
        self.fetch_result_service.build_result_request.return_value = fetch_result

        result = self.coordinator.build_fetch_completion_result(
            DockFetchCompletionRequest(cancelled=True)
        )

        self.assertTrue(result.cancelled)
        self.assertEqual(result.status_text, "Fetch cancelled.")
        self.activity_preview_service.build_result_request.assert_not_called()

    def test_build_fetch_completion_result_returns_error_without_preview(self):
        fetch_result = SimpleNamespace(cancelled=False, error="boom", status_text="Strava fetch failed")
        self.fetch_result_service.build_request.return_value = "fetch-request"
        self.fetch_result_service.build_result_request.return_value = fetch_result

        result = self.coordinator.build_fetch_completion_result(
            DockFetchCompletionRequest(error="boom")
        )

        self.assertEqual(result.error_title, "Strava import failed")
        self.assertEqual(result.error_message, "boom")
        self.assertEqual(result.status_text, "Strava fetch failed")
        self.activity_preview_service.build_result_request.assert_not_called()

    def test_build_fetch_completion_result_builds_activity_options_and_preview(self):
        activities = ["a1", "a2"]
        fetch_result = SimpleNamespace(
            cancelled=False,
            error=None,
            activities=activities,
            metadata={"today_str": "2026-04-16", "detailed_count": 1},
            today_str="2026-04-16",
            count_label_text="2 activities loaded",
            status_text="Fetched 2 activities",
        )
        preview_request = build_activity_preview_request(
            activities=["old"],
            activity_type="Ride",
        )
        preview_result = SimpleNamespace(
            query_summary_text="2 activities",
            preview_text="first\nsecond",
            fetched_activities=activities,
        )
        self.fetch_result_service.build_request.return_value = "fetch-request"
        self.fetch_result_service.build_result_request.return_value = fetch_result
        self.activity_preview_service.build_result_request.return_value = preview_result

        result = self.coordinator.build_fetch_completion_result(
            DockFetchCompletionRequest(
                activities=activities,
                provider=object(),
                current_activity_type="Ride",
                preview_request=preview_request,
            )
        )

        self.assertEqual(result.activities, activities)
        self.assertEqual(result.metadata, {"today_str": "2026-04-16", "detailed_count": 1})
        self.assertEqual(result.today_str, "2026-04-16")
        self.assertEqual(result.count_label_text, "2 activities loaded")
        self.assertEqual(result.status_text, "Fetched 2 activities")
        self.assertIsNotNone(result.activity_type_options)
        self.assertEqual(result.activity_type_options.options, ["All"])
        self.assertEqual(result.activity_type_options.selected_value, "All")
        self.assertIs(result.preview_result, preview_result)
        preview_call = self.activity_preview_service.build_result_request.call_args.args[0]
        self.assertEqual(preview_call.activities, activities)
        self.assertEqual(preview_call.activity_type, "All")

    def test_build_preview_result_delegates_to_preview_service(self):
        preview_request = object()
        preview_result = object()
        self.activity_preview_service.build_result_request.return_value = preview_result

        result = self.coordinator.build_preview_result(preview_request)

        self.assertIs(result, preview_result)
        self.activity_preview_service.build_result_request.assert_called_once_with(preview_request)


if __name__ == "__main__":
    unittest.main()
