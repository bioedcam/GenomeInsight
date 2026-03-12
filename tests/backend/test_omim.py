"""Tests for optional OMIM enrichment (P2-14).

Covers:
- T2-13 (partial): With OMIM API key, enrichment adds MIM number and
  inheritance pattern.
- Genemap2 text parsing
- OMIM record creation
- Inheritance pattern parsing
- Loading into gene_phenotype table (source='omim')
- Preservation of existing MONDO/HPO data
- Version recording
- API key validation
- OMIMLoadStats dataclass
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from backend.annotation.omim import (
    OMIMLoadStats,
    OMIMRecord,
    _parse_inheritance,
    _parse_phenotype_entry,
    _records_to_rows,
    enrich_with_omim,
    fetch_omim_genemap2,
    load_omim_enrichment,
    parse_genemap2_text,
    record_omim_version,
)
from backend.db.tables import database_versions, gene_phenotype, reference_metadata

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def reference_engine() -> sa.Engine:
    """In-memory reference engine with tables created."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    reference_metadata.create_all(engine)
    return engine


@pytest.fixture
def engine_with_mondo_data(reference_engine: sa.Engine) -> sa.Engine:
    """Reference engine pre-loaded with MONDO/HPO data."""
    with reference_engine.begin() as conn:
        conn.execute(
            gene_phenotype.insert(),
            [
                {
                    "gene_symbol": "BRCA1",
                    "disease_name": "Hereditary breast and ovarian cancer",
                    "disease_id": "MONDO:0011450",
                    "hpo_terms": json.dumps(["HP:0003002"]),
                    "source": "mondo_hpo",
                    "inheritance": "Autosomal dominant",
                },
                {
                    "gene_symbol": "CFTR",
                    "disease_name": "Cystic fibrosis",
                    "disease_id": "MONDO:0009061",
                    "hpo_terms": json.dumps(["HP:0002110"]),
                    "source": "mondo_hpo",
                    "inheritance": "Autosomal recessive",
                },
            ],
        )
    return reference_engine


def _genemap2_row(
    chrom: str,
    start: str,
    end: str,
    cyto: str,
    mim: str,
    gene: str,
    symbols: str,
    name: str,
    phenotypes: str,
) -> str:
    """Build a single genemap2 TSV row."""
    return "\t".join(
        [
            chrom,
            start,
            end,
            cyto,
            cyto,
            mim,
            "gene",
            gene,
            symbols,
            name,
            "",
            "",
            phenotypes,
        ]
    )


@pytest.fixture
def sample_genemap2_text() -> str:
    """Minimal genemap2 text for testing."""
    # The genemap2 format: 13 tab-separated columns minimum
    # Index 5: Locus MIM, Index 8: Gene symbols, Index 12: Phenotypes
    header = "# Generated from omim.org\n"
    lines = [
        header,
        # Cols: Chrom, Start, End, Cyto, CompCyto, MIM, Type,
        #   Gene/Locus, GeneSymbols, Name, Comments, Mouse, Phenotypes
        _genemap2_row(
            "17",
            "43044295",
            "43125483",
            "17q21.31",
            "113705",
            "BRCA1",
            "BRCA1, RNF53",
            "BRCA1 DNA repair associated",
            "Breast-ovarian cancer, familial, 1, 604370 (3), Autosomal dominant",
        ),
        _genemap2_row(
            "7",
            "117120017",
            "117308718",
            "7q31.2",
            "602421",
            "CFTR",
            "CFTR, ABCC7",
            "CF transmembrane conductance regulator",
            "Cystic fibrosis, 219700 (3), Autosomal recessive; "
            "Congenital bilateral absence of vas deferens, "
            "277180 (3), Autosomal recessive",
        ),
        _genemap2_row(
            "1",
            "11856378",
            "11873305",
            "1p36.22",
            "191170",
            "MTHFR",
            "MTHFR",
            "Methylenetetrahydrofolate reductase",
            "Homocysteinemia, 603174 (3)",
        ),
    ]
    return "\n".join(lines) + "\n"


# ── Genemap2 parsing tests ──────────────────────────────────────────────


