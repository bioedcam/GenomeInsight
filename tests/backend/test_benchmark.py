"""Performance benchmark tests for the annotation pipeline (P2-29 / T2-24).

Tests that the full annotation engine meets PRD performance targets:
  - Full 600k SNP annotation: < 2 min (target) / < 5 min (hard limit)
  - Ingest (raw variant loading): < 30s (target) / < 2 min (hard limit)

These tests use synthetic data with in-memory SQLite databases to benchmark
the annotation pipeline without requiring real reference databases.

Marked ``slow`` so they can be excluded from fast CI runs::

    pytest -m "not slow"        # skip benchmarks
    pytest -m slow              # run only benchmarks
"""

from __future__ import annotations

import time

import pytest
import sqlalchemy as sa

from backend.annotation.engine import run_annotation
from backend.db.sample_schema import create_sample_tables
from backend.db.tables import annotated_variants, raw_variants, reference_metadata
from scripts.benchmark import (
    BenchmarkDBRegistry,
    _create_shared_memory_engine,
    generate_raw_variants,
    seed_clinvar,
    seed_dbnsfp,
    seed_gene_phenotype,
    seed_gnomad,
    seed_vep_bundle,
)

# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def benchmark_data_600k() -> list[dict]:
    """Generate 600k synthetic raw variants (cached per module)."""
    return generate_raw_variants(600_000)


@pytest.fixture(scope="module")
def benchmark_rsids_600k(benchmark_data_600k: list[dict]) -> list[str]:
    """Extract rsids from 600k benchmark data."""
    return [r["rsid"] for r in benchmark_data_600k]


@pytest.fixture(scope="module")
def benchmark_engines_600k(
    benchmark_rsids_600k: list[str],
) -> dict[str, sa.Engine]:
    """Pre-populated in-memory annotation source engines (cached per module).

    Returns a dict with keys: reference, vep, gnomad, dbnsfp.
    """
    reference_engine = _create_shared_memory_engine()
    reference_metadata.create_all(reference_engine)

    vep_engine = _create_shared_memory_engine()
    gnomad_engine = _create_shared_memory_engine()
    dbnsfp_engine = _create_shared_memory_engine()

    rsids = benchmark_rsids_600k
    seed_vep_bundle(vep_engine, rsids, match_rate=0.7)
    seed_clinvar(reference_engine, rsids, match_rate=0.05)
    seed_gene_phenotype(reference_engine)
    seed_gnomad(gnomad_engine, rsids, match_rate=0.6)
    seed_dbnsfp(dbnsfp_engine, rsids, match_rate=0.5)

    return {
        "reference": reference_engine,
        "vep": vep_engine,
        "gnomad": gnomad_engine,
        "dbnsfp": dbnsfp_engine,
    }


# ── Benchmark: ingest timing ────────────────────────────────────────────


@pytest.mark.slow
def test_ingest_600k_timing(benchmark_data_600k: list[dict]) -> None:
    """T2-24 sub-test: 600k variant ingest completes within 2 minutes."""
    sample_engine = _create_shared_memory_engine()
    create_sample_tables(sample_engine)

    t0 = time.perf_counter()
    batch_size = 50_000
    with sample_engine.begin() as conn:
        for i in range(0, len(benchmark_data_600k), batch_size):
            conn.execute(raw_variants.insert(), benchmark_data_600k[i : i + batch_size])
    elapsed = time.perf_counter() - t0

    # Verify all rows loaded
    with sample_engine.connect() as conn:
        count = conn.execute(sa.select(sa.func.count()).select_from(raw_variants)).scalar()
    assert count == 600_000

    # PRD target: < 30s, acceptable: < 2 min
    assert elapsed < 120.0, f"Ingest took {elapsed:.1f}s, exceeds 2-minute hard limit"


# ── Benchmark: full annotation timing ────────────────────────────────────


