import errno
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests import _path  # noqa: F401
from qfit.analysis.domain.route_density import HeatmapCancelled
from qfit.analysis.infrastructure.route_heatmap_cache_lock import publication_lock, _try_lock, _unlock
from qfit.analysis.infrastructure.route_heatmap_raster import _publish_artifact, _cached_artifact


class RouteHeatmapCacheLockTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_independent_process_cannot_publish_through_held_lock(self):
        path = self.root / 'key.lock'
        code = ('from tests import _path; '
                'from qfit.analysis.infrastructure.route_heatmap_cache_lock import _try_lock; '
                'import sys; '
                'handle=open(sys.argv[1],"a+b"); print(_try_lock(handle))')
        def probe():
            result = subprocess.run([sys.executable, '-c', code, str(path)],
                                    cwd=Path(__file__).parents[1], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip().splitlines()[-1]
        with publication_lock(path, lambda: False):
            self.assertEqual(probe(), 'False')
            with self.assertRaises(TimeoutError):
                with publication_lock(path, lambda: False, timeout=0):
                    self.fail('Contended lock was acquired')
            with self.assertRaises(HeatmapCancelled):
                with publication_lock(path, lambda: True):
                    self.fail('Cancelled publication was acquired')
        self.assertEqual(probe(), 'True')
        self.assertTrue(path.exists())
        with patch('qfit.analysis.infrastructure.route_heatmap_cache_lock._try_lock', return_value=False), patch(
            'qfit.analysis.infrastructure.route_heatmap_cache_lock.time.sleep', Mock(),
        ), patch('qfit.analysis.infrastructure.route_heatmap_cache_lock.time.monotonic', side_effect=(0, 0, 1)):
            with self.assertRaises(TimeoutError):
                with publication_lock(path, lambda: False, timeout=.5):
                    self.fail('Unreleased lock was acquired')

    def test_windows_backend_busy_success_unlock_and_real_io_errors(self):
        backend = SimpleNamespace(locking=Mock(), LK_NBLCK=1, LK_UNLCK=2)
        handle = Mock()
        handle.fileno.return_value = 7
        with patch('qfit.analysis.infrastructure.route_heatmap_cache_lock.os.name', 'nt'), patch.dict(
            'sys.modules', {'msvcrt': backend},
        ):
            self.assertTrue(_try_lock(handle))
            _unlock(handle)
            backend.locking.assert_any_call(7, 1, 1)
            backend.locking.assert_any_call(7, 2, 1)
            backend.locking.side_effect = OSError(errno.EACCES, 'busy')
            self.assertFalse(_try_lock(handle))
            backend.locking.side_effect = OSError(errno.EIO, 'disk failure')
            with self.assertRaises(OSError):
                _try_lock(handle)

    def _artifact(self, directory):
        directory.mkdir()
        files = {}
        for name in ('heatmap.vrt', 'tile.tif'):
            contents = ('immutable-' + name).encode()
            (directory / name).write_bytes(contents)
            files[name] = hashlib.sha256(contents).hexdigest()
        data = json.dumps({'cache_key': 'key', 'files': files, 'activity_count': 1,
                           'maximum': 2, 'crs': 'EPSG:32632'}).encode()
        (directory / 'manifest.json').write_bytes(data)
        (directory / 'manifest.sha256').write_text(hashlib.sha256(data).hexdigest())

    def test_simultaneous_repairs_reuse_winner_without_removing_it(self):
        destination = self.root / 'key'
        destination.mkdir()
        (destination / 'broken').write_text('corrupted cache')
        candidates = [self.root / 'first', self.root / 'second']
        for candidate in candidates:
            self._artifact(candidate)
        barrier = threading.Barrier(2)
        results, errors = [], []
        def publish(candidate):
            try:
                barrier.wait(timeout=2)
                results.append(_publish_artifact(candidate, destination, 'key', lambda: False))
            except Exception as exc:
                errors.append(exc)
        workers = [threading.Thread(target=publish, args=(candidate,)) for candidate in candidates]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(sum(value is None for value in results), 1)
        self.assertEqual(sum(value is not None and value.reused for value in results), 1)
        self.assertIsNotNone(_cached_artifact(destination, 'key'))
        self.assertEqual((destination/'heatmap.vrt').read_bytes(), b'immutable-heatmap.vrt')

    def test_metadata_edits_and_missing_checksum_never_reuse_cache(self):
        destination = self.root / 'key'
        self._artifact(destination)
        original = (destination / 'manifest.json').read_bytes()
        for field, value in (('maximum', 200), ('crs', 'EPSG:3857'), ('activity_count', 100)):
            manifest = json.loads(original)
            manifest[field] = value
            (destination / 'manifest.json').write_text(json.dumps(manifest))
            self.assertIsNone(_cached_artifact(destination, 'key'))
        (destination / 'manifest.json').write_bytes(original)
        self.assertIsNotNone(_cached_artifact(destination, 'key'))
        (destination / 'manifest.sha256').unlink()
        self.assertIsNone(_cached_artifact(destination, 'key'))
