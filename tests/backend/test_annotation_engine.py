"""Tests for the annotation engine orchestrator (P2-04).

Covers:
- T2-04: Annotation engine processes 1000 variants end-to-end, all fields
  populated in annotated_variants
- Concurrent lookup orchestration across VEP, ClinVar, gnomAD, dbNSFP
- Bitmask computation (annotation_coverage)
- Crash recovery (delete partial, re-run)
- Graceful degradation when sources are unavailable
- Progress callback
- Merge logic across sources
"""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from backend.annotation.engine import (
    CLINVAR_BIT,
    DBNSFP_BIT,
    GNOMAD_BIT,
    VEP_BIT,
    AnnotationEngineResult,
    _bulk_upsert,
    _delete_all_annotations,
    _lookup_clinvar,
    _lookup_dbnsfp,
    _lookup_gnomad,
    _lookup_vep,
    _merge_annotations,
    run_annotation,
)
from backend.db.sample_schema import create_sample_tables
from backend.db.tables import (
    annotated_variants,
    clinvar_variants,
    raw_variants,
    reference_metadata,
)

# ── Fixtures ────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
VEP_SEED_CSV = FIXTURES_DIR / "seed_csvs" / "vep_seed.csv"
GNOMAD_SEED_CSV = FIXTURES_DIR / "seed_csvs" / "gnomad_seed.csv"
DBNSFP_SEED_CSV = FIXTURES_DIR / "seed_csvs" / "dbnsfp_seed.csv"

SEED_CLINVAR = [
    {
        "rsid": "rs429358",
        "chrom": "19",
        "pos": 44908684,
        "ref": "T",
        "alt": "C",
        "significance": "risk_factor",
        "review_stars": 3,
        "accession": "VCV000017864",
        "conditions": "Alzheimer disease",
        "gene_symbol": "APOE",
        "variation_id": 17864,
    },
    {
        "rsid": "rs1801133",
        "chrom": "1",
        "pos": 11856378,
        "ref": "G",
        "alt": "A",
        "significance": "drug_response",
        "review_stars": 2,
        "accession": "VCV000003520",
        "conditions": "Homocysteinemia",
        "gene_symbol": "MTHFR",
        "variation_id": 3520,
    },
    {
        "rsid": "rs80357906",
        "chrom": "17",
        "pos": 43091983,
        "ref": "CTC",
        "alt": "C",
        "significance": "Pathogenic",
        "review_stars": 3,
        "accession": "VCV000017661",
        "conditions": "Hereditary breast and ovarian cancer syndrome",
        "gene_symbol": "BRCA1",
        "variation_id": 17661,
    },
]

SEED_RAW_VARIANTS = [
    {"rsid": "rs429358", "chrom": "19", "pos": 44908684, "genotype": "TC"},
    {"rsid": "rs7412", "chrom": "19", "pos": 44908822, "genotype": "CC"},
    {"rsid": "rs1801133", "chrom": "1", "pos": 11856378, "genotype": "AG"},
    {"rsid": "rs4680", "chrom": "22", "pos": 19963748, "genotype": "AG"},
    {"rsid": "rs80357906", "chrom": "17", "pos": 43091983, "genotype": "CT"},
    {"rsid": "rs12913832", "chrom": "15", "pos": 28365618, "genotype": "GG"},
    {"rsid": "rs7903146", "chrom": "10", "pos": 114758349, "genotype": "CT"},
    {"rsid": "rs_nomatch", "chrom": "99", "pos": 1, "genotype": "AA"},
]