class TestGenemap2Parsing:
    """Test OMIM genemap2 text parsing."""

    def test_parse_basic(self, sample_genemap2_text: str) -> None:
        """Parse minimal genemap2 text."""
        records, stats = parse_genemap2_text(sample_genemap2_text)
        assert stats.total_lines == 3
        assert stats.records_loaded >= 3  # BRCA1=1, CFTR=2, MTHFR=1

        gene_symbols = {r.gene_symbol for r in records}
        assert "BRCA1" in gene_symbols
        assert "CFTR" in gene_symbols
        assert "MTHFR" in gene_symbols

    def test_parse_brca1_details(self, sample_genemap2_text: str) -> None:
        """BRCA1 record has correct MIM and inheritance."""
        records, _ = parse_genemap2_text(sample_genemap2_text)
        brca1_records = [r for r in records if r.gene_symbol == "BRCA1"]
        assert len(brca1_records) >= 1
        brca1 = brca1_records[0]
        assert brca1.mim_number == "113705"
        assert brca1.inheritance == "Autosomal dominant"
        assert "Breast" in brca1.phenotype_text or "breast" in brca1.phenotype_text.lower()

    def test_parse_cftr_multiple_phenotypes(self, sample_genemap2_text: str) -> None:
        """CFTR has two phenotype entries (semicolon-separated)."""
        records, _ = parse_genemap2_text(sample_genemap2_text)
        cftr_records = [r for r in records if r.gene_symbol == "CFTR"]
        assert len(cftr_records) == 2
        diseases = {r.phenotype_text for r in cftr_records}
        # Should have both cystic fibrosis and CBAVD
        assert any("Cystic fibrosis" in d for d in diseases)

    def test_parse_skips_comments(self, sample_genemap2_text: str) -> None:
        """Comment lines are counted as skipped."""
        records, stats = parse_genemap2_text(sample_genemap2_text)
        assert stats.skipped_comments >= 1

    def test_parse_empty_text(self) -> None:
        """Empty text produces empty records."""
        records, stats = parse_genemap2_text("")
        assert len(records) == 0
        assert stats.total_lines == 0

    def test_parse_no_phenotype(self) -> None:
        """Lines with no phenotype column are skipped."""
        line = "\t".join(
            [
                "1",
                "100",
                "200",
                "1p36",
                "1p36",
                "100000",
                "gene",
                "FAKE",
                "FAKE",
                "Fake gene",
                "",
                "",
                "",
            ]
        )
        records, stats = parse_genemap2_text(line)
        assert stats.skipped_no_phenotype == 1


# ── Inheritance parsing tests ────────────────────────────────────────────


class TestInheritanceParsing:
    """Test OMIM inheritance pattern parsing."""

    def test_ad(self) -> None:
        assert _parse_inheritance("AD") == "Autosomal dominant"

    def test_ar(self) -> None:
        assert _parse_inheritance("AR") == "Autosomal recessive"

    def test_xlr(self) -> None:
        assert _parse_inheritance("XLR") == "X-linked recessive"

    def test_full_text(self) -> None:
        assert _parse_inheritance("Autosomal dominant") == "Autosomal dominant"

    def test_question_mark_prefix(self) -> None:
        assert _parse_inheritance("?AD") == "Autosomal dominant"

    def test_multiple_patterns(self) -> None:
        """First recognized pattern is returned."""
        result = _parse_inheritance("AD, AR")
        assert result == "Autosomal dominant"

    def test_empty(self) -> None:
        assert _parse_inheritance("") is None

    def test_none(self) -> None:
        assert _parse_inheritance("") is None


# ── Phenotype entry parsing tests ────────────────────────────────────────


class TestPhenotypeEntryParsing:
    """Test individual phenotype entry parsing."""

    def test_basic_entry(self) -> None:
        record = _parse_phenotype_entry(
            "Breast cancer, 604370 (3), Autosomal dominant",
            "BRCA1",
            "113705",
        )
        assert record is not None
        assert record.gene_symbol == "BRCA1"
        assert record.inheritance == "Autosomal dominant"

    def test_entry_no_inheritance(self) -> None:
        record = _parse_phenotype_entry(
            "Homocysteinemia, 603174 (3)",
            "MTHFR",
            "191170",
        )
        assert record is not None
        assert record.gene_symbol == "MTHFR"
        assert record.phenotype_mim == "603174"
        assert record.mapping_key == 3

    def test_entry_simple_text(self) -> None:
        record = _parse_phenotype_entry(
            "Simple phenotype",
            "GENE1",
            "100000",
        )
        assert record is not None
        assert record.phenotype_text == "Simple phenotype"

    def test_entry_empty(self) -> None:
        result = _parse_phenotype_entry("", "GENE1", "100000")
        assert result is None


