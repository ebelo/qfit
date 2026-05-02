import importlib
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

from tests import _path  # noqa: F401


class _FakeQgsTask:
    CanCancel = 1

    def __init__(self, description, flags=0):
        self._cancelled = False

    def isCanceled(self):
        return self._cancelled

    def cancel(self):
        self._cancelled = True


_qgis_core = ModuleType("qgis.core")
_qgis_core.QgsTask = _FakeQgsTask
_qgis = ModuleType("qgis")
_qgis.core = _qgis_core
_ORIGINAL_QGIS = sys.modules.get("qgis")
_ORIGINAL_QGIS_CORE = sys.modules.get("qgis.core")
sys.modules["qgis"] = _qgis
sys.modules["qgis.core"] = _qgis_core

from qfit.activities.application import route_sync_task as route_sync_task_module  # noqa: E402
from qfit.providers.domain import ProviderError  # noqa: E402

route_sync_task_module = importlib.reload(route_sync_task_module)
RouteSyncTask = route_sync_task_module.RouteSyncTask

if _ORIGINAL_QGIS is not None:
    sys.modules["qgis"] = _ORIGINAL_QGIS
else:
    sys.modules.pop("qgis", None)
if _ORIGINAL_QGIS_CORE is not None:
    sys.modules["qgis.core"] = _ORIGINAL_QGIS_CORE
else:
    sys.modules.pop("qgis.core", None)


def _run_task(task):
    ok = task.run()
    task.finished(ok)
    return ok


class RouteSyncTaskTests(unittest.TestCase):
    def test_fetches_enriches_and_writes_routes(self):
        received = {}
        summary_route = SimpleNamespace(source_route_id="42", details_json={})
        detailed_route = SimpleNamespace(
            source_route_id="42",
            details_json={"gpx_geometry_status": "downloaded"},
        )
        provider = MagicMock()
        provider.source_name = "strava"
        provider.last_fetch_notice = None
        provider.last_rate_limit = {"short_remaining": 50}
        provider.fetch_routes.return_value = [summary_route]
        provider.fetch_route_detail.return_value = detailed_route
        writer = MagicMock()
        writer.write_routes.return_value = {"path": "/tmp/routes.gpkg", "sync": None}
        writer_factory = MagicMock(return_value=writer)

        task = RouteSyncTask(
            provider=provider,
            output_path="/tmp/routes.gpkg",
            per_page=25,
            max_pages=0,
            writer_factory=writer_factory,
            on_finished=lambda result, error, cancelled, provider: received.update(
                result=result,
                error=error,
                cancelled=cancelled,
                provider=provider,
            ),
        )

        self.assertTrue(_run_task(task))
        provider.fetch_routes.assert_called_once_with(per_page=25, max_pages=0)
        provider.fetch_route_detail.assert_called_once_with("42", use_gpx_geometry=True)
        writer_factory.assert_called_once_with(output_path="/tmp/routes.gpkg")
        written_routes = writer.write_routes.call_args.args[0]
        metadata = writer.write_routes.call_args.kwargs["sync_metadata"]
        self.assertEqual(written_routes, [detailed_route])
        self.assertEqual(metadata["provider"], "strava")
        self.assertEqual(metadata["fetched_count"], 1)
        self.assertEqual(metadata["detailed_count"], 1)
        self.assertTrue(metadata["is_full_sync"])
        self.assertEqual(received["result"], {"path": "/tmp/routes.gpkg", "sync": None})
        self.assertIsNone(received["error"])
        self.assertFalse(received["cancelled"])
        self.assertIs(received["provider"], provider)

    def test_returns_error_when_provider_fails(self):
        received = {}
        provider = MagicMock()
        provider.fetch_routes.side_effect = ProviderError("route scope missing")

        task = RouteSyncTask(
            provider=provider,
            output_path="/tmp/routes.gpkg",
            writer_factory=MagicMock(),
            on_finished=lambda result, error, cancelled, provider: received.update(
                result=result,
                error=error,
                cancelled=cancelled,
            ),
        )

        self.assertFalse(_run_task(task))
        self.assertIsNone(received["result"])
        self.assertEqual(received["error"], "route scope missing")
        self.assertFalse(received["cancelled"])

    def test_preserves_write_result_when_cancelled_after_persisting(self):
        received = {}
        route = SimpleNamespace(source_route_id="42", details_json={})
        provider = MagicMock()
        provider.source_name = "strava"
        provider.last_fetch_notice = None
        provider.last_rate_limit = None
        provider.fetch_routes.return_value = [route]
        writer = MagicMock()

        task = RouteSyncTask(
            provider=provider,
            output_path="/tmp/routes.gpkg",
            use_gpx_geometry=False,
            writer_factory=MagicMock(return_value=writer),
            on_finished=lambda result, error, cancelled, provider: received.update(
                result=result,
                error=error,
                cancelled=cancelled,
            ),
        )

        write_result = {"path": "/tmp/routes.gpkg", "sync": None}

        def _write_routes(_routes, sync_metadata=None):
            task.cancel()
            return write_result

        writer.write_routes.side_effect = _write_routes

        self.assertTrue(_run_task(task))
        self.assertEqual(received["result"], write_result)
        self.assertIsNone(received["error"])
        self.assertTrue(received["cancelled"])

    def test_can_skip_gpx_detail_fetch(self):
        route = SimpleNamespace(source_route_id="42", details_json={})
        provider = MagicMock()
        provider.source_name = "strava"
        provider.last_fetch_notice = None
        provider.last_rate_limit = None
        provider.fetch_routes.return_value = [route]
        writer = MagicMock()
        writer.write_routes.return_value = {}

        task = RouteSyncTask(
            provider=provider,
            output_path="/tmp/routes.gpkg",
            use_gpx_geometry=False,
            writer_factory=MagicMock(return_value=writer),
        )

        self.assertTrue(task.run())
        provider.fetch_route_detail.assert_not_called()
        self.assertEqual(writer.write_routes.call_args.args[0], [route])


if __name__ == "__main__":
    unittest.main()
