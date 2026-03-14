"""Tests for the curated cancer gene panel (P3-12).

Covers:
  - Panel JSON loading and validation
  - All 28 genes present (22 gene groups per PRD)
  - Gene lookup by symbol
  - Syndrome and cancer type queries
  - BRCA1/2 dual-role cross-links to carrier module
  - Expected ClinVar rsids are populated
  - Evidence levels are valid (1-4)
  - Inheritance patterns are valid (AD/AR)
  - Panel structure integrity
  - T3-12 prerequisite: BRCA1 rs80357906 is in expected rsids
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.analysis.cancer import (
    CancerGene,
    CancerPanel,
    load_cancer_panel,
)

# ── Fixtures ──────────────────────────────────────────────────────────────

PANEL_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "backend"
    / "data"
    / "panels"
    / "cancer_panel.json"
)


@pytest.fixture()
def panel() -> CancerPanel:
    """Load the curated cancer panel from the real JSON file."""
    return load_cancer_panel(PANEL_PATH)


# ── Panel loading tests ──────────────────────────────────────────────────


class TestPanelLoading:
    """Test panel JSON loading and basic structure."""

    def test_panel_loads_successfully(self, panel: CancerPanel) -> None:
        assert panel is not None
        assert panel.module == "cancer"
        assert panel.version == "1.0.0"

    def test_panel_has_description(self, panel: CancerPanel) -> None:
        assert panel.description
        assert "cancer" in panel.description.lower()

    def test_panel_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_cancer_panel(tmp_path / "nonexistent.json")

    def test_panel_malformed_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_cancer_panel(bad_file)

    def test_panel_missing_required_field(self, tmp_path: Path) -> None:
        """Missing required field raises ValueError with gene context."""
        bad_panel = tmp_path / "bad_panel.json"
        bad_panel.write_text(
            json.dumps(
                {
                    "module": "cancer",
                    "version": "1.0.0",
                    "description": "test",
                    "genes": [{"gene_symbol": "TEST"}],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Missing required field.*TEST"):
            load_cancer_panel(bad_panel)


# ── Gene count and completeness ──────────────────────────────────────────


class TestGeneCompleteness:
    """Verify all PRD-specified genes are present."""

    # The 22 gene groups from the PRD (expanded to individual genes)
    EXPECTED_GENES = [
        "BRCA1",
        "BRCA2",  # BRCA1/2
        "TP53",
        "PALB2",
        "ATM",
        "CHEK2",
        "RAD51C",
        "RAD51D",  # RAD51C/D
        "MLH1",
        "MSH2",
        "MSH6",  # MSH2/6
        "PMS2",
        "APC",
        "MUTYH",
        "VHL",
        "RET",
        "PTEN",
        "STK11",
        "CDH1",
        "NF1",
        "NF2",  # NF1/2
        "MEN1",
        "SDHA",
        "SDHB",
        "SDHC",
        "SDHD",  # SDHA/B/C/D
        "BAP1",
        "CDKN2A",
    ]

    def test_gene_count(self, panel: CancerPanel) -> None:
        assert len(panel.genes) == 28

    def test_all_expected_genes_present(self, panel: CancerPanel) -> None:
        panel_symbols = set(panel.all_gene_symbols())
        for gene in self.EXPECTED_GENES:
            assert gene in panel_symbols, f"Missing gene: {gene}"

    def test_no_unexpected_genes(self, panel: CancerPanel) -> None:
        panel_symbols = set(panel.all_gene_symbols())
        expected = set(self.EXPECTED_GENES)
        unexpected = panel_symbols - expected
        assert not unexpected, f"Unexpected genes: {unexpected}"


# ── Gene lookup ──────────────────────────────────────────────────────────


class TestGeneLookup:
    """Test gene lookup methods."""

    def test_get_gene_by_symbol(self, panel: CancerPanel) -> None:
        brca1 = panel.get_gene("BRCA1")
        assert brca1 is not None
        assert brca1.gene_symbol == "BRCA1"

    def test_get_gene_case_insensitive(self, panel: CancerPanel) -> None:
        brca1 = panel.get_gene("brca1")
        assert brca1 is not None
        assert brca1.gene_symbol == "BRCA1"

    def test_get_gene_not_found(self, panel: CancerPanel) -> None:
        result = panel.get_gene("NONEXISTENT")
        assert result is None

    def test_genes_by_syndrome_lynch(self, panel: CancerPanel) -> None:
        lynch_genes = panel.genes_by_syndrome("Lynch")
        symbols = {g.gene_symbol for g in lynch_genes}
        assert {"MLH1", "MSH2", "MSH6", "PMS2"} == symbols

    def test_genes_by_cancer_type_breast(self, panel: CancerPanel) -> None:
        breast_genes = panel.genes_by_cancer_type("Breast")
        symbols = {g.gene_symbol for g in breast_genes}
        assert "BRCA1" in symbols
        assert "BRCA2" in symbols
        assert "TP53" in symbols
        assert "PALB2" in symbols

    def test_genes_by_cancer_type_colorectal(self, panel: CancerPanel) -> None:
        crc_genes = panel.genes_by_cancer_type("Colorectal")
        symbols = {g.gene_symbol for g in crc_genes}
        assert "APC" in symbols
        assert "MLH1" in symbols
        assert "MSH2" in symbols


# ── Cross-links and dual-role genes ──────────────────────────────────────


class TestCrossLinks:
    """Test BRCA1/2 dual-role cross-links."""

    def test_brca1_has_carrier_cross_link(self, panel: CancerPanel) -> None:
        brca1 = panel.get_gene("BRCA1")
        assert brca1 is not None
        assert "carrier" in brca1.cross_links
        assert brca1.is_dual_role

    def test_brca2_has_carrier_cross_link(self, panel: CancerPanel) -> None:
        brca2 = panel.get_gene("BRCA2")
        assert brca2 is not None
        assert "carrier" in brca2.cross_links
        assert brca2.is_dual_role

    def test_dual_role_genes_are_brca_only(self, panel: CancerPanel) -> None:
        dual = panel.dual_role_genes()
        symbols = {g.gene_symbol for g in dual}
        assert symbols == {"BRCA1", "BRCA2"}

    def test_non_brca_genes_have_no_cross_links(self, panel: CancerPanel) -> None:
        tp53 = panel.get_gene("TP53")
        assert tp53 is not None
        assert not tp53.is_dual_role
        assert tp53.cross_links == []


# ── Expected ClinVar rsids ───────────────────────────────────────────────


class TestExpectedClinVarRsids:
    """Test expected ClinVar P/LP rsid entries."""

    def test_all_genes_have_expected_rsids(self, panel: CancerPanel) -> None:
        for gene in panel.genes:
            assert len(gene.expected_clinvar_rsids) > 0, (
                f"{gene.gene_symbol} has no expected ClinVar rsids"
            )

    def test_rsids_are_valid_format(self, panel: CancerPanel) -> None:
        for gene in panel.genes:
            for rsid in gene.expected_clinvar_rsids:
                assert rsid.startswith("rs"), f"Invalid rsid format: {rsid} in {gene.gene_symbol}"
                # Ensure the numeric part is valid
                assert rsid[2:].isdigit(), (
                    f"Invalid rsid numeric part: {rsid} in {gene.gene_symbol}"
                )

    def test_no_duplicate_rsids_within_gene(self, panel: CancerPanel) -> None:
        for gene in panel.genes:
            rsids = gene.expected_clinvar_rsids
            assert len(rsids) == len(set(rsids)), f"Duplicate rsids in {gene.gene_symbol}"

    def test_total_expected_rsids(self, panel: CancerPanel) -> None:
        """Panel should have a substantial number of expected rsids."""
        all_rsids = panel.all_expected_rsids()
        assert len(all_rsids) >= 100  # At least 100 across all genes

    def test_brca1_rs80357906_present(self, panel: CancerPanel) -> None:
        """T3-12 prerequisite: BRCA1 rs80357906 must be in expected rsids."""
        brca1 = panel.get_gene("BRCA1")
        assert brca1 is not None
        assert "rs80357906" in brca1.expected_clinvar_rsids


# ── Evidence levels ──────────────────────────────────────────────────────


class TestEvidenceLevels:
    """Test evidence level assignments."""

    def test_evidence_levels_valid_range(self, panel: CancerPanel) -> None:
        for gene in panel.genes:
            assert 1 <= gene.evidence_level <= 4, (
                f"{gene.gene_symbol} has invalid evidence level: {gene.evidence_level}"
            )

    def test_high_evidence_genes(self, panel: CancerPanel) -> None:
        """BRCA1/2, TP53, MLH1, MSH2, APC should be 4-star."""
        four_star_genes = ["BRCA1", "BRCA2", "TP53", "MLH1", "MSH2", "APC"]
        for symbol in four_star_genes:
            gene = panel.get_gene(symbol)
            assert gene is not None
            assert gene.evidence_level == 4, (
                f"{symbol} should be 4-star evidence, got {gene.evidence_level}"
            )

    def test_moderate_evidence_genes(self, panel: CancerPanel) -> None:
        """ATM, CHEK2 should be 3-star (moderate penetrance)."""
        three_star_genes = ["ATM", "CHEK2"]
        for symbol in three_star_genes:
            gene = panel.get_gene(symbol)
            assert gene is not None
            assert gene.evidence_level == 3, (
                f"{symbol} should be 3-star evidence, got {gene.evidence_level}"
            )


# ── Inheritance patterns ─────────────────────────────────────────────────


class TestInheritance:
    """Test inheritance pattern assignments."""

    def test_inheritance_values_valid(self, panel: CancerPanel) -> None:
        valid_patterns = {"AD", "AR"}
        for gene in panel.genes:
            assert gene.inheritance in valid_patterns, (
                f"{gene.gene_symbol} has invalid inheritance: {gene.inheritance}"
            )

    def test_mutyh_is_autosomal_recessive(self, panel: CancerPanel) -> None:
        """MUTYH-Associated Polyposis is AR."""
        mutyh = panel.get_gene("MUTYH")
        assert mutyh is not None
        assert mutyh.inheritance == "AR"

    def test_most_genes_are_autosomal_dominant(self, panel: CancerPanel) -> None:
        """Most cancer predisposition genes are AD."""
        ad_count = sum(1 for g in panel.genes if g.inheritance == "AD")
        assert ad_count >= 27  # All except MUTYH should be AD


# ── PubMed citations ─────────────────────────────────────────────────────


class TestPMIDs:
    """Test PubMed citation data."""

    def test_all_genes_have_pmids(self, panel: CancerPanel) -> None:
        for gene in panel.genes:
            assert len(gene.pmids) > 0, f"{gene.gene_symbol} has no PubMed citations"

    def test_pmids_are_numeric(self, panel: CancerPanel) -> None:
        for gene in panel.genes:
            for pmid in gene.pmids:
                assert pmid.isdigit(), f"Invalid PMID: {pmid} in {gene.gene_symbol}"


# ── Gene metadata ────────────────────────────────────────────────────────


class TestGeneMetadata:
    """Test gene metadata completeness."""

    def test_all_genes_have_syndromes(self, panel: CancerPanel) -> None:
        for gene in panel.genes:
            assert len(gene.syndromes) > 0, f"{gene.gene_symbol} has no syndromes"

    def test_all_genes_have_cancer_types(self, panel: CancerPanel) -> None:
        for gene in panel.genes:
            assert len(gene.cancer_types) > 0, f"{gene.gene_symbol} has no cancer types"

    def test_all_genes_have_chromosome(self, panel: CancerPanel) -> None:
        valid_chroms = {str(i) for i in range(1, 23)} | {"X", "Y"}
        for gene in panel.genes:
            assert gene.chromosome in valid_chroms, (
                f"{gene.gene_symbol} has invalid chromosome: {gene.chromosome}"
            )

    def test_all_genes_have_name(self, panel: CancerPanel) -> None:
        for gene in panel.genes:
            assert gene.name, f"{gene.gene_symbol} has no name"

    def test_all_genes_have_notes(self, panel: CancerPanel) -> None:
        for gene in panel.genes:
            assert gene.notes, f"{gene.gene_symbol} has no notes"


# ── Dataclass properties ─────────────────────────────────────────────────


class TestDataclassProperties:
    """Test CancerGene dataclass properties."""

    def test_is_dual_role_true(self) -> None:
        gene = CancerGene(
            gene_symbol="TEST",
            name="Test Gene",
            chromosome="1",
            syndromes=["Test Syndrome"],
            cancer_types=["Test Cancer"],
            inheritance="AD",
            evidence_level=4,
            cross_links=["carrier"],
            expected_clinvar_rsids=["rs123"],
            pmids=["12345"],
            notes="Test note",
        )
        assert gene.is_dual_role is True

    def test_is_dual_role_false(self) -> None:
        gene = CancerGene(
            gene_symbol="TEST",
            name="Test Gene",
            chromosome="1",
            syndromes=["Test Syndrome"],
            cancer_types=["Test Cancer"],
            inheritance="AD",
            evidence_level=3,
            cross_links=[],
            expected_clinvar_rsids=["rs123"],
            pmids=["12345"],
            notes="Test note",
        )
        assert gene.is_dual_role is False