# ── Records to rows conversion tests ────────────────────────────────────


class TestRecordsToRows:
    """Test OMIM record to row dict conversion."""

    def test_basic_conversion(self) -> None:
        records = [
            OMIMRecord(
                gene_symbol="BRCA1",
                mim_number="113705",
                phenotype_text="Breast cancer",
                phenotype_mim="604370",
                inheritance="Autosomal dominant",
                mapping_key=3,
            ),
        ]
        rows = _records_to_rows(records)
        assert len(rows) == 1
        row = rows[0]
        assert row["gene_symbol"] == "BRCA1"
        assert row["disease_name"] == "Breast cancer"
        assert row["disease_id"] == "OMIM:604370"
        assert row["source"] == "omim"
        assert row["inheritance"] == "Autosomal dominant"
        assert row["hpo_terms"] is None  # OMIM doesn't provide HPO

    def test_fallback_mim_number(self) -> None:
        """When phenotype_mim is None, use gene MIM number."""
        records = [
            OMIMRecord(
                gene_symbol="MTHFR",
                mim_number="191170",
                phenotype_text="Homocysteinemia",
            ),
        ]
        rows = _records_to_rows(records)
        assert rows[0]["disease_id"] == "OMIM:191170"


# ── DB loading tests ────────────────────────────────────────────────────


class TestOMIMLoading:
    """Test loading OMIM records into gene_phenotype table."""

    def test_load_records(self, reference_engine: sa.Engine) -> None:
        """Load OMIM records into empty table."""
        records = [
            OMIMRecord(
                gene_symbol="BRCA1",
                mim_number="113705",
                phenotype_text="Breast cancer",
                phenotype_mim="604370",
                inheritance="Autosomal dominant",
            ),
            OMIMRecord(
                gene_symbol="CFTR",
                mim_number="602421",
                phenotype_text="Cystic fibrosis",
                phenotype_mim="219700",
                inheritance="Autosomal recessive",
            ),
        ]
        loaded = load_omim_enrichment(records, reference_engine, clear_existing=False)
        assert loaded == 2

        with reference_engine.connect() as conn:
            rows = conn.execute(
                sa.select(gene_phenotype).where(gene_phenotype.c.source == "omim")
            ).fetchall()
            assert len(rows) == 2

    def test_preserves_mondo_data(self, engine_with_mondo_data: sa.Engine) -> None:
        """T2-13: OMIM enrichment preserves existing MONDO/HPO data."""
        records = [
            OMIMRecord(
                gene_symbol="BRCA1",
                mim_number="113705",
                phenotype_text="Breast cancer",
                phenotype_mim="604370",
                inheritance="Autosomal dominant",
            ),
        ]
        load_omim_enrichment(records, engine_with_mondo_data, clear_existing=True)

        with engine_with_mondo_data.connect() as conn:
            # MONDO data should still be there
            mondo_count = conn.execute(
                sa.select(sa.func.count())
                .select_from(gene_phenotype)
                .where(gene_phenotype.c.source == "mondo_hpo")
            ).scalar()
            assert mondo_count == 2  # BRCA1 + CFTR from mondo

            # OMIM data should be added
            omim_count = conn.execute(
                sa.select(sa.func.count())
                .select_from(gene_phenotype)
                .where(gene_phenotype.c.source == "omim")
            ).scalar()
            assert omim_count == 1

    def test_clear_replaces_omim_only(self, reference_engine: sa.Engine) -> None:
        """Successive loads with clear_existing replace only OMIM rows."""
        records_v1 = [
            OMIMRecord(
                gene_symbol="GENE_V1",
                mim_number="100001",
                phenotype_text="Disease v1",
            ),
        ]
        records_v2 = [
            OMIMRecord(
                gene_symbol="GENE_V2",
                mim_number="100002",
                phenotype_text="Disease v2",
            ),
        ]
        load_omim_enrichment(records_v1, reference_engine, clear_existing=False)
        load_omim_enrichment(records_v2, reference_engine, clear_existing=True)

        with reference_engine.connect() as conn:
            rows = conn.execute(
                sa.select(gene_phenotype.c.gene_symbol).where(gene_phenotype.c.source == "omim")
            ).fetchall()
            symbols = [r.gene_symbol for r in rows]
            assert "GENE_V2" in symbols
            assert "GENE_V1" not in symbols

    def test_load_empty_records(self, reference_engine: sa.Engine) -> None:
        """Loading empty records list returns 0."""
        loaded = load_omim_enrichment([], reference_engine)
        assert loaded == 0


