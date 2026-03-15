"""Ancestry inference API endpoints.

Implements the API layer for P3-23 (ancestry PCA projection).
Provides endpoints to run ancestry inference and retrieve results.
"""

from __future__ import annotations

import json

import sqlalchemy as sa
import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db.connection import get_registry
from backend.db.tables import findings, samples

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/analysis/ancestry", tags=["ancestry"])


# ── Response models ───────────────────────────────────────────────────────


class PopulationDistance(BaseModel):
    """Distance to a reference population centroid."""

    population: str
    distance: float


class AncestryFindingResponse(BaseModel):
    """Ancestry inference result."""

    top_population: str
    pc_scores: list[float]
    population_distances: dict[str, float]
    population_ranking: list[PopulationDistance]
    snps_used: int
    snps_total: int
    coverage_fraction: float
    projection_time_ms: float
    is_sufficient: bool
    evidence_level: int
    finding_text: str


class AncestryRunResponse(BaseModel):
    """Response from running ancestry inference."""

    top_population: str
    snps_used: int
    snps_total: int
    coverage_fraction: float
    is_sufficient: bool


# ── Helpers ───────────────────────────────────────────────────────────────


def _get_sample_engine(sample_id: int) -> sa.Engine:
    """Get a sample database engine by sample ID."""
    registry = get_registry()
    with registry.reference_engine.connect() as conn:
        row = conn.execute(
            sa.select(samples.c.db_path).where(samples.c.id == sample_id)
        ).fetchone()
    if not row:
        raise HTTPException(404, detail=f"Sample {sample_id} not found")
    sample_db_path = registry.settings.data_dir / row.db_path
    return registry.get_sample_engine(sample_db_path)


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("/findings")
def get_ancestry_findings(
    sample_id: int = Query(..., description="Sample ID"),
) -> AncestryFindingResponse | None:
    """Get ancestry inference results for a sample.

    Returns the most recent PCA projection finding, or null if
    ancestry inference has not been run yet.
    """
    sample_engine = _get_sample_engine(sample_id)

    with sample_engine.connect() as conn:
        row = conn.execute(
            sa.select(findings)
            .where(
                findings.c.module == "ancestry",
                findings.c.category == "pca_projection",
            )
            .order_by(findings.c.id.desc())
            .limit(1)
        ).fetchone()

    if row is None:
        return None

    detail = json.loads(row.detail_json) if row.detail_json else {}

    return AncestryFindingResponse(
        top_population=detail.get("top_population", ""),
        pc_scores=detail.get("pc_scores", []),
        population_distances=detail.get("population_distances", {}),
        population_ranking=[PopulationDistance(**p) for p in detail.get("population_ranking", [])],
        snps_used=detail.get("snps_used", 0),
        snps_total=detail.get("snps_total", 0),
        coverage_fraction=detail.get("coverage_fraction", 0.0),
        projection_time_ms=detail.get("projection_time_ms", 0.0),
        is_sufficient=detail.get("is_sufficient", False),
        evidence_level=row.evidence_level or 2,
        finding_text=row.finding_text or "",
    )


@router.post("/run")
def run_ancestry(
    sample_id: int = Query(..., description="Sample ID"),
) -> AncestryRunResponse:
    """Run ancestry inference for a sample.

    Projects the sample's genotypes onto pre-computed PCA space
    and classifies ancestry by nearest centroid.
    """
    sample_engine = _get_sample_engine(sample_id)

    from backend.analysis.ancestry import run_ancestry_inference

    result = run_ancestry_inference(sample_engine)

    return AncestryRunResponse(
        top_population=result.top_population,
        snps_used=result.snps_used,
        snps_total=result.snps_total,
        coverage_fraction=result.coverage_fraction,
        is_sufficient=result.is_sufficient,
    )
