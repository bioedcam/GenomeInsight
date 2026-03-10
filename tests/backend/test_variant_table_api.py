"""Tests for variant table API endpoints (P1-14, P1-15d).

T1-14: GET /api/variants returns cursor-paginated results.
       GET /api/variants/count returns total count.
T1-15d: Async total count returns correct value with annotation_coverage
        filtering; first page loads without waiting for count.
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
from backend.db.tables import annotated_variants, raw_variants, reference_metadata, samples

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
V5_FILE = FIXTURES / "sample_23andme_v5.txt"

# Deterministic test variants spanning multiple chromosomes.
# Ordered by canonical chrom sort: 1, 2, 10, 15, 19, 22, X, MT
TEST_VARIANTS = [
    {"rsid": "rs100", "chrom": "1", "pos": 50000, "genotype": "AA"},
    {"rsid": "rs101", "chrom": "1", "pos": 100000, "genotype": "AG"},
    {"rsid": "rs102", "chrom": "1", "pos": 200000, "genotype": "GG"},
    {"rsid": "rs200", "chrom": "2", "pos": 10000, "genotype": "CC"},
    {"rsid": "rs201", "chrom": "2", "pos": 20000, "genotype": "CT"},
    {"rsid": "rs1000", "chrom": "10", "pos": 50000, "genotype": "AA"},
    {"rsid": "rs1500", "chrom": "15", "pos": 30000, "genotype": "GG"},
    {"rsid": "rs1900", "chrom": "19", "pos": 44908684, "genotype": "TC"},
    {"rsid": "rs2200", "chrom": "22", "pos": 19963748, "genotype": "AG"},
    {"rsid": "rsX001", "chrom": "X", "pos": 5000, "genotype": "AA"},
    {"rsid": "rsMT01", "chrom": "MT", "pos": 1000, "genotype": "CC"},
]


@pytest.fixture
def client_with_sample(tmp_data_dir: Path):
    """FastAPI TestClient with a sample pre-loaded with TEST_VARIANTS.

    Yields (client, sample_id) tuple.
    """
    settings = Settings(data_dir=tmp_data_dir, wal_mode=False)

    # Create reference.db
    ref_path = settings.reference_db_path
    ref_engine = sa.create_engine(f"sqlite:///{ref_path}")
    reference_metadata.create_all(ref_engine)

    # Register a sample in reference.db
    with ref_engine.begin() as conn:
        result = conn.execute(
            samples.insert().values(
                name="test_sample",
                db_path="samples/sample_1.db",
                file_format="23andme_v5",
                file_hash="testhash123",
            )
        )
        sample_id = result.lastrowid
    ref_engine.dispose()

    # Create per-sample DB with test variants
    sample_db_path = tmp_data_dir / "samples" / "sample_1.db"
    sample_engine = sa.create_engine(f"sqlite:///{sample_db_path}")
    create_sample_tables(sample_engine)
    with sample_engine.begin() as conn:
        conn.execute(raw_variants.insert(), TEST_VARIANTS)
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


# ═══════════════════════════════════════════════════════════════════════
# GET /api/variants — Basic pagination
# ═══════════════════════════════════════════════════════════════════════


class TestListVariants:
    """GET /api/variants returns cursor-paginated raw variants."""

    def test_returns_200(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}")
        assert response.status_code == 200

    def test_returns_all_variants_when_under_limit(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&limit=50")
        data = response.json()
        assert len(data["items"]) == len(TEST_VARIANTS)
        assert data["has_more"] is False

    def test_returns_variant_fields(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&limit=1")
        item = response.json()["items"][0]
        assert "rsid" in item
        assert "chrom" in item
        assert "pos" in item
        assert "genotype" in item

    def test_canonical_chrom_order(self, client_with_sample):
        """Variants should be sorted by canonical chromosome order, not text."""
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&limit=50")
        items = response.json()["items"]
        chroms = [item["chrom"] for item in items]
        # Expected order: 1, 1, 1, 2, 2, 10, 15, 19, 22, X, MT
        expected = ["1", "1", "1", "2", "2", "10", "15", "19", "22", "X", "MT"]
        assert chroms == expected

    def test_within_chrom_sorted_by_pos(self, client_with_sample):
        """Within a chromosome, variants should be sorted by position."""
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&limit=50")
        items = response.json()["items"]
        chrom1_variants = [i for i in items if i["chrom"] == "1"]
        positions = [v["pos"] for v in chrom1_variants]
        assert positions == sorted(positions)

    def test_missing_sample_id_returns_422(self, client_with_sample):
        client, _ = client_with_sample
        response = client.get("/api/variants")
        assert response.status_code == 422

    def test_nonexistent_sample_returns_404(self, client_with_sample):
        client, _ = client_with_sample
        response = client.get("/api/variants?sample_id=999")
        assert response.status_code == 404

    def test_default_limit_is_50(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}")
        data = response.json()
        assert data["limit"] == 50


# ═══════════════════════════════════════════════════════════════════════
# Cursor-based pagination
# ═══════════════════════════════════════════════════════════════════════


class TestCursorPagination:
    """Keyset cursor pagination on (chrom, pos)."""

    def test_first_page_with_limit(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&limit=3")
        data = response.json()
        assert len(data["items"]) == 3
        assert data["has_more"] is True
        assert data["next_cursor_chrom"] is not None
        assert data["next_cursor_pos"] is not None

    def test_second_page_continues_from_cursor(self, client_with_sample):
        client, sid = client_with_sample
        # Page 1
        r1 = client.get(f"/api/variants?sample_id={sid}&limit=3")
        d1 = r1.json()
        cursor_chrom = d1["next_cursor_chrom"]
        cursor_pos = d1["next_cursor_pos"]

        # Page 2
        r2 = client.get(
            f"/api/variants?sample_id={sid}&limit=3"
            f"&cursor_chrom={cursor_chrom}&cursor_pos={cursor_pos}"
        )
        d2 = r2.json()
        assert len(d2["items"]) == 3

        # No overlap between pages
        page1_rsids = {i["rsid"] for i in d1["items"]}
        page2_rsids = {i["rsid"] for i in d2["items"]}
        assert page1_rsids.isdisjoint(page2_rsids)

    def test_full_traversal_returns_all_variants(self, client_with_sample):
        """Walking all pages collects every variant exactly once."""
        client, sid = client_with_sample
        all_items = []
        cursor_chrom = None
        cursor_pos = None

        for _ in range(20):  # safety limit
            params = f"sample_id={sid}&limit=3"
            if cursor_chrom is not None:
                params += f"&cursor_chrom={cursor_chrom}&cursor_pos={cursor_pos}"
            response = client.get(f"/api/variants?{params}")
            data = response.json()
            all_items.extend(data["items"])
            if not data["has_more"]:
                break
            cursor_chrom = data["next_cursor_chrom"]
            cursor_pos = data["next_cursor_pos"]

        assert len(all_items) == len(TEST_VARIANTS)
        collected_rsids = {i["rsid"] for i in all_items}
        expected_rsids = {v["rsid"] for v in TEST_VARIANTS}
        assert collected_rsids == expected_rsids

    def test_last_page_has_more_false(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&limit=50")
        data = response.json()
        assert data["has_more"] is False
        assert data["next_cursor_chrom"] is None
        assert data["next_cursor_pos"] is None

    def test_cursor_at_end_returns_empty(self, client_with_sample):
        """Cursor past the last variant returns an empty page."""
        client, sid = client_with_sample
        response = client.get(
            f"/api/variants?sample_id={sid}&cursor_chrom=MT&cursor_pos=999999"
        )
        data = response.json()
        assert len(data["items"]) == 0
        assert data["has_more"] is False

    def test_cursor_jump_to_chromosome(self, client_with_sample):
        """Providing cursor_chrom=10&cursor_pos=0 skips to chr10 variants."""
        client, sid = client_with_sample
        response = client.get(
            f"/api/variants?sample_id={sid}&cursor_chrom=2&cursor_pos=999999"
        )
        data = response.json()
        # Should skip past chrom 1 and 2, start at chrom 10
        assert len(data["items"]) > 0
        assert data["items"][0]["chrom"] == "10"


# ═══════════════════════════════════════════════════════════════════════
# Filtering
# ═══════════════════════════════════════════════════════════════════════


class TestFiltering:
    """Filter query parameter tests."""

    def test_filter_by_chrom(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&filter=chrom:1")
        data = response.json()
        assert all(i["chrom"] == "1" for i in data["items"])
        assert len(data["items"]) == 3  # 3 variants on chrom 1

    def test_filter_by_genotype(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&filter=genotype:AA")
        data = response.json()
        assert all(i["genotype"] == "AA" for i in data["items"])

    def test_filter_with_no_matches(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&filter=chrom:99")
        data = response.json()
        assert len(data["items"]) == 0
        assert data["has_more"] is False

    def test_filter_combined_with_cursor(self, client_with_sample):
        """Filtering and cursor should work together."""
        client, sid = client_with_sample
        response = client.get(
            f"/api/variants?sample_id={sid}&filter=chrom:1&limit=2"
        )
        data = response.json()
        assert len(data["items"]) == 2
        assert data["has_more"] is True

        # Next page of filtered results
        r2 = client.get(
            f"/api/variants?sample_id={sid}&filter=chrom:1&limit=2"
            f"&cursor_chrom={data['next_cursor_chrom']}&cursor_pos={data['next_cursor_pos']}"
        )
        d2 = r2.json()
        assert len(d2["items"]) == 1
        assert d2["has_more"] is False

    def test_unknown_filter_key_ignored(self, client_with_sample):
        """Unknown filter keys should be silently ignored."""
        client, sid = client_with_sample
        response = client.get(
            f"/api/variants?sample_id={sid}&filter=nonexistent:foo"
        )
        data = response.json()
        # Should return all variants (filter ignored)
        assert len(data["items"]) == len(TEST_VARIANTS)

    def test_multiple_filters(self, client_with_sample):
        """Multiple comma-separated filters should AND together."""
        client, sid = client_with_sample
        response = client.get(
            f"/api/variants?sample_id={sid}&filter=chrom:1,genotype:AG"
        )
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["rsid"] == "rs101"


# ═══════════════════════════════════════════════════════════════════════
# GET /api/variants/count
# ═══════════════════════════════════════════════════════════════════════


class TestVariantCount:
    """GET /api/variants/count returns total count."""

    def test_total_count(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants/count?sample_id={sid}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == len(TEST_VARIANTS)
        assert data["filtered"] is False

    def test_filtered_count(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(
            f"/api/variants/count?sample_id={sid}&filter=chrom:1"
        )
        data = response.json()
        assert data["total"] == 3
        assert data["filtered"] is True

    def test_count_nonexistent_sample(self, client_with_sample):
        client, _ = client_with_sample
        response = client.get("/api/variants/count?sample_id=999")
        assert response.status_code == 404

    def test_count_with_no_matches(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(
            f"/api/variants/count?sample_id={sid}&filter=chrom:99"
        )
        data = response.json()
        assert data["total"] == 0


# ═══════════════════════════════════════════════════════════════════════
# Limit validation
# ═══════════════════════════════════════════════════════════════════════


class TestLimitValidation:
    """Limit parameter validation."""

    def test_limit_zero_returns_422(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&limit=0")
        assert response.status_code == 422

    def test_limit_exceeds_max_returns_422(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&limit=501")
        assert response.status_code == 422

    def test_limit_1_returns_one_item(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants?sample_id={sid}&limit=1")
        data = response.json()
        assert len(data["items"]) == 1
        assert data["has_more"] is True


# ═══════════════════════════════════════════════════════════════════════
# GET /api/variants/chromosomes (P1-15b)
# ═══════════════════════════════════════════════════════════════════════


class TestChromosomeCounts:
    """GET /api/variants/chromosomes returns per-chromosome variant counts."""

    def test_returns_200(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants/chromosomes?sample_id={sid}")
        assert response.status_code == 200

    def test_returns_all_chromosomes_with_data(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants/chromosomes?sample_id={sid}")
        data = response.json()
        chroms = {item["chrom"] for item in data}
        # TEST_VARIANTS has: 1, 2, 10, 15, 19, 22, X, MT
        expected = {"1", "2", "10", "15", "19", "22", "X", "MT"}
        assert chroms == expected

    def test_returns_correct_counts(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(f"/api/variants/chromosomes?sample_id={sid}")
        data = response.json()
        count_map = {item["chrom"]: item["count"] for item in data}
        assert count_map["1"] == 3  # rs100, rs101, rs102
        assert count_map["2"] == 2  # rs200, rs201
        assert count_map["10"] == 1
        assert count_map["X"] == 1
        assert count_map["MT"] == 1

    def test_canonical_order(self, client_with_sample):
        """Chromosomes should be returned in canonical sort order."""
        client, sid = client_with_sample
        response = client.get(f"/api/variants/chromosomes?sample_id={sid}")
        data = response.json()
        chroms = [item["chrom"] for item in data]
        assert chroms == ["1", "2", "10", "15", "19", "22", "X", "MT"]

    def test_with_filter(self, client_with_sample):
        client, sid = client_with_sample
        response = client.get(
            f"/api/variants/chromosomes?sample_id={sid}&filter=genotype:AA"
        )
        data = response.json()
        count_map = {item["chrom"]: item["count"] for item in data}
        # AA genotype: rs100 (chr1), rs1000 (chr10), rsX001 (chrX)
        assert count_map["1"] == 1
        assert count_map["10"] == 1
        assert count_map["X"] == 1
        assert "2" not in count_map  # no AA on chr2

    def test_nonexistent_sample_returns_404(self, client_with_sample):
        client, _ = client_with_sample
        response = client.get("/api/variants/chromosomes?sample_id=999")
        assert response.status_code == 404

    def test_missing_sample_id_returns_422(self, client_with_sample):
        client, _ = client_with_sample
        response = client.get("/api/variants/chromosomes")
        assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# P1-15d: Async total count with annotation_coverage filtering
# ═══════════════════════════════════════════════════════════════════════

# Mix of annotated (coverage != NULL) and unannotated (coverage = NULL) variants.
ANNOTATED_TEST_VARIANTS = [
    {"rsid": "rs100", "chrom": "1", "pos": 50000, "genotype": "AA",
     "gene_symbol": "BRCA1", "consequence": "missense_variant",
     "annotation_coverage": 0b000111},
    {"rsid": "rs101", "chrom": "1", "pos": 100000, "genotype": "AG",
     "gene_symbol": "TP53", "consequence": "synonymous_variant",
     "annotation_coverage": 0b000011},
    {"rsid": "rs102", "chrom": "1", "pos": 200000, "genotype": "GG",
     "gene_symbol": None, "consequence": None,
     "annotation_coverage": None},  # unannotated
    {"rsid": "rs200", "chrom": "2", "pos": 10000, "genotype": "CC",
     "gene_symbol": "APOE", "consequence": "missense_variant",
     "annotation_coverage": 0b111111},
    {"rsid": "rs201", "chrom": "2", "pos": 20000, "genotype": "CT",
     "gene_symbol": None, "consequence": None,
     "annotation_coverage": None},  # unannotated
    {"rsid": "rs1000", "chrom": "10", "pos": 50000, "genotype": "AA",
     "gene_symbol": None, "consequence": None,
     "annotation_coverage": None},  # unannotated
]


@pytest.fixture
def client_with_annotated_sample(tmp_data_dir: Path):
    """FastAPI TestClient with a sample using annotated_variants table.

    3 annotated variants (coverage != NULL) + 3 unannotated (coverage = NULL).
    """
    settings = Settings(data_dir=tmp_data_dir, wal_mode=False)

    ref_path = settings.reference_db_path
    ref_engine = sa.create_engine(f"sqlite:///{ref_path}")
    reference_metadata.create_all(ref_engine)

    with ref_engine.begin() as conn:
        result = conn.execute(
            samples.insert().values(
                name="annotated_sample",
                db_path="samples/sample_2.db",
                file_format="23andme_v5",
                file_hash="annothash456",
            )
        )
        sample_id = result.lastrowid
    ref_engine.dispose()

    sample_db_path = tmp_data_dir / "samples" / "sample_2.db"
    sample_engine = sa.create_engine(f"sqlite:///{sample_db_path}")
    create_sample_tables(sample_engine)
    with sample_engine.begin() as conn:
        conn.execute(annotated_variants.insert(), ANNOTATED_TEST_VARIANTS)
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


class TestAnnotationCoverageFilter:
    """P1-15d: annotation_coverage:notnull/null filtering on count and list endpoints."""

    def test_count_all_variants(self, client_with_annotated_sample):
        """Unfiltered count returns all variants (annotated + unannotated)."""
        client, sid = client_with_annotated_sample
        response = client.get(f"/api/variants/count?sample_id={sid}")
        data = response.json()
        assert data["total"] == 6
        assert data["filtered"] is False

    def test_count_annotated_only(self, client_with_annotated_sample):
        """annotation_coverage:notnull filters to annotated variants only."""
        client, sid = client_with_annotated_sample
        response = client.get(
            f"/api/variants/count?sample_id={sid}&filter=annotation_coverage:notnull"
        )
        data = response.json()
        assert data["total"] == 3
        assert data["filtered"] is True

    def test_count_unannotated_only(self, client_with_annotated_sample):
        """annotation_coverage:null filters to unannotated variants only."""
        client, sid = client_with_annotated_sample
        response = client.get(
            f"/api/variants/count?sample_id={sid}&filter=annotation_coverage:null"
        )
        data = response.json()
        assert data["total"] == 3
        assert data["filtered"] is True

    def test_list_annotated_only(self, client_with_annotated_sample):
        """List endpoint respects annotation_coverage:notnull filter."""
        client, sid = client_with_annotated_sample
        response = client.get(
            f"/api/variants?sample_id={sid}&filter=annotation_coverage:notnull"
        )
        data = response.json()
        assert len(data["items"]) == 3
        assert all(
            item["annotation_coverage"] is not None for item in data["items"]
        )

    def test_list_unannotated_only(self, client_with_annotated_sample):
        """List endpoint respects annotation_coverage:null filter."""
        client, sid = client_with_annotated_sample
        response = client.get(
            f"/api/variants?sample_id={sid}&filter=annotation_coverage:null"
        )
        data = response.json()
        assert len(data["items"]) == 3
        assert all(
            item["annotation_coverage"] is None for item in data["items"]
        )

    def test_combined_filter_chrom_and_coverage(self, client_with_annotated_sample):
        """annotation_coverage filter combines with other filters."""
        client, sid = client_with_annotated_sample
        response = client.get(
            f"/api/variants/count?sample_id={sid}"
            "&filter=chrom:1,annotation_coverage:notnull"
        )
        data = response.json()
        # chrom 1 has rs100 (annotated), rs101 (annotated), rs102 (unannotated)
        assert data["total"] == 2
        assert data["filtered"] is True

    def test_chromosome_counts_with_coverage_filter(self, client_with_annotated_sample):
        """Chromosome counts endpoint respects annotation_coverage filter."""
        client, sid = client_with_annotated_sample
        response = client.get(
            f"/api/variants/chromosomes?sample_id={sid}"
            "&filter=annotation_coverage:notnull"
        )
        data = response.json()
        count_map = {item["chrom"]: item["count"] for item in data}
        assert count_map["1"] == 2  # rs100, rs101
        assert count_map["2"] == 1  # rs200
        assert "10" not in count_map  # rs1000 is unannotated
