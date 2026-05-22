"""Tests for the v7 → v8 per-sample schema migration.

AncestryDNA Plan §10.4 step 3 (the schema bump itself):

  * v8 adds four provenance columns (``source``, ``concordance``,
    ``discordant_alt_genotype``, ``alt_rsid``) to ``raw_variants``; each is
    ``TEXT NOT NULL DEFAULT ''`` so unmerged samples carry no semantic load.
  * v8 creates the single-row ``merge_provenance`` table with a
    ``CheckConstraint("id = 1")`` enforcing one row max.

This test fixture builds a synthetic v7 sample DB (the predecessor schema —
``raw_variants`` without the provenance columns, no ``merge_provenance``
table) and exercises ``ensure_sample_schema_current()`` against it.

Step 64 introduces the ``is_merged_sample`` PK divergence; this step
intentionally leaves the in-place v7→v8 upgrade with ``rsid`` PK on
``raw_variants`` (Plan §10.4 final paragraph: "The (chrom, pos) PK
divergence does not apply to in-place v7→v8 upgrades").
"""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa

from backend.db.sample_schema import (
    SAMPLE_SCHEMA_VERSION,
    ensure_sample_schema_current,
)

V8_PROVENANCE_COLUMNS = (
    "source",
    "concordance",
    "discordant_alt_genotype",
    "alt_rsid",
)


def _create_v7_sample_db(db_path: Path) -> sa.Engine:
    """Materialise a v7-shaped sample DB on disk.

    Pre-v8 ``raw_variants`` has only ``(rsid, chrom, pos, genotype)``; no
    ``merge_provenance`` table; ``user_version = 7``.
    """
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.execute(sa.text("PRAGMA journal_mode=WAL"))
        conn.execute(
            sa.text(
                """CREATE TABLE raw_variants (
                    rsid TEXT PRIMARY KEY,
                    chrom TEXT NOT NULL,
                    pos INTEGER NOT NULL,
                    genotype TEXT NOT NULL
                )"""
            )
        )
        conn.execute(sa.text("PRAGMA user_version = 7"))
        conn.commit()
    return engine


def _column_names(engine: sa.Engine, table: str) -> set[str]:
    inspector = sa.inspect(engine)
    return {col["name"] for col in inspector.get_columns(table)}


def _column_info(engine: sa.Engine, table: str) -> dict[str, dict]:
    inspector = sa.inspect(engine)
    return {col["name"]: col for col in inspector.get_columns(table)}


class TestRawVariantsProvenanceColumns:
    def test_v7_db_lacks_provenance_columns(self, tmp_path: Path) -> None:
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")
        cols = _column_names(engine, "raw_variants")
        for col in V8_PROVENANCE_COLUMNS:
            assert col not in cols

    def test_upgrade_adds_all_four_provenance_columns(self, tmp_path: Path) -> None:
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")

        updated = ensure_sample_schema_current(engine)
        assert updated is True

        cols = _column_names(engine, "raw_variants")
        for col in V8_PROVENANCE_COLUMNS:
            assert col in cols

    def test_upgrade_preserves_existing_rows(self, tmp_path: Path) -> None:
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO raw_variants (rsid, chrom, pos, genotype) "
                    "VALUES (:rsid, :chrom, :pos, :gt)"
                ),
                [
                    {"rsid": "rs429358", "chrom": "19", "pos": 45411941, "gt": "TT"},
                    {"rsid": "rs7412", "chrom": "19", "pos": 45412079, "gt": "CC"},
                ],
            )

        ensure_sample_schema_current(engine)

        with engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT rsid, chrom, pos, genotype, source, concordance, "
                    "discordant_alt_genotype, alt_rsid FROM raw_variants "
                    "ORDER BY rsid"
                )
            ).fetchall()

        assert len(rows) == 2
        # Pre-existing rows: original payload intact, new columns default to ''.
        for row in rows:
            assert row.source == ""
            assert row.concordance == ""
            assert row.discordant_alt_genotype == ""
            assert row.alt_rsid == ""
        rsids = {row.rsid for row in rows}
        assert rsids == {"rs429358", "rs7412"}

    def test_new_provenance_columns_are_not_null(self, tmp_path: Path) -> None:
        """ALTER ... ADD COLUMN ... NOT NULL DEFAULT '' enforces the NOT NULL contract."""
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")
        ensure_sample_schema_current(engine)

        info = _column_info(engine, "raw_variants")
        for col in V8_PROVENANCE_COLUMNS:
            assert info[col]["nullable"] is False, (
                f"{col} should be NOT NULL after v8 migration"
            )

    def test_explicit_null_into_new_columns_is_rejected(self, tmp_path: Path) -> None:
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")
        ensure_sample_schema_current(engine)

        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO raw_variants "
                        "(rsid, chrom, pos, genotype, source) "
                        "VALUES ('rs1', '1', 100, 'AA', NULL)"
                    )
                )

    def test_insert_without_provenance_columns_uses_defaults(self, tmp_path: Path) -> None:
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")
        ensure_sample_schema_current(engine)

        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO raw_variants (rsid, chrom, pos, genotype) "
                    "VALUES ('rs1', '1', 100, 'AA')"
                )
            )

        with engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT source, concordance, discordant_alt_genotype, alt_rsid "
                    "FROM raw_variants WHERE rsid = 'rs1'"
                )
            ).one()

        assert row.source == ""
        assert row.concordance == ""
        assert row.discordant_alt_genotype == ""
        assert row.alt_rsid == ""


