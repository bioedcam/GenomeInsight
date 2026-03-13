"""Tests for consequence summary API endpoint (P2-25).

T2-22: Consequence donut shows expected distribution for test data.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

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
# Test data
# ═══════════════════════════════════════════════════════════════════════

CONSEQUENCE_TEST_VARIANTS = [
    # 3 missense (MODERATE)
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
        "pos": 200_000,
        "genotype": "CT",
        "consequence": "missense_variant",
        "annotation_coverage": 1,
    },
    {
        "rsid": "rs003",
        "chrom": "2",
        "pos": 100_000,
        "genotype": "AG",
        "consequence": "missense_variant",
        "annotation_coverage": 1,
    },
    # 2 synonymous (LOW)
    {
        "rsid": "rs004",
        "chrom": "1",
        "pos": 300_000,
        "genotype": "GG",
        "consequence": "synonymous_variant",
        "annotation_coverage": 1,
    },
    {
        "rsid": "rs005",
        "chrom": "3",
        "pos": 100_000,
        "genotype": "AA",
        "consequence": "synonymous_variant",
        "annotation_coverage": 1,
    },
    # 1 frameshift (HIGH)
    {
        "rsid": "rs006",
        "chrom": "1",
        "pos": 400_000,
        "genotype": "AG",
        "consequence": "frameshift_variant",
        "annotation_coverage": 1,
    },
    # 2 intron (MODIFIER)
    {
        "rsid": "rs007",
        "chrom": "2",
        "pos": 200_000,
        "genotype": "CC",
        "consequence": "intron_variant",
        "annotation_coverage": 1,
    },
    {
        "rsid": "rs008",
        "chrom": "4",
        "pos": 100_000,
        "genotype": "GG",
        "consequence": "intron_variant",
        "annotation_coverage": 1,
    },
    # 1 NULL consequence (MODIFIER / unknown)
    {
        "rsid": "rs009",
        "chrom": "5",
        "pos": 100_000,
        "genotype": "AG",
        "consequence": None,
        "annotation_coverage": 1,
    },
]

RAW_CONSEQUENCE_VARIANTS = [
    {"rsid": "rs100", "chrom": "1", "pos": 100_000, "genotype": "AG"},
    {"rsid": "rs101", "chrom": "1", "pos": 200_000, "genotype": "CT"},
    {"rsid": "rs102", "chrom": "2", "pos": 100_000, "genotype": "AA"},
]


def _setup_consequence_client(
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
                name="consequence_sample",
                db_path=f"samples/{db_filename}",
                file_format="23andme_v5",
                file_hash="consequencehash123",
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
def consequence_client(tmp_data_dir: Path):
    """TestClient with annotated variants for consequence summary testing."""
    yield from _setup_consequence_client(
        tmp_data_dir,
        variants_table=annotated_variants,
        variants_data=CONSEQUENCE_TEST_VARIANTS,
    )


@pytest.fixture
def consequence_client_raw(tmp_data_dir: Path):
    """TestClient with raw variants (no consequence column)."""
    yield from _setup_consequence_client(
        tmp_data_dir,
        variants_table=raw_variants,
        variants_data=RAW_CONSEQUENCE_VARIANTS,
        db_filename="sample_raw.db",
    )


# ═══════════════════════════════════════════════════════════════════════
# GET /api/variants/consequence-summary — Annotated variants
# ═══════════════════════════════════════════════════════════════════════


class TestConsequenceSummary:
    """GET /api/variants/consequence-summary returns per-type counts."""

    def test_returns_200(self, consequence_client):
        client, sid = consequence_client
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        assert response.status_code == 200

    def test_response_structure(self, consequence_client):
        client, sid = consequence_client
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_item_fields(self, consequence_client):
        client, sid = consequence_client
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        data = response.json()
        item = data["items"][0]
        assert "consequence" in item
        assert "count" in item
        assert "tier" in item

    def test_correct_total(self, consequence_client):
        client, sid = consequence_client
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        data = response.json()
        assert data["total"] == len(CONSEQUENCE_TEST_VARIANTS)

    def test_total_matches_item_sum(self, consequence_client):
        client, sid = consequence_client
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        data = response.json()
        item_sum = sum(item["count"] for item in data["items"])
        assert item_sum == data["total"]

    def test_sorted_by_count_descending(self, consequence_client):
        client, sid = consequence_client
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        data = response.json()
        counts = [item["count"] for item in data["items"]]
        assert counts == sorted(counts, reverse=True)

    def test_correct_consequence_counts(self, consequence_client):
        client, sid = consequence_client
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        data = response.json()
        by_consequence = {item["consequence"]: item["count"] for item in data["items"]}
        assert by_consequence["missense_variant"] == 3
        assert by_consequence["synonymous_variant"] == 2
        assert by_consequence["frameshift_variant"] == 1
        assert by_consequence["intron_variant"] == 2

    def test_correct_tiers(self, consequence_client):
        client, sid = consequence_client
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        data = response.json()
        by_consequence = {item["consequence"]: item["tier"] for item in data["items"]}
        assert by_consequence["missense_variant"] == "MODERATE"
        assert by_consequence["synonymous_variant"] == "LOW"
        assert by_consequence["frameshift_variant"] == "HIGH"
        assert by_consequence["intron_variant"] == "MODIFIER"

    def test_null_consequence_becomes_unknown(self, consequence_client):
        client, sid = consequence_client
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        data = response.json()
        by_consequence = {item["consequence"]: item for item in data["items"]}
        assert "unknown" in by_consequence
        assert by_consequence["unknown"]["count"] == 1
        assert by_consequence["unknown"]["tier"] == "MODIFIER"

    def test_nonexistent_sample_returns_404(self, consequence_client):
        client, _ = consequence_client
        response = client.get("/api/variants/consequence-summary?sample_id=999")
        assert response.status_code == 404

    def test_missing_sample_id_returns_422(self, consequence_client):
        client, _ = consequence_client
        response = client.get("/api/variants/consequence-summary")
        assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# GET /api/variants/consequence-summary — Raw variants
# ═══════════════════════════════════════════════════════════════════════


class TestConsequenceSummaryRaw:
    """Consequence summary with raw_variants (no consequence column)."""

    def test_returns_200(self, consequence_client_raw):
        client, sid = consequence_client_raw
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        assert response.status_code == 200

    def test_all_unknown(self, consequence_client_raw):
        """Raw variants have no consequence, so everything is 'unknown'."""
        client, sid = consequence_client_raw
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["consequence"] == "unknown"
        assert data["items"][0]["tier"] == "MODIFIER"
        assert data["items"][0]["count"] == len(RAW_CONSEQUENCE_VARIANTS)

    def test_correct_total(self, consequence_client_raw):
        client, sid = consequence_client_raw
        response = client.get(f"/api/variants/consequence-summary?sample_id={sid}")
        data = response.json()
        assert data["total"] == len(RAW_CONSEQUENCE_VARIANTS)
