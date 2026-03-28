"""VUS watched-variants API endpoints (P4-21h).

Watch/unwatch variants to track ClinVar reclassification events.

POST   /api/watches          — Watch a variant (snapshot current ClinVar significance)
DELETE /api/watches/{rsid}   — Unwatch a variant
GET    /api/watches          — List all watched variants for a sample
PATCH  /api/watches/{rsid}   — Update notes on a watched variant
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db.connection import get_registry
from backend.db.tables import annotated_variants, samples, watched_variants

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/watches", tags=["watches"])


# ── Response / Request models ─────────────────────────────────────


class WatchCreate(BaseModel):
    """Request body for watching a variant."""

    sample_id: int
    rsid: str
    notes: str = ""


class WatchNotesUpdate(BaseModel):
    """Request body for updating notes on a watched variant."""

    sample_id: int
    notes: str


class WatchResponse(BaseModel):
    """Single watched variant returned by the API."""

    rsid: str
    watched_at: str
    clinvar_significance_at_watch: str | None = None
    notes: str | None = None


# ── Helpers ───────────────────────────────────────────────────────


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


def _get_clinvar_significance(engine: sa.Engine, rsid: str) -> str | None:
    """Look up current ClinVar significance for a variant in the sample DB."""
    with engine.connect() as conn:
        row = conn.execute(
            sa.select(annotated_variants.c.clinvar_significance).where(
                annotated_variants.c.rsid == rsid
            )
        ).fetchone()
    return row.clinvar_significance if row is not None else None


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("")
def list_watched(
    sample_id: int = Query(..., description="Sample ID"),
) -> list[WatchResponse]:
    """List all watched variants for a sample."""
    engine = _get_sample_engine(sample_id)

    query = sa.select(
        watched_variants.c.rsid,
        watched_variants.c.watched_at,
        watched_variants.c.clinvar_significance_at_watch,
        watched_variants.c.notes,
    ).order_by(watched_variants.c.watched_at.desc())

    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()

    return [
        WatchResponse(
            rsid=row.rsid,
            watched_at=str(row.watched_at) if row.watched_at else "",
            clinvar_significance_at_watch=row.clinvar_significance_at_watch,
            notes=row.notes,
        )
        for row in rows
    ]


@router.post("", status_code=201)
def watch_variant(body: WatchCreate) -> WatchResponse:
    """Watch a variant, snapshotting its current ClinVar significance."""
    engine = _get_sample_engine(body.sample_id)

    # Snapshot the current ClinVar significance from annotated_variants
    clinvar_sig = _get_clinvar_significance(engine, body.rsid)

    now = datetime.now(UTC)

    with engine.begin() as conn:
        # Check if already watched
        existing = conn.execute(
            sa.select(watched_variants.c.rsid).where(watched_variants.c.rsid == body.rsid)
        ).fetchone()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Variant {body.rsid} is already being watched.",
            )

        conn.execute(
            watched_variants.insert().values(
                rsid=body.rsid,
                watched_at=now,
                clinvar_significance_at_watch=clinvar_sig,
                notes=body.notes,
            )
        )

    return WatchResponse(
        rsid=body.rsid,
        watched_at=str(now),
        clinvar_significance_at_watch=clinvar_sig,
        notes=body.notes,
    )


@router.delete("/{rsid}", status_code=204)
def unwatch_variant(
    rsid: str,
    sample_id: int = Query(..., description="Sample ID"),
) -> None:
    """Remove a variant from the watch list."""
    engine = _get_sample_engine(sample_id)

    with engine.begin() as conn:
        row = conn.execute(
            sa.select(watched_variants.c.rsid).where(watched_variants.c.rsid == rsid)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Variant {rsid} is not being watched.",
            )

        conn.execute(watched_variants.delete().where(watched_variants.c.rsid == rsid))


@router.patch("/{rsid}")
def update_watch_notes(rsid: str, body: WatchNotesUpdate) -> WatchResponse:
    """Update notes on a watched variant."""
    engine = _get_sample_engine(body.sample_id)

    with engine.begin() as conn:
        row = conn.execute(
            sa.select(watched_variants).where(watched_variants.c.rsid == rsid)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Variant {rsid} is not being watched.",
            )

        conn.execute(
            watched_variants.update()
            .where(watched_variants.c.rsid == rsid)
            .values(notes=body.notes)
        )

        updated = conn.execute(
            sa.select(watched_variants).where(watched_variants.c.rsid == rsid)
        ).fetchone()

    return WatchResponse(
        rsid=updated.rsid,
        watched_at=str(updated.watched_at) if updated.watched_at else "",
        clinvar_significance_at_watch=updated.clinvar_significance_at_watch,
        notes=updated.notes,
    )
