"""Cancer predisposition gene panel definition and loader.

Implements P3-12: Curated cancer gene panel with expected ClinVar entries.

The panel covers 28 genes (22 gene groups per PRD) associated with
hereditary cancer syndromes:

    BRCA1, BRCA2, TP53, PALB2, ATM, CHEK2, RAD51C, RAD51D,
    MLH1, MSH2, MSH6, PMS2, APC, MUTYH, VHL, RET, PTEN, STK11,
    CDH1, NF1, NF2, MEN1, SDHA, SDHB, SDHC, SDHD, BAP1, CDKN2A

Each gene entry includes associated syndromes, cancer types, inheritance
pattern, evidence level, expected ClinVar P/LP rsids, and PubMed citations.

BRCA1/2 have cross-links to the carrier status module — variants in these
genes produce findings in both the cancer and carrier modules with distinct
framing.

Usage::

    from backend.analysis.cancer import (
        load_cancer_panel,
        CancerPanel,
        CancerGene,
    )

    panel = load_cancer_panel()
    assert len(panel.genes) == 28
    brca1 = panel.get_gene("BRCA1")
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Path to the curated panel JSON (relative to this file)
_PANEL_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "panels" / "cancer_panel.json"
)


# ── Data classes ──────────────────────────────────────────────────────────


@dataclass
class CancerGene:
    """A single gene entry from the curated cancer panel."""

    gene_symbol: str
    name: str
    chromosome: str
    syndromes: list[str]
    cancer_types: list[str]
    inheritance: str  # AD or AR
    evidence_level: int  # 1-4 stars
    cross_links: list[str]  # module names (e.g. "carrier")
    expected_clinvar_rsids: list[str]
    pmids: list[str]
    notes: str

    @property
    def is_dual_role(self) -> bool:
        """Whether this gene produces findings in multiple modules."""
        return len(self.cross_links) > 0


@dataclass
class CancerPanel:
    """The complete curated cancer predisposition gene panel."""

    module: str
    version: str
    description: str
    genes: list[CancerGene]

    def all_gene_symbols(self) -> list[str]:
        """Return all gene symbols in the panel."""
        return [g.gene_symbol for g in self.genes]

    def all_expected_rsids(self) -> list[str]:
        """Return all expected ClinVar rsids across all genes."""
        return [
            rsid
            for gene in self.genes
            for rsid in gene.expected_clinvar_rsids
        ]

    def get_gene(self, gene_symbol: str) -> CancerGene | None:
        """Look up a gene by symbol (case-insensitive)."""
        symbol_upper = gene_symbol.upper()
        for gene in self.genes:
            if gene.gene_symbol.upper() == symbol_upper:
                return gene
        return None

    def dual_role_genes(self) -> list[CancerGene]:
        """Return genes that have cross-links to other modules."""
        return [g for g in self.genes if g.is_dual_role]

    def genes_by_syndrome(self, syndrome: str) -> list[CancerGene]:
        """Return all genes associated with a given syndrome (substring match)."""
        syndrome_lower = syndrome.lower()
        return [
            g for g in self.genes
            if any(syndrome_lower in s.lower() for s in g.syndromes)
        ]

    def genes_by_cancer_type(self, cancer_type: str) -> list[CancerGene]:
        """Return all genes associated with a given cancer type (substring match)."""
        cancer_lower = cancer_type.lower()
        return [
            g for g in self.genes
            if any(cancer_lower in ct.lower() for ct in g.cancer_types)
        ]


# ── Panel loading ─────────────────────────────────────────────────────────


def load_cancer_panel(panel_path: Path | None = None) -> CancerPanel:
    """Load the curated cancer gene panel from JSON.

    Args:
        panel_path: Optional override for the panel JSON path.
            Defaults to ``backend/data/panels/cancer_panel.json``.

    Returns:
        Parsed CancerPanel with all genes.

    Raises:
        FileNotFoundError: If the panel JSON does not exist.
        json.JSONDecodeError: If the panel JSON is malformed.
    """
    path = panel_path or _PANEL_PATH
    logger.info("loading_cancer_panel", path=str(path))

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    genes: list[CancerGene] = []
    for idx, gene_data in enumerate(data["genes"]):
        try:
            genes.append(
                CancerGene(
                    gene_symbol=gene_data["gene_symbol"],
                    name=gene_data["name"],
                    chromosome=gene_data["chromosome"],
                    syndromes=gene_data["syndromes"],
                    cancer_types=gene_data["cancer_types"],
                    inheritance=gene_data["inheritance"],
                    evidence_level=gene_data["evidence_level"],
                    cross_links=gene_data.get("cross_links", []),
                    expected_clinvar_rsids=gene_data.get("expected_clinvar_rsids", []),
                    pmids=gene_data.get("pmids", []),
                    notes=gene_data.get("notes", ""),
                )
            )
        except KeyError as e:
            symbol = gene_data.get("gene_symbol", f"index {idx}")
            raise ValueError(f"Missing required field {e} for gene {symbol}") from e

    panel = CancerPanel(
        module=data["module"],
        version=data["version"],
        description=data["description"],
        genes=genes,
    )

    logger.info(
        "cancer_panel_loaded",
        gene_count=len(panel.genes),
        total_expected_rsids=len(panel.all_expected_rsids()),
        dual_role_genes=[g.gene_symbol for g in panel.dual_role_genes()],
    )

    return panel
