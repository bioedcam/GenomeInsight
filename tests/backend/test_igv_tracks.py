"""Tests for IGV.js track data endpoints (P2-17).

Validates:
- ClinVar VCF region + header endpoints
- User sample VCF region + header endpoints
- gnomAD AF JSON features endpoint
- ENCODE cCREs JSON features endpoint
- Chromosome normalization (chr prefix handling)
- Error handling (missing samples, unavailable DBs)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_registry
from backend.db.sample_schema import create_sample_tables
from backend.db.tables import (
    clinvar_variants,
    raw_variants,
    samples,
)

# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def _seed_clinvar(test_client: TestClient) -> None:
    """Insert test ClinVar variants into reference.db via the active registry."""
    registry = get_registry()
    with registry.reference_engine.begin() as conn:
        conn.execute(
            clinvar_variants.insert(),
            [
                {
                    "rsid": "rs123",
                    "chrom": "17",
                    "pos": 41245466,
                    "ref": "A",
                    "alt": "G",
                    "significance": "Pathogenic",
                    "review_stars": 3,
                    "accession": "VCV000012345",
                    "conditions": "Breast cancer",
                    "gene_symbol": "BRCA1",
                    "variation_id": 12345,
                },
                {
                    "rsid": "rs456",
                    "chrom": "17",
                    "pos": 41245500,
                    "ref": "C",
                    "alt": "T",
                    "significance": "Benign",
                    "review_stars": 2,
                    "accession": "VCV000067890",
                    "conditions": None,
                    "gene_symbol": "BRCA1",
                    "variation_id": 67890,
                },
                {
                    "rsid": "rs789",
                    "chrom": "1",
                    "pos": 100000,
                    "ref": "G",
                    "alt": "A",
                    "significance": "Uncertain_significance",
                    "review_stars": 1,
                    "accession": "VCV000011111",
                    "conditions": "Unknown condition",
                    "gene_symbol": "GENE1",
                    "variation_id": 11111,
                },
            ],
        )


@pytest.fixture()
def sample_with_variants(test_client: TestClient) -> int:
    """Create a sample with raw variants and return its ID."""
    registry = get_registry()

    # Register sample in reference.db
    with registry.reference_engine.begin() as conn:
        result = conn.execute(
            samples.insert().values(
                name="Test Sample",
                db_path="samples/test_igv_sample.db",
                file_format="23andme",
            )
        )
        sample_id = result.lastrowid

    # Create per-sample DB
    sample_db_path = registry.settings.data_dir / "samples" / "test_igv_sample.db"
    sample_db_path.parent.mkdir(parents=True, exist_ok=True)
    sample_engine = registry.get_sample_engine(sample_db_path)
    create_sample_tables(sample_engine)

    # Insert raw variants
    with sample_engine.begin() as conn:
        conn.execute(
            raw_variants.insert(),
            [
                {"rsid": "rs100", "chrom": "17", "pos": 41245466, "genotype": "AG"},
                {"rsid": "rs101", "chrom": "17", "pos": 41245500, "genotype": "CC"},
                {"rsid": "rs102", "chrom": "17", "pos": 41246000, "genotype": "A"},
                {"rsid": "rs103", "chrom": "1", "pos": 50000, "genotype": "--"},
            ],
        )

    return sample_id


# ── ClinVar VCF Track Tests ─────────────────────────────────────────


class TestClinVarTrack:
    """Tests for ClinVar VCF region and header endpoints."""

    def test_clinvar_header_returns_vcf(self, test_client: TestClient) -> None:
        resp = test_client.get("/api/igv-tracks/clinvar/header")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/plain; charset=utf-8"
        text = resp.text
        assert "##fileformat=VCFv4.2" in text
        assert "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO" in text

    @pytest.mark.usefixtures("_seed_clinvar")
    def test_clinvar_region_returns_variants(self, test_client: TestClient) -> None:
        resp = test_client.get(
            "/api/igv-tracks/clinvar",
            params={"chr": "chr17", "start": 41245400, "end": 41245600},
        )
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        data_lines = [line for line in lines if not line.startswith("#")]
        assert len(data_lines) == 2
        assert "rs123" in data_lines[0]
        assert "CLNSIG=Pathogenic" in data_lines[0]
        assert "chr17" in data_lines[0]
        assert "rs456" in data_lines[1]
        assert "CLNSIG=Benign" in data_lines[1]

    @pytest.mark.usefixtures("_seed_clinvar")
    def test_clinvar_region_normalizes_chrom(self, test_client: TestClient) -> None:
        """Requesting with or without 'chr' prefix should work."""
        resp = test_client.get(
            "/api/igv-tracks/clinvar",
            params={"chr": "17", "start": 41245400, "end": 41245600},
        )
        assert resp.status_code == 200
        data_lines = [line for line in resp.text.strip().split("\n") if not line.startswith("#")]
        assert len(data_lines) == 2

    @pytest.mark.usefixtures("_seed_clinvar")
    def test_clinvar_region_empty_when_no_overlap(self, test_client: TestClient) -> None:
        resp = test_client.get(
            "/api/igv-tracks/clinvar",
            params={"chr": "chr17", "start": 1, "end": 100},
        )
        assert resp.status_code == 200
        data_lines = [line for line in resp.text.strip().split("\n") if not line.startswith("#")]
        assert len(data_lines) == 0

    @pytest.mark.usefixtures("_seed_clinvar")
    def test_clinvar_vcf_info_fields(self, test_client: TestClient) -> None:
        resp = test_client.get(
            "/api/igv-tracks/clinvar",
            params={"chr": "chr17", "start": 41245460, "end": 41245470},
        )
        text = resp.text
        assert "GENEINFO=BRCA1" in text
        assert "CLNACC=VCV000012345" in text
        assert "CLNDN=Breast cancer" in text
        assert "CLNREVSTAT=3" in text


# ── User Sample VCF Track Tests ──────────────────────────────────────


class TestSampleVariantsTrack:
    """Tests for user sample VCF region and header endpoints."""

    def test_sample_header_returns_vcf(
        self, test_client: TestClient, sample_with_variants: int
    ) -> None:
        resp = test_client.get(f"/api/igv-tracks/sample/{sample_with_variants}/header")
        assert resp.status_code == 200
        assert "##fileformat=VCFv4.2" in resp.text
        assert "FORMAT\tSAMPLE" in resp.text

    def test_sample_header_404_missing(self, test_client: TestClient) -> None:
        resp = test_client.get("/api/igv-tracks/sample/9999/header")
        assert resp.status_code == 404

    def test_sample_region_returns_variants(
        self, test_client: TestClient, sample_with_variants: int
    ) -> None:
        resp = test_client.get(
            f"/api/igv-tracks/sample/{sample_with_variants}/variants",
            params={"chr": "chr17", "start": 41245400, "end": 41246100},
        )
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        data_lines = [line for line in lines if not line.startswith("#")]
        assert len(data_lines) == 3  # rs100, rs101, rs102 on chr17

    def test_sample_region_het_genotype(
        self, test_client: TestClient, sample_with_variants: int
    ) -> None:
        """AG genotype -> REF=A, ALT=G, GT=0/1"""
        resp = test_client.get(
            f"/api/igv-tracks/sample/{sample_with_variants}/variants",
            params={"chr": "chr17", "start": 41245466, "end": 41245467},
        )
        data_lines = [line for line in resp.text.strip().split("\n") if not line.startswith("#")]
        assert len(data_lines) == 1
        fields = data_lines[0].split("\t")
        assert fields[3] == "A"  # REF
        assert fields[4] == "G"  # ALT
        assert fields[9] == "0/1"  # GT

    def test_sample_region_hom_genotype(
        self, test_client: TestClient, sample_with_variants: int
    ) -> None:
        """CC genotype -> REF=C, ALT=., GT=0/0"""
        resp = test_client.get(
            f"/api/igv-tracks/sample/{sample_with_variants}/variants",
            params={"chr": "chr17", "start": 41245500, "end": 41245501},
        )
        data_lines = [line for line in resp.text.strip().split("\n") if not line.startswith("#")]
        assert len(data_lines) == 1
        fields = data_lines[0].split("\t")
        assert fields[3] == "C"  # REF
        assert fields[4] == "."  # ALT (hom ref)
        assert fields[9] == "0/0"  # GT

    def test_sample_region_haploid_genotype(
        self, test_client: TestClient, sample_with_variants: int
    ) -> None:
        """Single-char genotype (e.g., chrY/MT) -> haploid call."""
        resp = test_client.get(
            f"/api/igv-tracks/sample/{sample_with_variants}/variants",
            params={"chr": "chr17", "start": 41246000, "end": 41246001},
        )
        data_lines = [line for line in resp.text.strip().split("\n") if not line.startswith("#")]
        assert len(data_lines) == 1
        fields = data_lines[0].split("\t")
        assert fields[9] == "0"  # Haploid GT

    def test_sample_region_nocall_genotype(
        self, test_client: TestClient, sample_with_variants: int
    ) -> None:
        """'--' genotype -> no-call."""
        resp = test_client.get(
            f"/api/igv-tracks/sample/{sample_with_variants}/variants",
            params={"chr": "chr1", "start": 49999, "end": 50001},
        )
        data_lines = [line for line in resp.text.strip().split("\n") if not line.startswith("#")]
        assert len(data_lines) == 1
        fields = data_lines[0].split("\t")
        assert fields[9] == "./."  # No-call GT

    def test_sample_region_404_missing(self, test_client: TestClient) -> None:
        resp = test_client.get(
            "/api/igv-tracks/sample/9999/variants",
            params={"chr": "chr1", "start": 0, "end": 100},
        )
        assert resp.status_code == 404


# ── gnomAD AF Track Tests ────────────────────────────────────────────


class TestGnomadTrack:
    """Tests for gnomAD AF JSON features endpoint."""

    def test_gnomad_returns_empty_when_db_unavailable(
        self, test_client: TestClient
    ) -> None:
        """When gnomAD DB doesn't exist, return empty array (not error)."""
        resp = test_client.get(
            "/api/igv-tracks/gnomad",
            params={"chr": "chr1", "start": 0, "end": 100000},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_gnomad_normalizes_chrom(self, test_client: TestClient) -> None:
        """Both 'chr1' and '1' should work."""
        resp1 = test_client.get(
            "/api/igv-tracks/gnomad",
            params={"chr": "chr1", "start": 0, "end": 100},
        )
        resp2 = test_client.get(
            "/api/igv-tracks/gnomad",
            params={"chr": "1", "start": 0, "end": 100},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200


# ── ENCODE cCREs Track Tests ─────────────────────────────────────────


class TestEncodeCcresTrack:
    """Tests for ENCODE cCREs JSON features endpoint."""

    def test_ccres_returns_empty_when_db_unavailable(
        self, test_client: TestClient
    ) -> None:
        """When ENCODE cCREs DB is not loaded, return empty array."""
        resp = test_client.get(
            "/api/igv-tracks/encode-ccres",
            params={"chr": "chr1", "start": 0, "end": 100000},
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ── Genotype conversion unit tests ───────────────────────────────────


class TestGenotypeConversion:
    """Unit tests for _genotype_to_vcf_fields helper."""

    def test_het(self) -> None:
        from backend.api.routes.igv_tracks import _genotype_to_vcf_fields

        ref, alt, gt = _genotype_to_vcf_fields("AG")
        assert ref == "A"
        assert alt == "G"
        assert gt == "0/1"

    def test_hom(self) -> None:
        from backend.api.routes.igv_tracks import _genotype_to_vcf_fields

        ref, alt, gt = _genotype_to_vcf_fields("CC")
        assert ref == "C"
        assert alt == "."
        assert gt == "0/0"

    def test_haploid(self) -> None:
        from backend.api.routes.igv_tracks import _genotype_to_vcf_fields

        ref, alt, gt = _genotype_to_vcf_fields("A")
        assert ref == "A"
        assert alt == "."
        assert gt == "0"

    def test_nocall(self) -> None:
        from backend.api.routes.igv_tracks import _genotype_to_vcf_fields

        ref, alt, gt = _genotype_to_vcf_fields("--")
        assert ref == "N"
        assert alt == "."
        assert gt == "./."

    def test_empty(self) -> None:
        from backend.api.routes.igv_tracks import _genotype_to_vcf_fields

        ref, alt, gt = _genotype_to_vcf_fields("")
        assert gt == "./."

    def test_none(self) -> None:
        from backend.api.routes.igv_tracks import _genotype_to_vcf_fields

        ref, alt, gt = _genotype_to_vcf_fields(None)
        assert gt == "./."


# ── Chromosome normalization tests ───────────────────────────────────


class TestChromNormalization:
    """Unit tests for _normalize_chrom helper."""

    def test_strips_chr_prefix(self) -> None:
        from backend.api.routes.igv_tracks import _normalize_chrom

        assert _normalize_chrom("chr17") == "17"
        assert _normalize_chrom("chrX") == "X"
        assert _normalize_chrom("chrMT") == "MT"

    def test_no_prefix_passthrough(self) -> None:
        from backend.api.routes.igv_tracks import _normalize_chrom

        assert _normalize_chrom("17") == "17"
        assert _normalize_chrom("X") == "X"