class TestMergeProvenanceTable:
    def test_v7_db_lacks_merge_provenance(self, tmp_path: Path) -> None:
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")
        inspector = sa.inspect(engine)
        assert "merge_provenance" not in inspector.get_table_names()

    def test_upgrade_creates_merge_provenance_table(self, tmp_path: Path) -> None:
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")
        ensure_sample_schema_current(engine)

        inspector = sa.inspect(engine)
        assert "merge_provenance" in inspector.get_table_names()

        cols = _column_names(engine, "merge_provenance")
        assert cols == {
            "id",
            "merged_at",
            "strategy",
            "source_sample_ids",
            "source_file_hashes",
            "concordance_summary",
        }

    def test_merge_provenance_check_constraint_enforces_single_row(
        self, tmp_path: Path
    ) -> None:
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")
        ensure_sample_schema_current(engine)

        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO merge_provenance "
                    "(id, strategy, source_sample_ids, source_file_hashes, "
                    "concordance_summary) "
                    "VALUES (1, 'flag_only', '[1,2]', '[\"h1\",\"h2\"]', '{}')"
                )
            )

        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO merge_provenance "
                        "(id, strategy, source_sample_ids, source_file_hashes, "
                        "concordance_summary) "
                        "VALUES (2, 'flag_only', '[3,4]', '[\"h3\",\"h4\"]', '{}')"
                    )
                )

    def test_merge_provenance_required_columns_not_null(self, tmp_path: Path) -> None:
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")
        ensure_sample_schema_current(engine)

        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO merge_provenance "
                        "(id, strategy, source_sample_ids, source_file_hashes, "
                        "concordance_summary) "
                        "VALUES (1, NULL, '[1,2]', '[\"h1\",\"h2\"]', '{}')"
                    )
                )


class TestUpgradeStamping:
    def test_upgrade_stamps_v8(self, tmp_path: Path) -> None:
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")
        ensure_sample_schema_current(engine)

        with engine.connect() as conn:
            row = conn.execute(sa.text("PRAGMA user_version")).fetchone()
        assert row[0] == SAMPLE_SCHEMA_VERSION
        assert row[0] == 8

    def test_upgrade_is_idempotent(self, tmp_path: Path) -> None:
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")

        first = ensure_sample_schema_current(engine)
        assert first is True

        # Second pass — already current, must be a no-op and must not raise
        # (would raise OperationalError "duplicate column name" if the v8
        # branch re-ran without its column-exists check).
        second = ensure_sample_schema_current(engine)
        assert second is False

        cols = _column_names(engine, "raw_variants")
        for col in V8_PROVENANCE_COLUMNS:
            assert col in cols

    def test_upgrade_returns_true_when_only_columns_change(self, tmp_path: Path) -> None:
        """Even when no *tables* are added by the upgrade (the merge_provenance
        path also fires), ``ensure_sample_schema_current`` reports True when
        the v8 column-add ran. Guards against a stale return-value contract.
        """
        engine = _create_v7_sample_db(tmp_path / "sample_001.db")
        updated = ensure_sample_schema_current(engine)
        assert updated is True


class TestFreshSampleStillCreatesV8Surfaces:
    """Sanity check that a freshly-created sample DB lands at v8 directly."""

    def test_fresh_db_has_provenance_columns_and_merge_provenance(
        self, sample_engine: sa.Engine
    ) -> None:
        cols = _column_names(sample_engine, "raw_variants")
        for col in V8_PROVENANCE_COLUMNS:
            assert col in cols

        inspector = sa.inspect(sample_engine)
        assert "merge_provenance" in inspector.get_table_names()

        with sample_engine.connect() as conn:
            row = conn.execute(sa.text("PRAGMA user_version")).fetchone()
        assert row[0] == SAMPLE_SCHEMA_VERSION
