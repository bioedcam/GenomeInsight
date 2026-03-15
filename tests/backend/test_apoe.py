"""Tests for APOE genotype determination (P3-22a).

Covers:
  - All 6 standard APOE diplotypes (ε2/ε2 through ε4/ε4)
  - rs429358 TT + rs7412 CC → ε3/ε3 (T3-17 golden fixture)
  - Missing SNPs (one or both)
  - No-call genotypes ("--")
  - Genotype normalisation (TC vs CT)
  - APOEResult properties (has_e4, e4_count, has_e2, e2_count)
  - Finding storage (module='apoe', category='genotype')
  - Idempotent re-runs (clear previous findings)
  - Finding skipped when genotype not determined
"""

from __future__ import annotations

import json

import pytest
import sqlalchemy as sa

from backend.analysis.apoe import (
    APOE_RS7412,
    APOE_RS429358,
    APOEAllele,
    APOEResult,
    APOEStatus,
    _normalise_genotype,
    determine_apoe_genotype,
    store_apoe_finding,
)
from backend.db.sample_schema import create_sample_tables
from backend.db.tables import findings, raw_variants

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def sample_engine() -> sa.Engine:
    """In-memory SQLite engine with all sample tables."""
    engine = sa.create_engine("sqlite://")
    create_sample_tables(engine)
    return engine


def _seed_apoe_variants(
    engine: sa.Engine,
    rs429358_genotype: str | None = None,
    rs7412_genotype: str | None = None,
) -> None:
    """Insert APOE SNPs into raw_variants."""
    rows = []
    if rs429358_genotype is not None:
        rows.append(
            {"rsid": APOE_RS429358, "chrom": "19", "pos": 44908684, "genotype": rs429358_genotype}
        )
    if rs7412_genotype is not None:
        rows.append(
            {"rsid": APOE_RS7412, "chrom": "19", "pos": 44908822, "genotype": rs7412_genotype}
        )
    if rows:
        with engine.begin() as conn:
            conn.execute(sa.insert(raw_variants), rows)


# ── Genotype normalisation ────────────────────────────────────────────────


class TestNormaliseGenotype:
    """Test genotype string normalisation."""

    def test_already_sorted(self) -> None:
        assert _normalise_genotype("CC") == "CC"

    def test_needs_sorting(self) -> None:
        assert _normalise_genotype("TC") == "CT"

    def test_same_alleles(self) -> None:
        assert _normalise_genotype("TT") == "TT"

    def test_single_char_passthrough(self) -> None:
        assert _normalise_genotype("A") == "A"

    def test_three_char_passthrough(self) -> None:
        assert _normalise_genotype("ACG") == "ACG"


# ── All 6 standard diplotypes ────────────────────────────────────────────


class TestAPOEDiplotypes:
    """Test all 6 standard APOE diplotype determinations."""

    @pytest.mark.parametrize(
        (
            "rs429358_gt",
            "rs7412_gt",
            "expected_diplotype",
            "expected_e4_count",
            "expected_e2_count",
        ),
        [
            # ε2/ε2: rs429358=TT, rs7412=TT
            ("TT", "TT", "ε2/ε2", 0, 2),
            # ε2/ε3: rs429358=TT, rs7412=CT
            ("TT", "CT", "ε2/ε3", 0, 1),
            # ε2/ε4: rs429358=CT, rs7412=CT
            ("CT", "CT", "ε2/ε4", 1, 1),
            # ε3/ε3: rs429358=TT, rs7412=CC (T3-17 golden fixture)
            ("TT", "CC", "ε3/ε3", 0, 0),
            # ε3/ε4: rs429358=CT, rs7412=CC
            ("CT", "CC", "ε3/ε4", 1, 0),
            # ε4/ε4: rs429358=CC, rs7412=CC
            ("CC", "CC", "ε4/ε4", 2, 0),
        ],
        ids=["e2/e2", "e2/e3", "e2/e4", "e3/e3-T3-17", "e3/e4", "e4/e4"],
    )
    def test_diplotype(
        self,
        sample_engine: sa.Engine,
        rs429358_gt: str,
        rs7412_gt: str,
        expected_diplotype: str,
        expected_e4_count: int,
        expected_e2_count: int,
    ) -> None:
        _seed_apoe_variants(sample_engine, rs429358_gt, rs7412_gt)
        result = determine_apoe_genotype(sample_engine)

        assert result.is_determined
        assert result.status == APOEStatus.DETERMINED
        assert result.diplotype == expected_diplotype
        assert result.e4_count == expected_e4_count
        assert result.e2_count == expected_e2_count
        assert result.has_e4 == (expected_e4_count > 0)
        assert result.has_e2 == (expected_e2_count > 0)

    def test_e3_e3_golden_fixture(self, sample_engine: sa.Engine) -> None:
        """T3-17: APOE genotype correctly determined: rs429358 TT + rs7412 CC → ε3/ε3."""
        _seed_apoe_variants(sample_engine, "TT", "CC")
        result = determine_apoe_genotype(sample_engine)

        assert result.is_determined
        assert result.diplotype == "ε3/ε3"
        assert result.allele1 == APOEAllele.E3
        assert result.allele2 == APOEAllele.E3
        assert result.rs429358_genotype == "TT"
        assert result.rs7412_genotype == "CC"
        assert not result.has_e4
        assert result.e4_count == 0
        assert not result.has_e2
        assert result.e2_count == 0

    def test_e4_e4_homozygous(self, sample_engine: sa.Engine) -> None:
        """ε4/ε4 correctly identified with both alleles."""
        _seed_apoe_variants(sample_engine, "CC", "CC")
        result = determine_apoe_genotype(sample_engine)

        assert result.is_determined
        assert result.diplotype == "ε4/ε4"
        assert result.allele1 == APOEAllele.E4
        assert result.allele2 == APOEAllele.E4
        assert result.has_e4
        assert result.e4_count == 2

    def test_e2_e4_mixed(self, sample_engine: sa.Engine) -> None:
        """ε2/ε4 correctly identified with one of each."""
        _seed_apoe_variants(sample_engine, "CT", "CT")
        result = determine_apoe_genotype(sample_engine)

        assert result.is_determined
        assert result.diplotype == "ε2/ε4"
        assert result.has_e4
        assert result.e4_count == 1
        assert result.has_e2
        assert result.e2_count == 1


