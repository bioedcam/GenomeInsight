"""Tests for the Runs-of-Homozygosity (ROH / FROH) autozygosity module.

Exercises the clean-room sliding-run detector: a clean long homozygous run is
detected as an ROH segment; FROH = segment length / fixed autosomal denominator;
heterozygous-rich regions and too-short runs produce nothing; a large
position-gap breaks a run; a single het within tolerance does not; and the
finding is framed as a genomic estimate ("not a diagnosis", "not a statement
about whether your parents are related"), stored at evidence_level 1.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from backend.analysis.roh import (
    AUTOSOMAL_GENOME_KB,
    MODULE,
    _genotype_state,
    detect_roh,
    store_roh_findings,
)
from backend.db.tables import findings, raw_variants


def _seed(engine: sa.Engine, rows: list[dict]) -> None:
    if rows:
        with engine.begin() as conn:
            conn.execute(sa.insert(raw_variants), rows)


def _run(
    chrom: str,
    start: int,
    count: int,
    *,
    spacing: int = 10_000,
    genotype: str = "AA",
    rs_prefix: str = "r",
) -> list[dict]:
    """Generate `count` evenly-spaced SNP rows on `chrom` from `start`."""
    return [
        {
            "rsid": f"{rs_prefix}{chrom}_{i}",
            "chrom": chrom,
            "pos": start + i * spacing,
            "genotype": genotype,
        }
        for i in range(count)
    ]


class TestGenotypeState:
    def test_homozygous(self) -> None:
        assert _genotype_state("AA") == "hom"
        assert _genotype_state("gg") == "hom"

    def test_heterozygous(self) -> None:
        assert _genotype_state("AG") == "het"

    def test_missing_variants(self) -> None:
        for gt in ("--", "", "A", "DD", "II", "0", None):
            assert _genotype_state(gt) == "miss"


class TestDetection:
    def test_clean_long_run_detected(self, sample_engine: sa.Engine) -> None:
        # 200 hom SNPs, 10 kb spacing → ~1990 kb span, 200 SNPs (≥1500 kb, ≥100).
        _seed(sample_engine, _run("1", 1_000_000, 200))
        result = detect_roh(sample_engine)
        assert len(result.segments) == 1
        seg = result.segments[0]
        assert seg.chrom == "1"
        assert seg.n_snps == 200
        assert seg.length_kb == pytest.approx(1990.0, abs=1.0)
        # FROH = total ROH length / fixed autosomal denominator (rounded to 5 dp).
        assert result.froh == pytest.approx(seg.length_kb / AUTOSOMAL_GENOME_KB, abs=5e-5)

    def test_short_run_not_detected(self, sample_engine: sa.Engine) -> None:
        # 50 hom SNPs over ~490 kb — below both thresholds.
        _seed(sample_engine, _run("1", 1_000_000, 50))
        result = detect_roh(sample_engine)
        assert result.segments == []
        assert result.froh == 0.0

    def test_heterozygous_region_not_detected(self, sample_engine: sa.Engine) -> None:
        _seed(sample_engine, _run("1", 1_000_000, 200, genotype="AG"))
        result = detect_roh(sample_engine)
        assert result.segments == []

    def test_single_het_within_tolerance_keeps_run(self, sample_engine: sa.Engine) -> None:
        rows = _run("1", 1_000_000, 200)
        rows[100]["genotype"] = "AG"  # one het embedded; tolerance is 1
        _seed(sample_engine, rows)
        result = detect_roh(sample_engine)
        assert len(result.segments) == 1
        # The single het is not counted as a homozygous SNP.
        assert result.segments[0].n_snps == 199

    def test_large_gap_breaks_run(self, sample_engine: sa.Engine) -> None:
        # Two qualifying blocks (each ~1990 kb, 200 SNPs) separated by a 2 Mb gap
        # (> MAX_GAP_KB=1000 kb), so the gap rule must split them into two ROHs.
        block_a = _run("1", 1_000_000, 200, rs_prefix="a")  # ends at 2_990_000
        block_b = _run("1", 4_990_000, 200, rs_prefix="b")  # 2 Mb gap before it
        _seed(sample_engine, block_a + block_b)
        result = detect_roh(sample_engine)
        assert len(result.segments) == 2

    def test_outbred_sample_no_roh(self, sample_engine: sa.Engine) -> None:
        # Alternating hom/het across the genome → no long runs.
        rows = []
        for i in range(400):
            rows.append(
                {
                    "rsid": f"r{i}",
                    "chrom": "2",
                    "pos": 1_000_000 + i * 10_000,
                    "genotype": "AA" if i % 2 == 0 else "AG",
                }
            )
        _seed(sample_engine, rows)
        result = detect_roh(sample_engine)
        assert result.segments == []


class TestStorage:
    def test_stores_single_summary_finding(self, sample_engine: sa.Engine) -> None:
        _seed(sample_engine, _run("1", 1_000_000, 200))
        result = detect_roh(sample_engine)
        assert store_roh_findings(result, sample_engine) == 1
        with sample_engine.connect() as conn:
            row = conn.execute(sa.select(findings).where(findings.c.module == MODULE)).fetchone()
        assert row.evidence_level == 1
        assert row.clinvar_significance is None
        assert row.category == "autozygosity"
        corpus = row.finding_text.lower()
        assert "not a diagnosis" in corpus
        assert "parents are related" in corpus

    def test_store_is_idempotent(self, sample_engine: sa.Engine) -> None:
        _seed(sample_engine, _run("1", 1_000_000, 200))
        result = detect_roh(sample_engine)
        store_roh_findings(result, sample_engine)
        store_roh_findings(result, sample_engine)
        with sample_engine.connect() as conn:
            n = conn.execute(
                sa.select(sa.func.count()).select_from(findings).where(findings.c.module == MODULE)
            ).scalar()
        assert n == 1

    def test_empty_result_still_stores_informational_finding(
        self, sample_engine: sa.Engine
    ) -> None:
        _seed(sample_engine, _run("1", 1_000_000, 30))  # too short → no segments
        result = detect_roh(sample_engine)
        assert result.segments == []
        assert store_roh_findings(result, sample_engine) == 1
        with sample_engine.connect() as conn:
            row = conn.execute(sa.select(findings).where(findings.c.module == MODULE)).fetchone()
        assert "froh" in row.finding_text.lower()
