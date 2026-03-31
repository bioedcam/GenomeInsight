"""SQLite compile-time limit detection (P4-22 performance optimization).

Detects ``SQLITE_MAX_VARIABLE_NUMBER`` at runtime so that batch lookup
functions in annotation modules can use the largest safe IN-clause size.

macOS system SQLite defaults to 999; Linux builds typically allow 32766.
Rather than hard-coding 999 everywhere, we probe once at import time and
export the result.
"""

from __future__ import annotations

import sqlite3


def _detect_max_variable_number() -> int:
    """Detect SQLite's SQLITE_MAX_VARIABLE_NUMBER at runtime.

    Probes by executing a large IN clause.  Returns the detected limit
    (or 999 as a safe fallback).
    """
    try:
        conn = sqlite3.connect(":memory:")
        # Linux SQLite is typically compiled with 32766; try that first.
        for candidate in (32766, 9999, 999):
            try:
                placeholders = ",".join("?" for _ in range(candidate))
                conn.execute(
                    f"SELECT 1 WHERE 1 IN ({placeholders})",  # noqa: S608
                    list(range(candidate)),
                )
                conn.close()
                return candidate
            except sqlite3.OperationalError:
                continue
        conn.close()
    except Exception:
        pass
    return 999


SQLITE_MAX_VARIABLE_NUMBER: int = _detect_max_variable_number()
