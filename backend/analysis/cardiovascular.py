"""Cardiovascular gene panel definition, loader, and analysis module.

Implements P3-19 (cardiovascular module annotation):
  - Curated cardiovascular gene panel covering familial hypercholesterolemia
    (LDLR, PCSK9, APOB), lipid metabolism (LPA, ABCG5/8),
    channelopathies (KCNQ1, SCN5A, KCNH2, RYR2), and
    cardiomyopathies (MYBPC3, MYH7, TNNT2, LMNA, DSP, PKP2).
  - Extract ClinVar Pathogenic/Likely pathogenic variants in the
    cardiovascular gene panel and generate findings.

The panel covers 16 genes across 4 cardiovascular categories:
  - Familial hypercholesterolemia: LDLR, PCSK9, APOB
  - Lipid metabolism: LPA, ABCG5, ABCG8
  - Channelopathies: KCNQ1, SCN5A, KCNH2, RYR2
  - Cardiomyopathies: MYBPC3, MYH7, TNNT2, LMNA, DSP, PKP2

Usage::

    from backend.analysis.cardiovascular import (
        load_cardiovascular_panel,
        extract_cardiovascular_variants,
        store_cardiovascular_findings,
        CardiovascularPanel,
        CardiovascularGene,
        CardiovascularVariantResult,
        CardiovascularAnalysisResult,
    )

    panel = load_cardiovascular_panel()
    result = extract_cardiovascular_variants(panel, sample_engine)
    store_cardiovascular_findings(result, sample_engine)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import sqlalchemy as sa
import structlog

from backend.db.tables import annotated_variants, findings

logger = structlog.get_logger(__name__)

# Path to the curated panel JSON (relative to this file)
_PANEL_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "panels" / "cardiovascular_panel.json"
)

# Cardiovascular categories for grouping findings
CATEGORY_FH = "familial_hypercholesterolemia"
CATEGORY_LIPID = "lipid_metabolism"
CATEGORY_CHANNELOPATHY = "channelopathy"
CATEGORY_CARDIOMYOPATHY = "cardiomyopathy"

VALID_CATEGORIES = {CATEGORY_FH, CATEGORY_LIPID, CATEGORY_CHANNELOPATHY, CATEGORY_CARDIOMYOPATHY}


# ── Data classes ──────────────────────────────────────────────────────────


@dataclass
class CardiovascularGene:
    """A single gene entry from the curated cardiovascular panel."""

    gene_symbol: str
    name: str
    chromosome: str
    conditions: list[str]
    cardiovascular_category: str  # familial_hypercholesterolemia, lipid_metabolism, etc.
    inheritance: str  # AD or AR
    evidence_level: int  # 1-4 stars
    cross_links: list[str]
    expected_clinvar_rsids: list[str]
    pmids: list[str]
    notes: str


@dataclass
class CardiovascularPanel:
    """The complete curated cardiovascular gene panel."""

    module: str
    version: str
    description: str
    genes: list[CardiovascularGene]

    def all_gene_symbols(self) -> list[str]:
        """Return all gene symbols in the panel."""
        return [g.gene_symbol for g in self.genes]

    def all_expected_rsids(self) -> list[str]:
        """Return all expected ClinVar rsids across all genes."""
        return [rsid for gene in self.genes for rsid in gene.expected_clinvar_rsids]

    def get_gene(self, gene_symbol: str) -> CardiovascularGene | None:
        """Look up a gene by symbol (case-insensitive)."""
        symbol_upper = gene_symbol.upper()
        for gene in self.genes:
            if gene.gene_symbol.upper() == symbol_upper:
                return gene
        return None

    def genes_by_category(self, category: str) -> list[CardiovascularGene]:
        """Return all genes in a given cardiovascular category."""
        return [g for g in self.genes if g.cardiovascular_category == category]

    def genes_by_condition(self, condition: str) -> list[CardiovascularGene]:
        """Return all genes associated with a given condition (substring match)."""
        condition_lower = condition.lower()
        return [g for g in self.genes if any(condition_lower in c.lower() for c in g.conditions)]

    def fh_genes(self) -> list[CardiovascularGene]:
        """Return genes associated with familial hypercholesterolemia."""
        return self.genes_by_category(CATEGORY_FH)


# ── Panel loading ─────────────────────────────────────────────────────────


def load_cardiovascular_panel(panel_path: Path | None = None) -> CardiovascularPanel:
    """Load the curated cardiovascular gene panel from JSON.

    Args:
        panel_path: Optional override for the panel JSON path.
            Defaults to ``backend/data/panels/cardiovascular_panel.json``.

    Returns:
        Parsed CardiovascularPanel with all genes.

    Raises:
        FileNotFoundError: If the panel JSON does not exist.
        json.JSONDecodeError: If the panel JSON is malformed.
    """
    path = panel_path or _PANEL_PATH
    logger.info("loading_cardiovascular_panel", path=str(path))

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    genes: list[CardiovascularGene] = []
    for idx, gene_data in enumerate(data["genes"]):
        try:
            genes.append(
                CardiovascularGene(
                    gene_symbol=gene_data["gene_symbol"],
                    name=gene_data["name"],
                    chromosome=gene_data["chromosome"],
                    conditions=gene_data["conditions"],
                    cardiovascular_category=gene_data["cardiovascular_category"],
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

    panel = CardiovascularPanel(
        module=data["module"],
        version=data["version"],
        description=data["description"],
        genes=genes,
    )

    logger.info(
        "cardiovascular_panel_loaded",
        gene_count=len(panel.genes),
        total_expected_rsids=len(panel.all_expected_rsids()),
        fh_genes=[g.gene_symbol for g in panel.fh_genes()],
    )

    return panel


# ── P3-19: Cardiovascular module annotation ───────────────────────────────

# ClinVar significance values considered pathogenic
_PATHOGENIC_SIGNIFICANCE = {"Pathogenic", "Likely pathogenic", "Pathogenic/Likely pathogenic"}


@dataclass
class CardiovascularVariantResult:
    """A single ClinVar P/LP variant found in the cardiovascular gene panel."""

    rsid: str
    gene_symbol: str
    genotype: str
    zygosity: str | None
    clinvar_significance: str
    clinvar_review_stars: int
    clinvar_accession: str | None
    clinvar_conditions: str | None
    conditions: list[str]
    cardiovascular_category: str
    inheritance: str
    evidence_level: int
    cross_links: list[str]
    pmids: list[str]


@dataclass
class CardiovascularAnalysisResult:
    """Complete cardiovascular analysis result for a sample."""

    variants: list[CardiovascularVariantResult] = field(default_factory=list)
    panel_genes_checked: int = 0
    variants_in_panel_genes: int = 0

    @property
    def pathogenic_count(self) -> int:
        """Number of P/LP variants found."""
        return len(self.variants)

    @property
    def fh_variants(self) -> list[CardiovascularVariantResult]:
        """Variants in FH genes (LDLR, PCSK9, APOB)."""
        return [v for v in self.variants if v.cardiovascular_category == CATEGORY_FH]

    @property
    def cardiomyopathy_variants(self) -> list[CardiovascularVariantResult]:
        """Variants in cardiomyopathy genes."""
        return [v for v in self.variants if v.cardiovascular_category == CATEGORY_CARDIOMYOPATHY]

    @property
    def channelopathy_variants(self) -> list[CardiovascularVariantResult]:
        """Variants in channelopathy genes."""
        return [v for v in self.variants if v.cardiovascular_category == CATEGORY_CHANNELOPATHY]

    @property
    def lipid_variants(self) -> list[CardiovascularVariantResult]:
        """Variants in lipid metabolism genes."""
        return [v for v in self.variants if v.cardiovascular_category == CATEGORY_LIPID]


def _assign_evidence_level(
    clinvar_significance: str,
    clinvar_review_stars: int,
    gene_evidence_level: int,
) -> int:
    """Assign evidence level (1-4 stars) based on ClinVar data.

    Evidence star criteria from PRD §3.4:
      ★★★★ — ClinVar P/LP with ≥2-star review
      ★★★☆ — ClinVar LP with 1-star review
      ★★☆☆ — ClinVar VUS with functional evidence
      ★☆☆☆ — Single study, candidate gene

    For P/LP variants in the cardiovascular panel:
      - ≥2 review stars → 4 (Definitive/Pathogenic)
      - 1 review star + Pathogenic → 4
      - 1 review star + Likely pathogenic → 3 (Strong)
      - 0 review stars → min(gene baseline, 2)
    """
    if clinvar_review_stars >= 2:
        return 4

    if clinvar_review_stars == 1:
        if clinvar_significance == "Pathogenic":
            return 4
        return 3  # Likely pathogenic with 1 star

    # 0 review stars — cap at gene baseline or 2
    return min(gene_evidence_level, 2)


def extract_cardiovascular_variants(
    panel: CardiovascularPanel,
    sample_engine: sa.Engine,
) -> CardiovascularAnalysisResult:
    """Extract ClinVar P/LP variants in the cardiovascular gene panel.

    Queries the annotated_variants table for variants where:
      1. gene_symbol is in the cardiovascular panel genes
      2. clinvar_significance is Pathogenic or Likely pathogenic

    For each matching variant, enriches with panel metadata (conditions,
    cardiovascular category, inheritance, cross-links, PMIDs).

    Args:
        panel: Loaded CardiovascularPanel.
        sample_engine: SQLAlchemy engine for the sample database.

    Returns:
        CardiovascularAnalysisResult with all P/LP variants found.
    """
    gene_symbols = panel.all_gene_symbols()
    gene_map = {g.gene_symbol.upper(): g for g in panel.genes}

    with sample_engine.connect() as conn:
        # Count total variants in panel genes (for stats)
        count_stmt = (
            sa.select(sa.func.count())
            .select_from(annotated_variants)
            .where(annotated_variants.c.gene_symbol.in_(gene_symbols))
        )
        total_in_panel = conn.execute(count_stmt).scalar() or 0

        # Fetch P/LP variants
        stmt = (
            sa.select(
                annotated_variants.c.rsid,
                annotated_variants.c.gene_symbol,
                annotated_variants.c.genotype,
                annotated_variants.c.zygosity,
                annotated_variants.c.clinvar_significance,
                annotated_variants.c.clinvar_review_stars,
                annotated_variants.c.clinvar_accession,
                annotated_variants.c.clinvar_conditions,
            )
            .where(
                annotated_variants.c.gene_symbol.in_(gene_symbols),
                annotated_variants.c.clinvar_significance.in_(list(_PATHOGENIC_SIGNIFICANCE)),
            )
            .order_by(annotated_variants.c.gene_symbol, annotated_variants.c.rsid)
        )
        rows = conn.execute(stmt).fetchall()

    variants: list[CardiovascularVariantResult] = []
    for row in rows:
        gene_info = gene_map.get((row.gene_symbol or "").upper())
        if gene_info is None:
            continue

        evidence = _assign_evidence_level(
            row.clinvar_significance or "",
            row.clinvar_review_stars or 0,
            gene_info.evidence_level,
        )

        variants.append(
            CardiovascularVariantResult(
                rsid=row.rsid,
                gene_symbol=row.gene_symbol,
                genotype=row.genotype or "",
                zygosity=row.zygosity,
                clinvar_significance=row.clinvar_significance,
                clinvar_review_stars=row.clinvar_review_stars or 0,
                clinvar_accession=row.clinvar_accession,
                clinvar_conditions=row.clinvar_conditions,
                conditions=gene_info.conditions,
                cardiovascular_category=gene_info.cardiovascular_category,
                inheritance=gene_info.inheritance,
                evidence_level=evidence,
                cross_links=gene_info.cross_links,
                pmids=gene_info.pmids,
            )
        )

    logger.info(
        "cardiovascular_variants_extracted",
        panel_genes=len(gene_symbols),
        variants_in_panel_genes=total_in_panel,
        pathogenic_variants=len(variants),
        fh_variants=len([v for v in variants if v.cardiovascular_category == CATEGORY_FH]),
        cardiomyopathy_variants=len(
            [v for v in variants if v.cardiovascular_category == CATEGORY_CARDIOMYOPATHY]
        ),
        channelopathy_variants=len(
            [v for v in variants if v.cardiovascular_category == CATEGORY_CHANNELOPATHY]
        ),
    )

    return CardiovascularAnalysisResult(
        variants=variants,
        panel_genes_checked=len(gene_symbols),
        variants_in_panel_genes=total_in_panel,
    )


# ── Findings storage ─────────────────────────────────────────────────────


def store_cardiovascular_findings(
    result: CardiovascularAnalysisResult,
    sample_engine: sa.Engine,
) -> int:
    """Store cardiovascular findings in the sample database.

    Creates one finding per P/LP variant with module='cardiovascular' and
    category='monogenic_variant'. Each finding includes ClinVar accession,
    review stars, cardiovascular category, inheritance, and condition metadata.

    Args:
        result: CardiovascularAnalysisResult from extract_cardiovascular_variants.
        sample_engine: SQLAlchemy engine for the sample database.

    Returns:
        Number of findings inserted.
    """
    rows: list[dict] = []

    for v in result.variants:
        # Build human-readable finding text
        sig_display = v.clinvar_significance
        condition_text = ", ".join(v.conditions) if v.conditions else "Cardiovascular condition"
        finding_text = (
            f"{v.gene_symbol} {v.rsid} ({v.genotype}) — {sig_display} for {condition_text}"
        )

        detail = {
            "clinvar_accession": v.clinvar_accession,
            "clinvar_review_stars": v.clinvar_review_stars,
            "clinvar_conditions": v.clinvar_conditions,
            "conditions": v.conditions,
            "cardiovascular_category": v.cardiovascular_category,
            "inheritance": v.inheritance,
            "cross_links": v.cross_links,
        }

        rows.append(
            {
                "module": "cardiovascular",
                "category": "monogenic_variant",
                "evidence_level": v.evidence_level,
                "gene_symbol": v.gene_symbol,
                "rsid": v.rsid,
                "finding_text": finding_text,
                "conditions": v.clinvar_conditions,
                "zygosity": v.zygosity,
                "clinvar_significance": v.clinvar_significance,
                "pmid_citations": json.dumps(v.pmids),
                "detail_json": json.dumps(detail),
            }
        )

    with sample_engine.begin() as conn:
        # Clear previous cardiovascular findings
        conn.execute(sa.delete(findings).where(findings.c.module == "cardiovascular"))
        if rows:
            conn.execute(sa.insert(findings), rows)
        else:
            logger.info("no_cardiovascular_findings_to_store")

    logger.info("cardiovascular_findings_stored", count=len(rows))
    return len(rows)
