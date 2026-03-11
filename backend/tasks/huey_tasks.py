"""Huey task queue configuration and tasks.

Uses SqliteHuey for persistent task state with a single worker.
In test/dev mode, immediate=True runs tasks synchronously.
"""

import os

from huey import SqliteHuey

from backend.config import get_settings

_settings = get_settings()
_settings.data_dir.mkdir(parents=True, exist_ok=True)
_huey_db = str(_settings.data_dir / "huey.db")

# Allow override for testing (immediate mode runs tasks inline)
_immediate = os.environ.get("GENOMEINSIGHT_HUEY_IMMEDIATE", "").lower() in ("1", "true", "yes")

huey = SqliteHuey(
    "genomeinsight",
    filename=_huey_db,
    immediate=_immediate,
)
