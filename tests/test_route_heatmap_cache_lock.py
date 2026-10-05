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
            contended = publication_lock(path, lambda: False, timeout=0)
            with self.assertRaises(TimeoutError):
                contended.__enter__()
            cancelled = publication_lock(path, lambda: True)
            with self.assertRaises(HeatmapCancelled):
                cancelled.__enter__()
        self.assertEqual(probe(), 'True')
        self.assertTrue(path.exists())
        with patch('qfit.analysis.infrastructure.route_heatmap_cache_lock._try_lock', return_value=False), patch(
            'qfit.analysis.infrastructure.route_heatmap_cache_lock.time.sleep', Mock(),
        ), patch('qfit.analysis.infrastructure.route_heatmap_cache_lock.time.monotonic', side_effect=(0, 0, 1)):
            waiting = publication_lock(path, lambda: False, timeout=.5)
            with self.assertRaises(TimeoutError):
                waiting.__enter__()

    def test_empty_lock_file_contention_waits_without_writing_locked_byte(self):
        path = self.root / 'empty.lock'
        with open(path, 'a+b') as held:
            self.assertTrue(_try_lock(held))
            try:
                with self.assertRaises(TimeoutError):
                    with publication_lock(path, lambda: False, timeout=0):
                        self.fail('Contender acquired an already held lock')
            finally:
                _unlock(held)
        self.assertEqual(path.stat().st_size, 0)
        with publication_lock(path, lambda: False):
            pass

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
        self.assertEqual(sum(value is not None and not value.reused for value in results), 1)
        self.assertEqual(sum(value is not None and value.reused for value in results), 1)
        self.assertIsNotNone(_cached_artifact(destination, 'key'))
        self.assertEqual(Path(_cached_artifact(destination, 'key').path).read_bytes(), b'immutable-heatmap.vrt')

    def test_repair_does_not_delete_files_held_by_a_raster_reader(self):
        destination = self.root / 'key'
        self._artifact(destination)
        (destination / 'manifest.sha256').unlink()
        original = {p.name: p.read_bytes() for p in destination.iterdir()}
        candidate = self.root / 'candidate'
        self._artifact(candidate)
        with patch('shutil.rmtree',
                   side_effect=PermissionError('WinError 32: reader holds tile')):
            _publish_artifact(candidate, destination, 'key', lambda: False)
        for name, contents in original.items():
            self.assertEqual((destination / name).read_bytes(), contents)
        repaired = _cached_artifact(destination, 'key')
        self.assertIsNotNone(repaired)
        self.assertNotEqual(Path(repaired.path).parent, destination)

    def test_invalid_generation_pointer_and_cancel_leave_old_files_untouched(self):
        destination = self.root / 'key'
        self._artifact(destination)
        for value in ('../escape', '/absolute', 123, 'generation-../escape'):
            with self.subTest(value=value):
                (destination / 'current.json').write_text(json.dumps({'generation': value}))
                self.assertIsNone(_cached_artifact(destination, 'key'))
        candidate = self.root / 'candidate'
        self._artifact(candidate)
        before = {p.name: p.read_bytes() for p in destination.iterdir()}
        with self.assertRaises(HeatmapCancelled):
            _publish_artifact(candidate, destination, 'key', lambda: True)
        self.assertEqual(before, {p.name: p.read_bytes() for p in destination.iterdir()})

    def test_cache_validation_remains_cancellable_between_file_hashes(self):
        destination = self.root / 'key'
        self._artifact(destination)
        with self.assertRaises(HeatmapCancelled):
            _cached_artifact(destination, 'key', Mock(side_effect=(False, False, True)))

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
