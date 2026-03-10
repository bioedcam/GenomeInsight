"""Tests for database schemas (reference.db + sample DB)."""

import sqlite3
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from backend.db.sample_schema import create_sample_tables


def _run_alembic_upgrade(db_path: Path) -> None:
    """Run Alembic upgrade to head on a SQLite database."""
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")


def _get_tables(db_path: Path) -> set[str]:
    """Return table names in a SQLite database."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'alembic_%'"
    )
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    return tables


def _get_columns(db_path: Path, table: str) -> list[str]:
    """Return column names for a table."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(f"PRAGMA table_info({table})")  # noqa: S608
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    return columns


def _get_indexes(db_path: Path) -> set[str]:
    """Return index names in a SQLite database."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
    )
    indexes = {row[0] for row in cursor.fetchall()}
    conn.close()
    return indexes


# ── Reference DB Tests ──────────────────────────────────────────────


class TestReferenceSchema:
    """Test that Alembic migration creates all reference.db tables."""

    def test_alembic_creates_all_tables(self, tmp_path):
        db_path = tmp_path / "reference.db"
        _run_alembic_upgrade(db_path)
        tables = _get_tables(db_path)
        expected = {
            "samples",
            "jobs",
            "database_versions",
            "update_history",
            "downloads",
            "clinvar_variants",
            "gene_phenotype",
            "cpic_alleles",
            "cpic_diplotypes",
            "cpic_guidelines",
            "literature_cache",
            "uniprot_cache",
            "log_entries",
            "reannotation_prompts",
            "gwas_associations",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_samples_table_columns(self, tmp_path):
        db_path = tmp_path / "reference.db"
        _run_alembic_upgrade(db_path)
        cols = _get_columns(db_path, "samples")
        assert "id" in cols
        assert "name" in cols
        assert "db_path" in cols
        assert "created_at" in cols

    def test_jobs_table_columns(self, tmp_path):
        db_path = tmp_path / "reference.db"
        _run_alembic_upgrade(db_path)
        cols = _get_columns(db_path, "jobs")
        assert "job_id" in cols
        assert "status" in cols
        assert "progress_pct" in cols
        assert "message" in cols
        assert "job_type" in cols

    def test_clinvar_table_has_indexes(self, tmp_path):
        db_path = tmp_path / "reference.db"
        _run_alembic_upgrade(db_path)
        indexes = _get_indexes(db_path)
        assert "idx_clinvar_chrom_pos" in indexes
        assert "ix_clinvar_variants_rsid" in indexes

    def test_update_history_columns(self, tmp_path):
        db_path = tmp_path / "reference.db"
        _run_alembic_upgrade(db_path)
        cols = _get_columns(db_path, "update_history")
        assert "db_name" in cols
        assert "previous_version" in cols
        assert "new_version" in cols
        assert "variants_reclassified" in cols
        assert "download_size_bytes" in cols

    def test_alembic_downgrade(self, tmp_path):
        db_path = tmp_path / "reference.db"
        _run_alembic_upgrade(db_path)
        cfg = Config()
        cfg.set_main_option("script_location", "alembic")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
        command.downgrade(cfg, "base")
        tables = _get_tables(db_path)
        assert len(tables) == 0


# ── Sample DB Tests ─────────────────────────────────────────────────


class TestSampleSchema:
    """Test that create_sample_tables() creates all per-sample tables."""

    def _create_sample_db(self, db_path: Path) -> sa.Engine:
        engine = sa.create_engine(f"sqlite:///{db_path}")
        create_sample_tables(engine)
        return engine

    def test_creates_all_tables(self, tmp_path):
        db_path = tmp_path / "sample_001.db"
        self._create_sample_db(db_path)
        tables = _get_tables(db_path)
        expected = {
            "raw_variants",
            "annotated_variants",
            "findings",
            "qc_metrics",
            "sample_metadata",
            "apoe_gate",
            "tags",
            "variant_tags",
            "haplogroup_assignments",
            "watched_variants",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_raw_variants_columns(self, tmp_path):
        db_path = tmp_path / "sample_001.db"
        self._create_sample_db(db_path)
        cols = _get_columns(db_path, "raw_variants")
        assert cols == ["rsid", "chrom", "pos", "genotype"]

    def test_annotated_variants_has_30_plus_columns(self, tmp_path):
        db_path = tmp_path / "sample_001.db"
        self._create_sample_db(db_path)
        cols = _get_columns(db_path, "annotated_variants")
        assert len(cols) >= 30, f"Only {len(cols)} columns, expected 30+"

    def test_annotated_variants_key_columns(self, tmp_path):
        db_path = tmp_path / "sample_001.db"
        self._create_sample_db(db_path)
        cols = _get_columns(db_path, "annotated_variants")
        # Core identity
        for col in ["rsid", "chrom", "pos", "ref", "alt", "genotype", "zygosity"]:
            assert col in cols, f"Missing column: {col}"
        # VEP
        for col in ["gene_symbol", "consequence", "hgvs_protein", "mane_select"]:
            assert col in cols, f"Missing column: {col}"
        # ClinVar
        for col in ["clinvar_significance", "clinvar_review_stars"]:
            assert col in cols, f"Missing column: {col}"
        # gnomAD
        for col in ["gnomad_af_global", "gnomad_af_eur", "rare_flag"]:
            assert col in cols, f"Missing column: {col}"
        # dbNSFP
        for col in ["cadd_phred", "sift_score", "revel"]:
            assert col in cols, f"Missing column: {col}"
        # Bitmask
        assert "annotation_coverage" in cols

    def test_sample_has_indexes(self, tmp_path):
        db_path = tmp_path / "sample_001.db"
        self._create_sample_db(db_path)
        indexes = _get_indexes(db_path)
        assert "idx_raw_chrom_pos" in indexes
        assert "idx_annot_chrom_pos" in indexes
        assert "idx_annot_gene" in indexes
        assert "idx_annot_coverage" in indexes

    def test_predefined_tags_seeded(self, tmp_path):
        db_path = tmp_path / "sample_001.db"
        self._create_sample_db(db_path)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT name FROM tags WHERE is_predefined = 1")
        tags = {row[0] for row in cursor.fetchall()}
        conn.close()
        expected = {
            "Review later",
            "Discuss with clinician",
            "False positive",
            "Actionable",
            "Benign override",
        }
        assert expected == tags

    def test_wal_mode_enabled(self, tmp_path):
        db_path = tmp_path / "sample_001.db"
        self._create_sample_db(db_path)
        conn = sqlite3.connect(str(db_path))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_findings_table_columns(self, tmp_path):
        db_path = tmp_path / "sample_001.db"
        self._create_sample_db(db_path)
        cols = _get_columns(db_path, "findings")
        for col in [
            "module",
            "evidence_level",
            "gene_symbol",
            "finding_text",
            "diplotype",
            "prs_score",
            "pathway",
            "svg_path",
        ]:
            assert col in cols, f"Missing column: {col}"

    def test_watched_variants_columns(self, tmp_path):
        db_path = tmp_path / "sample_001.db"
        self._create_sample_db(db_path)
        cols = _get_columns(db_path, "watched_variants")
        assert "rsid" in cols
        assert "clinvar_significance_at_watch" in cols

    def test_sample_metadata_single_row(self, tmp_path):
        """sample_metadata uses CHECK(id=1) for single-row enforcement."""
        db_path = tmp_path / "sample_001.db"
        self._create_sample_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("INSERT INTO sample_metadata (id, name) VALUES (1, 'Test Sample')")
        try:
            conn.execute("INSERT INTO sample_metadata (id, name) VALUES (2, 'Another')")
            conn.commit()
            assert False, "Should have raised constraint error"
        except sqlite3.IntegrityError:
            pass
        conn.close()

    def test_idempotent_creation(self, tmp_path):
        """create_sample_tables can be called multiple times safely."""
        db_path = tmp_path / "sample_001.db"
        engine = sa.create_engine(f"sqlite:///{db_path}")
        create_sample_tables(engine)
        create_sample_tables(engine)  # Should not raise
        tables = _get_tables(db_path)
        assert "raw_variants" in tables