# ── Version recording tests ─────────────────────────────────────────────


class TestOMIMVersionRecording:
    """Test OMIM version recording."""

    def test_record_version(self, reference_engine: sa.Engine) -> None:
        """Record OMIM version in database_versions."""
        record_omim_version(reference_engine, version="20260312", records_count=100)
        with reference_engine.connect() as conn:
            row = conn.execute(
                sa.select(database_versions).where(database_versions.c.db_name == "omim")
            ).first()
        assert row is not None
        assert row.version == "20260312"

    def test_record_version_update(self, reference_engine: sa.Engine) -> None:
        """Second call updates existing version."""
        record_omim_version(reference_engine, version="20260301")
        record_omim_version(reference_engine, version="20260312")
        with reference_engine.connect() as conn:
            row = conn.execute(
                sa.select(database_versions).where(database_versions.c.db_name == "omim")
            ).first()
        assert row.version == "20260312"


# ── API key validation tests ─────────────────────────────────────────────


class TestAPIKeyValidation:
    """Test API key validation."""

    def test_fetch_requires_api_key(self) -> None:
        """fetch_omim_genemap2 raises ValueError with empty key."""
        with pytest.raises(ValueError, match="OMIM API key is required"):
            fetch_omim_genemap2("")

    def test_enrich_requires_api_key(self, reference_engine: sa.Engine) -> None:
        """enrich_with_omim raises ValueError with empty key."""
        with pytest.raises(ValueError, match="OMIM API key is required"):
            enrich_with_omim(reference_engine, "")


# ── Full pipeline test (mocked) ─────────────────────────────────────────


class TestEnrichPipeline:
    """Test the full OMIM enrichment pipeline with mocked HTTP."""

    def test_enrich_pipeline(
        self,
        engine_with_mondo_data: sa.Engine,
        sample_genemap2_text: str,
    ) -> None:
        """T2-13: Full enrichment adds MIM number and inheritance."""
        with patch(
            "backend.annotation.omim.fetch_omim_genemap2",
            return_value=sample_genemap2_text,
        ):
            stats = enrich_with_omim(engine_with_mondo_data, api_key="test-key-123")

        assert stats.records_loaded >= 3
        assert stats.genes_enriched >= 3

        # Verify OMIM data was added
        with engine_with_mondo_data.connect() as conn:
            omim_rows = conn.execute(
                sa.select(gene_phenotype).where(gene_phenotype.c.source == "omim")
            ).fetchall()
            assert len(omim_rows) >= 3

            # Verify MONDO data is preserved
            mondo_count = conn.execute(
                sa.select(sa.func.count())
                .select_from(gene_phenotype)
                .where(gene_phenotype.c.source == "mondo_hpo")
            ).scalar()
            assert mondo_count == 2  # Original BRCA1 + CFTR

            # Check BRCA1 OMIM enrichment has disease_id
            brca1_omim = conn.execute(
                sa.select(gene_phenotype).where(
                    sa.and_(
                        gene_phenotype.c.gene_symbol == "BRCA1",
                        gene_phenotype.c.source == "omim",
                    )
                )
            ).first()
            assert brca1_omim is not None
            assert "OMIM:" in brca1_omim.disease_id
            assert brca1_omim.inheritance == "Autosomal dominant"


# ── OMIMLoadStats tests ─────────────────────────────────────────────────


class TestOMIMLoadStats:
    """Test OMIMLoadStats dataclass."""

    def test_defaults(self) -> None:
        stats = OMIMLoadStats()
        assert stats.total_lines == 0
        assert stats.records_loaded == 0
        assert stats.genes_enriched == 0