@pytest.mark.slow
def test_annotation_600k_timing(
    benchmark_data_600k: list[dict],
    benchmark_engines_600k: dict[str, sa.Engine],
) -> None:
    """T2-24: Full 600k SNP annotation completes within 5 minutes (hard limit).

    PRD target: < 2 min. Acceptable max: < 5 min.
    """
    # Create a fresh sample DB and load raw variants
    sample_engine = _create_shared_memory_engine()
    create_sample_tables(sample_engine)
    batch_size = 50_000
    with sample_engine.begin() as conn:
        for i in range(0, len(benchmark_data_600k), batch_size):
            conn.execute(raw_variants.insert(), benchmark_data_600k[i : i + batch_size])

    # Build registry
    engines = benchmark_engines_600k
    registry = BenchmarkDBRegistry(
        reference_engine=engines["reference"],
        vep_engine=engines["vep"],
        gnomad_engine=engines["gnomad"],
        dbnsfp_engine=engines["dbnsfp"],
    )

    # Time the annotation pipeline
    t0 = time.perf_counter()
    result = run_annotation(sample_engine, registry)
    elapsed = time.perf_counter() - t0

    # Verify output
    with sample_engine.connect() as conn:
        count = conn.execute(sa.select(sa.func.count()).select_from(annotated_variants)).scalar()

    assert result.total_variants == 600_000
    assert count > 0, "No annotated variants written"
    assert result.rows_written == count
    assert result.vep_matched > 0, "No VEP matches"
    assert result.clinvar_matched > 0, "No ClinVar matches"
    assert result.gnomad_matched > 0, "No gnomAD matches"
    assert result.dbnsfp_matched > 0, "No dbNSFP matches"
    assert result.gene_phenotype_matched > 0, "No gene-phenotype matches"
    assert not result.errors, f"Annotation errors: {result.errors}"

    # PRD hard limit: < 5 min (300s)
    assert elapsed < 300.0, f"Annotation took {elapsed:.1f}s, exceeds 5-minute hard limit"

    # Log performance info
    rate = 600_000 / elapsed if elapsed > 0 else 0
    print(
        f"\n  Annotation benchmark: {elapsed:.1f}s "
        f"({rate:,.0f} var/s), "
        f"{result.rows_written:,} rows written, "
        f"{result.batches_processed} batches"
    )
    if elapsed <= 120.0:
        print("  Status: PASS (target < 2 min)")
    else:
        print("  Status: PASS (acceptable < 5 min)")


# ── Smaller benchmark for CI fast path ───────────────────────────────────


def test_annotation_10k_smoke() -> None:
    """Quick smoke test: 10k variants annotate without errors.

    Always runs (not marked slow) to catch annotation pipeline regressions.
    """
    num = 10_000
    raw_data = generate_raw_variants(num, seed=99)
    rsids = [r["rsid"] for r in raw_data]

    # Create engines
    sample_engine = _create_shared_memory_engine()
    create_sample_tables(sample_engine)
    with sample_engine.begin() as conn:
        conn.execute(raw_variants.insert(), raw_data)

    reference_engine = _create_shared_memory_engine()
    reference_metadata.create_all(reference_engine)
    vep_engine = _create_shared_memory_engine()
    gnomad_engine = _create_shared_memory_engine()
    dbnsfp_engine = _create_shared_memory_engine()

    seed_vep_bundle(vep_engine, rsids, match_rate=0.7, seed=99)
    seed_clinvar(reference_engine, rsids, match_rate=0.05, seed=99)
    seed_gene_phenotype(reference_engine)
    seed_gnomad(gnomad_engine, rsids, match_rate=0.6, seed=99)
    seed_dbnsfp(dbnsfp_engine, rsids, match_rate=0.5, seed=99)

    registry = BenchmarkDBRegistry(
        reference_engine=reference_engine,
        vep_engine=vep_engine,
        gnomad_engine=gnomad_engine,
        dbnsfp_engine=dbnsfp_engine,
    )

    t0 = time.perf_counter()
    result = run_annotation(sample_engine, registry)
    elapsed = time.perf_counter() - t0

    assert result.total_variants == num
    assert result.rows_written > 0
    assert not result.errors
    # 10k should complete well under 30s
    assert elapsed < 30.0, f"10k annotation took {elapsed:.1f}s"
