"""Process-global guard serializing concurrent builds of the same database.

Two builds of the same SQLite file running at once — a duplicate setup-wizard
download (the in-flight dedup in ``trigger_download`` has a check-then-act gap),
a wizard build racing an auto-update (which builds standalone DBs on its own
engine, bypassing the wizard's path), or an orphaned build thread after a
restart — open two independent write connections through the shared engine
pool.  On a multi-GB load they contend for the WAL write lock long enough that
``busy_timeout`` expires and one batch ``INSERT`` fails with
``OperationalError: database is locked``.

:func:`build_lock` serializes builds **per database name** with a blocking
lock, so only one writer is ever active for a given DB while different DBs
still build in parallel.  Callers should re-check whether the DB is already
present after acquiring (a concurrent build may have just finished it) to avoid
a redundant rebuild.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

# Guards the ``_locks`` registry itself (NOT held during a build).
_registry_lock = threading.Lock()
# Per-DB locks are *reentrant*: a single thread that holds the build slot (e.g.
# the clean path, which acquires it then calls health, which probes the lock via
# is_build_locked) must not deadlock or self-report a phantom build. Reentrancy
# is same-thread only — cross-thread mutual exclusion is identical to a plain Lock.
_locks: dict[str, threading.RLock] = {}


def _lock_for(db_name: str) -> threading.RLock:
    """Return the (lazily created) per-database reentrant lock for ``db_name``."""
    with _registry_lock:
        lock = _locks.get(db_name)
        if lock is None:
            lock = threading.RLock()
            _locks[db_name] = lock
        return lock


@contextmanager
def build_lock(db_name: str) -> Iterator[None]:
    """Block until this thread owns the build slot for ``db_name``, then release.

    Same-DB builds run one at a time; different DBs are unaffected and keep
    building concurrently.
    """
    lock = _lock_for(db_name)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def is_build_locked(db_name: str) -> bool:
    """Best-effort check of whether a build is currently running for ``db_name``.

    Probes the per-DB lock without blocking: if it cannot be acquired, a builder
    holds it (a build is in flight). Used by health reporting to surface an
    in-progress build even when no session job links it (e.g. an update-manager
    rebuild). A builder holds the lock for the whole build, so a transient
    between-operations false negative is not possible mid-build.
    """
    lock = _lock_for(db_name)
    acquired = lock.acquire(blocking=False)
    if acquired:
        lock.release()
    return not acquired


@contextmanager
def try_acquire_build_lock(db_name: str) -> Iterator[bool]:
    """Non-blocking variant of :func:`build_lock` for mutually-exclusive callers.

    Yields ``True`` if this thread acquired the build slot (and releases it on
    exit), or ``False`` immediately if a build already holds it. Used by the
    "clean" path so removing a partial/corrupt artifact can never race a build
    of the same database.
    """
    lock = _lock_for(db_name)
    acquired = lock.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()
