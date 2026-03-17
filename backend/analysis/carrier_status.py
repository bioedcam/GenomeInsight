"""Carrier status gene panel definition and loader.

Implements P3-35: Carrier gene panel definition.

Curated panel of 7 genes associated with autosomal recessive conditions
relevant to reproductive carrier screening:

    CFTR   — Cystic Fibrosis
    HBB    — Sickle Cell Disease / Beta-Thalassemia
    GBA    — Gaucher Disease
    HEXA   — Tay-Sachs Disease
    BRCA1  — Hereditary Breast and Ovarian Cancer (dual-role: cancer + carrier)
    BRCA2  — Hereditary Breast and Ovarian Cancer (dual-role: cancer + carrier)
    SMN1   — Spinal Muscular Atrophy

BRCA1/2 are included for reproductive carrier context — distinct from the
cancer module's disease predisposition framing.  A heterozygous BRCA1/2 P/LP
variant produces TWO distinct findings: one in the cancer module (disease
risk) and one in the carrier module (reproductive risk).

Usage::

    from backend.analysis.carrier_status import (
        load_carrier_panel,
        CarrierPanel,
        CarrierGene,
    )

    panel = load_carrier_panel()
    print(panel.all_gene_symbols())
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Path to the curated panel JSON (relative to this file)
_PANEL_PATH = Path(__file__).resolve().parent.parent / "data" / "panels" / "carrier_panel.json"


# ── Data classes ──────────────────────────────────────────────────────────


@dataclass
class CarrierGene:
    """A single gene entry from the curated carrier panel."""

    gene_symbol: str
    name: str
    chromosome: str
    conditions: list[str]
    inheritance: str  # AR (most) or AD (BRCA1/2)
    evidence_level: int  # 1-4 stars
    cross_links: list[str]  # module names (e.g. "cancer" for BRCA1/2)
    expected_clinvar_rsids: list[str]
    pmids: list[str]
    notes: str

    @property
    def is_dual_role(self) -> bool:
        """Whether this gene produces findings in multiple modules."""
        return len(self.cross_links) > 0


@dataclass
class CarrierPanel:
    """The complete curated carrier status gene panel."""

    module: str
    version: str
    description: str
    genes: list[CarrierGene]

    def all_gene_symbols(self) -> list[str]:
        """Return all gene symbols in the panel."""
        return [g.gene_symbol for g in self.genes]

    def all_expected_rsids(self) -> list[str]:
        """Return all expected ClinVar rsids across all genes."""
        return [rsid for gene in self.genes for rsid in gene.expected_clinvar_rsids]

    def get_gene(self, gene_symbol: str) -> CarrierGene | None:
        """Look up a gene by symbol (case-insensitive)."""
        symbol_upper = gene_symbol.upper()
        for gene in self.genes:
            if gene.gene_symbol.upper() == symbol_upper:
                return gene
        return None

    def dual_role_genes(self) -> list[CarrierGene]:
        """Return genes that have cross-links to other modules."""
        return [g for g in self.genes if g.is_dual_role]

    def autosomal_recessive_genes(self) -> list[CarrierGene]:
        """Return only AR-inheritance genes (excludes BRCA1/2)."""
        return [g for g in self.genes if g.inheritance == "AR"]

    def genes_by_condition(self, condition: str) -> list[CarrierGene]:
        """Return all genes associated with a given condition (substring match)."""
        condition_lower = condition.lower()
        return [g for g in self.genes if any(condition_lower in c.lower() for c in g.conditions)]


# ── Panel loading ─────────────────────────────────────────────────────────


def load_carrier_panel(panel_path: Path | None = None) -> CarrierPanel:
    """Load the curated carrier gene panel from JSON.

    Args:
        panel_path: Optional override for the panel JSON path.
            Defaults to ``backend/data/panels/carrier_panel.json``.

    Returns:
        Parsed CarrierPanel with all genes.

    Raises:
        FileNotFoundError: If the panel JSON does not exist.
        json.JSONDecodeError: If the panel JSON is malformed.
    """
    path = panel_path or _PANEL_PATH
    logger.info("loading_carrier_panel", path=str(path))

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    genes: list[CarrierGene] = []
    for idx, gene_data in enumerate(data["genes"]):
        try:
            genes.append(
                CarrierGene(
                    gene_symbol=gene_data["gene_symbol"],
                    name=gene_data["name"],
                    chromosome=gene_data["chromosome"],
                    conditions=gene_data["conditions"],
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

    try:
        module = data["module"]
        version = data["version"]
        description = data["description"]
    except KeyError as e:
        raise ValueError(f"Missing required panel field: {e}") from e

    panel = CarrierPanel(
        module=module,
        version=version,
        description=description,
        genes=genes,
    )

    logger.info(
        "carrier_panel_loaded",
        gene_count=len(panel.genes),
        total_expected_rsids=len(panel.all_expected_rsids()),
        dual_role_genes=[g.gene_symbol for g in panel.dual_role_genes()],
        ar_gene_count=len(panel.autosomal_recessive_genes()),
    )

    return panel
