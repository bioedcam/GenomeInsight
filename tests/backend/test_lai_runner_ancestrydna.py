"""LAI runner: AncestryDNA single-key telemetry (Step 22; Plan §6.6).

Builds a small in-memory sample DB stamped with ``file_format='ancestrydna_v2.0'``
and exercises the LAI runner's filter + per-source accumulator. Asserts:

- Non-zero variant count after filtering.
- All retained variants are autosomal.
- Telemetry collapses to single-key ``{"ancestrydna": {hits, drops}}`` (Plan §6.6).

The full Phase-0 fixture ``sample_ancestrydna_v2.txt`` is curated in step 34;
this test uses an inline payload derived from the existing v1 fixture so step 22
can ship independently. Soft-gate (degraded_coverage) cases land in step 23.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import sqlalchemy as sa

from backend.analysis.lai import _read_sample_file_format, _read_sample_genotypes
from backend.analysis.lai_runner import LAIRunner
from backend.db.sample_schema import create_sample_tables
from backend.db.tables import raw_variants, sample_metadata_table

# A minimal AncestryDNA-shaped payload (chrom/pos/genotype only; rsids picked
# to overlap the runner stub's liftover map below). Includes mixed autosomal,
# chrY/MT, an in-bundle but chrX-mapped rsid (drop bucket), no-call, and indel
# rows so the filter and per-source counters exercise the full set of branches.
_ANCESTRYDNA_ROWS = [
    {"rsid": "rs_auto_1", "chrom": "1", "pos": 82154, "genotype": "AA"},
    {"rsid": "rs_auto_2", "chrom": "1", "pos": 752566, "genotype": "AG"},
    {"rsid": "rs_auto_3", "chrom": "2", "pos": 100200, "genotype": "GG"},
    {"rsid": "rs_auto_4", "chrom": "22", "pos": 42523610, "genotype": "AG"},
    {"rsid": "rs_off_bundle", "chrom": "5", "pos": 11856378, "genotype": "CT"},
    {"rsid": "rs_chry", "chrom": "Y", "pos": 6873643, "genotype": "C"},
    {"rsid": "rs_nocall", "chrom": "1", "pos": 800007, "genotype": "00"},
    {"rsid": "rs_indel", "chrom": "1", "pos": 11854476, "genotype": "DI"},
    {"rsid": "rs_chrx_mapped", "chrom": "1", "pos": 999000, "genotype": "AG"},
]


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def ancestrydna_sample_engine() -> sa.Engine:
    """In-memory sample DB stamped with ``file_format='ancestrydna_v2.0'``."""
    engine = sa.create_engine("sqlite://")
    create_sample_tables(engine)
    with engine.begin() as conn:
        conn.execute(
            sample_metadata_table.insert().values(
                id=1,
                name="ancestrydna_test",
                file_format="ancestrydna_v2.0",
                file_hash="testhash",
            )
        )
        conn.execute(
            raw_variants.insert(),
            _ANCESTRYDNA_ROWS,
        )
    return engine


@pytest.fixture()
def runner() -> LAIRunner:
    """LAIRunner stub with a deterministic rsid_lookup; bundle init bypassed."""
    instance = LAIRunner.__new__(LAIRunner)
    instance.rsid_lookup = {
        "rs_auto_1": ("chr1", 82154),
        "rs_auto_2": ("chr1", 752566),
        "rs_auto_3": ("chr2", 100200),
        "rs_auto_4": ("chr22", 42523610),
        # In-bundle but maps to chrX → drop bucket (Plan §6.6 LAI is autosomal)
        "rs_chrx_mapped": ("chrX", 999000),
        # rs_off_bundle deliberately absent → drop bucket
    }
    return instance


# ── Tests ─────────────────────────────────────────────────────────────────


class TestAncestryDNAReadPath:
    """`_read_sample_file_format` + `_read_sample_genotypes` thread vendor + source."""

    def test_reads_ancestrydna_file_format(self, ancestrydna_sample_engine):
        assert _read_sample_file_format(ancestrydna_sample_engine) == "ancestrydna_v2.0"

    def test_genotypes_default_source_to_empty_on_pre_phase3_db(
        self, ancestrydna_sample_engine
    ):
        genotypes = _read_sample_genotypes(ancestrydna_sample_engine)
        assert len(genotypes) == len(_ANCESTRYDNA_ROWS)
        assert all(gt["source"] == "" for gt in genotypes)
        assert {gt["rsid"] for gt in genotypes} == {r["rsid"] for r in _ANCESTRYDNA_ROWS}


class TestAncestryDNARunnerTelemetry:
    """End-to-end: AncestryDNA sample DB → single-key telemetry."""

    def test_non_zero_autosomal_variant_count(
        self, runner, ancestrydna_sample_engine, tmp_path
    ):
        genotypes = _read_sample_genotypes(ancestrydna_sample_engine)
        filtered = runner._filter_genotypes(genotypes)
        with patch.object(LAIRunner, "_write_single_vcf", lambda *a, **k: None):
            vcf_paths, total, _ = runner._write_per_chrom_vcfs(filtered, tmp_path)

        assert total > 0  # non-zero variant count
        # All written contigs are autosomal (chr1..chr22)
        autosomal_chroms = {f"chr{i}" for i in range(1, 23)}
        assert set(vcf_paths.keys()) <= autosomal_chroms
        # The runner already drops Y/MT/X + no-calls + indels in _filter_genotypes
        # and rs_chrx_mapped via the autosomal post-lookup check.
        assert all(s["chrom"] in autosomal_chroms for s in [
            {"chrom": chrom} for chrom in vcf_paths
        ])

    def test_single_key_ancestrydna_telemetry(
        self, runner, ancestrydna_sample_engine, tmp_path
    ):
        file_format = _read_sample_file_format(ancestrydna_sample_engine)
        genotypes = _read_sample_genotypes(ancestrydna_sample_engine)
        filtered = runner._filter_genotypes(genotypes)
        with patch.object(LAIRunner, "_write_single_vcf", lambda *a, **k: None):
            _, _, per_source = runner._write_per_chrom_vcfs(filtered, tmp_path)

        telemetry = LAIRunner._build_coverage_telemetry(per_source, file_format)
        assert set(telemetry.keys()) == {"ancestrydna"}
        assert telemetry["ancestrydna"]["hits"] == 4  # rs_auto_1..4
        # Drops: rs_off_bundle (autosomal but missing) + rs_chrx_mapped
        # (in-bundle but non-autosomal). rs_chry / rs_nocall / rs_indel are
        # filtered upstream by _filter_genotypes and never reach the
        # lookup-based accumulator.
        assert telemetry["ancestrydna"]["drops"] == 2

    def test_lookup_drops_attribute_to_ancestrydna_source(
        self, runner, ancestrydna_sample_engine, tmp_path
    ):
        """Single empty-source bucket — no S1/S2/both leakage on unmerged DB."""
        genotypes = _read_sample_genotypes(ancestrydna_sample_engine)
        filtered = runner._filter_genotypes(genotypes)
        with patch.object(LAIRunner, "_write_single_vcf", lambda *a, **k: None):
            _, _, per_source = runner._write_per_chrom_vcfs(filtered, tmp_path)

        # Only the empty-source bucket should exist on a pre-Phase-3 DB
        assert set(per_source.keys()) == {""}

    def test_ancestrydna_v2_0_format_dispatch(self):
        """`_build_coverage_telemetry` correctly derives 'ancestrydna' vendor."""
        per_source = {"": {"hits": 7, "drops": 2}}
        telemetry = LAIRunner._build_coverage_telemetry(per_source, "ancestrydna_v2.0")
        assert telemetry == {"ancestrydna": {"hits": 7, "drops": 2}}
