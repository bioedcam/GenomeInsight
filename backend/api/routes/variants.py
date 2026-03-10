"""Variant table API endpoints (P1-14).

Cursor-based keyset pagination on (chrom, pos) for raw_variants and
annotated_variants tables in per-sample databases.

GET  /api/variants          — Paginated variant list
GET  /api/variants/count    — Total count (async, separate query)
"""

from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db.connection import get_registry
from backend.db.tables import annotated_variants, raw_variants, samples

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/variants", tags=["variants"])

# Canonical chromosome sort order — same as VCF export.
CHROM_ORDER: dict[str, int] = {
    **{str(i): i for i in range(1, 23)},
    "X": 23,
    "Y": 24,
    "MT": 25,
}

# Columns allowed as filter keys on raw_variants.
_RAW_FILTER_COLS = frozenset({"chrom", "genotype"})

# Columns allowed as filter keys on annotated_variants.
_ANNOTATED_FILTER_COLS = frozenset({
    "chrom",
    "genotype",
    "gene_symbol",
    "consequence",
    "clinvar_significance",
    "rare_flag",
    "ultra_rare_flag",
    "evidence_conflict",
    "ensemble_pathogenic",
    "zygosity",
})


# ── Response models ──────────────────────────────────────────────────


class VariantRow(BaseModel):
    """Single variant row returned by the paginated endpoint."""

    rsid: str
    chrom: str
    pos: int
    genotype: str
    # Annotation fields (None when reading from raw_variants)
    ref: str | None = None
    alt: str | None = None
    zygosity: str | None = None
    gene_symbol: str | None = None
    consequence: str | None = None
    clinvar_significance: str | None = None
    clinvar_review_stars: int | None = None
    gnomad_af_global: float | None = None
    rare_flag: bool | None = None
    cadd_phred: float | None = None
    sift_score: float | None = None
    sift_pred: str | None = None
    polyphen2_hsvar_score: float | None = None
    polyphen2_hsvar_pred: str | None = None
    revel: float | None = None
    annotation_coverage: int | None = None
    evidence_conflict: bool | None = None
    ensemble_pathogenic: bool | None = None


class VariantPage(BaseModel):
    """Paginated response for variant listing."""

    items: list[VariantRow]
    next_cursor_chrom: str | None = None
    next_cursor_pos: int | None = None
    has_more: bool = False
    limit: int


class VariantCount(BaseModel):
    """Response for the async total count endpoint."""

    total: int
    filtered: bool = False


class ChromosomeSummary(BaseModel):
    """Per-chromosome variant count for the chromosome nav bar."""

    chrom: str
    count: int


# ── Helpers ──────────────────────────────────────────────────────────


def _get_sample_engine(sample_id: int) -> sa.Engine:
    """Resolve sample_id to a per-sample DB engine.

    Raises HTTPException(404) if the sample doesn't exist.
    """
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


def _chrom_sort_key(chrom: str) -> int:
    """Return an integer sort key for a chromosome string."""
    return CHROM_ORDER.get(chrom, 99)


def _select_table(sample_engine: sa.Engine) -> sa.Table:
    """Choose annotated_variants if populated, else raw_variants."""
    with sample_engine.connect() as conn:
        has_rows = conn.execute(
            sa.select(sa.literal(1)).select_from(annotated_variants).limit(1)
        ).fetchone()
    if has_rows is not None:
        return annotated_variants
    return raw_variants


def _parse_filters(
    filter_str: str | None, table: sa.Table
) -> list[sa.ColumnElement]:
    """Parse filter query param into SQLAlchemy WHERE clauses.

    Filter format: ``key:value`` pairs separated by commas.
    Example: ``chrom:1,gene_symbol:BRCA1,rare_flag:1``

    Returns a list of SQLAlchemy column conditions.
    """
    if not filter_str:
        return []

    allowed_cols = (
        _ANNOTATED_FILTER_COLS if table is annotated_variants else _RAW_FILTER_COLS
    )

    clauses: list[sa.ColumnElement] = []
    for part in filter_str.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            continue
        key, _, value = part.partition(":")
        key = key.strip()
        value = value.strip()

        if key not in allowed_cols:
            continue
        if not hasattr(table.c, key):
            continue

        col = getattr(table.c, key)
        # Boolean columns: accept 0/1/true/false
        if key in ("rare_flag", "ultra_rare_flag", "evidence_conflict", "ensemble_pathogenic"):
            bool_val = value.lower() in ("1", "true", "yes")
            clauses.append(col == bool_val)
        else:
            clauses.append(col == value)

    return clauses


def _chrom_order_expr(table: sa.Table) -> sa.Case:
    """Build CASE expression mapping chrom text to canonical sort integer."""
    return sa.case(
        *[(table.c.chrom == k, v) for k, v in CHROM_ORDER.items()],
        else_=99,
    )