@pytest.fixture
def sample_engine() -> sa.Engine:
    """In-memory sample engine with tables created."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_sample_tables(engine)
    return engine


@pytest.fixture
def sample_with_variants(sample_engine: sa.Engine) -> sa.Engine:
    """Sample engine pre-loaded with known raw variants."""
    with sample_engine.begin() as conn:
        conn.execute(raw_variants.insert(), SEED_RAW_VARIANTS)
    return sample_engine


@pytest.fixture
def vep_engine_inmemory() -> sa.Engine:
    """In-memory VEP bundle loaded from seed CSV."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE vep_annotations ("
                "  rsid TEXT, chrom TEXT, pos INTEGER,"
                "  ref TEXT, alt TEXT, gene_symbol TEXT,"
                "  transcript_id TEXT, consequence TEXT,"
                "  hgvs_coding TEXT, hgvs_protein TEXT,"
                "  strand TEXT, exon_number INTEGER,"
                "  intron_number INTEGER, mane_select INTEGER"
                ")"
            )
        )
        conn.execute(sa.text("CREATE INDEX idx_vep_rsid ON vep_annotations(rsid)"))
        with open(VEP_SEED_CSV) as f:
            reader = csv.DictReader(f)
            for row in reader:
                conn.execute(
                    sa.text(
                        "INSERT INTO vep_annotations "
                        "(rsid, chrom, pos, ref, alt, gene_symbol, "
                        "transcript_id, consequence, hgvs_coding, "
                        "hgvs_protein, strand, exon_number, "
                        "intron_number, mane_select) "
                        "VALUES (:rsid, :chrom, :pos, :ref, :alt, "
                        ":gene_symbol, :transcript_id, :consequence, "
                        ":hgvs_coding, :hgvs_protein, :strand, "
                        ":exon_number, :intron_number, :mane_select)"
                    ),
                    {
                        "rsid": row["rsid"],
                        "chrom": row["chrom"],
                        "pos": int(row["pos"]),
                        "ref": row["ref"],
                        "alt": row["alt"],
                        "gene_symbol": row["gene_symbol"],
                        "transcript_id": row["transcript_id"],
                        "consequence": row["consequence"],
                        "hgvs_coding": row["hgvs_coding"] or None,
                        "hgvs_protein": row["hgvs_protein"] or None,
                        "strand": row["strand"],
                        "exon_number": (int(row["exon_number"]) if row["exon_number"] else None),
                        "intron_number": (
                            int(row["intron_number"]) if row["intron_number"] else None
                        ),
                        "mane_select": int(row["mane_select"]),
                    },
                )
    return engine


@pytest.fixture
def reference_engine() -> sa.Engine:
    """In-memory reference engine with ClinVar data."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    reference_metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(clinvar_variants.insert(), SEED_CLINVAR)
    return engine


@pytest.fixture
def gnomad_engine() -> sa.Engine:
    """In-memory gnomAD engine loaded from seed CSV."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE gnomad_af ("
                "  rsid TEXT PRIMARY KEY, chrom TEXT, pos INTEGER,"
                "  ref TEXT, alt TEXT, af_global REAL,"
                "  af_afr REAL, af_amr REAL, af_eas REAL,"
                "  af_eur REAL, af_fin REAL, af_sas REAL,"
                "  homozygous_count INTEGER"
                ")"
            )
        )
        conn.execute(sa.text("CREATE INDEX idx_gnomad_rsid ON gnomad_af(rsid)"))
        with open(GNOMAD_SEED_CSV) as f:
            reader = csv.DictReader(f)
            for row in reader:
                conn.execute(
                    sa.text(
                        "INSERT INTO gnomad_af VALUES "
                        "(:rsid, :chrom, :pos, :ref, :alt, :af_global, "
                        ":af_afr, :af_amr, :af_eas, :af_eur, :af_fin, "
                        ":af_sas, :homozygous_count)"
                    ),
                    {
                        "rsid": row["rsid"],
                        "chrom": row["chrom"],
                        "pos": int(row["pos"]),
                        "ref": row["ref"],
                        "alt": row["alt"],
                        "af_global": float(row["af_global"]),
                        "af_afr": float(row["af_afr"]),
                        "af_amr": float(row["af_amr"]),
                        "af_eas": float(row["af_eas"]),
                        "af_eur": float(row["af_eur"]),
                        "af_fin": float(row["af_fin"]),
                        "af_sas": float(row["af_sas"]),
                        "homozygous_count": int(row["homozygous_count"]),
                    },
                )
    return engine


