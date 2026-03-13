"""Tests for variant density histogram API (P2-23).

T2-21: Density histogram renders with correct bin counts.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from backend.api.routes.variants import BIN_SIZE, _consequence_to_tier  # noqa: PLC2701
from backend.config import Settings
from backend.db.connection import DBRegistry, reset_registry
from backend.db.sample_schema import create_sample_tables
from backend.db.tables import (
    annotated_variants,
    raw_variants,
    reference_metadata,
    samples,
)

# ═══════════════════════════════════════════════════════════════════════
# Test data — variants spanning multiple chromosomes and 1 Mb bins
# ═══════════════════════════════════════════════════════════════════════

# Variants placed to test bin boundaries and consequence tiers.
DENSITY_TEST_VARIANTS = [
    # chr1 bin 0-1M: 2 variants (1 missense, 1 synonymous)
    {
        "rsid": "rs001",
        "chrom": "1",
        "pos": 100_000,
        "genotype": "AG",
        "consequence": "missense_variant",
        "annotation_coverage": 1,
    },
    {
        "rsid": "rs002",
        "chrom": "1",
        "pos": 500_000,
        "genotype": "CT",
        "consequence": "synonymous_variant",
        "annotation_coverage": 1,
    },
    # chr1 bin 1-2M: 1 variant (frameshift = HIGH)
    {
        "rsid": "rs003",
        "chrom": "1",
        "pos": 1_200_000,
        "genotype": "AG",
        "consequence": "frameshift_variant",
        "annotation_coverage": 1,
    },
    # chr1 bin 2-3M: 1 variant (intron = MODIFIER)
    {
        "rsid": "rs004",
        "chrom": "1",
        "pos": 2_800_000,
        "genotype": "GG",
        "consequence": "intron_variant",
        "annotation_coverage": 1,
    },
    # chr2 bin 0-1M: 3 variants (2 missense, 1 stop_gained)
    {
        "rsid": "rs005",
        "chrom": "2",
        "pos": 100_000,
        "genotype": "AA",
        "consequence": "missense_variant",
        "annotation_coverage": 1,
    },
    {
        "rsid": "rs006",
        "chrom": "2",
        "pos": 200_000,
        "genotype": "CC",
        "consequence": "missense_variant",
        "annotation_coverage": 1,
    },
    {
        "rsid": "rs007",
        "chrom": "2",
        "pos": 300_000,
        "genotype": "AG",
        "consequence": "stop_gained",
        "annotation_coverage": 1,
    },
    # chr22 bin 19-20M: 1 variant (no consequence = MODIFIER)
    {
        "rsid": "rs008",
        "chrom": "22",
        "pos": 19_963_748,
        "genotype": "AG",
        "consequence": None,
        "annotation_coverage": 1,
    },
]

# Raw variants (no consequence column)
RAW_DENSITY_VARIANTS = [
    {"rsid": "rs100", "chrom": "1", "pos": 100_000, "genotype": "AG"},
    {"rsid": "rs101", "chrom": "1", "pos": 500_000, "genotype": "CT"},
    {"rsid": "rs200", "chrom": "2", "pos": 100_000, "genotype": "AA"},
]


def _setup_density_client(
    tmp_data_dir: Path,
    *,
    variants_table: sa.Table,
    variants_data: list[dict],
    db_filename: str = "sample_1.db",
):
    """Helper: create TestClient with a sample pre-loaded with given variants."""
    settings = Settings(data_dir=tmp_data_dir, wal_mode=False)

    ref_path = settings.reference_db_path
    ref_engine = sa.create_engine(f"sqlite:///{ref_path}")
    reference_metadata.create_all(ref_engine)

    with ref_engine.begin() as conn:
        result = conn.execute(
            samples.insert().values(
                name="density_sample",
                db_path=f"samples/{db_filename}",
                file_format="23andme_v5",
                file_hash="densityhash123",
            )
        )
        sample_id = result.lastrowid
    ref_engine.dispose()

    sample_db_path = tmp_data_dir / "samples" / db_filename
    sample_engine = sa.create_engine(f"sqlite:///{sample_db_path}")
    create_sample_tables(sample_engine)
    with sample_engine.begin() as conn:
        conn.execute(variants_table.insert(), variants_data)
    sample_engine.dispose()

    with (
        patch("backend.main.get_settings", return_value=settings),
        patch("backend.db.connection.get_settings", return_value=settings),
        patch("backend.api.routes.variants.get_registry") as mock_reg,
        patch("backend.api.routes.ingest.get_registry") as mock_reg2,
        patch("backend.api.routes.samples.get_registry") as mock_reg3,
    ):
        reset_registry()
        registry = DBRegistry(settings)
        mock_reg.return_value = registry
        mock_reg2.return_value = registry
        mock_reg3.return_value = registry

        from backend.main import create_app

        app = create_app()
        with TestClient(app) as tc:
            yield tc, sample_id

        registry.dispose_all()
        reset_registry()


@pytest.fixture
def density_client(tmp_data_dir: Path):
    """TestClient with annotated variants for density testing."""
    yield from _setup_density_client(
        tmp_data_dir,
        variants_table=annotated_variants,
        variants_data=DENSITY_TEST_VARIANTS,
    )


@pytest.fixture
def density_client_raw(tmp_data_dir: Path):
    """TestClient with raw variants (no consequence column)."""
    yield from _setup_density_client(
        tmp_data_dir,
        variants_table=raw_variants,
        variants_data=RAW_DENSITY_VARIANTS,
        db_filename="sample_raw.db",
    )


# ═══════════════════════════════════════════════════════════════════════
# Unit tests: consequence tier mapping
# ═══════════════════════════════════════════════════════════════════════


class TestConsequenceToTier:
    """Unit tests for _consequence_to_tier helper."""

    def test_high_consequences(self):
        assert _consequence_to_tier("frameshift_variant") == "HIGH"
        assert _consequence_to_tier("stop_gained") == "HIGH"
        assert _consequence_to_tier("splice_acceptor_variant") == "HIGH"
        assert _consequence_to_tier("start_lost") == "HIGH"

    def test_moderate_consequences(self):
        assert _consequence_to_tier("missense_variant") == "MODERATE"
        assert _consequence_to_tier("inframe_deletion") == "MODERATE"
        assert _consequence_to_tier("inframe_insertion") == "MODERATE"

    def test_low_consequences(self):
        assert _consequence_to_tier("synonymous_variant") == "LOW"
        assert _consequence_to_tier("splice_region_variant") == "LOW"

    def test_modifier_for_unknown(self):
        assert _consequence_to_tier("intron_variant") == "MODIFIER"
        assert _consequence_to_tier("intergenic_variant") == "MODIFIER"
        assert _consequence_to_tier("upstream_gene_variant") == "MODIFIER"

    def test_modifier_for_none(self):
        assert _consequence_to_tier(None) == "MODIFIER"

    def test_modifier_for_empty(self):
        assert _consequence_to_tier("") == "MODIFIER"


# ═══════════════════════════════════════════════════════════════════════
# GET /api/variants/density — Annotated variants
# ═══════════════════════════════════════════════════════════════════════


class TestVariantDensity:
    """GET /api/variants/density returns per 1 Mb bins with consequence tiers."""

    def test_returns_200(self, density_client):
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        assert response.status_code == 200

    def test_response_structure(self, density_client):
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        data = response.json()
        assert "bins" in data
        assert "bin_size" in data
        assert data["bin_size"] == BIN_SIZE

    def test_bin_fields(self, density_client):
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        data = response.json()
        b = data["bins"][0]
        expected_fields = (
            "chrom",
            "bin_start",
            "bin_end",
            "high",
            "moderate",
            "low",
            "modifier",
            "total",
        )
        for field in expected_fields:
            assert field in b

    def test_correct_number_of_bins(self, density_client):
        """Should have 5 distinct bins across chr1, chr2, chr22."""
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        data = response.json()
        assert len(data["bins"]) == 5

    def test_bin_counts_chr1_first_bin(self, density_client):
        """chr1 bin 0-1M: 1 missense (MODERATE) + 1 synonymous (LOW)."""
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        bins = response.json()["bins"]
        b = bins[0]
        assert b["chrom"] == "1"
        assert b["bin_start"] == 0
        assert b["moderate"] == 1  # missense
        assert b["low"] == 1  # synonymous
        assert b["high"] == 0
        assert b["modifier"] == 0
        assert b["total"] == 2

    def test_bin_counts_chr1_second_bin(self, density_client):
        """chr1 bin 1-2M: 1 frameshift (HIGH)."""
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        bins = response.json()["bins"]
        b = bins[1]
        assert b["chrom"] == "1"
        assert b["bin_start"] == 1_000_000
        assert b["high"] == 1
        assert b["total"] == 1

    def test_bin_counts_chr2(self, density_client):
        """chr2 bin 0-1M: 2 missense (MODERATE) + 1 stop_gained (HIGH)."""
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        bins = response.json()["bins"]
        # Find chr2 bin
        chr2_bins = [b for b in bins if b["chrom"] == "2"]
        assert len(chr2_bins) == 1
        b = chr2_bins[0]
        assert b["moderate"] == 2
        assert b["high"] == 1
        assert b["total"] == 3

    def test_null_consequence_is_modifier(self, density_client):
        """Variants with NULL consequence should be counted as MODIFIER."""
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        bins = response.json()["bins"]
        chr22_bins = [b for b in bins if b["chrom"] == "22"]
        assert len(chr22_bins) == 1
        assert chr22_bins[0]["modifier"] == 1
        assert chr22_bins[0]["total"] == 1

    def test_canonical_chrom_order(self, density_client):
        """Bins should be sorted by canonical chromosome order."""
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        bins = response.json()["bins"]
        chroms = [b["chrom"] for b in bins]
        # Should be: 1, 1, 1, 2, 22 (canonical order)
        assert chroms == ["1", "1", "1", "2", "22"]

    def test_bins_sorted_by_position_within_chrom(self, density_client):
        """Within a chromosome, bins should be sorted by bin_start."""
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        bins = response.json()["bins"]
        chr1_bins = [b for b in bins if b["chrom"] == "1"]
        starts = [b["bin_start"] for b in chr1_bins]
        assert starts == sorted(starts)

    def test_bin_end_is_start_plus_size(self, density_client):
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        bins = response.json()["bins"]
        for b in bins:
            assert b["bin_end"] == b["bin_start"] + BIN_SIZE

    def test_total_equals_tier_sum(self, density_client):
        """Total should equal sum of all tier counts in each bin."""
        client, sid = density_client
        response = client.get(f"/api/variants/density?sample_id={sid}")
        bins = response.json()["bins"]
        for b in bins:
            assert b["total"] == b["high"] + b["moderate"] + b["low"] + b["modifier"]

    def test_nonexistent_sample_returns_404(self, density_client):
        client, _ = density_client
        response = client.get("/api/variants/density?sample_id=999")
        assert response.status_code == 404

    def test_missing_sample_id_returns_422(self, density_client):
        client, _ = density_client
        response = client.get("/api/variants/density")
        assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# GET /api/variants/density — Raw variants (no consequence column)
# ═══════════════════════════════════════════════════════════════════════


class TestVariantDensityRaw:
    """Density endpoint works with raw_variants (all variants → MODIFIER)."""

    def test_returns_200(self, density_client_raw):
        client, sid = density_client_raw
        response = client.get(f"/api/variants/density?sample_id={sid}")
        assert response.status_code == 200

    def test_all_modifier_tier(self, density_client_raw):
        """Raw variants have no consequence, so everything is MODIFIER."""
        client, sid = density_client_raw
        response = client.get(f"/api/variants/density?sample_id={sid}")
        bins = response.json()["bins"]
        for b in bins:
            assert b["high"] == 0
            assert b["moderate"] == 0
            assert b["low"] == 0
            assert b["modifier"] == b["total"]

    def test_correct_bin_count(self, density_client_raw):
        """Should have 2 bins: chr1:0-1M (2 variants), chr2:0-1M (1 variant)."""
        client, sid = density_client_raw
        response = client.get(f"/api/variants/density?sample_id={sid}")
        bins = response.json()["bins"]
        assert len(bins) == 2
        assert bins[0]["chrom"] == "1"
        assert bins[0]["total"] == 2
        assert bins[1]["chrom"] == "2"
        assert bins[1]["total"] == 1