# ── Biologically impossible combinations ──────────────────────────────────


class TestAPOEAmbiguousCases:
    """Test biologically impossible genotype combinations return AMBIGUOUS."""

    @pytest.mark.parametrize(
        ("rs429358_gt", "rs7412_gt"),
        [
            ("CT", "TT"),  # Would require ε1 allele
            ("CC", "CT"),  # Would require ε1 allele
            ("CC", "TT"),  # Would require ε1 allele
        ],
        ids=["CT/TT", "CC/CT", "CC/TT"],
    )
    def test_impossible_combinations_return_ambiguous(
        self,
        sample_engine: sa.Engine,
        rs429358_gt: str,
        rs7412_gt: str,
    ) -> None:
        """Biologically impossible combinations should be AMBIGUOUS."""
        _seed_apoe_variants(sample_engine, rs429358_gt, rs7412_gt)
        result = determine_apoe_genotype(sample_engine)

        assert not result.is_determined
        assert result.status == APOEStatus.AMBIGUOUS
        assert result.diplotype is None


# ── Genotype ordering ────────────────────────────────────────────────────


class TestGenotypeOrdering:
    """Test that genotype order doesn't affect result."""

    def test_reversed_rs429358(self, sample_engine: sa.Engine) -> None:
        """TC at rs429358 treated same as CT."""
        _seed_apoe_variants(sample_engine, "TC", "CC")
        result = determine_apoe_genotype(sample_engine)

        assert result.is_determined
        assert result.diplotype == "ε3/ε4"

    def test_reversed_rs7412(self, sample_engine: sa.Engine) -> None:
        """TC at rs7412 treated same as CT."""
        _seed_apoe_variants(sample_engine, "TT", "TC")
        result = determine_apoe_genotype(sample_engine)

        assert result.is_determined
        assert result.diplotype == "ε2/ε3"

    def test_both_reversed(self, sample_engine: sa.Engine) -> None:
        """Both genotypes reversed."""
        _seed_apoe_variants(sample_engine, "TC", "TC")
        result = determine_apoe_genotype(sample_engine)

        assert result.is_determined
        assert result.diplotype == "ε2/ε4"


# ── Edge cases ────────────────────────────────────────────────────────────