def _build_cursor_clause(
    table: sa.Table,
    cursor_chrom: str | None,
    cursor_pos: int | None,
) -> sa.ColumnElement | None:
    """Build the WHERE clause for keyset cursor pagination.

    The cursor is on (chrom_sort_order, pos). Since SQLite doesn't have a
    native array comparison, we use the standard two-part OR:

        (chrom_order > cursor_chrom_order)
        OR (chrom_order = cursor_chrom_order AND pos > cursor_pos)

    Because chrom is stored as text (e.g. "1", "X"), we compare using
    CHROM_ORDER integer mapping via a CASE expression.
    """
    if cursor_chrom is None or cursor_pos is None:
        return None

    cursor_order = _chrom_sort_key(cursor_chrom)
    expr = _chrom_order_expr(table)

    return sa.or_(
        expr > cursor_order,
        sa.and_(expr == cursor_order, table.c.pos > cursor_pos),
    )


def _build_order_by(table: sa.Table) -> list:
    """Build ORDER BY clause: chrom (canonical order), then pos."""
    return [_chrom_order_expr(table).asc(), table.c.pos.asc()]


def _row_to_variant(row: sa.Row, table: sa.Table) -> VariantRow:
    """Convert a SQLAlchemy Row to a VariantRow response model."""
    data: dict[str, Any] = {
        "rsid": row.rsid,
        "chrom": row.chrom,
        "pos": row.pos,
        "genotype": row.genotype,
    }

    if table is annotated_variants:
        for field in (
            "ref", "alt", "zygosity", "gene_symbol", "consequence",
            "clinvar_significance", "clinvar_review_stars", "gnomad_af_global",
            "rare_flag", "cadd_phred", "sift_score", "sift_pred",
            "polyphen2_hsvar_score", "polyphen2_hsvar_pred", "revel",
            "annotation_coverage", "evidence_conflict", "ensemble_pathogenic",
        ):
            data[field] = getattr(row, field, None)

    return VariantRow(**data)


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("")
def list_variants(
    sample_id: int = Query(..., description="Sample ID to query variants for"),
    cursor_chrom: str | None = Query(None, description="Cursor chromosome"),
    cursor_pos: int | None = Query(None, description="Cursor position"),
    limit: int = Query(50, ge=1, le=500, description="Page size"),
    filter: str | None = Query(None, description="Filters as key:value,key:value"),
) -> VariantPage:
    """Return a page of variants using cursor-based keyset pagination.

    Pagination is on ``(chrom, pos)`` using canonical chromosome order
    (1-22, X, Y, MT). Performance is O(1) at any depth - no OFFSET.
    """
    sample_engine = _get_sample_engine(sample_id)
    table = _select_table(sample_engine)

    # Build query
    query = sa.select(table)

    # Apply filters
    filter_clauses = _parse_filters(filter, table)
    if filter_clauses:
        query = query.where(sa.and_(*filter_clauses))

    # Apply cursor
    cursor_clause = _build_cursor_clause(table, cursor_chrom, cursor_pos)
    if cursor_clause is not None:
        query = query.where(cursor_clause)

    # Order + limit (fetch limit+1 to detect has_more)
    query = query.order_by(*_build_order_by(table)).limit(limit + 1)

    with sample_engine.connect() as conn:
        rows = conn.execute(query).fetchall()

    has_more = len(rows) > limit
    result_rows = rows[:limit]

    items = [_row_to_variant(row, table) for row in result_rows]

    next_chrom: str | None = None
    next_pos: int | None = None
    if has_more and result_rows:
        last = result_rows[-1]
        next_chrom = last.chrom
        next_pos = last.pos

    return VariantPage(
        items=items,
        next_cursor_chrom=next_chrom,
        next_cursor_pos=next_pos,
        has_more=has_more,
        limit=limit,
    )


@router.get("/count")
def variant_count(
    sample_id: int = Query(..., description="Sample ID to count variants for"),
    filter: str | None = Query(None, description="Filters as key:value,key:value"),
) -> VariantCount:
    """Return the total variant count, optionally filtered.

    This endpoint is designed to be called asynchronously after the first
    page of variants has loaded, so the UI can show the count separately.
    """
    sample_engine = _get_sample_engine(sample_id)
    table = _select_table(sample_engine)

    query = sa.select(sa.func.count()).select_from(table)

    filter_clauses = _parse_filters(filter, table)
    if filter_clauses:
        query = query.where(sa.and_(*filter_clauses))

    with sample_engine.connect() as conn:
        total = conn.execute(query).scalar() or 0

    return VariantCount(total=total, filtered=bool(filter_clauses))


@router.get("/chromosomes")
def chromosome_counts(
    sample_id: int = Query(..., description="Sample ID to get chromosome counts for"),
    filter: str | None = Query(None, description="Filters as key:value,key:value"),
) -> list[ChromosomeSummary]:
    """Return per-chromosome variant counts in canonical order.

    Used by the chromosome navigation bar to show which chromosomes have
    data and their relative sizes.
    """
    sample_engine = _get_sample_engine(sample_id)
    table = _select_table(sample_engine)

    query = (
        sa.select(table.c.chrom, sa.func.count().label("count"))
        .select_from(table)
        .group_by(table.c.chrom)
    )

    filter_clauses = _parse_filters(filter, table)
    if filter_clauses:
        query = query.where(sa.and_(*filter_clauses))

    with sample_engine.connect() as conn:
        rows = conn.execute(query).fetchall()

    # Sort by canonical chromosome order and return
    summaries = [
        ChromosomeSummary(chrom=row.chrom, count=row.count)
        for row in rows
    ]
    summaries.sort(key=lambda s: _chrom_sort_key(s.chrom))
    return summaries
