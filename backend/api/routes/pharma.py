"""Drug lookup API (P3-05).

Given a drug name, returns relevant pharmacogenes with the user's genotype
effect: star allele calls, metabolizer phenotype, call confidence state,
CPIC classification level, and prescribing recommendation.

GET  /api/analysis/pharma/drugs           — List all CPIC drugs
GET  /api/analysis/pharma/drug/{drug_name} — Drug detail with user genotype
"""

from __future__ import annotations

import json
import logging
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db.connection import get_registry
from backend.db.tables import cpic_guidelines, findings, samples

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis/pharma", tags=["pharmacogenomics"])


# ── Response models ──────────────────────────────────────────────────


class DrugListItem(BaseModel):
    """Summary of a drug in the CPIC database."""

    drug: str
    genes: list[str]
    classification: str | None = None  # best (min) CPIC level across genes


class DrugListResponse(BaseModel):
    """List of all CPIC drugs with associated genes."""

    items: list[DrugListItem]
    total: int


class GeneEffect(BaseModel):
    """Per-gene genotype effect for a specific drug."""

    gene: str
    diplotype: str | None = None
    metabolizer_status: str | None = None
    recommendation: str | None = None
    classification: str | None = None  # CPIC level: A, B, C, D
    guideline_url: str | None = None
    call_confidence: str | None = None  # Complete / Partial / Insufficient
    confidence_note: str | None = None
    evidence_level: int | None = None  # 1-4 stars
    activity_score: float | None = None
    ehr_notation: str | None = None
    involved_rsids: list[str] = []


class DrugLookupResponse(BaseModel):
    """Full drug detail with per-gene genotype effects for a sample."""

    drug: str
    gene_effects: list[GeneEffect]


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


def _fetch_drug_guidelines(drug_name: str) -> list[dict[str, Any]]:
    """Fetch all CPIC guideline rows for a drug (case-insensitive)."""
    registry = get_registry()
    with registry.reference_engine.connect() as conn:
        stmt = (
            sa.select(
                cpic_guidelines.c.gene,
                cpic_guidelines.c.drug,
                cpic_guidelines.c.phenotype,
                cpic_guidelines.c.recommendation,
                cpic_guidelines.c.classification,
                cpic_guidelines.c.guideline_url,
            )
            .where(sa.func.lower(cpic_guidelines.c.drug) == drug_name.lower())
            .order_by(cpic_guidelines.c.gene, cpic_guidelines.c.phenotype)
        )
        rows = conn.execute(stmt).fetchall()

    return [
        {
            "gene": row.gene,
            "drug": row.drug,
            "phenotype": row.phenotype,
            "recommendation": row.recommendation,
            "classification": row.classification,
            "guideline_url": row.guideline_url,
        }
        for row in rows
    ]


def _fetch_sample_findings(sample_engine: sa.Engine, drug_name: str) -> dict[str, dict[str, Any]]:
    """Fetch pharmacogenomics findings for a drug from the sample DB.

    Returns a dict keyed by gene_symbol with the finding data.
    """
    with sample_engine.connect() as conn:
        stmt = (
            sa.select(findings)
            .where(
                sa.and_(
                    findings.c.module == "pharmacogenomics",
                    findings.c.category == "prescribing_alert",
                    sa.func.lower(findings.c.drug) == drug_name.lower(),
                )
            )
            .order_by(findings.c.gene_symbol)
        )
        rows = conn.execute(stmt).fetchall()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        gene = row.gene_symbol
        detail: dict[str, Any] = {}
        if row.detail_json:
            try:
                detail = json.loads(row.detail_json)
            except (json.JSONDecodeError, TypeError):
                pass

        result[gene] = {
            "diplotype": row.diplotype,
            "metabolizer_status": row.metabolizer_status,
            "evidence_level": row.evidence_level,
            "recommendation": detail.get("recommendation"),
            "classification": detail.get("classification"),
            "guideline_url": detail.get("guideline_url"),
            "call_confidence": detail.get("call_confidence"),
            "confidence_note": detail.get("confidence_note"),
            "activity_score": detail.get("activity_score"),
            "ehr_notation": detail.get("ehr_notation"),
            "involved_rsids": detail.get("involved_rsids", []),
        }

    return result


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/drugs")
def list_drugs() -> DrugListResponse:
    """List all drugs with CPIC guidelines.

    Returns each drug with its associated genes and the best (lowest)
    CPIC classification level.

    Example: ``GET /api/analysis/pharma/drugs``
    """
    registry = get_registry()
    with registry.reference_engine.connect() as conn:
        stmt = (
            sa.select(
                cpic_guidelines.c.drug,
                cpic_guidelines.c.gene,
                cpic_guidelines.c.classification,
            )
            .group_by(cpic_guidelines.c.drug, cpic_guidelines.c.gene)
            .order_by(cpic_guidelines.c.drug, cpic_guidelines.c.gene)
        )
        rows = conn.execute(stmt).fetchall()

    # Group by drug
    drugs: dict[str, dict[str, Any]] = {}
    for row in rows:
        drug = row.drug
        if drug not in drugs:
            drugs[drug] = {"genes": [], "classification": row.classification}
        drugs[drug]["genes"].append(row.gene)
        # Track best (min) classification
        current = drugs[drug]["classification"]
        if row.classification and (current is None or row.classification < current):
            drugs[drug]["classification"] = row.classification

    items = [
        DrugListItem(
            drug=drug,
            genes=info["genes"],
            classification=info["classification"],
        )
        for drug, info in sorted(drugs.items())
    ]

    return DrugListResponse(items=items, total=len(items))


