"""Rare variant finder API (P3-29).

Accept filter params, return matching variants, export as VCF/TSV.

POST /api/analysis/rare-variants/search?sample_id=N     — Search with filters
GET  /api/analysis/rare-variants/findings?sample_id=N    — Stored findings
GET  /api/analysis/rare-variants/export/tsv?sample_id=N  — Export as TSV
GET  /api/analysis/rare-variants/export/vcf?sample_id=N  — Export as VCF
"""

from __future__ import annotations

import io
import json
import logging
from datetime import date
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from backend.analysis.rare_variant_finder import (
    DEFAULT_AF_THRESHOLD,
    RareVariantFilter,
    find_rare_variants,
    store_rare_variant_findings,
)
from backend.db.connection import get_registry
from backend.db.tables import findings, samples

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis/rare-variants", tags=["rare-variants"])


# ── Request / response models ────────────────────────────────────────


class RareVariantFilterRequest(BaseModel):
    """Filter parameters accepted by the search endpoint."""

    gene_symbols: list[str] | None = Field(
        default=None, description="Gene symbols to filter by (custom gene panel)"
    )
    af_threshold: float = Field(
        default=DEFAULT_AF_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Maximum gnomAD global allele frequency (0–1)",
    )
    consequences: list[str] | None = Field(
        default=None, description="SO consequence terms to filter by"
    )
    clinvar_significance: list[str] | None = Field(
        default=None, description="ClinVar significance values to filter by"
    )
    include_novel: bool = Field(default=True, description="Include variants with no gnomAD data")
    zygosity: str | None = Field(
        default=None, description="Filter by zygosity: 'het' or 'hom_alt'"
    )


class RareVariantResponse(BaseModel):
    """A single rare variant in the response."""

    rsid: str
    chrom: str
    pos: int
    ref: str | None = None
    alt: str | None = None
    genotype: str | None = None
    zygosity: str | None = None
    gene_symbol: str | None = None
    consequence: str | None = None
    hgvs_coding: str | None = None
    hgvs_protein: str | None = None
    gnomad_af_global: float | None = None
    gnomad_af_afr: float | None = None
    gnomad_af_amr: float | None = None
    gnomad_af_eas: float | None = None
    gnomad_af_eur: float | None = None
    gnomad_af_fin: float | None = None
    gnomad_af_sas: float | None = None
    clinvar_significance: str | None = None
    clinvar_review_stars: int | None = None
    clinvar_accession: str | None = None
    clinvar_conditions: str | None = None
    cadd_phred: float | None = None
    revel: float | None = None
    ensemble_pathogenic: bool = False
    evidence_conflict: bool = False
    evidence_level: int = 1
    disease_name: str | None = None
    inheritance_pattern: str | None = None


class RareVariantSearchResponse(BaseModel):
    """Response from the search endpoint."""

    items: list[RareVariantResponse]
    total: int
    total_variants_scanned: int
    novel_count: int
    pathogenic_count: int
    genes_with_findings: list[str]
    filters_applied: RareVariantFilterRequest


class RareVariantFindingResponse(BaseModel):
    """A stored finding from the findings table."""

    rsid: str | None = None
    gene_symbol: str | None = None
    category: str
    evidence_level: int = 1
    finding_text: str
    zygosity: str | None = None
    clinvar_significance: str | None = None
    conditions: str | None = None
    detail: dict[str, Any] = {}


class RareVariantFindingsListResponse(BaseModel):
    """All stored rare variant findings for a sample."""

    items: list[RareVariantFindingResponse]
    total: int


class RareVariantRunResponse(BaseModel):
    """Result of running the rare variant finder."""

    variants_found: int
    findings_stored: int
    total_variants_scanned: int
    novel_count: int
    pathogenic_count: int
    genes_with_findings: list[str]


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