@pytest.fixture
def dbnsfp_engine() -> sa.Engine:
    """In-memory dbNSFP engine loaded from seed CSV."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE dbnsfp_scores ("
                "  rsid TEXT PRIMARY KEY, chrom TEXT, pos INTEGER,"
                "  ref TEXT, alt TEXT, cadd_phred REAL,"
                "  sift_score REAL, sift_pred TEXT,"
                "  polyphen2_hsvar_score REAL, polyphen2_hsvar_pred TEXT,"
                "  revel REAL, mutpred2 REAL, vest4 REAL,"
                "  metasvm REAL, metalr REAL, gerp_rs REAL,"
                "  phylop REAL, mpc REAL, primateai REAL"
                ")"
            )
        )
        conn.execute(sa.text("CREATE INDEX idx_dbnsfp_rsid ON dbnsfp_scores(rsid)"))
        with open(DBNSFP_SEED_CSV) as f:
            reader = csv.DictReader(f)
            for row in reader:
                conn.execute(
                    sa.text(
                        "INSERT INTO dbnsfp_scores VALUES "
                        "(:rsid, :chrom, :pos, :ref, :alt, :cadd_phred, "
                        ":sift_score, :sift_pred, :polyphen2_hsvar_score, "
                        ":polyphen2_hsvar_pred, :revel, :mutpred2, :vest4, "
                        ":metasvm, :metalr, :gerp_rs, :phylop, :mpc, :primateai)"
                    ),
                    {
                        "rsid": row["rsid"],
                        "chrom": row["chrom"],
                        "pos": int(row["pos"]),
                        "ref": row["ref"],
                        "alt": row["alt"],
                        "cadd_phred": float(row["cadd_phred"]) if row["cadd_phred"] else None,
                        "sift_score": float(row["sift_score"]) if row["sift_score"] else None,
                        "sift_pred": row["sift_pred"] or None,
                        "polyphen2_hsvar_score": (
                            float(row["polyphen2_hsvar_score"])
                            if row["polyphen2_hsvar_score"]
                            else None
                        ),
                        "polyphen2_hsvar_pred": row["polyphen2_hsvar_pred"] or None,
                        "revel": float(row["revel"]) if row["revel"] else None,
                        "mutpred2": float(row["mutpred2"]) if row["mutpred2"] else None,
                        "vest4": float(row["vest4"]) if row["vest4"] else None,
                        "metasvm": float(row["metasvm"]) if row["metasvm"] else None,
                        "metalr": float(row["metalr"]) if row["metalr"] else None,
                        "gerp_rs": float(row["gerp_rs"]) if row["gerp_rs"] else None,
                        "phylop": float(row["phylop"]) if row["phylop"] else None,
                        "mpc": float(row["mpc"]) if row["mpc"] else None,
                        "primateai": float(row["primateai"]) if row["primateai"] else None,
                    },
                )
    return engine


@pytest.fixture
def mock_registry(
    reference_engine: sa.Engine,
    vep_engine_inmemory: sa.Engine,
    gnomad_engine: sa.Engine,
    dbnsfp_engine: sa.Engine,
) -> MagicMock:
    """Mock DBRegistry with all annotation source engines."""
    registry = MagicMock()
    registry.reference_engine = reference_engine
    type(registry).vep_engine = property(lambda self: vep_engine_inmemory)
    type(registry).gnomad_engine = property(lambda self: gnomad_engine)
    type(registry).dbnsfp_engine = property(lambda self: dbnsfp_engine)
    return registry


# ═══════════════════════════════════════════════════════════════════════
# AnnotationEngineResult
# ═══════════════════════════════════════════════════════════════════════


class TestAnnotationEngineResult:
    def test_defaults(self) -> None:
        r = AnnotationEngineResult()
        assert r.total_variants == 0
        assert r.total_matched == 0
        assert r.errors == []

    def test_total_matched_equals_rows_written(self) -> None:
        r = AnnotationEngineResult(rows_written=42)
        assert r.total_matched == 42


# ═══════════════════════════════════════════════════════════════════════
# Individual source lookups
# ═══════════════════════════════════════════════════════════════════════


class TestLookupVep:
    def test_returns_vep_fields(self, vep_engine_inmemory: sa.Engine) -> None:
        result = _lookup_vep(["rs429358"], {}, vep_engine_inmemory)
        assert "rs429358" in result
        assert result["rs429358"]["gene_symbol"] == "APOE"
        assert result["rs429358"]["consequence"] == "missense_variant"

    def test_empty_rsids(self, vep_engine_inmemory: sa.Engine) -> None:
        result = _lookup_vep([], {}, vep_engine_inmemory)
        assert len(result) == 0


class TestLookupClinvar:
    def test_returns_clinvar_fields(self, reference_engine: sa.Engine) -> None:
        result = _lookup_clinvar(["rs429358"], {}, reference_engine)
        assert "rs429358" in result
        assert result["rs429358"]["clinvar_significance"] == "risk_factor"
        assert result["rs429358"]["clinvar_review_stars"] == 3


class TestLookupGnomad:
    def test_returns_gnomad_fields(self, gnomad_engine: sa.Engine) -> None:
        result = _lookup_gnomad(["rs429358"], {}, gnomad_engine)
        assert "rs429358" in result
        data = result["rs429358"]
        assert data["gnomad_af_global"] == pytest.approx(0.1387)
        assert isinstance(data["rare_flag"], bool)
        assert data["rare_flag"] is False  # 0.1387 > 0.01

    def test_rare_flag(self, gnomad_engine: sa.Engine) -> None:
        # Insert a rare variant
        with gnomad_engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO gnomad_af VALUES "
                    "('rs_rare', '1', 1, 'A', 'G', 0.005, "
                    "0.003, 0.004, 0.006, 0.005, 0.002, 0.007, 5)"
                )
            )
        result = _lookup_gnomad(["rs_rare"], {}, gnomad_engine)
        assert result["rs_rare"]["rare_flag"] is True
        assert result["rs_rare"]["ultra_rare_flag"] is False

    def test_ultra_rare_flag(self, gnomad_engine: sa.Engine) -> None:
        with gnomad_engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO gnomad_af VALUES "
                    "('rs_ultrarare', '1', 2, 'A', 'G', 0.00005, "
                    "0.00003, 0.00004, 0.00006, 0.00005, 0.00002, 0.00007, 1)"
                )
            )
        result = _lookup_gnomad(["rs_ultrarare"], {}, gnomad_engine)
        assert result["rs_ultrarare"]["rare_flag"] is True
        assert result["rs_ultrarare"]["ultra_rare_flag"] is True

    def test_empty_rsids(self, gnomad_engine: sa.Engine) -> None:
        result = _lookup_gnomad([], {}, gnomad_engine)
        assert len(result) == 0


class TestLookupDbnsfp:
    def test_returns_dbnsfp_fields(self, dbnsfp_engine: sa.Engine) -> None:
        result = _lookup_dbnsfp(["rs429358"], {}, dbnsfp_engine)
        assert "rs429358" in result
        data = result["rs429358"]
        assert data["cadd_phred"] == pytest.approx(28.3)
        assert data["sift_pred"] == "D"
        assert data["polyphen2_hsvar_pred"] == "D"

    def test_empty_rsids(self, dbnsfp_engine: sa.Engine) -> None:
        result = _lookup_dbnsfp([], {}, dbnsfp_engine)
        assert len(result) == 0


# ═══════════════════════════════════════════════════════════════════════
# Merge + bitmask
# ═══════════════════════════════════════════════════════════════════════


class TestMergeAnnotations:
    def test_merge_all_sources(self) -> None:
        """Merging data from all 4 sources produces correct bitmask."""
        # Create a fake raw row
        engine = sa.create_engine("sqlite://")
        with engine.begin() as conn:
            conn.execute(
                sa.text("CREATE TABLE t (rsid TEXT, chrom TEXT, pos INTEGER, genotype TEXT)")
            )
            conn.execute(sa.text("INSERT INTO t VALUES ('rs1', '1', 100, 'AG')"))
            row = conn.execute(sa.text("SELECT * FROM t")).fetchone()

        vep = {"rs1": {"gene_symbol": "GENE1", "consequence": "missense_variant"}}
        clinvar = {"rs1": {"clinvar_significance": "Pathogenic"}}
        gnomad = {"rs1": {"gnomad_af_global": 0.01}}
        dbnsfp = {"rs1": {"cadd_phred": 25.0}}

        merged = _merge_annotations([row], vep, clinvar, gnomad, dbnsfp)
        assert len(merged) == 1
        assert merged[0]["annotation_coverage"] == VEP_BIT | CLINVAR_BIT | GNOMAD_BIT | DBNSFP_BIT
        assert merged[0]["gene_symbol"] == "GENE1"
        assert merged[0]["clinvar_significance"] == "Pathogenic"
        assert merged[0]["gnomad_af_global"] == 0.01
        assert merged[0]["cadd_phred"] == 25.0

    def test_partial_sources(self) -> None:
        """Variant matched by only VEP has only VEP bit set."""
        engine = sa.create_engine("sqlite://")
        with engine.begin() as conn:
            conn.execute(
                sa.text("CREATE TABLE t (rsid TEXT, chrom TEXT, pos INTEGER, genotype TEXT)")
            )
            conn.execute(sa.text("INSERT INTO t VALUES ('rs1', '1', 100, 'AG')"))
            row = conn.execute(sa.text("SELECT * FROM t")).fetchone()

        vep = {"rs1": {"gene_symbol": "GENE1"}}
        merged = _merge_annotations([row], vep, {}, {}, {})
        assert len(merged) == 1
        assert merged[0]["annotation_coverage"] == VEP_BIT

    def test_no_match_excluded(self) -> None:
        """Variants with no matches in any source are excluded."""
        engine = sa.create_engine("sqlite://")
        with engine.begin() as conn:
            conn.execute(
                sa.text("CREATE TABLE t (rsid TEXT, chrom TEXT, pos INTEGER, genotype TEXT)")
            )
            conn.execute(sa.text("INSERT INTO t VALUES ('rs_none', '1', 100, 'AA')"))
            row = conn.execute(sa.text("SELECT * FROM t")).fetchone()

        merged = _merge_annotations([row], {}, {}, {}, {})
        assert len(merged) == 0


# ═══════════════════════════════════════════════════════════════════════
# Crash recovery
# ═══════════════════════════════════════════════════════════════════════


class TestCrashRecovery:
    def test_delete_all_annotations(self, sample_with_variants: sa.Engine) -> None:
        """Deleting annotations clears the table."""
        # Insert some annotations
        with sample_with_variants.begin() as conn:
            conn.execute(
                annotated_variants.insert().values(
                    rsid="rs429358", chrom="19", pos=44908684, genotype="TC"
                )
            )
        _delete_all_annotations(sample_with_variants)
        with sample_with_variants.connect() as conn:
            count = conn.execute(
                sa.select(sa.func.count()).select_from(annotated_variants)
            ).scalar()
        assert count == 0


# ═══════════════════════════════════════════════════════════════════════
# Bulk upsert
# ═══════════════════════════════════════════════════════════════════════


class TestBulkUpsert:
    def test_upsert_writes_rows(self, sample_engine: sa.Engine) -> None:
        rows = [
            {
                "rsid": "rs1",
                "chrom": "1",
                "pos": 100,
                "genotype": "AG",
                "gene_symbol": "GENE1",
                "annotation_coverage": VEP_BIT,
            }
        ]
        written = _bulk_upsert(sample_engine, rows)
        assert written == 1

        with sample_engine.connect() as conn:
            row = conn.execute(
                sa.select(annotated_variants).where(annotated_variants.c.rsid == "rs1")
            ).fetchone()
        assert row is not None
        assert row.gene_symbol == "GENE1"
        assert row.annotation_coverage == VEP_BIT

    def test_upsert_ors_bitmask(self, sample_engine: sa.Engine) -> None:
        """Second upsert ORs the bitmask with existing."""
        # First insert with VEP bit
        with sample_engine.begin() as conn:
            conn.execute(
                annotated_variants.insert().values(
                    rsid="rs1",
                    chrom="1",
                    pos=100,
                    genotype="AG",
                    annotation_coverage=VEP_BIT,
                )
            )
        # Upsert with ClinVar bit
        rows = [
            {
                "rsid": "rs1",
                "chrom": "1",
                "pos": 100,
                "genotype": "AG",
                "clinvar_significance": "Pathogenic",
                "annotation_coverage": CLINVAR_BIT,
            }
        ]
        _bulk_upsert(sample_engine, rows)

        with sample_engine.connect() as conn:
            row = conn.execute(
                sa.select(annotated_variants.c.annotation_coverage).where(
                    annotated_variants.c.rsid == "rs1"
                )
            ).fetchone()
        assert row.annotation_coverage == VEP_BIT | CLINVAR_BIT

    def test_empty_rows(self, sample_engine: sa.Engine) -> None:
        assert _bulk_upsert(sample_engine, []) == 0


# ═══════════════════════════════════════════════════════════════════════
# Full orchestration: run_annotation
# ═══════════════════════════════════════════════════════════════════════


class TestRunAnnotation:
    def test_full_annotation(
        self,
        sample_with_variants: sa.Engine,
        mock_registry: MagicMock,
    ) -> None:
        """Full annotation populates annotated_variants with data from all sources."""
        result = run_annotation(sample_with_variants, mock_registry)

        assert result.total_variants == len(SEED_RAW_VARIANTS)
        assert result.rows_written > 0
        assert result.vep_matched > 0
        assert result.clinvar_matched > 0
        assert result.gnomad_matched > 0
        assert result.dbnsfp_matched > 0
        assert result.batches_processed >= 1
        assert result.errors == []

    def test_all_fields_populated(
        self,
        sample_with_variants: sa.Engine,
        mock_registry: MagicMock,
    ) -> None:
        """T2-04: Known variant has VEP + ClinVar + gnomAD + dbNSFP fields."""
        run_annotation(sample_with_variants, mock_registry)

        with sample_with_variants.connect() as conn:
            row = conn.execute(
                sa.select(annotated_variants).where(annotated_variants.c.rsid == "rs429358")
            ).fetchone()

        assert row is not None
        # VEP fields
        assert row.gene_symbol == "APOE"
        assert row.consequence == "missense_variant"
        assert row.mane_select in (True, 1)
        # ClinVar fields
        assert row.clinvar_significance == "risk_factor"
        assert row.clinvar_review_stars == 3
        # gnomAD fields
        assert row.gnomad_af_global is not None
        assert row.gnomad_af_global == pytest.approx(0.1387)
        # dbNSFP fields
        assert row.cadd_phred is not None
        assert row.cadd_phred == pytest.approx(28.3)
        assert row.sift_pred == "D"
        # Bitmask: all 4 sources
        assert row.annotation_coverage == VEP_BIT | CLINVAR_BIT | GNOMAD_BIT | DBNSFP_BIT

    def test_bitmask_partial_coverage(
        self,
        sample_with_variants: sa.Engine,
        mock_registry: MagicMock,
    ) -> None:
        """Variants matched by fewer sources have partial bitmask."""
        run_annotation(sample_with_variants, mock_registry)

        with sample_with_variants.connect() as conn:
            rows = conn.execute(sa.select(annotated_variants)).fetchall()

        for row in rows:
            coverage = row.annotation_coverage
            assert coverage is not None
            assert coverage > 0
            # At least one bit must be set
            assert coverage & (VEP_BIT | CLINVAR_BIT | GNOMAD_BIT | DBNSFP_BIT) > 0

    def test_unmatched_variants_excluded(
        self,
        sample_with_variants: sa.Engine,
        mock_registry: MagicMock,
    ) -> None:
        """Variants matching no source are not in annotated_variants."""
        run_annotation(sample_with_variants, mock_registry)

        with sample_with_variants.connect() as conn:
            row = conn.execute(
                sa.select(annotated_variants).where(annotated_variants.c.rsid == "rs_nomatch")
            ).fetchone()
        assert row is None

    def test_crash_recovery_clears_previous(
        self,
        sample_with_variants: sa.Engine,
        mock_registry: MagicMock,
    ) -> None:
        """Re-running annotation deletes previous results first."""
        result1 = run_annotation(sample_with_variants, mock_registry)
        result2 = run_annotation(sample_with_variants, mock_registry)

        # Same number of rows written
        assert result1.rows_written == result2.rows_written

        # No duplicates
        with sample_with_variants.connect() as conn:
            count = conn.execute(
                sa.select(sa.func.count()).select_from(annotated_variants)
            ).scalar()
        assert count == result2.rows_written

    def test_empty_sample(
        self,
        sample_engine: sa.Engine,
        mock_registry: MagicMock,
    ) -> None:
        """Empty sample returns zeros."""
        result = run_annotation(sample_engine, mock_registry)
        assert result.total_variants == 0
        assert result.rows_written == 0

    def test_progress_callback(
        self,
        sample_with_variants: sa.Engine,
        mock_registry: MagicMock,
    ) -> None:
        """Progress callback is invoked at least once."""
        calls: list[tuple[int, int]] = []
        run_annotation(
            sample_with_variants,
            mock_registry,
            progress_callback=lambda done, total: calls.append((done, total)),
        )
        assert len(calls) >= 1
        # Final call should indicate all variants processed
        last_done, last_total = calls[-1]
        assert last_done == last_total

    def test_graceful_degradation_missing_vep(
        self,
        sample_with_variants: sa.Engine,
        reference_engine: sa.Engine,
        gnomad_engine: sa.Engine,
        dbnsfp_engine: sa.Engine,
    ) -> None:
        """Annotation proceeds when VEP engine is unavailable."""
        registry = MagicMock()
        registry.reference_engine = reference_engine
        # VEP engine raises an exception when accessed
        type(registry).vep_engine = property(
            lambda self: (_ for _ in ()).throw(FileNotFoundError("no VEP"))
        )
        type(registry).gnomad_engine = property(lambda self: gnomad_engine)
        type(registry).dbnsfp_engine = property(lambda self: dbnsfp_engine)

        result = run_annotation(sample_with_variants, registry)
        assert result.vep_matched == 0
        assert result.clinvar_matched > 0  # ClinVar should still work
        assert result.rows_written > 0

    def test_genotype_preserved(
        self,
        sample_with_variants: sa.Engine,
        mock_registry: MagicMock,
    ) -> None:
        """Genotype from raw_variants is carried into annotated_variants."""
        run_annotation(sample_with_variants, mock_registry)

        with sample_with_variants.connect() as conn:
            row = conn.execute(
                sa.select(annotated_variants).where(annotated_variants.c.rsid == "rs429358")
            ).fetchone()
        assert row is not None
        assert row.genotype == "TC"

    def test_custom_batch_size(
        self,
        sample_with_variants: sa.Engine,
        mock_registry: MagicMock,
    ) -> None:
        """Custom batch size of 3 processes multiple batches."""
        result = run_annotation(sample_with_variants, mock_registry, batch_size=3)
        assert result.batches_processed >= 2
        assert result.rows_written > 0


# ═══════════════════════════════════════════════════════════════════════
# T2-04: Integration test - 1000 variants end-to-end
# ═══════════════════════════════════════════════════════════════════════


class TestIntegration1000Variants:
    """T2-04: Annotation engine processes 1000 variants end-to-end."""

    def test_1000_variants_all_fields(
        self,
        sample_engine: sa.Engine,
        mock_registry: MagicMock,
    ) -> None:
        """Generate 1000 variants, annotate, verify fields populated."""
        # Insert 1000 raw variants (mix of known + synthetic)
        known = SEED_RAW_VARIANTS[:5]
        synthetic = [
            {"rsid": f"rs_synth_{i}", "chrom": "1", "pos": 200000 + i, "genotype": "AG"}
            for i in range(1000 - len(known))
        ]
        all_variants = known + synthetic

        with sample_engine.begin() as conn:
            conn.execute(raw_variants.insert(), all_variants)

        result = run_annotation(sample_engine, mock_registry)

        assert result.total_variants == 1000
        assert result.rows_written > 0
        # Known variants should have annotations
        assert result.vep_matched >= 3  # at least some known rsids match

        # Verify a known variant has all fields
        with sample_engine.connect() as conn:
            row = conn.execute(
                sa.select(annotated_variants).where(annotated_variants.c.rsid == "rs429358")
            ).fetchone()

        assert row is not None
        assert row.gene_symbol == "APOE"
        assert row.clinvar_significance is not None
        assert row.gnomad_af_global is not None
        assert row.cadd_phred is not None
        assert row.annotation_coverage == VEP_BIT | CLINVAR_BIT | GNOMAD_BIT | DBNSFP_BIT
