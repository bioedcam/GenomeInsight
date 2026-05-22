"""Sample management API endpoints (P1-13, P4-21f).

- ``GET    /api/samples`` — list all samples.
- ``GET    /api/samples/{sample_id}`` — single sample + full metadata.
- ``GET    /api/samples/{sample_id}/merged-children`` — merged samples
  referencing this row (Step 66 / Plan §10.8).
- ``PATCH  /api/samples/{sample_id}`` — update sample metadata.
- ``DELETE /api/samples/{sample_id}`` — delete + cascade to merged children
  (Step 66 / Plan §10.8).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from backend.db.connection import get_registry
from backend.db.tables import sample_metadata_table, samples
from backend.services.sample_delete import (
    delete_sample_with_cascade,
    list_merged_children,
)

router = APIRouter(prefix="/samples", tags=["samples"])


class SampleResponse(BaseModel):
    id: int
    name: str
    db_path: str
    file_format: str | None = None
    file_hash: str | None = None
    notes: str | None = None
    date_collected: str | None = None
    source: str | None = None
    extra: dict | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SampleUpdate(BaseModel):
    name: str | None = None
    notes: str | None = None
    date_collected: str | None = None
    source: str | None = None
    extra: dict | None = None

    @field_validator("extra", mode="before")
    @classmethod
    def validate_extra(cls, v: object) -> object:
        if v is None:
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
            except (json.JSONDecodeError, TypeError) as exc:
                raise ValueError("extra must be valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError("extra must be a JSON object")
            return parsed
        if not isinstance(v, dict):
            raise ValueError("extra must be a JSON object")
        return v


def _row_to_response(row: sa.Row) -> SampleResponse:
    """Convert a SQLAlchemy Row from reference.db to a SampleResponse."""
    return SampleResponse(
        id=row.id,
        name=row.name,
        db_path=row.db_path,
        file_format=row.file_format,
        file_hash=row.file_hash,
        created_at=str(row.created_at) if row.created_at else None,
        updated_at=str(row.updated_at) if row.updated_at else None,
    )


def _enrich_with_sample_metadata(response: SampleResponse, registry: object) -> SampleResponse:
    """Read per-sample DB metadata and merge into the response."""
    settings = registry.settings  # type: ignore[attr-defined]
    sample_db_path = settings.data_dir / response.db_path
    if not sample_db_path.exists():
        return response

    sample_engine = registry.get_sample_engine(sample_db_path)  # type: ignore[attr-defined]
    with sample_engine.connect() as conn:
        meta_row = conn.execute(
            sa.select(sample_metadata_table).where(sample_metadata_table.c.id == 1)
        ).fetchone()

    if meta_row is None:
        return response

    # Parse extra JSON
    extra_raw = meta_row.extra
    extra: dict = {}
    if extra_raw:
        try:
            extra = json.loads(extra_raw) if isinstance(extra_raw, str) else extra_raw
        except (json.JSONDecodeError, TypeError):
            extra = {}

    return response.model_copy(
        update={
            "notes": meta_row.notes if meta_row.notes else None,
            "date_collected": str(meta_row.date_collected) if meta_row.date_collected else None,
            "source": meta_row.source if meta_row.source else None,
            "extra": extra,
        }
    )


@router.get("")
async def list_samples() -> list[SampleResponse]:
    """List all registered samples."""
    registry = get_registry()
    with registry.reference_engine.connect() as conn:
        rows = conn.execute(sa.select(samples).order_by(samples.c.created_at.desc())).fetchall()
    return [_row_to_response(row) for row in rows]


@router.get("/{sample_id}")
async def get_sample(sample_id: int) -> SampleResponse:
    """Get a single sample by ID with full metadata from sample DB."""
    registry = get_registry()
    with registry.reference_engine.connect() as conn:
        row = conn.execute(sa.select(samples).where(samples.c.id == sample_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Sample {sample_id} not found.")
    response = _row_to_response(row)
    return _enrich_with_sample_metadata(response, registry)


@router.patch("/{sample_id}")
async def update_sample(sample_id: int, body: SampleUpdate) -> SampleResponse:
    """Update sample metadata (rename, notes, date, source, extra JSON)."""
    registry = get_registry()
    settings = registry.settings

    # Build update values from non-None fields
    update_values: dict = {}
    if body.name is not None:
        update_values["name"] = body.name

    now = datetime.now(UTC)
    update_values["updated_at"] = now

    with registry.reference_engine.begin() as conn:
        # Check sample exists
        row = conn.execute(sa.select(samples).where(samples.c.id == sample_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Sample {sample_id} not found.")

        # Update the sample registry
        conn.execute(samples.update().where(samples.c.id == sample_id).values(**update_values))

    # Also update per-sample metadata table if applicable
    sample_db_path = settings.data_dir / row.db_path
    if sample_db_path.exists():
        sample_engine = registry.get_sample_engine(sample_db_path)
        meta_updates: dict = {}
        if body.name is not None:
            meta_updates["name"] = body.name
        if body.notes is not None:
            meta_updates["notes"] = body.notes
        if body.date_collected is not None:
            try:
                meta_updates["date_collected"] = date.fromisoformat(body.date_collected)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid date format: {body.date_collected}. Expected YYYY-MM-DD.",
                ) from exc
        if body.source is not None:
            meta_updates["source"] = body.source
        if body.extra is not None:
            meta_updates["extra"] = json.dumps(body.extra)
        if meta_updates:
            meta_updates["updated_at"] = now
            with sample_engine.begin() as conn:
                conn.execute(
                    sample_metadata_table.update()
                    .where(sample_metadata_table.c.id == 1)
                    .values(**meta_updates)
                )

    # Return updated record with full metadata
    with registry.reference_engine.connect() as conn:
        updated_row = conn.execute(sa.select(samples).where(samples.c.id == sample_id)).fetchone()
    if updated_row is None:
        raise HTTPException(status_code=404, detail=f"Sample {sample_id} not found.")
    response = _row_to_response(updated_row)
    return _enrich_with_sample_metadata(response, registry)


class MergedChildResponse(BaseModel):
    id: int
    name: str


@router.get("/{sample_id}/merged-children")
async def list_sample_merged_children(sample_id: int) -> list[MergedChildResponse]:
    """List merged samples that reference this sample as a source.

    Frontend uses this to surface the cascade impact on the per-row delete
    confirmation (AncestryDNA Plan §10.8; Step 66 / MRG-02a). Returns ``[]``
    when the sample has never been merged.
    """
    registry = get_registry()
    with registry.reference_engine.connect() as conn:
        row = conn.execute(
            sa.select(samples.c.id).where(samples.c.id == sample_id)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Sample {sample_id} not found.")
    children = list_merged_children(registry, sample_id)
    return [MergedChildResponse(id=c.id, name=c.name) for c in children]


@router.delete("/{sample_id}", status_code=204)
async def delete_sample(sample_id: int) -> None:
    """Delete a sample and cascade to any merged children referencing it.

    AncestryDNA Plan §10.8 / Step 66: a single-confirmation cascade removes
    every ``file_format='merged_v1'`` sample whose ``merge_provenance``
    lists this row in ``source_sample_ids`` before tearing down the source.
    """
    registry = get_registry()
    result = delete_sample_with_cascade(registry, sample_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Sample {sample_id} not found.")