def _request_to_filter(req: RareVariantFilterRequest) -> RareVariantFilter:
    """Convert a Pydantic request model to the dataclass filter."""
    return RareVariantFilter(
        gene_symbols=req.gene_symbols,
        af_threshold=req.af_threshold,
        consequences=req.consequences,
        clinvar_significance=req.clinvar_significance,
        include_novel=req.include_novel,
        zygosity=req.zygosity,
    )


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/search")
def search_rare_variants(
    body: RareVariantFilterRequest,
    sample_id: int = Query(..., description="Sample ID"),
) -> RareVariantSearchResponse:
    """Search for rare variants with the given filter parameters.

    Accepts filter criteria (gene panel, AF threshold, consequence types,
    ClinVar significance) and returns matching variants sorted by clinical
    relevance.  Also stores findings in the sample database.

    Example: ``POST /api/analysis/rare-variants/search?sample_id=1``
    """
    sample_engine = _get_sample_engine(sample_id)
    filters = _request_to_filter(body)
    result = find_rare_variants(filters, sample_engine)
    store_rare_variant_findings(result, sample_engine)

    items = [
        RareVariantResponse(
            rsid=v.rsid,
            chrom=v.chrom,
            pos=v.pos,
            ref=v.ref,
            alt=v.alt,
            genotype=v.genotype,
            zygosity=v.zygosity,
            gene_symbol=v.gene_symbol,
            consequence=v.consequence,
            hgvs_coding=v.hgvs_coding,
            hgvs_protein=v.hgvs_protein,
            gnomad_af_global=v.gnomad_af_global,
            gnomad_af_afr=v.gnomad_af_afr,
            gnomad_af_amr=v.gnomad_af_amr,
            gnomad_af_eas=v.gnomad_af_eas,
            gnomad_af_eur=v.gnomad_af_eur,
            gnomad_af_fin=v.gnomad_af_fin,
            gnomad_af_sas=v.gnomad_af_sas,
            clinvar_significance=v.clinvar_significance,
            clinvar_review_stars=v.clinvar_review_stars,
            clinvar_accession=v.clinvar_accession,
            clinvar_conditions=v.clinvar_conditions,
            cadd_phred=v.cadd_phred,
            revel=v.revel,
            ensemble_pathogenic=v.ensemble_pathogenic,
            evidence_conflict=v.evidence_conflict,
            evidence_level=v.evidence_level,
            disease_name=v.disease_name,
            inheritance_pattern=v.inheritance_pattern,
        )
        for v in result.variants
    ]

    return RareVariantSearchResponse(
        items=items,
        total=result.count,
        total_variants_scanned=result.total_variants_scanned,
        novel_count=result.novel_count,
        pathogenic_count=result.pathogenic_count,
        genes_with_findings=result.genes_with_findings,
        filters_applied=body,
    )


@router.get("/findings")
def list_rare_variant_findings(
    sample_id: int = Query(..., description="Sample ID"),
) -> RareVariantFindingsListResponse:
    """List stored rare variant findings for a sample.

    Returns findings previously generated by the search endpoint,
    sorted by evidence level (highest first).

    Example: ``GET /api/analysis/rare-variants/findings?sample_id=1``
    """
    sample_engine = _get_sample_engine(sample_id)

    with sample_engine.connect() as conn:
        rows = conn.execute(
            sa.select(findings)
            .where(findings.c.module == "rare_variants")
            .order_by(findings.c.evidence_level.desc(), findings.c.gene_symbol)
        ).fetchall()

    items: list[RareVariantFindingResponse] = []
    for row in rows:
        detail: dict[str, Any] = {}
        if row.detail_json:
            try:
                detail = json.loads(row.detail_json)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse detail_json for finding id=%s", row.id)

        items.append(
            RareVariantFindingResponse(
                rsid=row.rsid,
                gene_symbol=row.gene_symbol,
                category=row.category,
                evidence_level=row.evidence_level or 1,
                finding_text=row.finding_text or "",
                zygosity=row.zygosity,
                clinvar_significance=row.clinvar_significance,
                conditions=row.conditions,
                detail=detail,
            )
        )

    return RareVariantFindingsListResponse(items=items, total=len(items))


@router.post("/run")
def run_rare_variant_finder(
    sample_id: int = Query(..., description="Sample ID"),
    body: RareVariantFilterRequest | None = None,
) -> RareVariantRunResponse:
    """Run the rare variant finder with optional filters.

    If no body is provided, uses default filters (AF < 1%, include novel).

    Example: ``POST /api/analysis/rare-variants/run?sample_id=1``
    """
    sample_engine = _get_sample_engine(sample_id)
    filters = _request_to_filter(body) if body else RareVariantFilter()
    result = find_rare_variants(filters, sample_engine)
    stored = store_rare_variant_findings(result, sample_engine)

    return RareVariantRunResponse(
        variants_found=result.count,
        findings_stored=stored,
        total_variants_scanned=result.total_variants_scanned,
        novel_count=result.novel_count,
        pathogenic_count=result.pathogenic_count,
        genes_with_findings=result.genes_with_findings,
    )