@router.get("/drug/{drug_name}")
def drug_lookup(
    drug_name: str,
    sample_id: int = Query(..., description="Sample ID"),
) -> DrugLookupResponse:
    """Look up a drug and return relevant pharmacogenes with user genotype effect.

    For each gene associated with the drug in CPIC guidelines, returns the
    user's star-allele diplotype, metabolizer phenotype, call confidence state,
    CPIC classification, and prescribing recommendation.

    The response combines CPIC reference data (guidelines) with per-sample
    findings (star-allele calls stored by the pharmacogenomics module).

    Example: ``GET /api/analysis/pharma/drug/clopidogrel?sample_id=1``
    """
    # 1. Look up drug in CPIC guidelines (reference.db)
    guidelines = _fetch_drug_guidelines(drug_name)
    if not guidelines:
        raise HTTPException(
            status_code=404,
            detail=f"No CPIC guidelines found for drug '{drug_name}'.",
        )

    # Canonical drug name from DB (preserves case)
    canonical_drug = guidelines[0]["drug"]

    # Collect unique genes for this drug
    gene_set: dict[str, dict[str, Any]] = {}
    for g in guidelines:
        gene = g["gene"]
        if gene not in gene_set:
            gene_set[gene] = {
                "classification": g["classification"],
                "guideline_url": g["guideline_url"],
            }

    # 2. Look up sample-specific findings
    sample_engine = _get_sample_engine(sample_id)
    sample_findings = _fetch_sample_findings(sample_engine, drug_name)

    # 3. Build per-gene effects
    gene_effects: list[GeneEffect] = []
    for gene in sorted(gene_set):
        finding = sample_findings.get(gene)

        if finding:
            # User has a finding for this gene-drug pair
            gene_effects.append(
                GeneEffect(
                    gene=gene,
                    diplotype=finding["diplotype"],
                    metabolizer_status=finding["metabolizer_status"],
                    recommendation=finding["recommendation"],
                    classification=finding["classification"],
                    guideline_url=finding["guideline_url"],
                    call_confidence=finding["call_confidence"],
                    confidence_note=finding["confidence_note"],
                    evidence_level=finding["evidence_level"],
                    activity_score=finding["activity_score"],
                    ehr_notation=finding["ehr_notation"],
                    involved_rsids=finding["involved_rsids"],
                )
            )
        else:
            # No sample finding — return gene info from guidelines only
            # This happens when the gene call was Insufficient or annotation
            # hasn't been run yet
            gene_info = gene_set[gene]

            # Try to find a matching guideline recommendation for this gene
            # using the default/normal phenotype
            gene_effects.append(
                GeneEffect(
                    gene=gene,
                    classification=gene_info["classification"],
                    guideline_url=gene_info["guideline_url"],
                )
            )

    return DrugLookupResponse(
        drug=canonical_drug,
        gene_effects=gene_effects,
    )