class TestAPOEEdgeCases:
    """Test APOE determination edge cases."""

    def test_missing_both_snps(self, sample_engine: sa.Engine) -> None:
        """No APOE SNPs in raw_variants."""
        result = determine_apoe_genotype(sample_engine)

        assert not result.is_determined
        assert result.status == APOEStatus.MISSING_SNPS
        assert result.diplotype is None
        assert result.allele1 is None
        assert result.allele2 is None
        assert result.rs429358_genotype is None
        assert result.rs7412_genotype is None

    def test_missing_rs429358(self, sample_engine: sa.Engine) -> None:
        """Only rs7412 present."""
        _seed_apoe_variants(sample_engine, rs7412_genotype="CC")
        result = determine_apoe_genotype(sample_engine)

        assert not result.is_determined
        assert result.status == APOEStatus.MISSING_SNPS
        assert result.rs429358_genotype is None
        assert result.rs7412_genotype == "CC"

    def test_missing_rs7412(self, sample_engine: sa.Engine) -> None:
        """Only rs429358 present."""
        _seed_apoe_variants(sample_engine, rs429358_genotype="TT")
        result = determine_apoe_genotype(sample_engine)

        assert not result.is_determined
        assert result.status == APOEStatus.MISSING_SNPS
        assert result.rs429358_genotype == "TT"
        assert result.rs7412_genotype is None

    def test_no_call_rs429358(self, sample_engine: sa.Engine) -> None:
        """No-call at rs429358."""
        _seed_apoe_variants(sample_engine, "--", "CC")
        result = determine_apoe_genotype(sample_engine)

        assert not result.is_determined
        assert result.status == APOEStatus.NO_CALL

    def test_no_call_rs7412(self, sample_engine: sa.Engine) -> None:
        """No-call at rs7412."""
        _seed_apoe_variants(sample_engine, "TT", "--")
        result = determine_apoe_genotype(sample_engine)

        assert not result.is_determined
        assert result.status == APOEStatus.NO_CALL

    def test_no_call_both(self, sample_engine: sa.Engine) -> None:
        """No-call at both SNPs."""
        _seed_apoe_variants(sample_engine, "--", "--")
        result = determine_apoe_genotype(sample_engine)

        assert not result.is_determined
        assert result.status == APOEStatus.NO_CALL

    def test_no_call_zero_genotype(self, sample_engine: sa.Engine) -> None:
        """00 genotype treated as no-call."""
        _seed_apoe_variants(sample_engine, "00", "CC")
        result = determine_apoe_genotype(sample_engine)

        assert not result.is_determined
        assert result.status == APOEStatus.NO_CALL


# ── APOEResult properties ────────────────────────────────────────────────


class TestAPOEResultProperties:
    """Test APOEResult computed properties."""

    def test_e4_properties_when_absent(self) -> None:
        result = APOEResult(
            status=APOEStatus.DETERMINED,
            allele1=APOEAllele.E3,
            allele2=APOEAllele.E3,
            diplotype="ε3/ε3",
        )
        assert not result.has_e4
        assert result.e4_count == 0

    def test_e4_properties_heterozygous(self) -> None:
        result = APOEResult(
            status=APOEStatus.DETERMINED,
            allele1=APOEAllele.E3,
            allele2=APOEAllele.E4,
            diplotype="ε3/ε4",
        )
        assert result.has_e4
        assert result.e4_count == 1

    def test_e4_properties_homozygous(self) -> None:
        result = APOEResult(
            status=APOEStatus.DETERMINED,
            allele1=APOEAllele.E4,
            allele2=APOEAllele.E4,
            diplotype="ε4/ε4",
        )
        assert result.has_e4
        assert result.e4_count == 2

    def test_e2_properties(self) -> None:
        result = APOEResult(
            status=APOEStatus.DETERMINED,
            allele1=APOEAllele.E2,
            allele2=APOEAllele.E3,
            diplotype="ε2/ε3",
        )
        assert result.has_e2
        assert result.e2_count == 1
        assert not result.has_e4
        assert result.e4_count == 0

    def test_undetermined_properties(self) -> None:
        result = APOEResult(status=APOEStatus.MISSING_SNPS)
        assert not result.has_e4
        assert result.e4_count == 0
        assert not result.has_e2
        assert result.e2_count == 0
        assert not result.is_determined


# ── Finding storage ──────────────────────────────────────────────────────