@router.get("/export/tsv")
def export_rare_variants_tsv(
    sample_id: int = Query(..., description="Sample ID"),
) -> StreamingResponse:
    """Export stored rare variant findings as a TSV file.

    Returns a downloadable tab-separated values file containing all
    rare variant findings for the given sample.

    Example: ``GET /api/analysis/rare-variants/export/tsv?sample_id=1``
    """
    sample_engine = _get_sample_engine(sample_id)

    with sample_engine.connect() as conn:
        rows = conn.execute(
            sa.select(findings)
            .where(findings.c.module == "rare_variants")
            .order_by(findings.c.evidence_level.desc(), findings.c.gene_symbol)
        ).fetchall()

    buf = io.StringIO()
    # Header
    tsv_columns = [
        "rsid",
        "gene_symbol",
        "category",
        "evidence_level",
        "zygosity",
        "clinvar_significance",
        "conditions",
        "consequence",
        "gnomad_af_global",
        "cadd_phred",
        "revel",
        "finding_text",
    ]
    buf.write("\t".join(tsv_columns) + "\n")

    for row in rows:
        detail: dict[str, Any] = {}
        if row.detail_json:
            try:
                detail = json.loads(row.detail_json)
            except (json.JSONDecodeError, TypeError):
                pass

        values = [
            row.rsid or "",
            row.gene_symbol or "",
            row.category or "",
            str(row.evidence_level or 1),
            row.zygosity or "",
            row.clinvar_significance or "",
            row.conditions or "",
            detail.get("consequence", ""),
            str(detail.get("af_global", "")) if detail.get("af_global") is not None else "",
            str(detail.get("cadd_phred", "")) if detail.get("cadd_phred") is not None else "",
            str(detail.get("revel", "")) if detail.get("revel") is not None else "",
            row.finding_text or "",
        ]
        buf.write("\t".join(values) + "\n")

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/tab-separated-values",
        headers={
            "Content-Disposition": f"attachment; filename=rare_variants_sample_{sample_id}.tsv"
        },
    )


@router.get("/export/vcf")
def export_rare_variants_vcf(
    sample_id: int = Query(..., description="Sample ID"),
) -> StreamingResponse:
    """Export stored rare variant findings as a minimal VCF 4.2 file.

    Returns a downloadable VCF file containing rare variant findings
    with basic annotation in the INFO field.

    Example: ``GET /api/analysis/rare-variants/export/vcf?sample_id=1``
    """
    sample_engine = _get_sample_engine(sample_id)

    with sample_engine.connect() as conn:
        rows = conn.execute(
            sa.select(findings)
            .where(findings.c.module == "rare_variants")
            .order_by(findings.c.gene_symbol, findings.c.rsid)
        ).fetchall()

    buf = io.StringIO()

    # VCF header
    today = date.today().isoformat()
    buf.write("##fileformat=VCFv4.2\n")
    buf.write(f"##fileDate={today}\n")
    buf.write("##source=GenomeInsight-RareVariantFinder\n")
    buf.write("##reference=GRCh37\n")
    buf.write('##INFO=<ID=GENE,Number=1,Type=String,Description="Gene symbol">\n')
    buf.write('##INFO=<ID=CSQ,Number=1,Type=String,Description="Consequence type">\n')
    buf.write('##INFO=<ID=CLNSIG,Number=1,Type=String,Description="ClinVar significance">\n')
    buf.write('##INFO=<ID=AF,Number=1,Type=Float,Description="gnomAD global allele frequency">\n')
    buf.write('##INFO=<ID=EVLVL,Number=1,Type=Integer,Description="Evidence level (1-4 stars)">\n')
    buf.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")

    for row in rows:
        detail: dict[str, Any] = {}
        if row.detail_json:
            try:
                detail = json.loads(row.detail_json)
            except (json.JSONDecodeError, TypeError):
                pass

        rsid = row.rsid or "."
        gene = row.gene_symbol or "."
        csq = detail.get("consequence", ".")
        clnsig = (row.clinvar_significance or ".").replace(" ", "_")
        af_val = detail.get("af_global")
        af_str = f"{af_val:.6f}" if af_val is not None else "."
        evlvl = str(row.evidence_level or 1)

        # Findings don't store chrom/pos directly, so parse from rsid context
        # We use "." placeholders since findings table doesn't have chrom/pos
        chrom = "."
        pos = "0"

        info_parts = [
            f"GENE={gene}",
            f"CSQ={csq}",
            f"CLNSIG={clnsig}",
            f"AF={af_str}",
            f"EVLVL={evlvl}",
        ]
        info_str = ";".join(info_parts)

        buf.write(f"{chrom}\t{pos}\t{rsid}\t.\t.\t.\tPASS\t{info_str}\n")

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=rare_variants_sample_{sample_id}.vcf"
        },
    )
