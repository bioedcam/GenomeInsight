"""Database connection management for GenomeInsight.

Provides the DBRegistry singleton that manages connections to all SQLite
databases (reference + per-sample). Reference DB connections are long-lived
and read-only. Sample DB connections are created per-request.

Usage::

    from backend.db.connection import get_registry

    registry = get_registry()
    with registry.reference_engine.connect() as conn:
        result = conn.execute(select(clinvar_variants).where(...))
"""

from __future__ import annotations

import functools
from pathlib import Path

import sqlalchemy as sa

from backend.config import Settings, get_settings


class DBRegistry:
    """Singleton managing SQLite engine connections for all databases.

    Reference DB engines are created once at startup. Sample DB engines
    are created on demand and cached.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sample_engines: dict[str, sa.Engine] = {}

        # Reference DB (shared, long-lived)
        self.reference_engine = self._create_engine(
            settings.reference_db_path, wal=settings.wal_mode
        )

        # Large reference DBs (opened lazily on first access)
        self._vep_engine: sa.Engine | None = None
        self._gnomad_engine: sa.Engine | None = None
        self._dbnsfp_engine: sa.Engine | None = None

    @staticmethod
    def _create_engine(db_path: Path, wal: bool = True) -> sa.Engine:
        """Create a SQLAlchemy engine for a SQLite database.

        Args:
            db_path: Path to the SQLite file.
            wal: Whether to enable WAL journal mode.

        Returns:
            Configured SQLAlchemy Engine.
        """
        engine = sa.create_engine(
            f"sqlite:///{db_path}",
            pool_pre_ping=True,
        )
        if wal:
            with engine.connect() as conn:
                conn.execute(sa.text("PRAGMA journal_mode=WAL"))
                conn.commit()
        return engine

    @property
    def vep_engine(self) -> sa.Engine:
        """Lazy-loaded VEP bundle engine (read-only, ~500 MB)."""
        if self._vep_engine is None:
            self._vep_engine = self._create_engine(
                self._settings.vep_bundle_db_path, wal=self._settings.wal_mode
            )
        return self._vep_engine

    @property
    def gnomad_engine(self) -> sa.Engine:
        """Lazy-loaded gnomAD engine (read-only, ~2 GB)."""
        if self._gnomad_engine is None:
            self._gnomad_engine = self._create_engine(
                self._settings.gnomad_db_path, wal=self._settings.wal_mode
            )
        return self._gnomad_engine

    @property
    def dbnsfp_engine(self) -> sa.Engine:
        """Lazy-loaded dbNSFP engine (read-only, ~1.5 GB)."""
        if self._dbnsfp_engine is None:
            self._dbnsfp_engine = self._create_engine(
                self._settings.dbnsfp_db_path, wal=self._settings.wal_mode
            )
        return self._dbnsfp_engine

    def get_sample_engine(self, sample_db_path: str | Path) -> sa.Engine:
        """Get or create an engine for a per-sample database.

        Args:
            sample_db_path: Path to the sample SQLite file.

        Returns:
            Cached SQLAlchemy Engine for the sample.
        """
        key = str(sample_db_path)
        if key not in self._sample_engines:
            self._sample_engines[key] = self._create_engine(
                Path(sample_db_path), wal=self._settings.wal_mode
            )
        return self._sample_engines[key]

    def dispose_all(self) -> None:
        """Dispose all engines. Call on application shutdown."""
        self.reference_engine.dispose()
        for engine in self._sample_engines.values():
            engine.dispose()
        self._sample_engines.clear()
        if self._vep_engine is not None:
            self._vep_engine.dispose()
            self._vep_engine = None
        if self._gnomad_engine is not None:
            self._gnomad_engine.dispose()
            self._gnomad_engine = None
        if self._dbnsfp_engine is not None:
            self._dbnsfp_engine.dispose()
            self._dbnsfp_engine = None


@functools.lru_cache(maxsize=1)
def get_registry(settings: Settings | None = None) -> DBRegistry:
    """Return the singleton DBRegistry instance.

    Args:
        settings: Optional settings override. Uses get_settings() by default.
    """
    if settings is None:
        settings = get_settings()
    return DBRegistry(settings)
