"""Query builder API endpoints (P4-01).

POST /api/query — Execute a react-querybuilder RuleGroupType filter tree
against the per-sample annotated_variants table.  The filter JSON is
translated server-side to SQLAlchemy Core expressions via the recursive
translator — values are always bound parameters, never interpolated.
"""

from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.db.connection import get_registry
from backend.db.tables import annotated_variants, samples
from backend.query.translator import (
    SUPPORTED_OPERATORS,
    TranslationError,
    translate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query-builder"])

# Canonical chromosome sort order (same as variants.py).
_CHROM_ORDER: dict[str, int] = {
    **{str(i): i for i in range(1, 23)},
    "X": 23,
    "Y": 24,
    "MT": 25,
}


# ── Request / Response models ────────────────────────────────────────


class RuleModel(BaseModel):
    """Single rule from react-querybuilder."""

    field: str
    operator: str
    value: Any = None
    disabled: bool | None = None


class RuleGroupModel(BaseModel):
    """Recursive rule group from react-querybuilder (RuleGroupType)."""

    combinator: str = "and"
    rules: list[RuleGroupModel | RuleModel | dict] = Field(default_factory=list)
    not_: bool | None = Field(default=None, alias="not")

    model_config = {"populate_by_name": True}


class QueryRequest(BaseModel):
    """POST /api/query request body."""

    sample_id: int
    filter: RuleGroupModel
    cursor_chrom: str | None = None
    cursor_pos: int | None = None
    limit: int = Field(default=50, ge=1, le=500)


class QueryVariantRow(BaseModel):
    """Single variant row in query results."""

    rsid: str
    chrom: str
    pos: int
    genotype: str | None = None
    ref: str | None = None
    alt: str | None = None
    zygosity: str | None = None
    gene_symbol: str | None = None
    transcript_id: str | None = None
    consequence: str | None = None
    hgvs_coding: str | None = None
    hgvs_protein: str | None = None
    clinvar_significance: str | None = None
    clinvar_review_stars: int | None = None
    clinvar_accession: str | None = None
    clinvar_conditions: str | None = None
    gnomad_af_global: float | None = None
    gnomad_af_afr: float | None = None
    gnomad_af_amr: float | None = None
    gnomad_af_eas: float | None = None
    gnomad_af_eur: float | None = None
    gnomad_af_fin: float | None = None
    gnomad_af_sas: float | None = None
    rare_flag: bool | None = None
    ultra_rare_flag: bool | None = None
    cadd_phred: float | None = None
    sift_score: float | None = None
    sift_pred: str | None = None
    polyphen2_hsvar_score: float | None = None
    polyphen2_hsvar_pred: str | None = None
    revel: float | None = None
    annotation_coverage: int | None = None
    evidence_conflict: bool | None = None
    ensemble_pathogenic: bool | None = None
    disease_name: str | None = None
    inheritance_pattern: str | None = None


class QueryResultPage(BaseModel):
    """Paginated query result."""

    items: list[QueryVariantRow]
    total_matching: int | None = None
    next_cursor_chrom: str | None = None
    next_cursor_pos: int | None = None
    has_more: bool = False
    limit: int


class QueryFieldInfo(BaseModel):
    """Metadata about an allowed query field."""

    name: str
    type: str
    label: str


class QueryMetaResponse(BaseModel):
    """Response for GET /api/query/fields — field definitions for the UI."""

    fields: list[QueryFieldInfo]
    operators: list[str]


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


def _has_annotated_variants(engine: sa.Engine) -> bool:
    """Check if annotated_variants table has data."""
    with engine.connect() as conn:
        row = conn.execute(
            sa.select(sa.literal(1)).select_from(annotated_variants).limit(1)
        ).fetchone()
    return row is not None


def _chrom_order_expr() -> sa.Case:
    """CASE expression for canonical chromosome ordering."""
    return sa.case(
        *[(annotated_variants.c.chrom == k, v) for k, v in _CHROM_ORDER.items()],
        else_=99,
    )


def _build_cursor_clause(
    cursor_chrom: str | None,
    cursor_pos: int | None,
) -> sa.ColumnElement | None:
    """Build keyset cursor pagination WHERE clause."""
    if cursor_chrom is None or cursor_pos is None:
        return None

    cursor_order = _CHROM_ORDER.get(cursor_chrom, 99)
    expr = _chrom_order_expr()

    return sa.or_(
        expr > cursor_order,
        sa.and_(expr == cursor_order, annotated_variants.c.pos > cursor_pos),
    )


def _row_to_dict(row: sa.Row) -> dict[str, Any]:
    """Convert a Row to a dict with all annotated_variants columns."""
    return {col.name: getattr(row, col.name, None) for col in annotated_variants.columns}


def _field_type_label(col: sa.Column) -> tuple[str, str]:
    """Return (type_string, human_label) for a column."""
    name = col.name
    # Determine type string
    if isinstance(col.type, sa.Boolean):
        type_str = "boolean"
    elif isinstance(col.type, sa.Integer):
        type_str = "integer"
    elif isinstance(col.type, sa.Float):
        type_str = "number"
    else:
        type_str = "text"

    # Human-readable label from column name
    label = name.replace("_", " ").title()
    return type_str, label


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/fields")
def query_fields() -> QueryMetaResponse:
    """Return metadata about queryable fields and supported operators.

    Used by the frontend react-querybuilder to populate field dropdowns
    and operator selectors.
    """
    fields = []
    for col in annotated_variants.columns:
        type_str, label = _field_type_label(col)
        fields.append(QueryFieldInfo(name=col.name, type=type_str, label=label))

    return QueryMetaResponse(
        fields=fields,
        operators=sorted(SUPPORTED_OPERATORS),
    )


@router.post("")
def execute_query(body: QueryRequest) -> QueryResultPage:
    """Execute a RuleGroupType filter tree against annotated_variants.

    The filter JSON is recursively translated to SQLAlchemy Core
    ``and_()/or_()`` expressions with bound parameters.  Values are
    **never** string-interpolated — SQL injection is structurally
    impossible.

    Supports cursor-based keyset pagination on (chrom, pos).
    """
    sample_engine = _get_sample_engine(body.sample_id)

    if not _has_annotated_variants(sample_engine):
        raise HTTPException(
            status_code=422,
            detail="Sample has no annotated variants. Run annotation first.",
        )

    # ── Translate the filter tree ─────────────────────────────────
    try:
        filter_tree = body.filter.model_dump(by_alias=True)
        where_clause = translate(filter_tree)
    except TranslationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # ── Build query ───────────────────────────────────────────────
    query = sa.select(annotated_variants).where(where_clause)

    # Apply cursor pagination
    cursor_clause = _build_cursor_clause(body.cursor_chrom, body.cursor_pos)
    if cursor_clause is not None:
        query = query.where(cursor_clause)

    # Order by canonical chrom, then pos
    chrom_expr = _chrom_order_expr()
    query = query.order_by(chrom_expr.asc(), annotated_variants.c.pos.asc())
    query = query.limit(body.limit + 1)

    with sample_engine.connect() as conn:
        rows = conn.execute(query).fetchall()

    has_more = len(rows) > body.limit
    result_rows = rows[: body.limit]

    items = [QueryVariantRow(**_row_to_dict(row)) for row in result_rows]

    next_chrom: str | None = None
    next_pos: int | None = None
    if has_more and result_rows:
        last = result_rows[-1]
        next_chrom = last.chrom
        next_pos = last.pos

    # ── Count total matching (first page only for performance) ────
    total: int | None = None
    if body.cursor_chrom is None and body.cursor_pos is None:
        count_query = (
            sa.select(sa.func.count()).select_from(annotated_variants).where(where_clause)
        )
        with sample_engine.connect() as conn:
            total = conn.execute(count_query).scalar() or 0

    return QueryResultPage(
        items=items,
        total_matching=total,
        next_cursor_chrom=next_chrom,
        next_cursor_pos=next_pos,
        has_more=has_more,
        limit=body.limit,
    )
