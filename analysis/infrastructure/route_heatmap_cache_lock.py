"""Cross-process publication lock; compute remains independent and cancellable."""
import errno
import os
import time
from contextlib import contextmanager

from ..domain.route_density import check_cancelled


def _try_lock(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise
            return False
    else:
        import fcntl
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
    return True


def _unlock(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def publication_lock(path, cancelled, timeout=30):
    # Leave the tiny lock file in place: deleting it would permit separate
    # processes to lock different inodes for the same cache key.
    with open(path, "a+b") as handle:
        # Windows byte-range locks may extend past EOF. Do not initialize a
        # byte before acquiring the lock: another worker can lock that byte
        # between our size check and flush, making initialization fail EACCES.
        deadline = time.monotonic() + timeout
        check_cancelled(cancelled)
        while not _try_lock(handle):
            check_cancelled(cancelled)
            if time.monotonic() >= deadline:
                raise TimeoutError("Another QGIS session is publishing this heatmap; retry analysis")
            time.sleep(0.05)
        try:
            check_cancelled(cancelled)
            yield
        finally:
            _unlock(handle)
