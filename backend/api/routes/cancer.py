"""Cancer predisposition findings API (P3-13).

ClinVar P/LP extraction results from the 28-gene cancer panel — monogenic
pathogenic variants with accession, review stars, syndrome, and inheritance.

GET  /api/analysis/cancer/variants?sample_id=N               — All cancer P/LP findings
GET  /api/analysis/cancer/gene/{gene_symbol}?sample_id=N     — Findings for a single gene
POST /api/analysis/cancer/run?sample_id=N                    — Run/re-run extraction
"""

from __future__ import annotations

import json
import logging
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db.connection import get_registry
from backend.db.tables import findings, samples

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis/cancer", tags=["cancer"])


# ── Response models ──────────────────────────────────────────────────


class CancerVariantResponse(BaseModel):
    """A single P/LP variant in the cancer panel."""

    rsid: str
    gene_symbol: str
    genotype: str | None = None
    zygosity: str | None = None
    clinvar_significance: str
    clinvar_accession: str | None = None
    clinvar_review_stars: int = 0
    clinvar_conditions: str | None = None
    syndromes: list[str] = []
    cancer_types: list[str] = []
    inheritance: str = "AD"
    evidence_level: int = 4
    cross_links: list[str] = []
    pmids: list[str] = []


class CancerVariantsListResponse(BaseModel):
    """All cancer P/LP findings for a sample."""

    items: list[CancerVariantResponse]
    total: int
    panel_genes_checked: int = 0


class CancerRunResponse(BaseModel):
    """Result of running cancer predisposition extraction."""

    findings_count: int
    panel_genes_checked: int
    variants_in_panel_genes: int


# ── Helpers ──────────────────────────────────────────────────────────


def _get_sample_engine(sample_id: int) -> sa.Engine:
    """Resolve sample_id to a per-sample DB engine."""
    registry = get_registry()
    with registry.reference_engine.connect() as conn:
        row = conn.execute(
            sa.select(samples.c.db_path).where(samples.c.id == sample_id)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Sample {sample_id} not found.")

    sample_db_path = registry.settings.data_dir / row.db_path
    if not sample_db_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Sample database file not found for sample {sample_id}.",
        )
    return registry.get_sample_engine(sample_db_path)


def _fetch_cancer_findings(
    sample_engine: sa.Engine,
    gene_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch cancer findings from the sample DB."""
    with sample_engine.connect() as conn:
        stmt = (
            sa.select(findings)
            .where(findings.c.module == "cancer")
            .order_by(findings.c.evidence_level.desc(), findings.c.gene_symbol)
        )
        if gene_filter:
            stmt = stmt.where(findings.c.gene_symbol == gene_filter.upper())

        rows = conn.execute(stmt).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        detail: dict[str, Any] = {}
        if row.detail_json:
            try:
                detail = json.loads(row.detail_json)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse detail_json for finding id=%s", row.id)

        pmids: list[str] = []
        if row.pmid_citations:
            try:
                pmids = json.loads(row.pmid_citations)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse pmid_citations for finding id=%s", row.id)

        result.append(
            {
                "rsid": row.rsid or "",
                "gene_symbol": row.gene_symbol or "",
                "genotype": detail.get("genotype"),
                "zygosity": row.zygosity,
                "clinvar_significance": row.clinvar_significance or "",
                "clinvar_accession": detail.get("clinvar_accession"),
                "clinvar_review_stars": detail.get("clinvar_review_stars", 0),
                "clinvar_conditions": row.conditions,
                "syndromes": detail.get("syndromes", []),
                "cancer_types": detail.get("cancer_types", []),
                "inheritance": detail.get("inheritance", "AD"),
                "evidence_level": row.evidence_level or 1,
                "cross_links": detail.get("cross_links", []),
                "pmids": pmids,
            }
        )

    return result


def _findings_to_response(
    finding_rows: list[dict[str, Any]],
) -> list[CancerVariantResponse]:
    """Convert raw finding dicts to response models."""
    return [CancerVariantResponse(**f) for f in finding_rows]


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/variants")
def list_cancer_variants(
    sample_id: int = Query(..., description="Sample ID"),
) -> CancerVariantsListResponse:
    """List all cancer P/LP variant findings for a sample.

    Returns ClinVar Pathogenic and Likely pathogenic variants in the
    28-gene cancer predisposition panel, sorted by evidence level
    (highest first).

    Example: ``GET /api/analysis/cancer/variants?sample_id=1``
    """
    sample_engine = _get_sample_engine(sample_id)
    raw = _fetch_cancer_findings(sample_engine)
    items = _findings_to_response(raw)
    return CancerVariantsListResponse(items=items, total=len(items))


@router.get("/gene/{gene_symbol}")
def cancer_gene_detail(
    gene_symbol: str,
    sample_id: int = Query(..., description="Sample ID"),
) -> CancerVariantsListResponse:
    """Get cancer findings for a specific gene.

    Example: ``GET /api/analysis/cancer/gene/BRCA1?sample_id=1``
    """
    sample_engine = _get_sample_engine(sample_id)
    raw = _fetch_cancer_findings(sample_engine, gene_filter=gene_symbol)
    items = _findings_to_response(raw)
    return CancerVariantsListResponse(items=items, total=len(items))


@router.post("/run")
def run_cancer_analysis(
    sample_id: int = Query(..., description="Sample ID"),
) -> CancerRunResponse:
    """Run or re-run cancer predisposition extraction for a sample.

    Loads the curated panel, extracts ClinVar P/LP variants from
    annotated_variants, and stores findings.

    Example: ``POST /api/analysis/cancer/run?sample_id=1``
    """
    from backend.analysis.cancer import (
        extract_cancer_variants,
        load_cancer_panel,
        store_cancer_findings,
    )

    sample_engine = _get_sample_engine(sample_id)

    panel = load_cancer_panel()
    result = extract_cancer_variants(panel, sample_engine)
    count = store_cancer_findings(result, sample_engine)

    return CancerRunResponse(
        findings_count=count,
        panel_genes_checked=result.panel_genes_checked,
        variants_in_panel_genes=result.variants_in_panel_genes,
    )