class TestAPOEFindingStorage:
    """Test APOE finding persistence."""

    def test_store_determined_finding(self, sample_engine: sa.Engine) -> None:
        """Determined APOE result creates one finding."""
        _seed_apoe_variants(sample_engine, "CT", "CC")
        result = determine_apoe_genotype(sample_engine)
        count = store_apoe_finding(result, sample_engine)

        assert count == 1

        with sample_engine.connect() as conn:
            rows = conn.execute(
                sa.select(findings).where(findings.c.module == "apoe")
            ).fetchall()

        assert len(rows) == 1
        row = rows[0]
        assert row.module == "apoe"
        assert row.category == "genotype"
        assert row.gene_symbol == "APOE"
        assert row.evidence_level == 4
        assert row.diplotype == "ε3/ε4"
        assert "ε3/ε4" in row.finding_text
        assert "1× ε4" in row.finding_text

        detail = json.loads(row.detail_json)
        assert detail["allele1"] == "ε3"
        assert detail["allele2"] == "ε4"
        assert detail["has_e4"] is True
        assert detail["e4_count"] == 1
        assert detail["rs429358_genotype"] == "CT"
        assert detail["rs7412_genotype"] == "CC"

    def test_store_e3_e3_no_e4_text(self, sample_engine: sa.Engine) -> None:
        """ε3/ε3 finding text does not mention ε4."""
        _seed_apoe_variants(sample_engine, "TT", "CC")
        result = determine_apoe_genotype(sample_engine)
        store_apoe_finding(result, sample_engine)

        with sample_engine.connect() as conn:
            row = conn.execute(
                sa.select(findings).where(findings.c.module == "apoe")
            ).fetchone()

        assert row is not None
        assert "ε4" not in row.finding_text
        assert "ε3/ε3" in row.finding_text

    def test_store_e4_e4_two_alleles(self, sample_engine: sa.Engine) -> None:
        """ε4/ε4 finding text mentions 2× ε4."""
        _seed_apoe_variants(sample_engine, "CC", "CC")
        result = determine_apoe_genotype(sample_engine)
        store_apoe_finding(result, sample_engine)

        with sample_engine.connect() as conn:
            row = conn.execute(
                sa.select(findings).where(findings.c.module == "apoe")
            ).fetchone()

        assert row is not None
        assert "2× ε4" in row.finding_text

    def test_idempotent_rerun(self, sample_engine: sa.Engine) -> None:
        """Re-running store clears previous findings and inserts new one."""
        _seed_apoe_variants(sample_engine, "TT", "CC")
        result = determine_apoe_genotype(sample_engine)

        store_apoe_finding(result, sample_engine)
        store_apoe_finding(result, sample_engine)

        with sample_engine.connect() as conn:
            count = conn.execute(
                sa.select(sa.func.count()).select_from(findings).where(
                    findings.c.module == "apoe",
                    findings.c.category == "genotype",
                )
            ).scalar()

        assert count == 1

    def test_store_skipped_when_not_determined(self, sample_engine: sa.Engine) -> None:
        """Undetermined result stores no finding."""
        result = determine_apoe_genotype(sample_engine)  # no variants seeded
        count = store_apoe_finding(result, sample_engine)

        assert count == 0

        with sample_engine.connect() as conn:
            count = conn.execute(
                sa.select(sa.func.count()).select_from(findings).where(
                    findings.c.module == "apoe"
                )
            ).scalar()

        assert count == 0

    def test_store_clears_previous_when_not_determined(self, sample_engine: sa.Engine) -> None:
        """If a previous finding exists but new run is undetermined, it gets cleared."""
        # First run: determined
        _seed_apoe_variants(sample_engine, "TT", "CC")
        result1 = determine_apoe_genotype(sample_engine)
        store_apoe_finding(result1, sample_engine)

        # Remove raw variants to simulate missing data on re-run
        with sample_engine.begin() as conn:
            conn.execute(sa.delete(raw_variants))

        result2 = determine_apoe_genotype(sample_engine)
        store_apoe_finding(result2, sample_engine)

        with sample_engine.connect() as conn:
            count = conn.execute(
                sa.select(sa.func.count()).select_from(findings).where(
                    findings.c.module == "apoe"
                )
            ).scalar()

        assert count == 0

    def test_does_not_affect_other_module_findings(self, sample_engine: sa.Engine) -> None:
        """APOE finding storage doesn't touch findings from other modules."""
        # Insert a cardiovascular finding first
        with sample_engine.begin() as conn:
            conn.execute(
                sa.insert(findings),
                [
                    {
                        "module": "cardiovascular",
                        "category": "monogenic_variant",
                        "finding_text": "Test cardiovascular finding",
                    }
                ],
            )

        _seed_apoe_variants(sample_engine, "CT", "CC")
        result = determine_apoe_genotype(sample_engine)
        store_apoe_finding(result, sample_engine)

        with sample_engine.connect() as conn:
            cv_count = conn.execute(
                sa.select(sa.func.count())
                .select_from(findings)
                .where(findings.c.module == "cardiovascular")
            ).scalar()
            apoe_count = conn.execute(
                sa.select(sa.func.count())
                .select_from(findings)
                .where(findings.c.module == "apoe")
            ).scalar()

        assert cv_count == 1
        assert apoe_count == 1


# ── Allele enum ──────────────────────────────────────────────────────────


class TestAPOEAlleleEnum:
    """Test APOEAllele enum values."""

    def test_values(self) -> None:
        assert APOEAllele.E2.value == "ε2"
        assert APOEAllele.E3.value == "ε3"
        assert APOEAllele.E4.value == "ε4"

    def test_sorting(self) -> None:
        alleles = sorted([APOEAllele.E4, APOEAllele.E2, APOEAllele.E3], key=lambda a: a.value)
        assert alleles == [APOEAllele.E2, APOEAllele.E3, APOEAllele.E4]
