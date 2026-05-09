"""Unit tests for ``backend.db.database_registry`` helpers."""

from __future__ import annotations

import sqlalchemy as sa

from backend.db.database_registry import _record_db_version
from backend.db.tables import database_versions


def test_record_db_version_inserts_new_row(reference_engine: sa.Engine) -> None:
    _record_db_version(
        reference_engine,
        db_name="lai_bundle",
        version="v1.1",
        file_size_bytes=523_801_111,
        sha256="959ed0fd9ebe2ad8fa542776a59ce73072d928c7ce59839ea81d0f1e78a5c18e",
    )

    with reference_engine.connect() as conn:
        rows = conn.execute(sa.select(database_versions)).fetchall()

    assert len(rows) == 1
    row = rows[0]
    assert row.db_name == "lai_bundle"
    assert row.version == "v1.1"
    assert row.file_size_bytes == 523_801_111
    assert (
        row.checksum_sha256 == "959ed0fd9ebe2ad8fa542776a59ce73072d928c7ce59839ea81d0f1e78a5c18e"
    )
    assert row.downloaded_at is not None


def test_record_db_version_updates_existing_row(reference_engine: sa.Engine) -> None:
    _record_db_version(
        reference_engine,
        db_name="encode_ccres",
        version="20260101",
        file_size_bytes=30_000_000,
    )
    _record_db_version(
        reference_engine,
        db_name="encode_ccres",
        version="20260508",
        file_size_bytes=31_000_000,
        sha256="aa" * 32,
    )

    with reference_engine.connect() as conn:
        rows = conn.execute(sa.select(database_versions)).fetchall()

    assert len(rows) == 1
    row = rows[0]
    assert row.db_name == "encode_ccres"
    assert row.version == "20260508"
    assert row.file_size_bytes == 31_000_000
    assert row.checksum_sha256 == "aa" * 32


def test_record_db_version_sha256_defaults_to_null(reference_engine: sa.Engine) -> None:
    _record_db_version(
        reference_engine,
        db_name="vep_bundle",
        version="2026-04-07",
        file_size_bytes=12_000_000,
    )

    with reference_engine.connect() as conn:
        row = conn.execute(
            sa.select(database_versions).where(database_versions.c.db_name == "vep_bundle")
        ).fetchone()

    assert row is not None
    assert row.checksum_sha256 is None
    assert row.version == "2026-04-07"
    assert row.file_size_bytes == 12_000_000


def test_record_db_version_update_clears_sha256(reference_engine: sa.Engine) -> None:
    """Re-recording without sha256 should overwrite the prior checksum."""
    _record_db_version(
        reference_engine,
        db_name="ancestry_pca",
        version="v1.0",
        file_size_bytes=414_432,
        sha256="bb" * 32,
    )
    _record_db_version(
        reference_engine,
        db_name="ancestry_pca",
        version="v1.1",
        file_size_bytes=414_500,
    )

    with reference_engine.connect() as conn:
        row = conn.execute(
            sa.select(database_versions).where(database_versions.c.db_name == "ancestry_pca")
        ).fetchone()

    assert row is not None
    assert row.version == "v1.1"
    assert row.checksum_sha256 is None


def test_record_db_version_independent_rows(reference_engine: sa.Engine) -> None:
    """Different db_names live in independent rows."""
    _record_db_version(
        reference_engine, db_name="clinvar", version="20260301", file_size_bytes=100
    )
    _record_db_version(reference_engine, db_name="gnomad", version="v4.1", file_size_bytes=200)

    with reference_engine.connect() as conn:
        rows = conn.execute(
            sa.select(database_versions).order_by(database_versions.c.db_name)
        ).fetchall()

    assert [r.db_name for r in rows] == ["clinvar", "gnomad"]
    assert [r.version for r in rows] == ["20260301", "v4.1"]
